"""
Market Events Engine

Manages dynamic market events including seasonal demand patterns,
economic cycles (booms/recessions), supply chain disruptions,
and player decision events.
"""

import random
import json
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.models import MarketEvent, Product, Company


@dataclass
class EventChoice:
    """Represents a player choice for an event."""
    id: str
    label: str
    description: str
    effects: Dict


@dataclass
class DecisionEvent:
    """Template for events requiring player decisions."""
    title: str
    description: str
    choices: List[EventChoice]
    trigger_condition: Optional[callable] = None


# Decision Event Templates
DECISION_EVENT_TEMPLATES = [
    DecisionEvent(
        title="Viral Social Media Post",
        description="Your Premium Gadget was featured by a major influencer! Demand will spike +200% for 2 turns.",
        choices=[
            EventChoice(
                id="RUSH_PRODUCTION",
                label="Rush Production",
                description="Increase production capacity to meet demand, but quality may suffer (-15% quality risk)",
                effects={"inventory_boost": 1.5, "quality_risk": 0.15, "cost_increase": 1.2}
            ),
            EventChoice(
                id="MAINTAIN_QUALITY",
                label="Maintain Quality Standards",
                description="Keep current production levels, miss 60% of spike demand but protect brand",
                effects={"demand_cap": 0.4, "brand_protection": True}
            ),
            EventChoice(
                id="RAISE_PRICES",
                label="Raise Prices +30%",
                description="Capitalize on hype with premium pricing, but risk brand damage",
                effects={"price_modifier": 1.3, "brand_risk": 0.3, "duration": 2}
            )
        ]
    ),
    
    DecisionEvent(
        title="Supplier Bankruptcy",
        description="Your main supplier went bankrupt. A competitor offers to buy their inventory at 40% discount, but quality is uncertain.",
        choices=[
            EventChoice(
                id="BUY_INVENTORY",
                label="Buy Discounted Inventory",
                description="Purchase 500 units at 40% off, but 20% defect rate risk",
                effects={"cash": -6000, "inventory_boost": 500, "defect_risk": 0.2}
            ),
            EventChoice(
                id="FIND_NEW_SUPPLIER",
                label="Find New Supplier",
                description="Spend $5K on sourcing, miss 1 turn of production",
                effects={"cash": -5000, "production_delay": 1}
            ),
            EventChoice(
                id="VERTICAL_INTEGRATION",
                label="Acquire Supplier Assets",
                description="Buy bankrupt supplier for $25K, gain long-term 15% cost savings",
                effects={"cash": -25000, "cost_reduction": 0.15, "permanent": True}
            )
        ]
    ),
    
    DecisionEvent(
        title="Competitor Price War",
        description="A competitor slashed prices by 30% to gain market share. How do you respond?",
        choices=[
            EventChoice(
                id="MATCH_PRICES",
                label="Match Their Prices",
                description="Protect market share but sacrifice margins for 2 turns",
                effects={"price_modifier": 0.7, "market_share_protection": True, "duration": 2}
            ),
            EventChoice(
                id="DIFFERENTIATE",
                label="Invest in Marketing",
                description="Spend $10K on brand campaign to justify premium pricing",
                effects={"cash": -10000, "brand_equity": 1.5}
            ),
            EventChoice(
                id="IGNORE",
                label="Maintain Current Strategy",
                description="Let them compete on price, you compete on quality (lose 15% market share)",
                effects={"market_share_loss": 0.15, "duration": 2}
            )
        ]
    ),
    
    DecisionEvent(
        title="Product Recall Threat",
        description="Quality control found a potential defect in 20% of your inventory. Recall now or risk customer complaints?",
        choices=[
            EventChoice(
                id="FULL_RECALL",
                label="Full Product Recall",
                description="Recall all affected inventory, lose $15K but protect brand reputation",
                effects={"cash": -15000, "inventory_loss": 0.2, "brand_protection": True}
            ),
            EventChoice(
                id="SILENT_FIX",
                label="Silent Fix",
                description="Fix new production only, hope customers don't notice (60% chance of scandal)",
                effects={"scandal_risk": 0.6, "brand_risk": -2.0}
            ),
            EventChoice(
                id="DISCOUNT_SALE",
                label="Discount Sale",
                description="Sell defective inventory at 50% off with disclaimer, recover some costs",
                effects={"revenue_recovery": 0.5, "brand_equity": -0.5}
            )
        ]
    ),
    
    DecisionEvent(
        title="Major Client Opportunity",
        description="A corporate client wants to order 1000 units at 20% discount with exclusive 6-month contract.",
        choices=[
            EventChoice(
                id="ACCEPT_CONTRACT",
                label="Accept Exclusive Contract",
                description="Guaranteed revenue but locked into lower prices for 6 months",
                effects={"guaranteed_sales": 1000, "price_lock": 0.8, "duration": 6}
            ),
            EventChoice(
                id="NEGOTIATE",
                label="Negotiate Better Terms",
                description="Counter-offer at 10% discount, 50% chance they accept",
                effects={"negotiation_chance": 0.5, "price_lock": 0.9, "guaranteed_sales": 1000}
            ),
            EventChoice(
                id="DECLINE",
                label="Decline Offer",
                description="Maintain pricing flexibility, miss guaranteed revenue",
                effects={"opportunity_cost": 1000}
            )
        ]
    )
]


