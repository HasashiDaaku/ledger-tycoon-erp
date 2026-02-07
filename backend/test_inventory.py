"""
Test script for intelligent inventory management system
"""
import asyncio
from app.database import AsyncSessionLocal
from core.engine import GameEngine

async def test_inventory_system():
    async with AsyncSessionLocal() as db:
        engine = GameEngine(db)
        await engine.load_state()
        
        print("=" * 80)
        print("TESTING INTELLIGENT INVENTORY MANAGEMENT")
        print("=" * 80)
        
        # Process one turn
        result = await engine.process_turn()
        
        # Print last 60 lines of logs
        logs = result['logs']
        print("\n".join(logs[-80:]))

if __name__ == "__main__":
    asyncio.run(test_inventory_system())
