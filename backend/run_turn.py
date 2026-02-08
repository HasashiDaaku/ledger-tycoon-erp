
import asyncio
import sys
import os

# Add backend directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import AsyncSessionLocal, engine, Base
from app.models import * # Register models
from core.engine import GameEngine

async def run_turn():
    # Ensure tables exist (for local testing flexibility)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    async with AsyncSessionLocal() as db:
        engine_instance = GameEngine(db)
        # Load state first to ensure we have the right month/year
        await engine_instance.load_state()
        
        print(f"Starting turn {engine_instance.current_month}/{engine_instance.current_year}...")
        result = await engine_instance.process_turn()
        
        print("\n\n--- TURN LOGS ---")
        for log in result["logs"]:
            print(log)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(run_turn())
    except Exception as e:
        print(f"Error: {e}")
