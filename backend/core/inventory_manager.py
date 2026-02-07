"""
Intelligent Inventory Management System

Provides demand forecasting and dynamic inventory purchasing recommendations
to eliminate stockouts and optimize inventory turnover.
"""

from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models import MarketHistory, InventoryItem, Product
import statistics


class InventoryManager:
    """Manages inventory forecasting and purchasing recommendations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        # Service level for safety stock (95% = 1.65 z-score)
        self.service_level_z = 1.65
        
    async def forecast_demand(
        self, 
        company_id: int, 
        product_id: int, 
        periods_back: int = 3
    ) -> float:
        """
        Forecast future demand using weighted moving average of historical sales.
        
        Args:
            company_id: Company to forecast for
            product_id: Product to forecast
            periods_back: Number of historical periods to analyze
            
        Returns:
            Forecasted demand (units)
        """
        # Get historical sales data
        result = await self.db.execute(
            select(MarketHistory)
            .where(MarketHistory.company_id == company_id)
            .where(MarketHistory.product_id == product_id)
            .order_by(MarketHistory.year.desc(), MarketHistory.month.desc())
            .limit(periods_back)
        )
        history = result.scalars().all()
        
        if not history:
            # No history - use market average demand
            avg_result = await self.db.execute(
                select(func.avg(MarketHistory.demand_captured))
                .where(MarketHistory.product_id == product_id)
            )
            avg_demand = avg_result.scalar() or 300.0
            return avg_demand
        
        # Weighted moving average (recent periods weighted higher)
        weights = [3, 2, 1][:len(history)]  # Most recent gets weight 3
        total_weight = sum(weights)
        
        weighted_demand = sum(
            h.demand_captured * weights[i] 
            for i, h in enumerate(history)
        )
        
        forecast = weighted_demand / total_weight
        return forecast
    
    async def calculate_safety_stock(
        self, 
        company_id: int, 
        product_id: int,
        periods_back: int = 3
    ) -> float:
        """
        Calculate safety stock based on demand variability.
        
        Formula: safety_stock = z_score * std_dev(demand)
        
        Returns:
            Safety stock quantity (units)
        """
        # Get historical demand captured
        result = await self.db.execute(
            select(MarketHistory.demand_captured)
            .where(MarketHistory.company_id == company_id)
            .where(MarketHistory.product_id == product_id)
            .order_by(MarketHistory.year.desc(), MarketHistory.month.desc())
            .limit(periods_back)
        )
        demands = [row[0] for row in result.all()]
        
        if len(demands) < 2:
            # Not enough history - use 20% of forecast as buffer
            forecast = await self.forecast_demand(company_id, product_id, periods_back)
            return forecast * 0.2
        
        # Calculate standard deviation
        std_dev = statistics.stdev(demands)
        safety_stock = self.service_level_z * std_dev
        
        return max(safety_stock, 0)
    
    async def get_current_inventory(
        self, 
        company_id: int, 
        product_id: int
    ) -> int:
        """Get current inventory quantity for a product."""
        result = await self.db.execute(
            select(InventoryItem.quantity)
            .where(InventoryItem.company_id == company_id)
            .where(InventoryItem.product_id == product_id)
        )
        quantity = result.scalar()
        return quantity if quantity is not None else 0
    
    async def get_reorder_quantity(
        self, 
        company_id: int, 
        product_id: int
    ) -> int:
        """
        Calculate recommended reorder quantity.
        
        Formula: reorder_qty = forecast + safety_stock - current_inventory
        
        Returns:
            Recommended order quantity (units), minimum 0
        """
        forecast = await self.forecast_demand(company_id, product_id)
        safety_stock = await self.calculate_safety_stock(company_id, product_id)
        current_inv = await self.get_current_inventory(company_id, product_id)
        
        # Target inventory = forecast + safety stock
        target_inventory = forecast + safety_stock
        
        # Reorder quantity = target - current
        reorder_qty = target_inventory - current_inv
        
        # Don't order if we have enough
        return max(int(reorder_qty), 0)
    
    async def calculate_turnover(
        self, 
        company_id: int, 
        product_id: int,
        periods: int = 3
    ) -> Optional[float]:
        """
        Calculate inventory turnover ratio.
        
        Formula: turnover = total_units_sold / avg_inventory
        
        Returns:
            Turnover ratio (times per period), or None if insufficient data
        """
        # Get sales for period
        result = await self.db.execute(
            select(func.sum(MarketHistory.units_sold))
            .where(MarketHistory.company_id == company_id)
            .where(MarketHistory.product_id == product_id)
            .limit(periods)
        )
        total_sold = result.scalar() or 0
        
        if total_sold == 0:
            return None
        
        # Get average inventory (simplified - use current as proxy)
        current_inv = await self.get_current_inventory(company_id, product_id)
        
        if current_inv == 0:
            return None
        
        turnover = total_sold / current_inv
        return turnover
