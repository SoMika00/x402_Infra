from fastapi.testclient import TestClient
import subprocess
import sys
from app.main import app

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

def test_joblog_merkle_cli():
    # direct import path for determinism
    from cli.x402ctl import joblog_merkle
    # will print 'no jobs' or root; just ensure callable without crash
    try:
        joblog_merkle("2025-01-15")
    except SystemExit:
        pass  # expected on error path
