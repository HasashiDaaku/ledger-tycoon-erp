"""
Test market events system with game simulation
"""
import asyncio
from app.database import AsyncSessionLocal
from core.engine import GameEngine

async def test_market_events():
    async with AsyncSessionLocal() as db:
        engine = GameEngine(db)
        
        print("=" * 80)
        print("TESTING MARKET EVENTS SYSTEM")
        print("=" * 80)
        
        # Initialize new game
        print("\n🎮 Initializing new game...")
        player = await engine.initialize_game()
        
        print(f"✅ Player company created: {player.name}")
        
        # Manually purchase some inventory for player
        print("\n📦 Player purchasing initial inventory...")
        from sqlalchemy import select
        from app.models import Product
        result = await db.execute(select(Product))
        products = result.scalars().all()
        
        for product in products:
            await engine.purchase_inventory(
                company_id=player.id,
                product_id=product.id,
                quantity=300,
                unit_cost=product.base_cost
            )
        await db.commit()
        
        print("✅ Inventory purchased")
        
        # Run 6 turns to see events trigger and seasonal changes
        print("\n🎮 Running 6 month simulation...\n")
        for i in range(6):
            result = await engine.process_turn()
            print("\n" + "🔄" * 30)
            print(f"Turn {i+1} complete")
            print("🔄" * 30 + "\n")
        
        print("\n" + "=" * 80)
        print("✅ SIMULATION COMPLETE")
        print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_market_events())
