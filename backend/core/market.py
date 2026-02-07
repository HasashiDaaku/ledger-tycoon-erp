"""
Market Demand and Sales Engine for Ledger Tycoon

Simulates market demand, price elasticity, and competitive dynamics.
"""

from typing import List, Dict, Tuple
import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Company, Product, CompanyProduct, MarketHistory

class MarketEngine:
    """Handles market demand calculation and sales distribution."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.base_demand = 1000  # Base market demand per product per month
        self.price_elasticity = 0.5  # How sensitive demand is to price changes
    
    async def calculate_market_demand(
        self, 
        product_id: int,
        events_engine=None,
        logs: List[str] = None
    ) -> float:
        """
        Calculate total market demand for a product.
        
        Factors:
        - Base demand (market size)
        - Seasonal modifiers (from events_engine)
        - Economic modifiers (booms/recessions)
        - Random variation (±10%)
        """
        if logs is None:
            logs = []
            
        # Get product
        result = await self.db.execute(
            select(Product).where(Product.id == product_id)
        )
        product = result.scalar_one()
        
        # Base demand with small random variation
        random_variation = random.uniform(0.9, 1.1)
        base_demand = self.base_demand * random_variation
        
        # Apply market event modifiers if engine provided
        if events_engine:
            final_demand, modifiers = await events_engine.apply_demand_modifiers(
                base_demand, 
                product.name
            )
            
            # Log demand calculation breakdown
            logs.append(f"    📊 Base Demand: {int(base_demand)} units")
            
            if modifiers['seasonal'] != 1.0:
                season = events_engine.get_season_name()
                modifier_pct = int((modifiers['seasonal'] - 1) * 100)
                sign = "+" if modifier_pct > 0 else ""
                logs.append(f"    🌸 Seasonal Modifier ({season}): ×{modifiers['seasonal']:.2f} ({sign}{modifier_pct}%)")
            
            if modifiers['economic'] != 1.0:
                modifier_pct = int((modifiers['economic'] - 1) * 100)
                sign = "+" if modifier_pct > 0 else ""
                econ_emoji = "💹" if modifiers['economic'] > 1.0 else "📉"
                logs.append(f"    {econ_emoji} Economic Modifier: ×{modifiers['economic']:.2f} ({sign}{modifier_pct}%)")
            
            return final_demand
        else:
            # Fallback: original behavior
            return base_demand
    
    async def distribute_sales(
        self, 
        product_id: int, 
        total_demand: float
    ) -> Dict[int, float]:
        """
        Distribute sales among companies based on pricing.
        
        Uses inverse price weighting:
        - Lower price = higher market share
        - Companies with no inventory get 0 sales
        
        Returns:
            Dict mapping company_id to units_sold
        """
        # Get all companies selling this product
        result = await self.db.execute(
            select(CompanyProduct)
            .where(CompanyProduct.product_id == product_id)
            .where(CompanyProduct.price > 0)  # Only active sellers
        )
        company_products = result.scalars().all()
        
        if not company_products:
            return {}
        
        # Calculate market shares using inverse price weighting
        # Lower price = higher weight
        total_weight = sum(1 / cp.price for cp in company_products)
        
        sales_distribution = {}
        for cp in company_products:
            # Market share = (1 / cp.price) / sum(1/all_prices)
            market_share = (1 / cp.price) / total_weight
            
            # Apply price elasticity
            # If price is much higher than average, reduce demand
            avg_price = sum(cp2.price for cp2 in company_products) / len(company_products)
            price_factor = 1 - ((cp.price - avg_price) / avg_price) * self.price_elasticity
            price_factor = max(0.1, min(1.5, price_factor))  # Clamp between 0.1 and 1.5
            
            # Calculate units sold
            units_sold = total_demand * market_share * price_factor
            sales_distribution[cp.company_id] = max(0, units_sold)
        
        return sales_distribution
    
    async def process_product_sales(
        self,
        product_id: int,
        sales_distribution: Dict[int, int],
        company_prices: Dict[int, float],
        month: int,
        year: int,
        db: AsyncSession,
        logs: List[str] = None
    ):
        """Process sales for a product across all companies."""
        from app.models import InventoryItem, CompanyProduct, MarketHistory
        from core.accounting import AccountingEngine
        
        if logs is None:
            logs = []
        
        for company_id, demand_units_float in sales_distribution.items():
            demand_units = int(demand_units_float)
            if demand_units == 0:
                continue
            
            # Get inventory with lock
            result = await db.execute(
                select(InventoryItem)
                .where(InventoryItem.company_id == company_id)
                .where(InventoryItem.product_id == product_id)
                .with_for_update()
            )
            inv_item = result.scalar_one_or_none()
            
            units_sold = demand_units
            if not inv_item or inv_item.quantity < units_sold:
                # Not enough inventory
                actual_sold = inv_item.quantity if inv_item else 0
                msg = f"        ⚠️  Insufficient inventory! Wanted {units_sold}, only had {actual_sold}"
                print(msg)
                logs.append(msg)
                units_sold = actual_sold
            
            # Calculate revenue and COGS using INTEGER units
            price = company_prices[company_id]
            revenue = units_sold * price
            
            # Record Market History
            history_entry = MarketHistory(
                company_id=company_id,
                product_id=product_id,
                month=month,
                year=year,
                price=price,
                units_sold=units_sold,
                revenue=revenue,
                demand_captured=demand_units
            )
            db.add(history_entry)

            if units_sold == 0:
                continue

            cogs = units_sold * inv_item.wac
            
            msg_revenue = f"        💵 Revenue: {units_sold} × ${price:.2f} = ${revenue:,.2f}"
            msg_cogs = f"        📊 COGS: {units_sold} × ${inv_item.wac:.2f} = ${cogs:,.2f}"
            msg_profit = f"        💰 Gross Profit: ${revenue - cogs:,.2f}"
            
            print(msg_revenue)
            print(msg_cogs)
            print(msg_profit)
            logs.append(msg_revenue)
            logs.append(msg_cogs)
            logs.append(msg_profit)
            
            # Update inventory
            old_qty = inv_item.quantity
            inv_item.quantity -= units_sold
            msg_inv = f"        📦 Inventory: {old_qty} → {inv_item.quantity} units"
            print(msg_inv)
            logs.append(msg_inv)
            
            # Update CompanyProduct stats
            result = await db.execute(
                select(CompanyProduct)
                .where(CompanyProduct.company_id == company_id)
                .where(CompanyProduct.product_id == product_id)
            )
            cp = result.scalar_one()
            cp.units_sold += units_sold
            cp.revenue += revenue
            
            # Record accounting transactions
            accounting = AccountingEngine(db)
            
            # Lookup accounts
            cash_acc = await accounting._get_account_by_code(company_id, "1000")
            revenue_acc = await accounting._get_account_by_code(company_id, "4000")
            inventory_acc = await accounting._get_account_by_code(company_id, "1200")
            cogs_acc = await accounting._get_account_by_code(company_id, "5000")
            
            # Record revenue (Debit: Cash, Credit: Revenue)
            # Only record if we found the accounts
            if cash_acc and revenue_acc:
                await accounting.create_transaction(
                    company_id=company_id,
                    description=f"Sales revenue - {units_sold} units",
                    entries=[
                        (cash_acc.id, revenue),      # Debit Cash
                        (revenue_acc.id, -revenue),  # Credit Revenue
                    ]
                )
                logs.append(f"        💰 Financial Transaction: +${revenue:,.2f} added to Cash (Account {cash_acc.code})")

            # Record COGS (Debit: COGS, Credit: Inventory)
            if cogs_acc and inventory_acc:
                await accounting.create_transaction(
                    company_id=company_id,
                    description=f"Cost of goods sold - {units_sold} units",
                    entries=[
                        (cogs_acc.id, cogs),          # Debit COGS
                        (inventory_acc.id, -cogs),    # Credit Inventory
                    ]
                )
