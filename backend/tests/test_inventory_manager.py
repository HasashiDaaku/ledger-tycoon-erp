import pytest
from unittest.mock import AsyncMock, MagicMock
from core.inventory_manager import InventoryManager
from app.models import Company, Product, InventoryItem, MarketHistory

@pytest.mark.asyncio
class TestInventoryManager:
    """Tests for InventoryManager class."""

    @pytest.fixture
    def inventory_manager(self, db_session):
        """Create InventoryManager instance."""
        return InventoryManager(db_session)

    async def test_init(self, inventory_manager, db_session):
        """Test InventoryManager initialization."""
        assert inventory_manager.db == db_session
        assert inventory_manager.service_level_z == 1.65

    async def test_forecast_demand_no_history_no_market_avg(self, inventory_manager, db_session, test_company, test_product):
        """Test forecast_demand when there's no history and no market average."""
        # No market history exists at all
        forecast = await inventory_manager.forecast_demand(test_company.id, test_product.id)
        
        # Should return default 300.0
        assert forecast == 300.0

    async def test_forecast_demand_no_history_with_market_avg(self, inventory_manager, db_session, test_company, test_product):
        """Test forecast_demand when there's no company history but market average exists."""
        # Create market history for other companies
        other_company = Company(name="Other Co", is_player=False, cash=10000.0)
        db_session.add(other_company)
        await db_session.commit()
        
        # Add market history for other company
        for i in range(3):
            history = MarketHistory(
                company_id=other_company.id,
                product_id=test_product.id,
                year=2024,
                month=i + 1,
                price=20.0,
                demand_captured=400.0 + i * 50,
                units_sold=int(350.0 + i * 50),
                revenue=7000.0
            )
            db_session.add(history)
        await db_session.commit()
        
        # Forecast for test_company (no history)
        forecast = await inventory_manager.forecast_demand(test_company.id, test_product.id)
        
        # Should return market average: (400 + 450 + 500) / 3 = 450
        assert abs(forecast - 450.0) < 0.01

    async def test_forecast_demand_with_history(self, inventory_manager, db_session, test_company, test_product):
        """Test forecast_demand with historical data using weighted moving average."""
        # Create 3 periods of history
        demands = [300.0, 400.0, 500.0]  # Oldest to newest
        for i, demand in enumerate(demands):
            history = MarketHistory(
                company_id=test_company.id,
                product_id=test_product.id,
                year=2024,
                month=i + 1,
                price=20.0,
                demand_captured=demand,
                units_sold=int(demand * 0.9),
                revenue=demand * 20
            )
            db_session.add(history)
        await db_session.commit()
        
        # Forecast uses weighted average: most recent gets weight 3, then 2, then 1
        # Result is ordered desc, so: [500, 400, 300]
        # Weighted: (500*3 + 400*2 + 300*1) / (3+2+1) = 2600 / 6 = 433.33
        forecast = await inventory_manager.forecast_demand(test_company.id, test_product.id, periods_back=3)
        
        expected = (500 * 3 + 400 * 2 + 300 * 1) / 6
        assert abs(forecast - expected) < 0.01

    async def test_forecast_demand_with_fewer_periods_than_requested(self, inventory_manager, db_session, test_company, test_product):
        """Test forecast_demand when less history exists than periods_back."""
        # Create only 2 periods of history
        for i in range(2):
            history = MarketHistory(
                company_id=test_company.id,
                product_id=test_product.id,
                year=2024,
                month=i + 1,
                price=20.0,
                demand_captured=400.0,
                units_sold=350,
                revenue=7000.0
            )
            db_session.add(history)
        await db_session.commit()
        
        # Request 3 periods but only 2 exist
        forecast = await inventory_manager.forecast_demand(test_company.id, test_product.id, periods_back=3)
        
        # Weights will be [3, 2] for 2 periods
        # (400*3 + 400*2) / 5 = 2000 / 5 = 400
        assert abs(forecast - 400.0) < 0.01

    async def test_forecast_demand_with_events_engine(self, inventory_manager, db_session, test_company, test_product):
        """Test forecast_demand with events_engine applying modifiers."""
        # Create history
        history = MarketHistory(
            company_id=test_company.id,
            product_id=test_product.id,
            year=2024,
            month=1,
            price=20.0,
            demand_captured=400.0,
            units_sold=350,
            revenue=7000.0
        )
        db_session.add(history)
        await db_session.commit()
        
        # Mock events engine
        mock_events = MagicMock()
        mock_events.apply_demand_modifiers = AsyncMock(return_value=(500.0, {"seasonality": 1.25}))
        
        forecast = await inventory_manager.forecast_demand(
            test_company.id, 
            test_product.id,
            events_engine=mock_events
        )
        
        # Should return modified forecast
        assert forecast == 500.0
        mock_events.apply_demand_modifiers.assert_awaited_once()

    async def test_forecast_demand_with_events_engine_no_product_name(self, inventory_manager, db_session, test_company):
        """Test forecast_demand with events_engine when product doesn't exist."""
        # Use non-existent product ID
        mock_events = MagicMock()
        mock_events.apply_demand_modifiers = AsyncMock(return_value=(500.0, {}))
        
        forecast = await inventory_manager.forecast_demand(
            test_company.id, 
            999,  # Non-existent product
            events_engine=mock_events
        )
        
        # Should return default forecast without calling events engine
        assert forecast == 300.0
        mock_events.apply_demand_modifiers.assert_not_awaited()

    async def test_calculate_safety_stock_insufficient_data(self, inventory_manager, db_session, test_company, test_product):
        """Test calculate_safety_stock with less than 2 data points."""
        # Create only 1 period of history
        history = MarketHistory(
            company_id=test_company.id,
            product_id=test_product.id,
            year=2024,
            month=1,
            price=20.0,
            demand_captured=400.0,
            units_sold=350,
            revenue=7000.0
        )
        db_session.add(history)
        await db_session.commit()
        
        safety_stock = await inventory_manager.calculate_safety_stock(test_company.id, test_product.id)
        
        # Should return 20% of forecast (400 * 0.2 = 80)
        assert abs(safety_stock - 80.0) < 0.01

    async def test_calculate_safety_stock_with_sufficient_data(self, inventory_manager, db_session, test_company, test_product):
        """Test calculate_safety_stock with sufficient historical data."""
        # Create 3 periods with varying demand
        demands = [300.0, 400.0, 500.0]
        for i, demand in enumerate(demands):
            history = MarketHistory(
                company_id=test_company.id,
                product_id=test_product.id,
                year=2024,
                month=i + 1,
                price=20.0,
                demand_captured=demand,
                units_sold=int(demand * 0.9),
                revenue=demand * 20
            )
            db_session.add(history)
        await db_session.commit()
        
        safety_stock = await inventory_manager.calculate_safety_stock(test_company.id, test_product.id)
        
        # Calculate expected: z_score (1.65) * stdev([500, 400, 300])
        import statistics
        std_dev = statistics.stdev([500.0, 400.0, 300.0])  # Order is desc from query
        expected = 1.65 * std_dev
        
        assert abs(safety_stock - expected) < 0.01

    async def test_calculate_safety_stock_no_history(self, inventory_manager, db_session, test_company, test_product):
        """Test calculate_safety_stock with no history at all."""
        safety_stock = await inventory_manager.calculate_safety_stock(test_company.id, test_product.id)
        
        # Should return 20% of default forecast (300 * 0.2 = 60)
        assert abs(safety_stock - 60.0) < 0.01

    async def test_get_current_inventory_exists(self, inventory_manager, db_session, test_company, test_product):
        """Test get_current_inventory when inventory exists."""
        # Create inventory item
        inventory = InventoryItem(
            company_id=test_company.id,
            product_id=test_product.id,
            quantity=150
        )
        db_session.add(inventory)
        await db_session.commit()
        
        quantity = await inventory_manager.get_current_inventory(test_company.id, test_product.id)
        
        assert quantity == 150

    async def test_get_current_inventory_not_exists(self, inventory_manager, db_session, test_company, test_product):
        """Test get_current_inventory when no inventory exists."""
        quantity = await inventory_manager.get_current_inventory(test_company.id, test_product.id)
        
        assert quantity == 0

    async def test_get_reorder_quantity_needs_reorder(self, inventory_manager, db_session, test_company, test_product):
        """Test get_reorder_quantity when reorder is needed."""
        # Create history for forecast
        history = MarketHistory(
            company_id=test_company.id,
            product_id=test_product.id,
            year=2024,
            month=1,
            price=20.0,
            demand_captured=400.0,
            units_sold=350,
            revenue=7000.0
        )
        db_session.add(history)
        
        # Create low inventory
        inventory = InventoryItem(
            company_id=test_company.id,
            product_id=test_product.id,
            quantity=50
        )
        db_session.add(inventory)
        await db_session.commit()
        
        reorder_qty = await inventory_manager.get_reorder_quantity(test_company.id, test_product.id)
        
        # Forecast = 400, Safety = 80 (20% of 400), Current = 50
        # Target = 480, Reorder = 480 - 50 = 430
        assert reorder_qty == 430

    async def test_get_reorder_quantity_no_reorder_needed(self, inventory_manager, db_session, test_company, test_product):
        """Test get_reorder_quantity when inventory is sufficient."""
        # Create history
        history = MarketHistory(
            company_id=test_company.id,
            product_id=test_product.id,
            year=2024,
            month=1,
            price=20.0,
            demand_captured=400.0,
            units_sold=350,
            revenue=7000.0
        )
        db_session.add(history)
        
        # Create high inventory
        inventory = InventoryItem(
            company_id=test_company.id,
            product_id=test_product.id,
            quantity=500
        )
        db_session.add(inventory)
        await db_session.commit()
        
        reorder_qty = await inventory_manager.get_reorder_quantity(test_company.id, test_product.id)
        
        # Current (500) > Target (480), so reorder = 0
        assert reorder_qty == 0

    async def test_get_reorder_quantity_with_events_engine(self, inventory_manager, db_session, test_company, test_product):
        """Test get_reorder_quantity with events_engine modifying forecast."""
        # Create history
        history = MarketHistory(
            company_id=test_company.id,
            product_id=test_product.id,
            year=2024,
            month=1,
            price=20.0,
            demand_captured=400.0,
            units_sold=350,
            revenue=7000.0
        )
        db_session.add(history)
        
        # Create inventory
        inventory = InventoryItem(
            company_id=test_company.id,
            product_id=test_product.id,
            quantity=100
        )
        db_session.add(inventory)
        await db_session.commit()
        
        # Mock events engine that increases demand
        mock_events = MagicMock()
        mock_events.apply_demand_modifiers = AsyncMock(return_value=(600.0, {"seasonality": 1.5}))
        
        reorder_qty = await inventory_manager.get_reorder_quantity(
            test_company.id,
            test_product.id,
            events_engine=mock_events
        )
        
        # Modified forecast = 600, Safety = 80, Current = 100
        # Target = 680, Reorder = 680 - 100 = 580
        assert reorder_qty == 580

    async def test_calculate_turnover_with_sales_and_inventory(self, inventory_manager, db_session, test_company, test_product):
        """Test calculate_turnover with sales and inventory data."""
        # Create sales history
        for i in range(3):
            history = MarketHistory(
                company_id=test_company.id,
                product_id=test_product.id,
                year=2024,
                month=i + 1,
                price=20.0,
                demand_captured=400.0,
                units_sold=100,  # 100 units sold per period
                revenue=2000.0
            )
            db_session.add(history)
        
        # Create current inventory
        inventory = InventoryItem(
            company_id=test_company.id,
            product_id=test_product.id,
            quantity=150
        )
        db_session.add(inventory)
        await db_session.commit()
        
        turnover = await inventory_manager.calculate_turnover(test_company.id, test_product.id, periods=3)
        
        # Total sold = 300 (100 * 3), Current inv = 150
        # Turnover = 300 / 150 = 2.0
        assert abs(turnover - 2.0) < 0.01

    async def test_calculate_turnover_no_sales(self, inventory_manager, db_session, test_company, test_product):
        """Test calculate_turnover when there are no sales."""
        # Create inventory but no sales
        inventory = InventoryItem(
            company_id=test_company.id,
            product_id=test_product.id,
            quantity=150
        )
        db_session.add(inventory)
        await db_session.commit()
        
        turnover = await inventory_manager.calculate_turnover(test_company.id, test_product.id)
        
        # No sales, should return None
        assert turnover is None

    async def test_calculate_turnover_no_inventory(self, inventory_manager, db_session, test_company, test_product):
        """Test calculate_turnover when there is no inventory."""
        # Create sales but no inventory
        history = MarketHistory(
            company_id=test_company.id,
            product_id=test_product.id,
            year=2024,
            month=1,
            price=20.0,
            demand_captured=400.0,
            units_sold=100,
            revenue=2000.0
        )
        db_session.add(history)
        await db_session.commit()
        
        turnover = await inventory_manager.calculate_turnover(test_company.id, test_product.id)
        
        # No inventory, should return None
        assert turnover is None

    async def test_calculate_turnover_zero_inventory(self, inventory_manager, db_session, test_company, test_product):
        """Test calculate_turnover when inventory quantity is zero."""
        # Create sales and zero inventory
        history = MarketHistory(
            company_id=test_company.id,
            product_id=test_product.id,
            year=2024,
            month=1,
            price=20.0,
            demand_captured=400.0,
            units_sold=100,
            revenue=2000.0
        )
        db_session.add(history)
        
        inventory = InventoryItem(
            company_id=test_company.id,
            product_id=test_product.id,
            quantity=0
        )
        db_session.add(inventory)
        await db_session.commit()
        
        turnover = await inventory_manager.calculate_turnover(test_company.id, test_product.id)
        
        # Zero inventory, should return None
        assert turnover is None
