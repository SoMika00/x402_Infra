from fastapi.testclient import TestClient
import subprocess
import sys
from app.main import app

from io import BytesIO

client = TestClient(app)

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True

def test_embed_402_then_200():
    r1 = client.post("/embed/", json={"text":"hello"})
    assert r1.status_code == 402
    r2 = client.post("/embed/", headers={"X-402-Proof":"pay:0xAlice"}, json={"text":"hello"})
    assert r2.status_code == 200
    assert r2.json()["ok"] is True
    # settlement response en header (stub)
    assert "X-PAYMENT-RESPONSE" in r2.headers

def test_idempotency():
    key = "test-key-123"
    r1 = client.post("/embed/", headers={"X-402-Proof":"pay:0xAlice", "Idempotency-Key": key}, json={"text":"same"})
    r2 = client.post("/embed/", headers={"X-402-Proof":"pay:0xAlice", "Idempotency-Key": key}, json={"text":"same"})
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json() == r2.json()

def test_buyer_balance():
    r1 = client.get("/buyer/balance")
    assert r1.status_code == 402
    r2 = client.get("/buyer/balance", headers={"X-402-Proof":"pay:0xAlice"})
    assert r2.status_code == 200
    data = r2.json()
    assert "address" in data and "balance_cents" in data and "last_tx" in data

def test_buyer_jobs():
    # 402 without proof
    r1 = client.get("/buyer/jobs")
    assert r1.status_code == 402
    # 200 with stub, list (may be empty)
    r2 = client.get("/buyer/jobs", headers={"X-402-Proof":"pay:0xAlice"})
    assert r2.status_code == 200
    assert isinstance(r2.json(), list)
    # with limit
    r3 = client.get("/buyer/jobs?limit=5", headers={"X-402-Proof":"pay:0xAlice"})
    assert r3.status_code == 200

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
    r2 = client.get("/audit/merkle/2025-01-15", headers={"X-402-Proof":"pay:0xAuditor"})
    assert r2.status_code == 404


def test_parse_pdf_402_then_200():
    # 402 without payment
    files = {"file": ("test.pdf", BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
    r1 = client.post("/parse/pdf", files=files)
    assert r1.status_code == 402

    # 200 with stub proof
    files = {"file": ("test.pdf", BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
    r2 = client.post("/parse/pdf", headers={"X-402-Proof":"pay:0xAlice"}, files=files)
    assert r2.status_code == 200
    data = r2.json()
    assert data.get("ok") is True
    assert "text" in data or "pages" in data
    assert "X-PAYMENT-RESPONSE" in r2.headers


def test_parse_pdf_idempotency():
    key = "pdf-key-456"
    files = {"file": ("test.pdf", BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
    r1 = client.post("/parse/pdf", headers={"X-402-Proof":"pay:0xAlice", "Idempotency-Key": key}, files=files)
    files = {"file": ("test.pdf", BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
    r2 = client.post("/parse/pdf", headers={"X-402-Proof":"pay:0xAlice", "Idempotency-Key": key}, files=files)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json() == r2.json()


def test_parse_pdf_creates_joblog():
    files = {"file": ("test.pdf", BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
    r = client.post("/parse/pdf", headers={"X-402-Proof":"pay:0xBob"}, files=files)
    assert r.status_code == 200
    # verify via buyer/jobs that a JobLog entry exists
    rj = client.get("/buyer/jobs?limit=5", headers={"X-402-Proof":"pay:0xBob"})
    assert rj.status_code == 200
    jobs = rj.json()
    assert any(j.get("endpoint") == "parse_pdf" for j in jobs)
