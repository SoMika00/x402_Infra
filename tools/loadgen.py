#!/usr/bin/env python3
import asyncio, httpx, argparse, time, uuid, random, string, json

def rand_text(n=10):
    words = ["alpha","bravo","charlie","delta","echo","foxtrot","golf","hotel","india","juliet","kilo","lima","mike"]
    return " ".join(random.choice(words) for _ in range(n))

def make_payload(endpoint, batch_size):
    if endpoint == "batch":
        return {"texts": [rand_text(8) for _ in range(batch_size)]}
    else:
        return {"text": rand_text(12)}

async def worker(name, client, url, endpoint, proof, idemp_prefix, batch_size, interval, end_ts, stats):
    while time.time() < end_ts:
        headers = {
            "Content-Type": "application/json",
            "X-402-Proof": proof,
            "Idempotency-Key": f"{idemp_prefix}-{uuid.uuid4().hex}",
        }
        payload = make_payload(endpoint, batch_size)
        t0 = time.perf_counter()
        ok = False
        code = 0
        try:
            r = await client.post(url, headers=headers, json=payload, timeout=10.0)
            code = r.status_code
            ok = (200 <= r.status_code < 300)
        except Exception:
            code = -1
            ok = False
        dt = time.perf_counter() - t0
        stats["count"] += 1
        stats["ok"] += 1 if ok else 0
        stats["lat_sum"] += dt
        stats["lat_max"] = max(stats["lat_max"], dt)
        await asyncio.sleep(interval)

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="http://localhost:8080", help="base URL (ex: http://localhost:8080)")
    ap.add_argument("--endpoint", choices=["fast","single","batch"], default="fast")
    ap.add_argument("--minutes", type=float, default=1.0)
    ap.add_argument("--rps", type=float, default=20.0, help="requêtes/seconde visées")
    ap.add_argument("--concurrency", type=int, default=20)
    ap.add_argument("--batch-size", type=int, default=8, help="pour /embed/batch")
    ap.add_argument("--wallet", default="0xAlice", help="adresse stub: pay:<wallet>")
    args = ap.parse_args()

    if args.endpoint == "batch":
        path = "/embed/batch"
    elif args.endpoint == "single":
        path = "/embed/"
    else:
        path = "/embed/fast"
    url = args.host.rstrip("/") + path

    proof = f"pay:{args.wallet}"
    interval = max(1e-6, args.concurrency / max(1.0, args.rps))  # pacing global ~rps
    end_ts = time.time() + args.minutes * 60.0

    stats = {"count":0, "ok":0, "lat_sum":0.0, "lat_max":0.0}
    async with httpx.AsyncClient(http2=True) as client:
        tasks = [
            asyncio.create_task(worker(f"w{i}", client, url, 
                                       "batch" if args.endpoint=="batch" else "fast" if args.endpoint=="fast" else "single",
                                       proof, f"lg-{int(time.time())}", 
                                       args.batch_size, interval, end_ts, stats))
            for i in range(args.concurrency)
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    if stats["count"]:
        p = {
            "sent": stats["count"],
            "ok": stats["ok"],
            "err": stats["count"]-stats["ok"],
            "ok_rate": round(100*stats["ok"]/stats["count"],2),
            "avg_ms": round(1000*stats["lat_sum"]/stats["count"],2),
            "max_ms": round(1000*stats["lat_max"],2),
        }
        print(json.dumps(p, indent=2))
    else:
        print("{}")

if __name__ == "__main__":
    asyncio.run
