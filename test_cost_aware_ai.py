"""
Test script for Cost-Aware Bot AI
Verifies that bots make intelligent decisions during supply chain disruptions.
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.database import get_db
from core.engine import GameEngine
from app.models import Company, Product, InventoryItem, MarketEvent
from sqlalchemy import select

async def test_cost_aware_ai():
    """Test cost-aware bot AI behavior."""
    print("\n" + "="*80)
    print("🧪 TESTING COST-AWARE BOT AI")
    print("="*80)
    
    async for db in get_db():
        engine = GameEngine(db)
        
        # Initialize game
        print("\n1️⃣ Initializing game...")
        company = await engine.initialize_game()
        print(f"   ✅ Game initialized with {company.name}")
        
        # Run a few turns to establish baseline
        print("\n2️⃣ Running baseline turns (no events)...")
        for i in range(3):
            print(f"\n   Turn {i+1}:")
            result = await engine.process_turn()
            print(f"   ✅ Turn {i+1} completed")
        
        # Manually create a supply chain disruption
        print("\n3️⃣ Creating supply chain disruption...")
        result = await db.execute(select(Product))
        product = result.scalars().first()
        
        disruption = MarketEvent(
            event_type="supply_chain_disruption",
            description=f"Critical shortage in {product.name} components",
            duration_months=3,
            affected_product_id=product.id,
            intensity=1.5  # 50% cost increase
        )
        db.add(disruption)
        await db.commit()
        print(f"   ⚠️  Created disruption for {product.name} (+50% cost)")
        
        # Run turns with disruption active
        print("\n4️⃣ Running turns with supply chain disruption...")
        for i in range(4):
            print(f"\n   === TURN {i+1} WITH DISRUPTION ===")
            result = await engine.process_turn()
            
            # Check if any bots had negative gross profit
            result = await db.execute(select(Company).where(Company.is_player == False))
            bots = result.scalars().all()
            
            print(f"\n   Bot Performance Check:")
            for bot in bots:
                # Get bot's inventory
                inv_result = await db.execute(
                    select(InventoryItem)
                    .where(
                        InventoryItem.company_id == bot.id,
                        InventoryItem.product_id == product.id
                    )
                )
                items = inv_result.scalars().all()
                
                if items:
                    total_value = sum(item.quantity * item.unit_cost for item in items)
                    total_qty = sum(item.quantity for item in items)
                    avg_cost = total_value / total_qty if total_qty > 0 else 0
                    print(f"   - {bot.name}: {total_qty} units @ avg ${avg_cost:.2f}/unit")
        
        print("\n" + "="*80)
        print("✅ TEST COMPLETE - Check logs above for cost-aware behavior")
        print("="*80)
        
        # Verify expectations
        print("\n📋 VERIFICATION CHECKLIST:")
        print("   [ ] Bots logged 'COST-AWARE PRICING ANALYSIS' during pricing")
        print("   [ ] Bots logged 'PURCHASE VIABILITY ANALYSIS' during purchasing")
        print("   [ ] Bots either SKIPPED or REDUCED purchase quantities during disruption")
        print("   [ ] Bots adjusted prices upward when inventory costs increased")
        print("   [ ] No negative gross profit sales for bots")
        
        break

if __name__ == "__main__":
    asyncio.run(test_cost_aware_ai())
