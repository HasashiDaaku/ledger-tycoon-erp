"""
Quick script to check the current state of market events in the database.
This will show if events are properly decrementing their durations.
"""
import asyncio
from sqlalchemy import select
from app.database import get_db
from app.models import MarketEvent

async def check_events():
    """Check all active market events."""
    async for db in get_db():
        result = await db.execute(select(MarketEvent))
        events = result.scalars().all()
        
        print(f"\n📊 Total Events in Database: {len(events)}")
        print("=" * 80)
        
        if not events:
            print("No events found in database.")
            return
        
        for event in events:
            print(f"\n🎯 Event ID: {event.id}")
            print(f"   Type: {event.event_type}")
            print(f"   Description: {event.description}")
            print(f"   Start: {event.start_month}/{event.start_year}")
            print(f"   Duration Remaining: {event.duration_months} month(s)")
            print(f"   Requires Decision: {event.requires_player_decision}")
            print(f"   Decision Made: {event.decision_made}")
            if event.player_decision:
                print(f"   Player Choice: {event.player_decision}")
            print("-" * 80)

if __name__ == "__main__":
    asyncio.run(check_events())
