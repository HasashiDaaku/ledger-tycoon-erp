import pytest
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from core.market import MarketEngine
from app.models import Product, CompanyProduct



@pytest.mark.asyncio
class TestMarketEngine:

    async def test_calculate_market_demand_basics(self, db_session: AsyncSession, test_product):
        """Test basic market demand calculation within expected range."""
        engine = MarketEngine(db_session)
        
        # Base demand is 1000 with +/- 10% random variation
        demand = await engine.calculate_market_demand(test_product.id)
        
        assert 900 <= demand <= 1100

    async def test_distribute_sales_logic(
        self, 
        db_session: AsyncSession, 
        test_company, 
        test_product, 
        test_company_product
    ):
        """Test that sales are distributed to the only active seller."""
        engine = MarketEngine(db_session)
        
        # 1000 units demand
        total_demand = 1000.0
        
        distribution = await engine.distribute_sales(test_product.id, total_demand)
        
        # Only one company, but price elasticity might reduce sales if price is high relative to "average"
        # Since it's the only one, average price == its price, so price factor should be 1.0
        
        assert test_company.id in distribution
        units_sold = distribution[test_company.id]
        
        # Should capture 100% of demand (give or take floating point)
        assert abs(units_sold - total_demand) < 0.1

    async def test_calculate_market_demand_with_events(self, db_session: AsyncSession, test_product):
        """Test demand calculation with a mock events engine."""
        class MockEventsEngine:
            def get_season_name(self):
                return "Summer"
            
            async def apply_demand_modifiers(self, base_demand, product_name):
                # Returns (final_demand, modifiers_dict)
                # Let's say it doubles demand
                return base_demand * 2, {"seasonal": 1.5, "economic": 1.33}

        engine = MarketEngine(db_session)
        logs = []
        demand = await engine.calculate_market_demand(
            test_product.id, 
            events_engine=MockEventsEngine(), 
            logs=logs
        )
        
        # Base is ~1000. Mock doubles it to ~2000
        assert 1800 <= demand <= 2200
        # Check logs for modifiers
        log_str = "".join(logs)
        assert "Seasonal Modifier" in log_str
        assert "Economic Modifier" in log_str

    async def test_distribute_sales_multiple_companies(
        self, 
        db_session: AsyncSession, 
        test_product,
        test_company
    ):
        """Test sales distribution between two companies."""
        from app.models import Company, CompanyProduct
        
        # Create a second company (Bot)
        competitor = Company(name="Competitor Inc", is_player=False, brand_equity=1.0)
        db_session.add(competitor)
        await db_session.commit()
        
        # Link both to product
        # Company 1: Price $20
        cp1 = CompanyProduct(company_id=test_company.id, product_id=test_product.id, price=20.0)
        db_session.add(cp1)
        
        # Competitor: Price $10 (Cheaper -> Should get more sales)
        cp2 = CompanyProduct(company_id=competitor.id, product_id=test_product.id, price=10.0)
        db_session.add(cp2)
        await db_session.commit()
        
        engine = MarketEngine(db_session)
        total_demand = 1000.0
        
        distribution = await engine.distribute_sales(test_product.id, total_demand)
        
        assert len(distribution) == 2
        sales_1 = distribution[test_company.id]
        sales_2 = distribution[competitor.id]
        
        # Competitor has half the price, so should have roughly double the weight (1/10 vs 1/20)
        # Weight 1 = 0.05, Weight 2 = 0.10. Total = 0.15.
        # Share 1 = 33%, Share 2 = 66%
        # Price factor also applies, expanding the gap.
        assert sales_2 > sales_1

    async def test_process_product_sales_full_flow(
        self, 
        db_session: AsyncSession, 
        test_company, 
        test_product, 
        test_company_product
    ):
        """Test the full sales processing flow: Inventory -> Revenue -> Accounting."""
        from app.models import InventoryItem
        from core.accounting import AccountingEngine
        
        # 1. Setup Inventory (100 units @ $10 WAC)
        inv = InventoryItem(
            company_id=test_company.id,
            product_id=test_product.id,
            quantity=100,
            wac=10.0
        )
        db_session.add(inv)
        
        # 2. Setup Accounts (Cash, Revenue, Inventory, COGS)
        acc_engine = AccountingEngine(db_session)
        await acc_engine.initialize_company_accounts(test_company.id)
        
        await db_session.commit()
        
        # 3. Process Sales (Sell 50 units)
        engine = MarketEngine(db_session)
        sales_dist = {test_company.id: 50}
        prices = {test_company.id: 20.0}
        
        logs = []
        await engine.process_product_sales(
            test_product.id, 
            sales_dist, 
            prices, 
            month=1, 
            year=2026, 
            db=db_session, 
            logs=logs
        )
        
        # 4. Verify Inventory Reduced
        await db_session.refresh(inv)
        assert inv.quantity == 50  # 100 - 50
        
        # 5. Verify CompanyProduct updated
        await db_session.refresh(test_company_product)
        assert test_company_product.units_sold == 50
        assert test_company_product.revenue == 1000.0  # 50 * $20
        
        # 6. Verify Log Output
        log_str = "".join(logs)
        assert "Revenue: 50 × $20.00 = $1,000.00" in log_str
        assert "COGS: 50 × $10.00 = $500.00" in log_str
        assert "Gross Profit: $500.00" in log_str
        
        # 7. Verify Accounting Balances
        # Revenue should be 50 * 20 = 1000 (credit)
        # COGS should be 50 * 10 = 500 (debit)
        revenue_acc = await acc_engine._get_account_by_code(test_company.id, "4000")
        revenue_bal = await acc_engine.get_account_balance(revenue_acc.id)
        assert revenue_bal == -1000.0
        
        cogs_acc = await acc_engine._get_account_by_code(test_company.id, "5000")
        cogs_bal = await acc_engine.get_account_balance(cogs_acc.id)
        assert cogs_bal == 500.0

    async def test_process_sales_stockout(
        self, 
        db_session: AsyncSession, 
        test_company, 
        test_product,
        test_company_product
    ):
        """Test sales processing when demand exceeds inventory."""
        from app.models import InventoryItem
        from core.accounting import AccountingEngine
        
        # 1. Setup Accounts (Crucial step missed in previous run)
        acc_engine = AccountingEngine(db_session)
        await acc_engine.initialize_company_accounts(test_company.id)
        
        # 2. Setup Low Inventory (10 units)
        inv = InventoryItem(
            company_id=test_company.id,
            product_id=test_product.id,
            quantity=10,
            wac=10.0
        )
        db_session.add(inv)
        await db_session.commit()
        
        # 3. Process High Demand (Sell 50 units)
        engine = MarketEngine(db_session)
        sales_dist = {test_company.id: 50}
        prices = {test_company.id: 20.0}
        
        logs = []
        await engine.process_product_sales(
            test_product.id, 
            sales_dist, 
            prices, 
            month=1, 
            year=2026, 
            db=db_session, 
            logs=logs
        )
        
        # 4. Verify Inventory Depleted
        await db_session.refresh(inv)
        assert inv.quantity == 0
        
        # 5. Verify Missed Opportunity Log
        log_str = "".join(logs)
        assert "Insufficient inventory" in log_str
        assert "Missed Sales: 40 units" in log_str
        assert "Market Opportunity Lost: 40 units" in log_str

    async def test_process_sales_no_sellers_logic(self, db_session: AsyncSession, test_product):
        """Test distribute_sales when no sellers exist (Line 100 coverage)."""
        engine = MarketEngine(db_session)
        # No company products added
        dist = await engine.distribute_sales(test_product.id, 1000.0)
        assert dist == {}

    async def test_process_sales_defaults(
        self, 
        db_session: AsyncSession, 
        test_company, 
        test_product
    ):
        """Test process_product_sales with default args and zero demand (Line 152, 160)."""
        engine = MarketEngine(db_session)
        
        # Case 1: Call without logs list (Line 152) and with 0 demand (Line 160)
        await engine.process_product_sales(
            test_product.id,
            sales_distribution={test_company.id: 0}, # 0 demand
            company_prices={test_company.id: 20.0},
            month=1,
            year=2026,
            db=db_session
            # logs is None by default
        )
        # Should finish without error and do nothing

    async def test_process_sales_zero_inventory(
        self, 
        db_session: AsyncSession, 
        test_company, 
        test_product
    ):
        """Test sales processing when inventory is 0 (hits continue on line 209)."""
        from core.accounting import AccountingEngine
        
        # 1. Setup Accounts
        acc_engine = AccountingEngine(db_session)
        await acc_engine.initialize_company_accounts(test_company.id)
        
        # 2. No Inventory created (or could create with 0)
        
        # 3. Process Demand
        engine = MarketEngine(db_session)
        # Demand exists, but no inventory
        sales_dist = {test_company.id: 10} 
        prices = {test_company.id: 20.0}
        
        logs = []
        await engine.process_product_sales(
            test_product.id, 
            sales_dist, 
            prices, 
            month=1, 
            year=2026, 
            db=db_session, 
            logs=logs
        )
        
        # Verify log indicates 0 sales / missed opportunity
        log_str = "".join(logs)
        assert "Insufficient inventory" in log_str
        assert "Missed Sales: 10 units" in log_str
        # And ensure no revenue logs
        assert "💵 Revenue:" not in log_str
