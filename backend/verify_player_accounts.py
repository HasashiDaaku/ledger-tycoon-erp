
import asyncio
from app.database import AsyncSessionLocal
from sqlalchemy import select
from app.models import Account, Company

async def verify():
    async with AsyncSessionLocal() as db:
        print("Checking accounts for Player Corp (ID 1):")
        result = await db.execute(select(Account).where(Account.company_id == 1))
        accounts = result.scalars().all()
        
        found_cash = False
        found_revenue = False
        
        for acc in accounts:
            print(f"  Account: {acc.code} - {acc.name} (ID: {acc.id})")
            if "1000" in acc.code: found_cash = True
            if "4000" in acc.code: found_revenue = True
            
        if not found_cash: print("ERROR: Cash account missing!")
        if not found_revenue: print("ERROR: Revenue account missing!")
        
        # Check cash balance
        if found_cash:
            from core.accounting import AccountingEngine
            engine = AccountingEngine(db)
            cash = await engine.get_company_cash(1)
            print(f"Current Cash Balance: ${cash:,.2f}")

if __name__ == "__main__":
    asyncio.run(verify())
