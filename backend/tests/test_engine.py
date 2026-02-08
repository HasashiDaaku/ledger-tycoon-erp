import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession
from core.engine import GameEngine
from app.models import GameState, Company, Product, Warehouse, InventoryItem, CompanyProduct

class TestGameEngine:
    
    @pytest.fixture
    async def engine(self, db_session):
        return GameEngine(db_session)

    async def test_init(self, engine):
        """Test engine initialization."""
        assert engine.current_month == 1
        assert engine.current_year == 2026
        assert engine.accounting is not None
        assert engine.market is not None

    async def test_load_state_existing(self, engine, db_session):
        """Test loading existing game state."""
        # Create existing state
        state = GameState(current_month=5, current_year=2027)
        db_session.add(state)
        await db_session.commit()
        
        await engine.load_state()
        
        assert engine.current_month == 5
        assert engine.current_year == 2027

    async def test_load_state_new(self, engine, db_session):
        """Test loading state when none exists (should create default)."""
        # Ensure no state exists
        await engine.load_state()
        
        assert engine.current_month == 1
        assert engine.current_year == 2026
        
        # Verify it was saved to DB
        from sqlalchemy import select
        result = await db_session.execute(select(GameState))
        state = result.scalar_one()
        assert state.current_month == 1
        assert state.current_year == 2026

    async def test_initialize_game(self, engine, db_session):
        """Test full game initialization."""
        # Mock the expensive sub-calls to speed up test and isolate logic
        # But we still want to verify the DB side effects of create_company etc if possible
        # For 100% coverage we need to let it run through.
        
        # We need to mock AccountingEngine methods called inside initialize_game
        # to avoid side-effects or errors if accounting isn't fully set up in this context,
        # OR we just let it run if it's robust enough.
        # Given we have a real DB session, let's try running it for real first.
        
        # However, initialize_game deletes everything.
        
        player_company = await engine.initialize_game()
        
        assert player_company.name == "Player Corp"
        assert player_company.is_player is True
        
        # Verify Bots created
        from sqlalchemy import select
        result = await db_session.execute(select(Company).where(Company.is_player == False))
        bots = result.scalars().all()
        assert len(bots) == 3
        
        # Verify Products created
        result = await db_session.execute(select(Product))
        products = result.scalars().all()
        assert len(products) == 3
        
        # Verify Warehouse created
        result = await db_session.execute(select(Warehouse))
        warehouse = result.scalar_one()
        assert warehouse.company_id == player_company.id
        
        # Verify CompanyProducts linked
        result = await db_session.execute(select(CompanyProduct))
        cps = result.scalars().all()
        # 4 companies * 3 products = 12 entries
        assert len(cps) == 12

    async def test_purchase_inventory_new_item(self, engine, db_session, test_company, test_product):
        """Test purchasing inventory for the first time."""
        # Mock accounting to avoid transaction complexity if needed, 
        # but let's rely on real DB for coverage.
        # We need to ensure accounts exist.
        await engine.accounting.initialize_company_accounts(test_company.id)
        # Fund the company
        await engine.accounting.record_cash_investment(test_company.id, 50000)
        
        await engine.purchase_inventory(
            company_id=test_company.id,
            product_id=test_product.id,
            quantity=100,
            unit_cost=10.0
        )
        
        # Verify InventoryItem created
        from sqlalchemy import select
        result = await db_session.execute(select(InventoryItem))
        item = result.scalar_one()
        assert item.quantity == 100
        assert item.wac == 10.0
        
        # Log check? The method prints to stdout.

    async def test_purchase_inventory_update_wac(self, engine, db_session, test_company, test_product):
        """Test purchasing inventory, updating WAC, and WAC init logging."""
        await engine.accounting.initialize_company_accounts(test_company.id)
        
        # 1. Initial Purchase (First Stock) -> Covers lines 458-459 (if old_qty == 0)
        # But wait, purchase_inventory creates checks if item exists. 
        # If it doesn't exist, it goes to "Create new inventory item" block (lines 463+).
        # To hit 458-459, item must EXIST but have 0 quantity.
        
        # Create item with 0 quantity
        inv = InventoryItem(
            company_id=test_company.id,
            product_id=test_product.id,
            quantity=0,
            wac=10.0
        )
        db_session.add(inv)
        await db_session.commit()
        
        # Buy 100 @ $20
        await engine.purchase_inventory(
            company_id=test_company.id,
            product_id=test_product.id,
            quantity=100,
            unit_cost=20.0
        )
        # Should trigger "WAC INITIALIZATION (First Stock)" print
        
        await db_session.refresh(inv)
        assert inv.quantity == 100
        assert inv.wac == 20.0

        # 2. Update existing -> Covers lines 461-462
        await engine.purchase_inventory(
            company_id=test_company.id,
            product_id=test_product.id,
            quantity=100,
            unit_cost=10.0
        )
        # 100@20 ($2000) + 100@10 ($1000) = 200@$15
        await db_session.refresh(inv)
        assert inv.quantity == 200
        assert inv.wac == 15.0

    async def test_record_financial_snapshots_logic(
        self, 
        engine, 
        db_session, 
        test_company,
        test_product
    ):
        """Test snapshot creation, ROI/Margin calc, and reports."""
        await engine.accounting.initialize_company_accounts(test_company.id)
        
        # 1. Add Revenue and Capital
        rev_acc = await engine.accounting._get_account_by_code(test_company.id, "4000")
        cap_acc = await engine.accounting._get_account_by_code(test_company.id, "3000")
        cash_acc = await engine.accounting._get_account_by_code(test_company.id, "1000")
        
        await engine.accounting.create_transaction(
            test_company.id, "Revenue", [(cash_acc.id, 1000), (rev_acc.id, -1000)]
        )
        await engine.accounting.create_transaction(
            test_company.id, "Capital", [(cash_acc.id, 5000), (cap_acc.id, -5000)]
        )
        
        # 2. Add Inventory -> Covers line 503 (loop over items)
        inv_item = InventoryItem(
            company_id=test_company.id,
            product_id=test_product.id,
            quantity=10,
            wac=100.0 # $1000 value
        )
        db_session.add(inv_item)
        
        # 3. Add MarketHistory -> Covers lines 604-605 (summary loop)
        from app.models import MarketHistory
        hist = MarketHistory(
            month=1, year=2026,
            company_id=test_company.id,
            product_id=test_product.id,
            price=20.0,
            demand_captured=50,
            units_sold=50,
            revenue=1000.0
        )
        db_session.add(hist)
        await db_session.commit()
        
        logs = []
        await engine._record_financial_snapshots(1, 2026, logs)
        
        from app.models import FinancialSnapshot
        from sqlalchemy import select
        res = await db_session.execute(select(FinancialSnapshot))
        snap = res.scalar_one()
        
        assert snap.inventory_value == 1000.0
        assert snap.total_assets >= 2000.0 # Cash + Inv
        
        log_str = "".join(logs)
        assert "Share: 100.0%" in log_str # Verifies line 605

    async def test_record_strategy_evolution_reports(self, engine, db_session, test_product):
        """Test strategy evolution reporting."""
        from app.models import Company
        
        # Case 1: Bot with NO memory (Covers 698-701)
        bot_new = Company(name="NewBot", is_player=False, strategy_memory={})
        db_session.add(bot_new)
        
        # Case 2: Bot with full memory and drift (Covers 771, 773)
        bot_old = Company(
            name="OldBot", 
            is_player=False, 
            strategy_memory={
                "stockouts": {str(test_product.id): 1.0},
                "pricing_regret": {str(test_product.id): 5.0},
                "inventory_waste": {str(test_product.id): 2.0}
            }
        )
        db_session.add(bot_old)
        await db_session.commit()
        
        logs = []
        with patch("core.bot_ai.BotAI") as MockBotAIHelper:
            mock_helper = MockBotAIHelper.return_value
            mock_helper._get_personality.return_value = "Balanced"
            
            # Mock adjustments to return ALL types
            mock_helper._apply_learned_adjustments = AsyncMock(return_value={
                "safety_stock_multiplier": 1.1,
                "margin_offset": 0.05,        # Covers 771
                "marketing_budget_offset": 0.1 # Covers 773
            })
            
            await engine._record_strategy_evolution(logs)
        
        log_str = "".join(logs)
        assert "NewBot (Balanced): No history yet." in log_str
        assert "Margin +5%" in log_str
        assert "Marketing +10%" in log_str

    async def test_process_warehouse_costs(self, engine, db_session, test_company):
        """Test warehouse cost processing."""
        await engine.accounting.initialize_company_accounts(test_company.id)
        
        wh = Warehouse(
            name="Test WH",
            location="Test",
            capacity=100,
            monthly_cost=500.0,
            company_id=test_company.id
        )
        db_session.add(wh)
        await db_session.commit()
        
        logs = []
        await engine._process_warehouse_costs(logs)
        
        assert any("Test WH (-$500.00)" in log for log in logs)
        
        # Verify transaction (Rent Expense)
        # We can check account balance for 5100 (Rent Expense)
        acc = await engine.accounting._get_account_by_code(test_company.id, "5100")
        bal = await engine.accounting.get_account_balance(acc.id)
        assert bal == 500.0

    async def test_apply_brand_decay(self, engine, db_session, test_company):
        """Test brand equity decay."""
        test_company.brand_equity = 2.0
        await db_session.commit()
        
        logs = []
        await engine._apply_brand_decay(logs)
        await db_session.commit() # Persist changes
        
        await db_session.refresh(test_company)
        # Decay is 10% of (2.0 - 1.0) = 0.1
        # New value = 1.9
        assert abs(test_company.brand_equity - 1.9) < 0.001
        assert "Decay" in "".join(logs) or "decay" in "".join(logs)


    async def test_log_general_ledger(self, engine, db_session, test_company):
        """Test general ledger report generation with data."""
        await engine.accounting.initialize_company_accounts(test_company.id)
        
        # Create a transaction to ensure non-zero balances
        cash_acc = await engine.accounting._get_account_by_code(test_company.id, "1000")
        capital_acc = await engine.accounting._get_account_by_code(test_company.id, "3000")
        
        await engine.accounting.create_transaction(
            test_company.id, "Invest", [(cash_acc.id, 1000), (capital_acc.id, -1000)]
        )
        
        logs = []
        await engine._log_general_ledger(logs)
        log_str = "".join(logs)
        assert "GENERAL LEDGER REPORT" in log_str
        assert "BALANCED" in log_str
        assert "1000" in log_str # Cash account code
        assert "$1,000.00" in log_str

    async def test_record_brand_report(self, engine, db_session, test_company):
        """Test brand report."""
        logs = []
        await engine._record_brand_report(logs)
        assert "MARKET COMPETITIVENESS" in "".join(logs)

    async def test_process_turn_new_year(self, engine, db_session, test_company, test_product, test_company_product):
        """Test year rollover."""
        engine.current_month = 12
        engine.current_year = 2026
        
        # Mock heavy subsystems
        with patch("core.bot_ai.BotAI"), patch("core.market_events.MarketEventsEngine") as MockEvents:
            MockEvents.return_value.trigger_random_events = AsyncMock(return_value=[])
            MockEvents.return_value.get_active_events = AsyncMock(return_value=[])
            MockEvents.return_value.update_event_durations = AsyncMock()
            
            engine.market.calculate_market_demand = AsyncMock(return_value=100)
            engine.market.distribute_sales = AsyncMock(return_value={test_company.id: 100})
            engine.market.process_product_sales = AsyncMock()
            
            await engine.load_state()
            
            # Force year end
            engine.current_month = 12
            engine.current_year = 2026
            
            result = await engine.process_turn()
            
        assert result["month"] == 1
        assert result["year"] == 2027
        assert "New Year: 2027" in result["events"][0]

    async def test_process_bot_decisions_standalone(self, engine, db_session):
        """Test the standalone _process_bot_decisions method."""
        from app.models import Company
        bot = Company(name="BotStandalone", is_player=False)
        db_session.add(bot)
        await db_session.commit()
        
        with patch("core.bot_ai.BotAI") as MockBotAI:
            mock_ai = MockBotAI.return_value
            mock_ai.make_decisions = AsyncMock()
            
            await engine._process_bot_decisions()
            
            assert mock_ai.make_decisions.called

    @patch("core.market_events.MarketEventsEngine")
    @patch("core.bot_ai.BotAI")
    async def test_process_turn_full_mocked(
        self, 
        MockBotAI, 
        MockMarketEventsEngine, 
        engine, 
        db_session, 
        test_company, 
        test_product, 
        test_company_product
    ):
        """
        Test the main game loop with mocks for heavy sub-systems.
        Verifies the orchestration logic.
        """
        # ... (setup mocks) ...
        # Mock MarketEventsEngine instance
        mock_events_engine = MockMarketEventsEngine.return_value
        mock_events_engine.trigger_random_events = AsyncMock(return_value=[])
        mock_events_engine.get_active_events = AsyncMock(return_value=[])
        mock_events_engine.update_event_durations = AsyncMock()
        
        # Mock BotAI instance
        mock_bot_ai = MockBotAI.return_value
        mock_bot_ai._update_strategy_memory = AsyncMock()
        mock_bot_ai.make_decisions = AsyncMock()
        mock_bot_ai._apply_learned_adjustments = AsyncMock(return_value={}) # For verify
        
        # Mock Engine's internal MarketEngine
        engine.market.calculate_market_demand = AsyncMock(return_value=100.0)
        engine.market.distribute_sales = AsyncMock(return_value={test_company.id: 100})
        engine.market.process_product_sales = AsyncMock()
        engine.market.price_elasticity = 1.0 
        
        # Ensure GameState exists
        await engine.load_state()

        await engine.accounting.initialize_company_accounts(test_company.id)
        
        # Add a bot to verify BotAI execution
        from app.models import Company
        bot = Company(name="Bot Corp", is_player=False, brand_equity=1.0)
        db_session.add(bot)
        await db_session.commit()
        
        # Run process_turn
        result = await engine.process_turn()
        
        # Verifications
        assert result["month"] == 2 
        
        mock_events_engine.trigger_random_events.assert_awaited_once()
        engine.market.calculate_market_demand.assert_awaited()
        engine.market.distribute_sales.assert_awaited_with(test_product.id, 100.0)
        engine.market.process_product_sales.assert_awaited()
        
        # Check BotAI was instantiated and called
        assert MockBotAI.called
        # We can't easily check instance calls because new instance per loop in engine code:
        # bot_ai = BotAI(self.db)
        # But we can check if the mocked class was called to create instances.


    @patch("core.market_events.MarketEventsEngine")
    async def test_process_turn_event_logging(self, MockEvents, engine, db_session):
        """Test new event logging in process_turn."""
        mock_ev = MockEvents.return_value
        from app.models import MarketEvent
        event = MarketEvent(description="Economic Boom", duration_months=3)
        mock_ev.trigger_random_events = AsyncMock(return_value=[event])
        mock_ev.get_active_events = AsyncMock(return_value=[event])
        mock_ev.update_event_durations = AsyncMock()
        
        # Mock market
        engine.market.calculate_market_demand = AsyncMock(return_value=0)
        engine.market.distribute_sales = AsyncMock(return_value={})
        engine.market.process_product_sales = AsyncMock()
        
        await engine.load_state()

        # Mock BotAI to avoid errors during bot loop if any bots exist
        with patch("core.bot_ai.BotAI"):
             result = await engine.process_turn()
        
        logs = result["logs"]
        log_str = "".join(logs)
        assert "Economic Boom" in log_str
        assert "ACTIVE MARKET CONDITIONS" in log_str
