import asyncio
import datetime as dt
import hashlib
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.payments.ledger import (
    compute_merkle_root,
    log_job,
    list_jobs_for_payer,
    JobLog,
)


def test_compute_merkle_root_empty():
    assert compute_merkle_root([]) == ""


def test_compute_merkle_root_single():
    leaves = ["a" * 64]
    root = compute_merkle_root(leaves)
    assert len(root) == 64
    assert root == hashlib.sha256(("a" * 64 + "a" * 64).encode()).hexdigest()  # odd case duplicates


def test_compute_merkle_root_two():
    leaves = ["a" * 64, "b" * 64]
    root = compute_merkle_root(leaves)
    expected = hashlib.sha256(("a" * 64 + "b" * 64).encode()).hexdigest()
    assert root == expected


def test_compute_merkle_root_three():
    leaves = ["a" * 64, "b" * 64, "c" * 64]
    root = compute_merkle_root(leaves)
    # deterministic and hex
    assert len(root) == 64
    # re-run same
    assert root == compute_merkle_root(leaves)


def test_compute_merkle_root_deterministic():
    leaves = ["x" * 64, "y" * 64, "z" * 64]
    r1 = compute_merkle_root(leaves)
    r2 = compute_merkle_root(list(reversed(leaves)))
    assert r1 == r2


@pytest.mark.asyncio
async def test_log_job_and_list_jobs_mock():
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()

    await log_job(
        session,
        endpoint="embed",
        payer="0xTest",
        cents=1,
        tx_hash="0xtx",
        latency_ms=10,
        gpu_id="0",
        batch_size=1,
    )
    session.execute.assert_called()
    session.commit.assert_awaited()

    # list_jobs mock
    mock_jobs = [MagicMock(spec=JobLog)]
    session.execute.return_value.scalars.return_value.all.return_value = mock_jobs
    jobs = await list_jobs_for_payer(session, "0xTest")
    assert len(jobs) == 1


def test_joblog_merkle_cli_path():
    # end-to-end import + call without crash (uses compute_merkle_root)
    from cli.x402ctl import joblog_merkle
    try:
        joblog_merkle("2025-01-01")
    except SystemExit:
        pass  # expected when no DB/jobs
    # also direct compute
    assert compute_merkle_root([]) == ""
