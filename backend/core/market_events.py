"""
Market Events Engine

Manages dynamic market events including seasonal demand patterns,
economic cycles (booms/recessions), and supply chain disruptions.
"""

import random
from typing import Dict, List, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.models import MarketEvent, Product


class MarketEventsEngine:
    """Manages market events and their effects on demand and costs."""
    
    # Seasonal demand modifiers by product name and month
    SEASONAL_PATTERNS = {
        # Spring (Mar-May): Widgets +20%, Tools +10%
        3: {"Basic Widget": 1.20, "Professional Tool": 1.10},
        4: {"Basic Widget": 1.20, "Professional Tool": 1.10},
        5: {"Basic Widget": 1.20, "Professional Tool": 1.10},
        
        # Summer (Jun-Aug): Gadgets +30%, Widgets -10%
        6: {"Premium Gadget": 1.30, "Basic Widget": 0.90},
        7: {"Premium Gadget": 1.30, "Basic Widget": 0.90},
        8: {"Premium Gadget": 1.30, "Basic Widget": 0.90},
        
        # Fall (Sep-Nov): Tools +25%
        9: {"Professional Tool": 1.25},
        10: {"Professional Tool": 1.25},
        11: {"Professional Tool": 1.25},
        
        # Winter (Dec-Feb): Widgets +15%, Gadgets -15%
        12: {"Basic Widget": 1.15, "Premium Gadget": 0.85},
        1: {"Basic Widget": 1.15, "Premium Gadget": 0.85},
        2: {"Basic Widget": 1.15, "Premium Gadget": 0.85},
    }
    
    def __init__(self, db: AsyncSession, current_month: int, current_year: int):
        self.db = db
        self.current_month = current_month
        self.current_year = current_year
        
    async def trigger_random_events(self) -> List[MarketEvent]:
        """
        Randomly trigger new market events.
        Returns list of newly created events.
        """
        new_events = []
        
        # 25% chance for economic event
        if random.random() < 0.25:
            event_type = random.choice(["ECONOMIC_BOOM", "RECESSION"])
            duration = random.randint(2, 4)
            
            if event_type == "ECONOMIC_BOOM":
                intensity = 1.25
                description = f"Economic Boom! Market demand +25% for {duration} months"
            else:  # RECESSION
                intensity = 0.80
                description = f"Economic Recession. Market demand -20% for {duration} months"
            
            event = MarketEvent(
                event_type=event_type,
                start_month=self.current_month,
                start_year=self.current_year,
                duration_months=duration,
                intensity=intensity,
                affected_product_id=None,
                description=description
            )
            self.db.add(event)
            new_events.append(event)
        
        # 15% chance for supply chain disruption
        if random.random() < 0.15:
            # Get all products
            result = await self.db.execute(select(Product))
            products = result.scalars().all()
            
            if products:
                affected_product = random.choice(products)
                duration = random.randint(1, 2)
                cost_increase = random.choice([1.20, 1.30])  # +20% or +30%
                
                event = MarketEvent(
                    event_type="SUPPLY_DISRUPTION",
                    start_month=self.current_month,
                    start_year=self.current_year,
                    duration_months=duration,
                    intensity=cost_increase,
                    affected_product_id=affected_product.id,
                    description=f"Supply Chain Disruption: {affected_product.name} costs +{int((cost_increase-1)*100)}% for {duration} month{'s' if duration > 1 else ''}"
                )
                self.db.add(event)
                new_events.append(event)
        
        await self.db.flush()
        return new_events
    
    async def get_active_events(self) -> List[MarketEvent]:
        """Get all active market events."""
        result = await self.db.execute(
            select(MarketEvent)
            .where(MarketEvent.duration_months > 0)
        )
        return result.scalars().all()
    
    async def update_event_durations(self):
        """Decrement duration of all active events and clean up expired ones."""
        result = await self.db.execute(
            select(MarketEvent)
            .where(MarketEvent.duration_months > 0)
        )
        events = result.scalars().all()
        
        for event in events:
            event.duration_months -= 1
        
        # Delete expired events
        await self.db.execute(
            delete(MarketEvent)
            .where(MarketEvent.duration_months <= 0)
        )
        
        await self.db.flush()
    
    def get_seasonal_modifier(self, product_name: str) -> float:
        """Get seasonal demand modifier for a product."""
        month_patterns = self.SEASONAL_PATTERNS.get(self.current_month, {})
        return month_patterns.get(product_name, 1.0)
    
    async def get_economic_modifier(self) -> float:
        """Get current economic modifier (from booms/recessions)."""
        result = await self.db.execute(
            select(MarketEvent)
            .where(MarketEvent.event_type.in_(["ECONOMIC_BOOM", "RECESSION"]))
            .where(MarketEvent.duration_months > 0)
        )
        event = result.scalar_one_or_none()
        
        return event.intensity if event else 1.0
    
    async def get_cost_modifier(self, product_id: int) -> float:
        """Get cost modifier for a specific product (from supply disruptions)."""
        result = await self.db.execute(
            select(MarketEvent)
            .where(MarketEvent.event_type == "SUPPLY_DISRUPTION")
            .where(MarketEvent.affected_product_id == product_id)
            .where(MarketEvent.duration_months > 0)
        )
        event = result.scalar_one_or_none()
        
        return event.intensity if event else 1.0
    
    async def apply_demand_modifiers(
        self, 
        base_demand: float, 
        product_name: str
    ) -> Tuple[float, Dict[str, float]]:
        """
        Apply all active demand modifiers.
        Returns: (final_demand, modifiers_dict)
        """
        seasonal = self.get_seasonal_modifier(product_name)
        economic = await self.get_economic_modifier()
        
        final_demand = base_demand * seasonal * economic
        
        modifiers = {
            "base": base_demand,
            "seasonal": seasonal,
            "economic": economic,
            "final": final_demand
        }
        
        return final_demand, modifiers
    
    def get_season_name(self) -> str:
        """Get the current season name for logging."""
        if self.current_month in [3, 4, 5]:
            return "Spring"
        elif self.current_month in [6, 7, 8]:
            return "Summer"
        elif self.current_month in [9, 10, 11]:
            return "Fall"
        else:  # 12, 1, 2
            return "Winter"
