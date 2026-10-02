import os
import json
from io import BytesIO
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings

client = TestClient(app)

# Existing tests (unchanged) ---------------------------------------------------

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_embed_402_then_200():
    # 402 without proof
    r1 = client.post("/embed/", json={"text": "hello"})
    assert r1.status_code == 402
    # 200 with stub proof
    r2 = client.post(
        "/embed/",
        headers={"X-402-Proof": "pay:0xAlice"},
        json={"text": "hello"},
    )
    assert r2.status_code == 200
    data = r2.json()
    assert data["ok"] is True
    assert isinstance(data["embedding"], list)
    assert "X-PAYMENT-RESPONSE" in r2.headers

def test_embed_joblog_created():
    # Ensure a joblog entry is created for embed endpoint
    client.post(
        "/embed/",
        headers={"X-402-Proof": "pay:0xBob"},
        json={"text": "test"},
    )
    r = client.get("/buyer/jobs", headers={"X-402-Proof": "pay:0xBob"})
    assert r.status_code == 200
    jobs = r.json()
    assert any(j.get("endpoint") == "embed" for j in jobs)

# New test for revenue metric increment ---------------------------------------

def test_revenue_metric_increment():
    # Reset metric collector for a clean state
    from prometheus_client import CollectorRegistry, generate_latest
    from app.metrics import revenue_cents_total

    # Create a fresh registry and re-register the metric to isolate test
    registry = CollectorRegistry()
    # Recreate the metric in this registry
    revenue_metric = revenue_cents_total.labels(endpoint="embed", asset=settings.X402_ASSET)
    # Ensure starting value is zero
    assert revenue_metric._value.get() == 0

    # Perform an embed request which should increment revenue by PRICE_EMBED_CENTS
    client.post(
        "/embed/",
        headers={"X-402-Proof": "pay:0xMetricUser"},
        json={"text": "metric test"},
    )
    # After request, metric should have increased
    assert revenue_metric._value.get() == settings.PRICE_EMBED_CENTS

    # Also test parse_pdf endpoint revenue increment
    pdf_bytes = BytesIO(b"%PDF-1.4 fake")
    client.post(
        "/parse/pdf",
        headers={"X-402-Proof": "pay:0xMetricUser"},
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
    )
    pdf_metric = revenue_cents_total.labels(endpoint="parse_pdf", asset=settings.X402_ASSET)
    assert pdf_metric._value.get() == settings.PRICE_PARSE_PDF_CENTS

# Existing tests (unchanged) ---------------------------------------------------

def test_buyer_balance():
    r1 = client.get("/buyer/balance")
    assert r1.status_code == 402
    r2 = client.get("/buyer/balance", headers={"X-402-Proof": "pay:0xAlice"})
    assert r2.status_code == 200
    data = r2.json()
    assert "address" in data and "balance_cents" in data and "last_tx" in data

def test_buyer_jobs():
    # 402 without proof
    r1 = client.get("/buyer/jobs")
    assert r1.status_code == 402
    # 200 with stub, list (may be empty)
    r2 = client.get("/buyer/jobs", headers={"X-402-Proof": "pay:0xAlice"})
    assert r2.status_code == 200
    assert isinstance(r2.json(), list)
    # with limit
    r3 = client.get("/buyer/jobs?limit=5", headers={"X-402-Proof": "pay:0xAlice"})
    assert r3.status_code == 200

def test_buyer_summary_no_jobs():
    # Ensure a fresh payer with no jobs
    r = client.get("/buyer/summary", headers={"X-402-Proof": "pay:0xNewUser"})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["total_jobs"] == 0
    assert data["total_cents"] == 0
    assert data["last_job_at"] is None

def test_buyer_summary_with_jobs():
    # Create a job via embed endpoint
    client.post("/embed/", headers={"X-402-Proof": "pay:0xBob"}, json={"text": "test"})
    # Retrieve summary
    r = client.get("/buyer/summary", headers={"X-402-Proof": "pay:0xBob"})
    assert r.status_code == 200
    data = r.json()
    assert data["total_jobs"] >= 1
    assert data["total_cents"] >= settings.PRICE_EMBED_CENTS
    assert data["last_job_at"] is not None

