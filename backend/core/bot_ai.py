"""
Bot AI Decision Making for Ledger Tycoon

Implements different bot personalities and strategic decision-making.
"""

from typing import Dict, List
import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Company, CompanyProduct, Product, InventoryItem
from core.accounting import AccountingEngine

class BotPersonality:
    """Bot strategy profiles."""
    AGGRESSIVE = "aggressive"  # Low margin, high volume
    PREMIUM = "premium"        # High margin, low volume
    BALANCED = "balanced"      # Medium margin, medium volume

class BotAI:
    """AI decision-making for bot companies."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.accounting = AccountingEngine(db)
        
        # Personality targets
        self.personality_config = {
            BotPersonality.AGGRESSIVE: {"margin": 0.15, "price_adjust": 0.95},
            BotPersonality.PREMIUM: {"margin": 0.50, "price_adjust": 1.10},
            BotPersonality.BALANCED: {"margin": 0.30, "price_adjust": 1.00},
        }
    
    async def make_decisions(self, company: Company, logs: List[str] = None, events_engine=None):
        """
        Make strategic decisions for a bot company.
        
        Decisions:
        1. Adjust pricing based on personality
        2. Purchase inventory if running low
        3. (Future) Marketing spend
        """
        if logs is None:
            logs = []
            
        # Assign personality (stored or random)
        personality = self._get_personality(company)
        
        # 1. Pricing decisions
        await self._adjust_pricing(company, personality, logs)
        
        # 2. Inventory management
        await self._manage_inventory(company, logs, events_engine)
    
    def _get_personality(self, company: Company) -> str:
        """Get or assign personality to a bot."""
        # Simple hash-based assignment for consistency
        personalities = [BotPersonality.AGGRESSIVE, BotPersonality.PREMIUM, BotPersonality.BALANCED]
        return personalities[company.id % 3]
    
    async def _adjust_pricing(self, company: Company, personality: str, logs: List[str]):
        """Adjust product prices based on personality and market conditions."""
        config = self.personality_config[personality]
        target_margin = config["margin"]
        
        # Get all company products
        result = await self.db.execute(
            select(CompanyProduct, Product)
            .join(Product, Product.id == CompanyProduct.product_id)
            .where(CompanyProduct.company_id == company.id)
        )
        rows = result.all()
        
        for cp, product in rows:
            # Calculate target price based on cost + margin
            base_cost = product.base_cost
            # Original calculation: target_price = base_cost / (1 - target_margin)
            # New calculation from user's provided snippet:
            target_price = base_cost * (1 + target_margin)
            
            # Add some randomness (±5%)
            # Original randomness: randomness = random.uniform(0.95, 1.05); new_price = target_price * randomness
            # New randomness from user's provided snippet:
            variance = random.uniform(-0.05, 0.05)  # ±5%
            new_price = target_price * (1 + variance)
            
            # Ensure price is above cost (from user's provided snippet)
            new_price = max(new_price, product.base_cost * 1.1)
            
            old_price = cp.price
            cp.price = round(new_price, 2)
            
            msg = f"    💵 {product.name}: ${old_price:.2f} → ${cp.price:.2f} (Target margin: {target_margin*100:.0f}%)"
            print(msg)
            logs.append(msg)
        
        await self.db.commit()
    
    async def _manage_inventory(self, company: Company, logs: List[str], events_engine=None):
        """Purchase inventory using intelligent demand forecasting."""
        from app.models import Product
        from core.inventory_manager import InventoryManager
        
        # Get cash balance
        cash = await self.accounting.get_company_cash(company.id)
        
        msg_cash = f"    💰 Cash available: ${cash:,.2f}"
        print(msg_cash)
        logs.append(msg_cash)
        
        if cash < 10000:  # Not enough cash
            msg_low = f"    ⚠️  Low cash, skipping inventory purchase"
            print(msg_low)
            logs.append(msg_low)
            return
        
        # Initialize inventory manager
        inv_mgr = InventoryManager(self.db)
        
        # Get all products
        result = await self.db.execute(select(Product))
        products = result.scalars().all()
        
        for product in products:
            # Get intelligent reorder recommendation
            recommended_qty = await inv_mgr.get_reorder_quantity(
                company_id=company.id,
                product_id=product.id
            )
            
            if recommended_qty == 0:
                msg_skip = f"    ℹ️  {product.name}: Inventory sufficient (no reorder needed)"
                print(msg_skip)
                logs.append(msg_skip)
                continue
            
            # Get base cost and apply market event modifiers
            base_cost = product.base_cost
            cost_modifier = 1.0
            
            if events_engine:
                cost_modifier = await events_engine.get_cost_modifier(product.id)
            
            unit_cost = base_cost * cost_modifier
            
            # Log cost impact if modifier applied
            if cost_modifier != 1.0:
                modifier_pct = int((cost_modifier - 1) * 100)
                msg_cost = f"    ⚠️  Supply Chain Impact: ${base_cost:.2f} → ${unit_cost:.2f} (×{cost_modifier:.2f}, +{modifier_pct}%)"
                print(msg_cost)
                logs.append(msg_cost)
            
            # Apply cash flow constraint
            max_affordable = int(cash / unit_cost)
            purchase_qty = min(recommended_qty, max_affordable)
            
            if purchase_qty == 0:
                msg_nofunds = f"    ⚠️  Not enough cash to buy {product.name}"
                print(msg_nofunds)
                logs.append(msg_nofunds)
                continue
            
            total_cost = purchase_qty * unit_cost
            
            # Get forecast info for logging
            forecast = await inv_mgr.forecast_demand(company.id, product.id)
            safety_stock = await inv_mgr.calculate_safety_stock(company.id, product.id)
            current_inv = await inv_mgr.get_current_inventory(company.id, product.id)
            
            msg_analysis = f"    📊 {product.name} Analysis: Forecast={int(forecast)}, Safety={int(safety_stock)}, Current={current_inv}"
            print(msg_analysis)
            logs.append(msg_analysis)
            
            msg_buy = f"    🛒 Purchasing {purchase_qty} × {product.name} @ ${unit_cost:.2f} = ${total_cost:,.2f}"
            print(msg_buy)
            logs.append(msg_buy)
            
            # Import here to avoid circular dependency
            from core.engine import GameEngine
            engine = GameEngine(self.db)
            
            try:
                await engine.purchase_inventory(
                    company_id=company.id,
                    product_id=product.id,
                    quantity=purchase_qty,
                    unit_cost=unit_cost
                )
                cash -= total_cost
                msg_success = f"    ✅ Purchase complete. Remaining cash: ${cash:,.2f}"
                print(msg_success)
                logs.append(msg_success)
            except Exception as e:
                msg_fail = f"    ❌ Purchase failed: {e}"
                print(msg_fail)
                logs.append(msg_fail)
