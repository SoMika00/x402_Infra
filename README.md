# x402 Pro — FastAPI, Gateway, Ledger, CLI, Tests

Starter net pour `x402` : **min-pay**, **ledger local**, **idempotency**, **/embed**, **/parse/pdf**, **metrics Prometheus**.

## Démarrage (Docker + Postgres)
```bash
cp .env.example .env
docker compose up --build -d
curl -s http://localhost:8080/health