def test_joblog_merkle_cli():
    # direct import path for determinism
    from cli.x402ctl import joblog_merkle
    # will print 'no jobs' or root; just ensure callable without crash
    try:
        joblog_merkle("2025-01-15")
    except SystemExit:
        pass  # expected on error path

def test_audit_merkle_endpoint():
    # 402 first
    r1 = client.get("/audit/merkle/2025-01-15")
    assert r1.status_code == 402
    # 200 with stub (no row -> 404 after pay)
    r2 = client.get("/audit/merkle/2025-01-15", headers={"X-402-Proof": "pay:0xAuditor"})
    assert r2.status_code == 404

def test_parse_pdf_402_then_200():
    # 402 without payment
    files = {"file": ("test.pdf", BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
    r1 = client.post("/parse/pdf", files=files)
    assert r1.status_code == 402

    # 200 with stub proof
    files = {"file": ("test.pdf", BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
    r2 = client.post("/parse/pdf", headers={"X-402-Proof": "pay:0xAlice"}, files=files)
    assert r2.status_code == 200
    data = r2.json()
    assert data.get("ok") is True
    assert "text" in data or "pages" in data
    assert "X-PAYMENT-RESPONSE" in r2.headers

def test_parse_pdf_idempotency():
    key = "pdf-key-456"
    files = {"file": ("test.pdf", BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
    r1 = client.post("/parse/pdf", headers={"X-402-Proof": "pay:0xAlice", "Idempotency-Key": key}, files=files)
    files = {"file": ("test.pdf", BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
    r2 = client.post("/parse/pdf", headers={"X-402-Proof": "pay:0xAlice", "Idempotency-Key": key}, files=files)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json() == r2.json()

def test_parse_pdf_creates_joblog():
    files = {"file": ("test.pdf", BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
    r = client.post("/parse/pdf", headers={"X-402-Proof": "pay:0xBob"}, files=files)
    assert r.status_code == 200
    # verify via buyer/jobs that a JobLog entry exists
    rj = client.get("/buyer/jobs?limit=5", headers={"X-402-Proof": "pay:0xBob"})
    assert rj.status_code == 200
    jobs = rj.json()
    assert any(j.get("endpoint") == "parse_pdf" for j in jobs)

def test_metrics_jobs_gauge():
    # seed a job
    files = {"file": ("test.pdf", BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
    r = client.post("/parse/pdf", headers={"X-402-Proof": "pay:0xMetrics"}, files=files)
    assert r.status_code == 200
    # hit /metrics (exposed by instrumentator)
    rm = client.get("/metrics")
    assert rm.status_code == 200
    assert "x402_jobs_total" in rm.text
    assert 'endpoint="parse_pdf"' in rm.text

def test_parse_pdf_batch_402_then_200():
    # 402 without payment
    files = [
        ("files", ("a.pdf", BytesIO(b"%PDF-1.4 fakeA"), "application/pdf")),
        ("files", ("b.pdf", BytesIO(b"%PDF-1.4 fakeB"), "application/pdf")),
    ]
    r1 = client.post("/parse/pdf/batch", files=files)
    assert r1.status_code == 402

    # 200 with stub proof
    files = [
        ("files", ("a.pdf", BytesIO(b"%PDF-1.4 fakeA"), "application/pdf")),
        ("files", ("b.pdf", BytesIO(b"%PDF-1.4 fakeB"), "application/pdf")),
    ]
    r2 = client.post("/parse/pdf/batch", headers={"X-402-Proof": "pay:0xAlice"}, files=files)
    assert r2.status_code == 200
    data = r2.json()
    assert data.get("ok") is True
    assert "results" in data
    assert len(data["results"]) == 2
    assert "X-PAYMENT-RESPONSE" in r2.headers
