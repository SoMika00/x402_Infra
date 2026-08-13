# app/metrics.py
from prometheus_client import Counter, Histogram, Gauge
import threading, time, asyncio, datetime as dt
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy import select, func

# NVML (télémétrie GPU) – import optionnel
try:
    import pynvml  # fourni par le paquet PyPI "nvidia-ml-py3" ou "nvidia-ml-py"
except Exception:
    pynvml = None

from app.payments.ledger import get_engine, JobLog

# € facturés (déjà consommé par ton code)
revenue_cents_total = Counter(
    "x402_revenue_cents_total",
    "Total revenue (cents) charged via x402",
    labelnames=("endpoint", "asset"),
)

# latence par endpoint
latency_seconds = Histogram(
    "x402_latency_seconds",
    "Request latency in seconds",
    labelnames=("endpoint",),
)

# métriques GPU
gpu_util_pct = Gauge("x402_gpu_util_pct", "GPU utilization percent", labelnames=("gpu",))
gpu_mem_used = Gauge("x402_gpu_mem_used_bytes", "GPU memory used", labelnames=("gpu",))
gpu_mem_total = Gauge("x402_gpu_mem_total_bytes", "GPU memory total", labelnames=("gpu",))

# new: jobs gauge per endpoint/payer last 24h
jobs_total = Gauge(
    "x402_jobs_total",
    "Count of JobLog entries per endpoint and payer over last 24h",
    labelnames=("endpoint", "payer"),
)


def start_gpu_polling(period: float = 5.0):
    """
    Lance un thread qui pousse l'usage GPU dans Prometheus toutes les N secondes.
    Si NVML n'est pas dispo, ne fait rien.
    """
    if pynvml is None:
        return

    def _loop():
        try:
            pynvml.nvmlInit()
            count = pynvml.nvmlDeviceGetCount()
            while True:
                for i in range(count):
                    h = pynvml.nvmlDeviceGetHandleByIndex(i)
                    util = pynvml.nvmlDeviceGetUtilizationRates(h)
                    mem = pynvml.nvmlDeviceGetMemoryInfo(h)
                    gpu_util_pct.labels(str(i)).set(util.gpu)
                    gpu_mem_used.labels(str(i)).set(mem.used)
                    gpu_mem_total.labels(str(i)).set(mem.total)
                time.sleep(period)
        except Exception:
            # on garde silencieux pour ne pas casser l'app si NVML bug
            pass

    t = threading.Thread(target=_loop, daemon=True)
    t.start()


async def _update_jobs():
    engine = get_engine()
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        since = dt.datetime.utcnow() - dt.timedelta(hours=24)
        q = (
            select(JobLog.endpoint, JobLog.payer, func.count())
            .where(JobLog.created_at >= since)
            .group_by(JobLog.endpoint, JobLog.payer)
        )
        res = await session.execute(q)
        for row in res.all():
            endpoint, payer, cnt = row
            jobs_total.labels(endpoint=endpoint, payer=payer).set(cnt)


def start_job_polling(period: float = 60.0):
    """
    Background thread polling JobLog counts (last 24h) every N seconds, like GPU.
    """
    def _loop():
        while True:
            try:
                asyncio.run(_update_jobs())
            except Exception:
                pass
            time.sleep(period)

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
