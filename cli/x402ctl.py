import asyncio
import datetime as dt
import hashlib
import json
import typer
from typing import Optional
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy import select, desc, insert, update
from app.payments.ledger import (
    get_engine,
    init_db,
    Buyer,
    credit_min_pay,
    JobLog,
    MerkleRoot,
    compute_merkle_root,
    job_leaf,
    hash_leaf,
    compute_merkle_proof,
    verify_merkle_proof,
)

app = typer.Typer(help="x402 control CLI")

# --- db_init aliases ---
@app.command("db-init")
@app.command("db_init")
def db_init():
    async def _run():
        await init_db()
        typer.echo("DB ready.")
    asyncio.run(_run())

# --- buyer_topup aliases ---
@app.command("buyer-topup")
@app.command("buyer_topup")
def buyer_topup(address: str, cents: int):
    async def _run():
        async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
            res = await session.execute(select(Buyer).where(Buyer.address==address))
            buyer = res.scalar_one_or_none()
            if not buyer:
                await session.execute(insert(Buyer).values(address=address, balance_cents=0))
                await session.commit()
                res = await session.execute(select(Buyer).where(Buyer.address==address))
                buyer = res.scalar_one()
            await credit_min_pay(session, buyer, "0xmanual", cents)
            typer.echo(f"Credited {cents} cents to {address}")
    asyncio.run(_run())

# --- buyer_balance aliases ---
@app.command("buyer-balance")
@app.command("buyer_balance")
def buyer_balance(address: str):
    async def _run():
        async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
            res = await session.execute(select(Buyer).where(Buyer.address==address))
            buyer = res.scalar_one_or_none()
            if not buyer:
                typer.echo("Not found")
            else:
                typer.echo(f"Balance {buyer.balance_cents} cents (last_tx={buyer.last_tx_hash})")
    asyncio.run(_run())

# --- joblog-list ---
@app.command("joblog-list")
def joblog_list(
    endpoint: Optional[str] = typer.Option(None, "--endpoint", help="Filter by endpoint"),
    limit: int = typer.Option(10, "--limit", help="Max rows to show"),
):
    """List recent JobLog entries (paid jobs)."""
    async def _run():
        try:
            async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
                q = select(JobLog).order_by(desc(JobLog.created_at)).limit(limit)
                if endpoint:
                    q = q.where(JobLog.endpoint == endpoint)
                res = await session.execute(q)
                rows = res.scalars().all()

            if not rows:
                typer.echo("No jobs found.")
                return

            # simple table
            cols = ["created_at", "endpoint", "payer", "cents", "tx_hash", "latency_ms", "gpu_id"]
            typer.echo(" | ".join(cols))
            typer.echo("-" * 100)
            for r in rows:
                vals = [
                    str(getattr(r, "created_at", "")),
                    getattr(r, "endpoint", ""),
                    getattr(r, "payer", ""),
                    str(getattr(r, "cents", "")),
                    getattr(r, "tx_hash", ""),
                    str(getattr(r, "latency_ms", "")),
                    getattr(r, "gpu_id", "") or "",
                ]
                typer.echo(" | ".join(vals))
            typer.echo(f"\n{len(rows)} row(s)")
        except Exception as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(code=1)
    asyncio.run(_run())


