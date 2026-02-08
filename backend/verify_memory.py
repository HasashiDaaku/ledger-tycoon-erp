
import asyncio
import sys
import os

# Add backend directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import AsyncSessionLocal
from app.database import AsyncSessionLocal
from app.models import Company, Product, InventoryItem, MarketHistory
from core.bot_ai import BotAI, BotPersonality
from sqlalchemy import select, update

async def verify_memory_logic():
    async with AsyncSessionLocal() as db:
        bot_ai = BotAI(db)
        
        print("=" * 80)
        print("VERIFYING STRATEGY MEMORY LOGIC")
        print("=" * 80)
        
        # 1. Setup Data for Pricing Regret
        # Company 2 (TechCorp) - Premium Gadget (ID 2)
        # Price it high, sell little
        try:
            # --- TEST: Stockout Persistence ---
            print("\n🧪 Testing Stockout Persistence...")
            
            # 1. Setup Stockout Condition for Company 2 (TechCorp) Product 1
            # Set Inventory to 0
            await db.execute(
                update(InventoryItem)
                .where(InventoryItem.company_id == 2, InventoryItem.product_id == 1)
                .values(quantity=0)
            )
            await db.commit()
            
            # 2. Get the bot
            bot_ai = BotAI(db)
            tech_corp = (await db.execute(select(Company).where(Company.id == 2))).scalar_one()
            
            # 3. First Run
            print("🔄 Running Turn 1 (Expect First Stockout)...")
            logs = []
            await bot_ai._update_strategy_memory(tech_corp, logs)
            
            for log in logs:
                print(log)
                
            # Verify memory content in DB
            # Refetch company to ensure DB write
            await db.refresh(tech_corp)
            print(f"Memory after Turn 1: {tech_corp.strategy_memory}")
            
            # 4. Second Run
            print("\n🔄 Running Turn 2 (Expect Stockout #2)...")
            logs = []
            await bot_ai._update_strategy_memory(tech_corp, logs)
            
            for log in logs:
                print(log)
                
            # Verify memory content again
            await db.refresh(tech_corp)
            print(f"Memory after Turn 2: {tech_corp.strategy_memory}")

        finally:
            # The `async with` block handles closing the session, so db.close() is not needed here.
            # If this were a standalone session, db.close() would be appropriate.
            pass

if __name__ == "__main__":
    asyncio.run(verify_memory_logic())
