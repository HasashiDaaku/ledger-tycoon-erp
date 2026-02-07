"""
Test bot initial inventory setup
"""
import asyncio
from app.database import AsyncSessionLocal
from core.engine import GameEngine
from sqlalchemy import select
from app.models import Company, InventoryItem

async def test_bot_initial_inventory():
    async with AsyncSessionLocal() as db:
        engine = GameEngine(db)
        
        print("=" * 80)
        print("TESTING BOT INITIAL INVENTORY SETUP")
        print("=" * 80)
        
        # Initialize new game
        print("\n🎮 Initializing new game...")
        player = await engine.initialize_game()
        
        print(f"✅ Player company created: {player.name}")
        
        # Check all companies' inventory
        result = await db.execute(select(Company))
        companies = result.scalars().all()
        
        print(f"\n📊 Companies created: {len(companies)}")
        
        for company in companies:
            print(f"\n{'='*60}")
            print(f"Company: {company.name} ({'PLAYER' if company.is_player else 'BOT'})")
            
            # Get cash
            cash = await engine.accounting.get_company_cash(company.id)
            print(f"💰 Cash: ${cash:,.2f}")
            
            # Get inventory
            inv_result = await db.execute(
                select(InventoryItem)
                .where(InventoryItem.company_id == company.id)
            )
            inventory_items = inv_result.scalars().all()
            
            if inventory_items:
                print(f"📦 Inventory:")
                total_inv_value = 0
                for item in inventory_items:
                    value = item.quantity * item.wac
                    total_inv_value += value
                    print(f"   - {item.quantity} units @ ${item.wac:.2f} = ${value:,.2f}")
                print(f"📊 Total Inventory Value: ${total_inv_value:,.2f}")
            else:
                print(f"⚠️  NO INVENTORY")

if __name__ == "__main__":
    asyncio.run(test_bot_initial_inventory())
