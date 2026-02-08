import asyncio
import sys
import os

# Add the current directory to sys.path so we can import 'app'
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import AsyncSessionLocal
from app.models import Company
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Company))
        companies = result.scalars().all()
        for c in companies:
            print(f"Company: {c.name}")
            print(f"  Memory: {c.strategy_memory}")
            print(f"  Brand Equity: {c.brand_equity}")
            print("-" * 20)

if __name__ == "__main__":
    asyncio.run(check())