@app.command("joblog-merkle")
def joblog_merkle(
    date: str,
    payer: Optional[str] = typer.Option("*", "--payer", help="Filter by payer (default '*' = all payers)"),
):
    """Compute daily Merkle root for JobLog entries on YYYY-MM-DD."""
    async def _run():
        try:
            d = dt.datetime.strptime(date, "%Y-%m-%d").date()
            day_start = dt.datetime(d.year, d.month, d.day)
            day_end = day_start + dt.timedelta(days=1)

            async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
                # Determine the set of payers to process
                if payer == "*":
                    payers_res = await session.execute(
                        select(JobLog.payer).where(
                            JobLog.created_at >= day_start,
                            JobLog.created_at < day_end,
                        ).distinct()
                    )
                    payers = [row[0] for row in payers_res.all()]
                else:
                    payers = [payer]

                if not payers:
                    typer.echo("no jobs")
                    return

                any_jobs = False
                for p in payers:
                    res = await session.execute(
                        select(JobLog).where(
                            JobLog.payer == p,
                            JobLog.created_at >= day_start,
                            JobLog.created_at < day_end,
                        ).order_by(JobLog.id)
                    )
                    jobs = res.scalars().all()
                    if not jobs:
                        continue
                    any_jobs = True

                    leaves = []
                    for j in jobs:
                        # deterministic leaf: id|endpoint|payer|cents|tx_hash
                        leaf = f"{j.id}|{j.endpoint}|{j.payer}|{j.cents}|{j.tx_hash}"
                        leaves.append(hashlib.sha256(leaf.encode()).hexdigest())
                    root = compute_merkle_root(leaves)

                    # Portable upsert: select existing row, then update or insert
                    existing = await session.execute(
                        select(MerkleRoot).where(
                            MerkleRoot.payer == p,
                            MerkleRoot.date == d,
                        )
                    )
                    row = existing.scalar_one_or_none()
                    if row is not None:
                        await session.execute(
                            update(MerkleRoot)
                            .where(MerkleRoot.payer == p, MerkleRoot.date == d)
                            .values(merkle_root=root, job_count=len(jobs))
                        )
                    else:
                        await session.execute(
                            insert(MerkleRoot).values(
                                payer=p,
                                date=d,
                                merkle_root=root,
                                job_count=len(jobs),
                            )
                        )
                    typer.echo(root)

                await session.commit()

                if not any_jobs:
                    typer.echo("no jobs")
        except Exception as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(code=1)
    asyncio.run(_run())


# --- merkle-verify-bundle ---
@app.command("merkle-verify-bundle")
@app.command("merkle_verify_bundle")
def merkle_verify_bundle(
    file: str = typer.Argument(..., help="Path to the exported audit bundle JSON file"),
    job_id: Optional[int] = typer.Option(None, "--job-id", help="Verify inclusion proof for a specific job id"),
):
    """Verify an exported audit bundle offline.

    Recomputes each job leaf hash, the Merkle root, and validates
    leaf_count == len(jobs). Optionally verifies a single job's inclusion
    proof via --job-id.
    """
    try:
        with open(file, "r", encoding="utf-8") as f:
            bundle = json.load(f)
    except Exception as e:
        typer.echo(f"FAIL: cannot read bundle file: {e}", err=True)
        raise typer.Exit(code=1)

    # Validate required fields
    required = ["version", "date", "payer", "root", "leaf_count", "jobs"]
    missing = [k for k in required if k not in bundle]
    if missing:
        typer.echo(f"FAIL: bundle missing required fields: {', '.join(missing)}", err=True)
        raise typer.Exit(code=1)

    jobs = bundle.get("jobs") or []
    if not isinstance(jobs, list):
        typer.echo("FAIL: bundle 'jobs' must be a list", err=True)
        raise typer.Exit(code=1)

    # (4) leaf_count must match len(jobs)
    if bundle.get("leaf_count") != len(jobs):
        typer.echo(
            f"FAIL: leaf_count mismatch: bundle.leaf_count={bundle.get('leaf_count')} != len(jobs)={len(jobs)}",
            err=True,
        )
        raise typer.Exit(code=1)

    # (2) recompute each job leaf hash from job fields
    leaves = []
    for job in jobs:
        try:
            leaf_str = f"{job['id']}|{job['endpoint']}|{job['payer']}|{job['cents']}|{job['tx_hash']}"
        except KeyError as e:
            typer.echo(f"FAIL: job missing field {e}", err=True)
            raise typer.Exit(code=1)
        leaves.append(hash_leaf(leaf_str))

    # (3) recompute Merkle root and compare
    computed_root = compute_merkle_root(leaves)
    if computed_root != bundle.get("root"):
        typer.echo(
            f"FAIL: root mismatch: computed={computed_root} != bundle.root={bundle.get('root')}",
            err=True,
        )
        raise typer.Exit(code=1)

    # (5) optional single job inclusion proof
    if job_id is not None:
        target_index = None
        for i, job in enumerate(jobs):
            if job.get("id") == job_id:
                target_index = i
                break
        if target_index is None:
            typer.echo(f"FAIL: job_id {job_id} not found in bundle", err=True)
            raise typer.Exit(code=1)

        leaf_hash = leaves[target_index]
        proof = compute_merkle_proof(leaves, target_index)
        verified = verify_merkle_proof(leaf_hash, proof, computed_root)
        typer.echo(f"job_id={job_id} verified={str(verified).lower()}")
        if not verified:
            raise typer.Exit(code=1)

    typer.echo("OK")


if __name__ == "__main__":
    app()