class MarketEventsEngine:
    """Manages market events and their effects on demand and costs."""
    
    # Event conflict groups - events in the same group are mutually exclusive
    EVENT_CONFLICTS = {
        "ECONOMIC": ["ECONOMIC_BOOM", "RECESSION"],
        "SUPPLY": ["SUPPLY_DISRUPTION"],  # Can expand later with more supply events
    }
    
    # Defined intensity levels for economic events
    ECONOMIC_INTENSITY_LEVELS = {
        "RECESSION": [
            {"name": "Mild", "intensity": 0.85},
            {"name": "Moderate", "intensity": 0.76},
            {"name": "Severe", "intensity": 0.68},
            {"name": "Crisis", "intensity": 0.60},
        ],
        "ECONOMIC_BOOM": [
            {"name": "Mild", "intensity": 1.15},
            {"name": "Moderate", "intensity": 1.25},
            {"name": "Strong", "intensity": 1.35},
            {"name": "Exceptional", "intensity": 1.45},
        ]
    }
    
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
            
            # Check for conflicting events (Different Type - e.g. Boom vs Recession)
            conflicting_events = await self.check_event_conflicts(event_type)
            if conflicting_events:
                # CONFLICT: Cancel old event, start new one at Mild intensity
                await self.cancel_events(
                    conflicting_events,
                    f"Replaced by new {event_type} (Economic Shock)"
                )
                
                # Start new event at Mild intensity
                level_data = self.ECONOMIC_INTENSITY_LEVELS[event_type][0]
                duration = random.randint(2, 4)
                
                event = MarketEvent(
                    event_type=event_type,
                    start_month=self.current_month,
                    start_year=self.current_year,
                    duration_months=duration,
                    intensity=level_data["intensity"],
                    description=f"{level_data['name']} {event_type.replace('_', ' ').title()}! Market demand x{level_data['intensity']} for {duration} months"
                )
                self.db.add(event)
                new_events.append(event)
                print(f"  🔄 ECONOMIC SHOCK: {event.description}")
            
            else:
                # Check for SAME event type (Stacking/Worsening)
                active_same_events = [
                    e for e in await self.get_active_events() 
                    if e.event_type == event_type
                ]
                
                if active_same_events:
                    # STACKING: Worsen the existing event
                    existing_event = active_same_events[0]
                    current_intensity = existing_event.intensity
                    
                    # Find current level index
                    levels = self.ECONOMIC_INTENSITY_LEVELS[event_type]
                    current_idx = -1
                    
                    # Find closest matching intensity level
                    closest_diff = float('inf')
                    for i, level in enumerate(levels):
                        diff = abs(level["intensity"] - current_intensity)
                        if diff < closest_diff:
                            closest_diff = diff
                            current_idx = i
                    
                    # Worsen by 1 level if possible
                    new_idx = min(current_idx + 1, len(levels) - 1)
                    new_level = levels[new_idx]
                    
                    # Update event
                    old_intensity = existing_event.intensity
                    existing_event.intensity = new_level["intensity"]
                    
                    # Extend duration
                    added_duration = random.randint(2, 4)
                    existing_event.duration_months += added_duration
                    
                    # Update description
                    existing_event.description = f"{new_level['name']} {event_type.replace('_', ' ').title()}! Market demand x{new_level['intensity']} (Worsened!)"
                    
                    print(f"  📉 ECONOMIC UPDATE: {event_type} worsened! "
                          f"Intensity {old_intensity} -> {existing_event.intensity}. "
                          f"Duration +{added_duration} months.")
                    
                else:
                    # NEW EVENT (No conflict, no existing same type)
                    # Start at Moderate level for standard random events
                    level_data = self.ECONOMIC_INTENSITY_LEVELS[event_type][1] # Moderate
                    duration = random.randint(2, 4)
                    
                    event = MarketEvent(
                        event_type=event_type,
                        start_month=self.current_month,
                        start_year=self.current_year,
                        duration_months=duration,
                        intensity=level_data["intensity"],
                        affected_product_id=None,
                        description=f"{level_data['name']} {event_type.replace('_', ' ').title()}. Market demand x{level_data['intensity']} for {duration} months"
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
    
    async def check_event_conflicts(self, new_event_type: str) -> List[MarketEvent]:
        """
        Check if a new event conflicts with active events.
        Returns list of conflicting events that should be cancelled.
        """
        # Find which conflict group this event belongs to
        conflict_group = None
        for group_name, event_types in self.EVENT_CONFLICTS.items():
            if new_event_type in event_types:
                conflict_group = event_types
                break
        
        if not conflict_group:
            return []  # No conflicts possible
        
        # Get active events
        active_events = await self.get_active_events()
        
        # Find conflicting events (same group, different type)
        conflicting = [
            event for event in active_events
            if event.event_type in conflict_group and event.event_type != new_event_type
        ]
        
        return conflicting
    
    async def cancel_events(self, events: List[MarketEvent], reason: str) -> None:
        """Cancel active events by setting their duration to 0."""
        for event in events:
            event.duration_months = 0
            print(f"  ⚠️  CANCELLED: {event.description} ({reason})")

    async def process_economic_evolution(self):
        """
        Evolve active economic events (Recession/Boom).
        - 25% chance to IMPROVE (stabilize towards neutral)
        - 10% chance to WORSEN (move away from neutral)
        """
        active_events = await self.get_active_events()
        
        for event in active_events:
            if event.event_type not in self.ECONOMIC_INTENSITY_LEVELS:
                continue
                
            # Evolution Logic
            roll = random.random()
            levels = self.ECONOMIC_INTENSITY_LEVELS[event.event_type]
            
            # Find current level index
            current_idx = -1
            closest_diff = float('inf')
            for i, level in enumerate(levels):
                diff = abs(level["intensity"] - event.intensity)
                if diff < closest_diff:
                    closest_diff = diff
                    current_idx = i
            
            original_intensity = event.intensity
            
            if roll < 0.25:
                # IMPROVE (Stabilize): Move towards index 0 (Mild) or remove if already Mild?
                # Actually, "Improve" means moving towards neutral (1.0). 
                # Since levels are ordered Mild -> Crisis, "Improve" means decreasing index.
                
                if current_idx > 0:
                    new_idx = current_idx - 1
                    new_level = levels[new_idx]
                    event.intensity = new_level["intensity"]
                    event.description = f"{new_level['name']} {event.event_type.replace('_', ' ').title()} (Stabilizing). Market demand x{new_level['intensity']}"
                    print(f"  📈 ECONOMIC RECOVERY: {event.event_type} stabilized! "
                          f"Intensity {original_intensity:.2f} -> {event.intensity:.2f} ({new_level['name']})")
                
            elif roll < 0.35: # Next 10% (0.25 to 0.35)
                # WORSEN: Move towards max index (Crisis/Exceptional)
                if current_idx < len(levels) - 1:
                    new_idx = current_idx + 1
                    new_level = levels[new_idx]
                    event.intensity = new_level["intensity"]
                    event.description = f"{new_level['name']} {event.event_type.replace('_', ' ').title()} (Intensifying!). Market demand x{new_level['intensity']}"
                    print(f"  📉 ECONOMIC DOWNTURN: {event.event_type} worsened! "
                          f"Intensity {original_intensity:.2f} -> {event.intensity:.2f} ({new_level['name']})")
    
    async def update_event_durations(self):
        """Decrement duration of all active events and clean up expired ones."""
        result = await self.db.execute(
            select(MarketEvent)
            .where(MarketEvent.duration_months > 0)
        )
        events = result.scalars().all()
        
        for event in events:
            event.duration_months -= 1
        
        # Flush the decrements first
        await self.db.flush()
        
        # Now delete expired events (duration <= 0)
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
            .limit(1)  # Only get the first active economic event
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
            .limit(1)  # Only get the first active disruption for this product
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
    
    async def trigger_decision_event(self) -> Optional[MarketEvent]:
        """
        Trigger a decision event requiring player input.
        Returns the created event or None if conditions not met.
        """
        # Only trigger if no active decision events
        result = await self.db.execute(
            select(MarketEvent)
            .where(MarketEvent.requires_player_decision == True)
            .where(MarketEvent.decision_made == False)
        )
        if result.scalar_one_or_none():
            return None  # Already have pending decision
        
        # 20% chance per turn
        if random.random() > 0.20:
            return None
        
        # Pick random event template
        template = random.choice(DECISION_EVENT_TEMPLATES)
        
        # Serialize choices to JSON
        event_data = {
            "title": template.title,
            "description": template.description,
            "choices": [
                {
                    "id": choice.id,
                    "label": choice.label,
                    "description": choice.description,
                    "effects": choice.effects
                }
                for choice in template.choices
            ]
        }
        
        # Create event
        event = MarketEvent(
            event_type="DECISION_EVENT",
            start_month=self.current_month,
            start_year=self.current_year,
            duration_months=1,  # Decision deadline is 1 month
            requires_player_decision=True,
            decision_deadline_month=self.current_month,
            decision_deadline_year=self.current_year,
            description=template.title,
            event_data=json.dumps(event_data)
        )
        
        self.db.add(event)
        await self.db.flush()
        return event
    
    async def apply_decision_effects(self, event: MarketEvent, choice_id: str, company_id: int) -> str:
        """
        Apply the effects of a player's decision.
        Returns a log string describing the effects applied.
        """
        from core.accounting import AccountingEngine
        
        event_data = json.loads(event.event_data)
        
        # Find the chosen option
        choice = next((c for c in event_data["choices"] if c["id"] == choice_id), None)
        if not choice:
            return f"❌ Invalid choice: {choice_id}"
        
        effects = choice["effects"]
        log = []
        log.append(f"    🎯 DECISION APPLIED: {choice['label']}")
        log.append(f"    📝 {choice['description']}")
        log.append(f"    ⚙️  Effects Applied:")
        
        # Get company
        company = await self.db.get(Company, company_id)
        
        # Apply cash effects
        if "cash" in effects:
            cash_change = effects["cash"]
            accounting = AccountingEngine(self.db)
            cash_account = await accounting._get_account_by_code(company_id, "1000")
            
            if cash_change < 0:
                # Expense
                expense_account = await accounting._get_account_by_code(company_id, "5200")  # Marketing Expense
                await accounting.create_transaction(
                    company_id=company_id,
                    description=f"Decision Event: {choice['label']}",
                    entries=[
                        (expense_account.id, abs(cash_change)),
                        (cash_account.id, cash_change)
                    ]
                )
                log.append(f"       💰 Cash: ${cash_change:,.2f}")
            else:
                # Revenue
                revenue_account = await accounting._get_account_by_code(company_id, "4000")
                await accounting.create_transaction(
                    company_id=company_id,
                    description=f"Decision Event Revenue: {choice['label']}",
                    entries=[
                        (cash_account.id, cash_change),
                        (revenue_account.id, -cash_change)
                    ]
                )
                log.append(f"       💰 Cash: +${cash_change:,.2f}")
        
        # Apply brand equity effects
        if "brand_equity" in effects:
            brand_change = effects["brand_equity"]
            old_brand = company.brand_equity
            company.brand_equity += brand_change
            log.append(f"       📈 Brand Equity: {old_brand:.2f} → {company.brand_equity:.2f} ({brand_change:+.2f})")
        
        # Apply brand risk (negative effect)
        if "brand_risk" in effects:
            risk = effects["brand_risk"]
            # Roll for risk
            if random.random() < risk:
                brand_damage = effects.get("brand_damage", -1.0)
                old_brand = company.brand_equity
                company.brand_equity += brand_damage
                log.append(f"       ⚠️  Brand Risk Triggered! Brand Equity: {old_brand:.2f} → {company.brand_equity:.2f} ({brand_damage:.2f})")
            else:
                log.append(f"       ✅ Brand Risk Avoided (Risk: {risk*100:.0f}%)")
        
        # Log other effects (to be implemented in future)
        for key, value in effects.items():
            if key not in ["cash", "brand_equity", "brand_risk", "duration"]:
                if isinstance(value, bool):
                    log.append(f"       🔧 {key.replace('_', ' ').title()}: {'Yes' if value else 'No'}")
                elif isinstance(value, (int, float)):
                    log.append(f"       🔧 {key.replace('_', ' ').title()}: {value}")
                else:
                    log.append(f"       🔧 {key.replace('_', ' ').title()}: {value}")
        
        # Mark decision as made
        event.decision_made = True
        event.player_decision = choice_id
        
        # If duration specified, create follow-up effect event
        if "duration" in effects:
            duration = effects["duration"]
            log.append(f"       ⏱️  Effect Duration: {duration} month(s)")
        
        return "\n".join(log)
    
    async def get_pending_decision_events(self) -> List[MarketEvent]:
        """Get all pending decision events requiring player input."""
        result = await self.db.execute(
            select(MarketEvent)
            .where(MarketEvent.requires_player_decision == True)
            .where(MarketEvent.decision_made == False)
        )
        return result.scalars().all()
    
    def format_decision_event_log(self, event: MarketEvent) -> str:
        """Format a decision event for the game log."""
        if not event.event_data:
            return ""
        
        event_data = json.loads(event.event_data)
        log = []
        log.append(f"\n🎲 DECISION EVENT TRIGGERED:")
        log.append(f"  📋 Event: {event_data['title']}")
        log.append(f"  📝 Description: {event_data['description']}")
        log.append(f"  ⏰ Decision Deadline: {event.decision_deadline_month}/{event.decision_deadline_year}")
        log.append(f"  🎯 Available Choices:")
        
        for i, choice in enumerate(event_data['choices'], 1):
            log.append(f"\n    Choice {i}: {choice['label']}")
            log.append(f"      📖 {choice['description']}")
            log.append(f"      ⚙️  Effects:")
            for key, value in choice['effects'].items():
                if isinstance(value, bool):
                    log.append(f"         • {key.replace('_', ' ').title()}: {'Yes' if value else 'No'}")
                elif isinstance(value, (int, float)):
                    if key == "cash":
                        log.append(f"         • Cash Impact: ${value:,.2f}")
                    elif "modifier" in key or "risk" in key:
                        log.append(f"         • {key.replace('_', ' ').title()}: {value:.1%}")
                    else:
                        log.append(f"         • {key.replace('_', ' ').title()}: {value}")
                else:
                    log.append(f"         • {key.replace('_', ' ').title()}: {value}")
        
        log.append(f"\n  ⚠️  This event requires a player decision before the next turn can be processed!")
        
        return "\n".join(log)

