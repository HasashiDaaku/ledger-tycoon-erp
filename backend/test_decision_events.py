"""
Test script to verify Decision Events feature implementation.

This script tests:
1. Decision event triggering
2. Pending events API
3. Decision submission API
4. Game log output
"""

import asyncio
import json
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import GameState, Company, MarketEvent
from core.market_events import MarketEventsEngine
from sqlalchemy import select

DATABASE_URL = "sqlite+aiosqlite:///./ledger_tycoon.db"

async def test_decision_events():
    """Test the decision events system."""
    
    # Create async engine
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        print("=" * 80)
        print("TESTING DECISION EVENTS FEATURE")
        print("=" * 80)
        
        # Get game state
        result = await db.execute(select(GameState))
        game_state = result.scalar_one_or_none()
        
        if not game_state:
            print("❌ No game state found. Please start a game first.")
            return
        
        print(f"\n✅ Game State: Month {game_state.current_month}/{game_state.current_year}")
        
        # Initialize events engine
        events_engine = MarketEventsEngine(db, game_state.current_month, game_state.current_year)
        
        # Test 1: Trigger a decision event manually
        print("\n" + "=" * 80)
        print("TEST 1: Triggering Decision Event")
        print("=" * 80)
        
        decision_event = await events_engine.trigger_decision_event()
        
        if decision_event:
            print("✅ Decision event triggered successfully!")
            print(f"   Event ID: {decision_event.id}")
            print(f"   Event Type: {decision_event.event_type}")
            print(f"   Description: {decision_event.description}")
            
            # Parse event data
            event_data = json.loads(decision_event.event_data)
            print(f"\n   Title: {event_data['title']}")
            print(f"   Description: {event_data['description']}")
            print(f"   Choices: {len(event_data['choices'])}")
            
            for i, choice in enumerate(event_data['choices'], 1):
                print(f"\n   Choice {i}: {choice['label']}")
                print(f"      {choice['description']}")
                print(f"      Effects: {choice['effects']}")
            
            # Test game log formatting
            print("\n" + "=" * 80)
            print("TEST 2: Game Log Formatting")
            print("=" * 80)
            log_output = events_engine.format_decision_event_log(decision_event)
            print(log_output)
            
            # Test 3: Get pending events
            print("\n" + "=" * 80)
            print("TEST 3: Get Pending Events")
            print("=" * 80)
            pending = await events_engine.get_pending_decision_events()
            print(f"✅ Found {len(pending)} pending decision event(s)")
            
            # Test 4: Apply decision effects
            print("\n" + "=" * 80)
            print("TEST 4: Apply Decision Effects")
            print("=" * 80)
            
            # Get player company
            result = await db.execute(select(Company).where(Company.is_player == True))
            player = result.scalar_one_or_none()
            
            if player:
                # Choose the first option
                first_choice_id = event_data['choices'][0]['id']
                print(f"Applying choice: {first_choice_id}")
                
                effect_log = await events_engine.apply_decision_effects(
                    decision_event, 
                    first_choice_id, 
                    player.id
                )
                
                print("\n" + effect_log)
                
                await db.commit()
                
                # Verify decision was recorded
                await db.refresh(decision_event)
                if decision_event.decision_made:
                    print(f"\n✅ Decision recorded: {decision_event.player_decision}")
                else:
                    print("\n❌ Decision not recorded properly")
            else:
                print("❌ No player company found")
        else:
            print("ℹ️  No decision event triggered (20% chance)")
            print("   Try running this test multiple times to trigger an event")
        
        print("\n" + "=" * 80)
        print("TEST COMPLETE")
        print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_decision_events())
