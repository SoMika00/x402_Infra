# app/metrics.py
from prometheus_client import Counter, Histogram, Gauge
import threading, time

# NVML (télémétrie GPU) – import optionnel
try:
    import pynvml  # fourni par le paquet PyPI "nvidia-ml-py3" ou "nvidia-ml-py"
except Exception:
    pynvml = None

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
