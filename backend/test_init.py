import asyncio
import sys
sys.path.insert(0, 'c:/Users/van Houten/accounting_erp_software/backend')

async def test_game_init():
    from app.database import get_db, engine, Base
    from core.engine import GameEngine
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Try to initialize game
    async for db in get_db():
        game_engine = GameEngine(db)
        try:
            player = await game_engine.initialize_game()
            print(f"✅ Game initialized successfully! Player: {player.name}")
        except Exception as e:
            print(f"❌ Error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            break

if __name__ == "__main__":
    asyncio.run(test_game_init())
