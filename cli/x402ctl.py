import asyncio
import typer
from typing import Optional
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy import select, desc
from app.payments.ledger import get_engine, init_db, Buyer, credit_min_pay, JobLog

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

if __name__ == "__main__":
    app()
