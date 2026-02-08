"""
Test Event Conflict Detection

This script tests that contradictory events (Economic Boom + Recession)
cannot coexist in the system.
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models import Base, MarketEvent
from core.market_events import MarketEventsEngine


async def test_event_conflicts():
    """Test that conflicting events are properly detected and cancelled."""
    
    print("=" * 80)
    print("🧪 TESTING EVENT CONFLICT DETECTION")
    print("=" * 80)
    
    # Setup test database
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        events_engine = MarketEventsEngine(session, current_month=1, current_year=2026)
        
        # Test 1: Create a RECESSION manually
        print("\n📝 Test 1: Creating initial RECESSION event")
        recession = MarketEvent(
            event_type="RECESSION",
            start_month=1,
            start_year=2026,
            duration_months=3,
            intensity=0.8,
            description="Economic Recession. Market demand -20% for 3 months"
        )
        session.add(recession)
        await session.commit()
        
        active_events = await events_engine.get_active_events()
        print(f"✅ Active events: {len(active_events)}")
        for event in active_events:
            print(f"   - {event.event_type}: {event.description}")
        
        # Test 2: Check for conflicts with ECONOMIC_BOOM
        print("\n📝 Test 2: Checking conflicts for ECONOMIC_BOOM")
        conflicts = await events_engine.check_event_conflicts("ECONOMIC_BOOM")
        print(f"✅ Conflicts found: {len(conflicts)}")
        assert len(conflicts) == 1, f"Expected 1 conflict, found {len(conflicts)}"
        assert conflicts[0].event_type == "RECESSION", "Conflict should be RECESSION"
        print(f"   - Conflicting event: {conflicts[0].event_type}")
        
        # Test 3: Cancel conflicting events
        print("\n📝 Test 3: Cancelling conflicting events")
        await events_engine.cancel_events(conflicts, "Replaced by ECONOMIC_BOOM")
        await session.commit()
        
        # Verify cancellation
        await session.refresh(recession)
        print(f"✅ Recession duration after cancellation: {recession.duration_months}")
        assert recession.duration_months == 0, "Event should be cancelled (duration = 0)"
        
        # Test 4: Verify no active events remain
        print("\n📝 Test 4: Verifying no active events remain")
        active_events = await events_engine.get_active_events()
        print(f"✅ Active events after cancellation: {len(active_events)}")
        assert len(active_events) == 0, "No events should be active after cancellation"
        
        # Test 5: Create ECONOMIC_BOOM
        print("\n📝 Test 5: Creating new ECONOMIC_BOOM event")
        boom = MarketEvent(
            event_type="ECONOMIC_BOOM",
            start_month=1,
            start_year=2026,
            duration_months=4,
            intensity=1.25,
            description="Economic Boom! Market demand +25% for 4 months"
        )
        session.add(boom)
        await session.commit()
        
        active_events = await events_engine.get_active_events()
        print(f"✅ Active events: {len(active_events)}")
        for event in active_events:
            print(f"   - {event.event_type}: {event.description}")
        assert len(active_events) == 1, "Only BOOM should be active"
        assert active_events[0].event_type == "ECONOMIC_BOOM"
        
        # Test 6: Verify no conflicts with same event type
        print("\n📝 Test 6: Checking conflicts for another ECONOMIC_BOOM (should be none)")
        conflicts = await events_engine.check_event_conflicts("ECONOMIC_BOOM")
        print(f"✅ Conflicts found: {len(conflicts)}")
        assert len(conflicts) == 0, "Same event type should not conflict with itself"
        
        print("\n" + "=" * 80)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 80)
        print("\n✅ Event conflict detection is working correctly!")
        print("✅ Contradictory events (BOOM + RECESSION) cannot coexist!")
        print("✅ Events are properly cancelled when conflicts occur!")


if __name__ == "__main__":
    asyncio.run(test_event_conflicts())
