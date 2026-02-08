"""
Bot AI Decision Making for Ledger Tycoon

Implements different bot personalities and strategic decision-making.
"""

from typing import Dict, List, Tuple
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
        """Adjust product prices based on personality and actual inventory costs."""
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
            # Use cost-aware pricing that considers actual inventory costs
            cost_aware_price = await self._get_cost_aware_price(
                product, company.id, target_margin, logs
            )
            
            # Add some randomness (±5%) for market dynamics
            variance = random.uniform(-0.05, 0.05)  # ±5%
            new_price = cost_aware_price * (1 + variance)
            
            old_price = cp.price
            cp.price = round(new_price, 2)
            
            msg = f"    💵 {product.name}: ${old_price:.2f} → ${cp.price:.2f} (Target margin: {target_margin*100:.0f}%)"
            print(msg)
            logs.append(msg)
        
        await self.db.commit()
    
    async def _calculate_inventory_cost(self, company_id: int, product_id: int) -> float:
        """Calculate weighted average cost of current inventory."""
        result = await self.db.execute(
            select(InventoryItem)
            .where(
                InventoryItem.company_id == company_id,
                InventoryItem.product_id == product_id
            )
        )
        items = result.scalars().all()
        
        if not items:
            # No inventory, return base cost as fallback
            product_result = await self.db.execute(
                select(Product).where(Product.id == product_id)
            )
            product = product_result.scalar_one()
            return product.base_cost
        
        total_value = sum(item.quantity * item.wac for item in items)
        total_quantity = sum(item.quantity for item in items)
        
        if total_quantity == 0:
            product_result = await self.db.execute(
                select(Product).where(Product.id == product_id)
            )
            product = product_result.scalar_one()
            return product.base_cost
        
        return total_value / total_quantity
    
    async def _get_cost_aware_price(self, product: Product, company_id: int, target_margin: float, logs: List[str]) -> float:
        """Calculate price based on actual inventory cost, not just base cost."""
        # Get current average inventory cost
        avg_cost = await self._calculate_inventory_cost(company_id, product.id)
        
        # Get current inventory quantity for logging
        result = await self.db.execute(
            select(InventoryItem)
            .where(
                InventoryItem.company_id == company_id,
                InventoryItem.product_id == product.id
            )
        )
        items = result.scalars().all()
        current_qty = sum(item.quantity for item in items)
        
        # Calculate minimum viable price (5% minimum margin)
        minimum_margin = 0.05
        minimum_price = avg_cost * (1 + minimum_margin)
        
        # Calculate base target price (using base cost)
        base_target = product.base_cost * (1 + target_margin)
        
        # Calculate cost-aware target price (using actual inventory cost)
        cost_aware_target = avg_cost * (1 + target_margin)
        
        # Choose the higher of the two to avoid losses
        target_price = max(base_target, cost_aware_target)
        
        # Ensure we're above minimum viable price
        final_price = max(target_price, minimum_price)
        
        # Log the cost-aware pricing analysis
        msg_header = f"    💡 COST-AWARE PRICING ANALYSIS:"
        msg_product = f"      Product: {product.name}"
        msg_inv = f"      📦 Current Inventory: {current_qty} units @ avg ${avg_cost:.2f}/unit"
        msg_base = f"      📊 Base Cost: ${product.base_cost:.2f}"
        msg_margin = f"      💰 Target Margin: {target_margin*100:.0f}%"
        msg_base_target = f"      ➡️  Base Target Price: ${base_target:.2f} ({product.base_cost:.2f} × {1+target_margin:.2f})"
        msg_cost_target = f"      ➡️  Cost-Aware Target: ${cost_aware_target:.2f} ({avg_cost:.2f} × {1+target_margin:.2f})"
        msg_min = f"      ➡️  Minimum Viable Price: ${minimum_price:.2f} ({avg_cost:.2f} × {1+minimum_margin:.2f})"
        
        # Determine which price was selected
        if final_price == cost_aware_target:
            decision = "cost-aware target"
        elif final_price == base_target:
            decision = "base target"
        else:
            decision = "minimum viable"
        
        msg_final = f"      ✅ FINAL PRICE: ${final_price:.2f} ({decision})"
        
        print(msg_header)
        print(msg_product)
        print(msg_inv)
        print(msg_base)
        print(msg_margin)
        print(msg_base_target)
        print(msg_cost_target)
        print(msg_min)
        print(msg_final)
        
        logs.append(msg_header)
        logs.append(msg_product)
        logs.append(msg_inv)
        logs.append(msg_base)
        logs.append(msg_margin)
        logs.append(msg_base_target)
        logs.append(msg_cost_target)
        logs.append(msg_min)
        logs.append(msg_final)
        
        return final_price
    
    async def _evaluate_purchase_viability(self, product: Product, purchase_cost: float, 
                                           target_margin: float, logs: List[str]) -> Tuple[bool, float, str]:
        """Evaluate if purchasing at given cost makes economic sense.
        
        Returns: (should_buy, quantity_multiplier, reason)
        """
        # Calculate break-even price needed to achieve target margin
        breakeven_price = purchase_cost * (1 + target_margin)
        
        # Get current market average price (estimate from base price)
        # In reality, we'd look at recent sales data
        market_estimate = product.base_price
        
        # Calculate viability score
        # If breakeven > market, it's risky
        price_gap = breakeven_price - market_estimate
        price_gap_pct = (price_gap / market_estimate) * 100 if market_estimate > 0 else 0
        
        # Decision logic
        if price_gap_pct > 20:
            # Break-even is >20% above market - SKIP entirely
            viability = "CRITICAL"
            should_buy = False
            qty_multiplier = 0.0
            reason = f"Break-even ${breakeven_price:.2f} exceeds market by {price_gap_pct:.0f}% - purchase would guarantee major losses"
        elif price_gap_pct > 10:
            # Break-even is 10-20% above market - REDUCE by 70%
            viability = "LOW"
            should_buy = True
            qty_multiplier = 0.3
            reason = f"Break-even ${breakeven_price:.2f} is {price_gap_pct:.0f}% above market - reducing purchase by 70%"
        elif price_gap_pct > 0:
            # Break-even is 0-10% above market - REDUCE by 50%
            viability = "MODERATE"
            should_buy = True
            qty_multiplier = 0.5
            reason = f"Break-even ${breakeven_price:.2f} is {price_gap_pct:.0f}% above market - reducing purchase by 50%"
        else:
            # Break-even is below market - FULL PURCHASE
            viability = "HIGH"
            should_buy = True
            qty_multiplier = 1.0
            reason = f"Break-even ${breakeven_price:.2f} is below market ${market_estimate:.2f} - profitable purchase"
        
        # Log the viability analysis
        msg_header = f"    💡 PURCHASE VIABILITY ANALYSIS:"
        msg_product = f"      Product: {product.name}"
        msg_cost = f"      🛒 Purchase Cost: ${purchase_cost:.2f}/unit"
        msg_margin = f"      📊 Target Margin: {target_margin*100:.0f}%"
        msg_breakeven = f"      ➡️  Break-Even Price: ${breakeven_price:.2f} ({purchase_cost:.2f} × {1+target_margin:.2f})"
        msg_market = f"      📈 Market Expectation: ${market_estimate:.2f} (base price)"
        msg_viability = f"      ⚠️  VIABILITY: {viability} (break-even {'+' if price_gap > 0 else ''}{price_gap_pct:.1f}% vs market)"
        
        if should_buy:
            msg_decision = f"      🔧 DECISION: Purchase at {qty_multiplier*100:.0f}% of recommended quantity"
        else:
            msg_decision = f"      🛑 DECISION: SKIP purchase entirely"
        
        msg_reason = f"      📝 Reason: {reason}"
        
        print(msg_header)
        print(msg_product)
        print(msg_cost)
        print(msg_margin)
        print(msg_breakeven)
        print(msg_market)
        print(msg_viability)
        print(msg_decision)
        print(msg_reason)
        
        logs.append(msg_header)
        logs.append(msg_product)
        logs.append(msg_cost)
        logs.append(msg_margin)
        logs.append(msg_breakeven)
        logs.append(msg_market)
        logs.append(msg_viability)
        logs.append(msg_decision)
        logs.append(msg_reason)
        
        return should_buy, qty_multiplier, reason
    
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
            
            # Get bot personality for margin calculation
            personality = self._get_personality(company)
            target_margin = self.personality_config[personality]["margin"]
            
            # Evaluate purchase viability (will this lead to guaranteed losses?)
            should_buy, qty_multiplier, reason = await self._evaluate_purchase_viability(
                product, unit_cost, target_margin, logs
            )
            
            if not should_buy:
                # Skip this purchase entirely
                msg_skip = f"    🛑 SKIPPING {product.name} purchase: {reason}"
                print(msg_skip)
                logs.append(msg_skip)
                continue
            
            # Apply viability adjustment to recommended quantity
            viability_adjusted_qty = int(recommended_qty * qty_multiplier)
            
            # Apply cash flow constraint
            max_affordable = int(cash / unit_cost)
            purchase_qty = min(viability_adjusted_qty, max_affordable)
            
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
            
            if qty_multiplier < 1.0:
                msg_adjusted = f"    🔧 Quantity Adjusted: {recommended_qty} → {viability_adjusted_qty} (×{qty_multiplier:.0%} due to viability)"
                print(msg_adjusted)
                logs.append(msg_adjusted)
            
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
