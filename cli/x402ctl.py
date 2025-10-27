import asyncio
import typer
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy import select, insert
from app.payments.ledger import get_engine, init_db, Buyer, credit_min_pay

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

if __name__ == "__main__":
    app()
