import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from app.main import app
from app.core.config import settings

client = TestClient(app)

def test_buyer_merkle_402():
    # No payment header should yield 402
    resp = client.get("/buyer/merkle?date=2025-01-01")
    assert resp.status_code == 402

def test_buyer_merkle_404():
    # Provide payment but date likely has no entry
    resp = client.get(
        "/buyer/merkle?date=2099-12-31",
        headers={"X-402-Proof": "pay:0xAlice"},
    )
    assert resp.status_code == 404

def test_buyer_merkle_200():
    # Insert a MerkleRoot directly via DB for test
    from app.payments.ledger import get_engine, MerkleRoot
    import asyncio

    async def insert_root():
        engine = await get_engine()
        async with engine.begin() as conn:
            await conn.execute(
                MerkleRoot.__table__.insert().values(
                    payer="0xAlice",
                    date=datetime.strptime("2025-01-15", "%Y-%m-%d").date(),
                    merkle_root="abc123def",
                    job_count=42,
                )
            )
    asyncio.run(insert_root())

    resp = client.get(
        "/buyer/merkle?date=2025-01-15",
        headers={"X-402-Proof": "pay:0xAlice"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["date"] == "2025-01-15"
    assert data["merkle_root"] == "abc123def"
    assert data["job_count"] == 42
