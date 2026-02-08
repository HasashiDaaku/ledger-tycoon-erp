import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from core.bot_ai import BotAI, BotPersonality
from app.models import Company, Product, InventoryItem, MarketHistory, CompanyProduct

@pytest.mark.asyncio
class TestBotAI:

    @pytest.fixture
    def bot_ai(self, db_session):
        return BotAI(db_session)

    def test_get_personality(self, bot_ai):
        """Test deterministic personality assignment."""
        c1 = Company(id=1, name="C1", is_player=False)
        c2 = Company(id=2, name="C2", is_player=False)
        c3 = Company(id=3, name="C3", is_player=False)
        
        # 1 % 3 = 1 -> PREMIUM
        # 2 % 3 = 2 -> BALANCED
        # 3 % 3 = 0 -> AGGRESSIVE
        # Based on: personalities = [AGGRESSIVE, PREMIUM, BALANCED]
        # index 0, 1, 2
        
        assert bot_ai._get_personality(c3) == BotPersonality.AGGRESSIVE
        assert bot_ai._get_personality(c1) == BotPersonality.PREMIUM
        assert bot_ai._get_personality(c2) == BotPersonality.BALANCED

    async def test_calculate_inventory_cost(self, bot_ai, db_session, test_company, test_product):
        """Test WAC calculation."""
        # 1. No inventory -> Base Cost
        cost = await bot_ai._calculate_inventory_cost(test_company.id, test_product.id)
        assert cost == test_product.base_cost
        
        # 2. Add inventory
        inv = InventoryItem(
            company_id=test_company.id,
            product_id=test_product.id,
            quantity=100,
            wac=20.0
        )
        db_session.add(inv)
        await db_session.commit()
        
        cost = await bot_ai._calculate_inventory_cost(test_company.id, test_product.id)
        assert cost == 20.0
        
        # 3. Add second batch (different row? mostly 1 row per product per company, but code sums list)
        # If code sums list, let's test that logic
        inv2 = InventoryItem(
            company_id=test_company.id,
            product_id=test_product.id,
            quantity=100,
            wac=40.0
        )
        db_session.add(inv2)
        await db_session.commit()
        
        # Total value = 100*20 + 100*40 = 2000 + 4000 = 6000
        # Total qty = 200
        # Avg = 30
        cost = await bot_ai._calculate_inventory_cost(test_company.id, test_product.id)
        assert cost == 30.0

    async def test_evaluate_purchase_viability(self, bot_ai):
        """Test purchase logic based on margin analysis."""
        product = Product(base_price=100.0, name="Test")
        logs = []
        
        # Case 1: Profitable
        # Cost 50, Target Margin 0.2 -> Breakeven 60. Market 100.
        # Gap: 60 vs 100 = -40%. Safe.
        buy, mult, reason = await bot_ai._evaluate_purchase_viability(
            product, 50.0, 0.2, logs
        )
        assert buy is True
        assert mult == 1.0
        assert "profitable" in reason
        
        # Case 2: Moderate Risk (0-10% above market)
        # Cost 90, Target Margin 0.2 -> Breakeven 108. Market 100.
        # Gap: +8%.
        buy, mult, reason = await bot_ai._evaluate_purchase_viability(
            product, 90.0, 0.2, logs
        )
        assert buy is True
        assert mult == 0.5
        assert "reducing purchase by 50%" in reason

        # Case 3: Low Viability (10-20% above market)
        # Cost 95, Margin 0.2 -> Breakeven 114. Gap +14%.
        buy, mult, reason = await bot_ai._evaluate_purchase_viability(
            product, 95.0, 0.2, logs
        )
        assert buy is True
        assert mult == 0.3
        assert "reducing purchase by 70%" in reason

        # Case 4: Critical (>20% above market)
        # Cost 110, Margin 0.2 -> Breakeven 132. Gap +32%.
        buy, mult, reason = await bot_ai._evaluate_purchase_viability(
            product, 110.0, 0.2, logs
        )
        assert buy is False
        assert mult == 0.0
        assert "guarantee major losses" in reason

    async def test_apply_learned_adjustments(self, bot_ai):
        """Test strategy adjustments based on memory."""
        c = Company(id=1, name="Bot", is_player=False)
        logs = []
        
        # 1. No memory
        adj = await bot_ai._apply_learned_adjustments(c, "balanced", logs)
        assert adj == {}
        
        # 2. Stockouts -> Increased Safety Stock
        c.strategy_memory = {
            "stockouts": {"1": 5.0, "2": 2.0}, # Total 7
            "adaptations": []
        }
        adj = await bot_ai._apply_learned_adjustments(c, "balanced", logs)
        # 7 * 0.10 = +0.70 safety stock = 1.7
        assert abs(adj["safety_stock_multiplier"] - 1.7) < 0.001
        
        # 3. Aggressive Bot Failing -> Reduced Marketing
        adj = await bot_ai._apply_learned_adjustments(c, BotPersonality.AGGRESSIVE, logs)
        assert adj["marketing_budget_offset"] == -0.02

    async def test_update_strategy_memory(self, bot_ai, db_session, test_company, test_product):
        """Test memory updates for stockouts, waste, regret."""
        logs = []
        
        # Setup Product
        # Create inventory item with 0 quantity (Stockout)
        inv = InventoryItem(
            company_id=test_company.id,
            product_id=test_product.id,
            quantity=0
        )
        db_session.add(inv)
        await db_session.commit()
        
        # 1. Test Stockout Detection
        # Logic: Detects stockout (+1) then Decays (-0.1) -> Net 0.9
        await bot_ai._update_strategy_memory(test_company, logs)
        assert abs(test_company.strategy_memory["stockouts"][str(test_product.id)] - 0.9) < 0.001
        assert "First stockout" in "".join(logs)
        
        # 2. Test Inventory Waste (High stock, low sales)
        # Update Inv to 100
        inv.quantity = 100
        await db_session.commit()
        
        # Create History: 1 sale
        mh = MarketHistory(
            company_id=test_company.id,
            product_id=test_product.id,
            units_sold=1, # 1% of 100 -> Waste
            price=10.0,
            revenue=10.0,
            month=1, year=2026,
            demand_captured=10
        )
        db_session.add(mh)
        await db_session.commit()
        
        logs = []
        # Pre-set waste count to 2 to trigger log
        test_company.strategy_memory["inventory_waste"] = {str(test_product.id): 2}
        
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(test_company, "strategy_memory")
        await db_session.commit()

        await bot_ai._update_strategy_memory(test_company, logs)
        
        assert test_company.strategy_memory["inventory_waste"][str(test_product.id)] == 3
        # Logic hits waste branch lines 158-167
        assert "Inventory Waste" in "".join(logs)
        
        # 3. Test Pricing Regret (High price, low sell-through)
        # Price 20 (Avg 10). Sell through 1/101 < 20%.
        mh.units_sold = 1
        mh.price = 20.0
        await db_session.commit()
        
        # Add a competitor history to lower average
        mh2 = MarketHistory(
            company_id=999,
            product_id=test_product.id,
            units_sold=100,
            price=10.0, # Competitor cheap
            revenue=1000.0,
            month=1, year=2026
        )
        db_session.add(mh2)
        await db_session.commit()
        
        # Pre-set regret to 2.1 to trigger log (>2)
        test_company.strategy_memory["pricing_regret"] = {str(test_product.id): 2.1}
        flag_modified(test_company, "strategy_memory")
        
        logs = []
        await bot_ai._update_strategy_memory(test_company, logs)
        
        # Logic hits regret branch lines 190-197
        assert test_company.strategy_memory["pricing_regret"][str(test_product.id)] == 3.1
        assert "Pricing Regret" in "".join(logs)
        
        # 4. Test Decay (lines 205-207)
        # Stockouts should decay by 0.1 every time _update is called.
        # Called in Step 1 (stockout): 1.0 -> 0.9
        # Called in Step 2 (waste): 0.9 -> 0.8
        # Called in Step 3 (regret): 0.8 -> 0.7
        # So expected value is 0.7
        assert abs(test_company.strategy_memory["stockouts"][str(test_product.id)] - 0.7) < 0.001

    async def test_update_strategy_memory_healing(self, bot_ai, db_session, test_company, test_product):
        """Test healing of regret and waste when conditions improve."""
        # 1. Healing Waste (Sold > 10%)
        # Inv 100. Sold 20.
        inv_item = InventoryItem(company_id=test_company.id, product_id=test_product.id, quantity=100)
        db_session.add(inv_item)
        
        hist = MarketHistory(
            company_id=test_company.id, product_id=test_product.id, 
            units_sold=20, price=10.0, month=1, year=2026
        )
        db_session.add(hist)
        
        test_company.strategy_memory = {
            "inventory_waste": {str(test_product.id): 5},
            "pricing_regret": {str(test_product.id): 5.0},
            "stockouts": {}
        }
        await db_session.commit()
        
        # Step 1: Run update.
        # Waste heals (Sold 20 > 10). -> 0.
        # Regret: Price 10. Avg 10 (self). Gap 0. Competitive.
        # Regret heals (-0.5). 5.0 -> 4.5.
        await bot_ai._update_strategy_memory(test_company, [])
        assert test_company.strategy_memory["inventory_waste"][str(test_product.id)] == 0
        assert test_company.strategy_memory["pricing_regret"][str(test_product.id)] == 4.5
        
        # 2. Healing Regret again (Price competitive or high sales)
        # Price 10. Avg 10.
        hist.price = 10.0
        # Add comp to make avg 10 explicitly
        comp_hist = MarketHistory(company_id=999, product_id=test_product.id, units_sold=10, price=10.0, month=1, year=2026)
        db_session.add(comp_hist)
        await db_session.commit()
        
        # Step 2: Run update again.
        # Regret heals again. 4.5 -> 4.0.
        await bot_ai._update_strategy_memory(test_company, [])
        assert test_company.strategy_memory["pricing_regret"][str(test_product.id)] == 4.0

    async def test_calculate_inventory_cost_fallback(self, bot_ai, db_session, test_company, test_product):
        """Test fallback when items exist but total quantity is 0."""
        # Setup: Zero qty item
        inv = InventoryItem(
            company_id=test_company.id,
            product_id=test_product.id,
            quantity=0,
            wac=50.0
        )
        db_session.add(inv)
        await db_session.commit()
        
        cost = await bot_ai._calculate_inventory_cost(test_company.id, test_product.id)
        assert cost == test_product.base_cost

    async def test_manage_branding(self, bot_ai, db_session, test_company):
        """Test branding spend."""
        test_company.brand_equity = 1.0
        
        # Give cash
        await bot_ai.accounting.initialize_company_accounts(test_company.id)
        await bot_ai.accounting.record_cash_investment(test_company.id, 100000.0)
        
        logs = []
        # PREMIUM personality -> 5% budget -> $5000 spend
        await bot_ai._manage_branding(test_company, BotPersonality.PREMIUM, logs)
        
        # Check equity
        # Boost = 5000 / 10000 = 0.5
        assert abs(test_company.brand_equity - 1.5) < 0.01
        # Fixed arrow character match
        assert "Brand Equity: 1.00" in "".join(logs)
        assert "1.50" in "".join(logs)
        
        # Verify transaction
        cash = await bot_ai.accounting.get_company_cash(test_company.id)
        assert cash == 95000.0

    async def test_manage_branding_low_cash(self, bot_ai, db_session, test_company):
        """Test branding skipped if low cash."""
        await bot_ai.accounting.initialize_company_accounts(test_company.id)
        # Cash is 0
        logs = []
        await bot_ai._manage_branding(test_company, BotPersonality.PREMIUM, logs)
        assert len(logs) == 0

        # Cash < 5000
        await bot_ai.accounting.record_cash_investment(test_company.id, 4000.0)
        await bot_ai._manage_branding(test_company, BotPersonality.PREMIUM, logs)
        assert len(logs) == 0

        # Spending < 100
        # Cash 10000. Budget 0.5% (very low). Spend 50.
        # But minimum config is 3%.
        # Let's mock personality config
        with patch.dict(bot_ai.personality_config, {BotPersonality.BALANCED: {"margin": 0.3, "marketing_budget": 0.001}}):
           await bot_ai.accounting.record_cash_investment(test_company.id, 10000.0) # Total 14000
           await bot_ai._manage_branding(test_company, BotPersonality.BALANCED, logs)
           # 14000 * 0.001 = 14. Should skip.
           assert len(logs) == 0

    async def test_adjust_pricing(self, bot_ai, db_session, test_company, test_product):
        """Test pricing adjustment logic."""
        # Setup product link
        cp = CompanyProduct(company_id=test_company.id, product_id=test_product.id, price=10.0)
        db_session.add(cp)
        
        # Initialize accounts so helper can query them if needed (it doesn't, but safely)
        
        # Setup Inventory Cost
        inv = InventoryItem(
            company_id=test_company.id,
            product_id=test_product.id,
            quantity=10,
            wac=50.0 # High cost
        )
        db_session.add(inv)
        await db_session.commit()
        
        logs = []
        # BALANCED -> Margin 0.30
        # Base Cost = 10. WAC = 50.
        # Base Target = 10 * 1.3 = 13.
        # Cost Target = 50 * 1.3 = 65.
        # Should pick 65.
        
        # Fix random seed? or patch random
        with patch("random.uniform", return_value=0.0): # No variance
            await bot_ai._adjust_pricing(test_company, BotPersonality.BALANCED, logs)
            
        await db_session.refresh(cp)
        assert cp.price == 65.0
        assert "FINAL PRICE: $65.00 (cost-aware target)" in "".join(logs)
        
        # Test Minimum Viable Case logic (min margin 5%)
        # Cost 100. Target Margin -0.5 (loss leader??). Min margin is +0.05.
        # We don't support neg margins in config, but let's test the "minimum viable" branch
        # by making base_target very low.
        
        # Let's say WAC is 100. Product base cost is 10.
        # Target margin 0.3.
        # Base target = 13. Cost target = 130.
        # This hits cost target.
        
        # To hit "minimum viable" (line 368):
        # final_price != cost_aware_target AND final_price != base_target
        # This means final_price == minimum_price.
        # minimum_price = avg_cost * 1.05
        # We need cost_aware_target < minimum_price.
        # avg_cost * (1+target) < avg_cost * (1.05)
        # target < 0.05.
        
        with patch.dict(bot_ai.personality_config, {BotPersonality.AGGRESSIVE: {"margin": 0.01, "marketing_budget": 0.1}}):
             with patch("random.uniform", return_value=0.0):
                await bot_ai._adjust_pricing(test_company, BotPersonality.AGGRESSIVE, logs)
                
        # Margin 1%. Min margin 5%.
        # WAC 50. Min Price = 52.5. Target = 50.5.
        # Should pick 52.5.
        await db_session.refresh(cp)
        assert cp.price == 52.5
        assert "(minimum viable)" in "".join(logs)
        
        # Test Base Target Case logic
        # Cost 0/Low. Base 100.
        inv.wac = 0.1
        inv.quantity = 0 # No inv -> uses base cost fallback in calculate_inventory_cost
        # Wait, if qty 0, calc_inv_cost returns base_cost (10.0 from coverage 306/316).
        # We need inventory to be very cheap.
        inv.quantity = 100
        inv.wac = 1.0 # Cheap!
        await db_session.commit()
        
        # Target margin 0.3.
        # Cost-aware: 1.0 * 1.3 = 1.3.
        # Base: 10 * 1.3 = 13.
        # Min: 1.0 * 1.05 = 1.05.
        # Max(13, 1.3) = 13. Max(13, 1.05) = 13.
        # Should pick 13.0 (Base Target)
        
        # Reset logs
        del logs[:]
        with patch("random.uniform", return_value=0.0):
             await bot_ai._adjust_pricing(test_company, BotPersonality.BALANCED, logs)
             
        await db_session.refresh(cp)
        assert cp.price == 13.0
        assert "(base target)" in "".join(logs)


    @patch("core.inventory_manager.InventoryManager")
    @patch("core.engine.GameEngine")
    async def test_manage_inventory_full_flow(self, MockGameEngine, MockInvMgr, bot_ai, db_session, test_company, test_product):
        """Test inventory management purchasing logic."""
        logs = []
        
        # Setup Mocks
        mock_inv = MockInvMgr.return_value
        mock_inv.calculate_safety_stock = AsyncMock(return_value=10)
        mock_inv.get_reorder_quantity = AsyncMock(return_value=100)
        mock_inv.forecast_demand = AsyncMock(return_value=50)
        mock_inv.get_current_inventory = AsyncMock(return_value=0)
        
        mock_engine = MockGameEngine.return_value
        mock_engine.purchase_inventory = AsyncMock()
        
        # Give cash
        await bot_ai.accounting.initialize_company_accounts(test_company.id)
        await bot_ai.accounting.record_cash_investment(test_company.id, 50000.0)
        
        # 1. Normal Purchase
        await bot_ai._manage_inventory(test_company, logs)
        
        # Verify purchase called
        # Base cost 10.0. Qty 100. Cost 1000.
        mock_engine.purchase_inventory.assert_awaited_with(
            company_id=test_company.id,
            product_id=test_product.id,
            quantity=100,
            unit_cost=10.0# Base cost of test_product default? Usually created in conftest
        )
        assert "Purchase complete" in "".join(logs)
        
    @patch("core.inventory_manager.InventoryManager")
    async def test_manage_inventory_low_cash(self, MockInvMgr, bot_ai, db_session, test_company):
        """Test skipping inventory when poor."""
        # Ensure 0 cash
        await bot_ai.accounting.initialize_company_accounts(test_company.id) # 0 cash
        
        logs = []
        await bot_ai._manage_inventory(test_company, logs)
        
        assert "Low cash" in "".join(logs)
        assert not MockInvMgr.called

    @patch("core.inventory_manager.InventoryManager")
    @patch("core.engine.GameEngine")
    async def test_manage_inventory_branches(self, MockGameEngine, MockInvMgr, bot_ai, db_session, test_company, test_product):
        """Test specific branches in manage_inventory."""
        logs = []
        mock_inv = MockInvMgr.return_value
        mock_inv.calculate_safety_stock = AsyncMock(return_value=10)
        mock_inv.get_reorder_quantity = AsyncMock(return_value=100)
        mock_inv.forecast_demand = AsyncMock(return_value=50)
        mock_inv.get_current_inventory = AsyncMock(return_value=0)
        
        mock_engine = MockGameEngine.return_value
        # Ensure it's an AsyncMock for proper access to methods
        mock_engine.purchase_inventory = AsyncMock()
        
        await bot_ai.accounting.initialize_company_accounts(test_company.id)
        
        # 4. Not enough cash for 1 unit (lines 572-576)
        # Move this up to ensure cash resets haven't messed up other steps if they shared state
        # But we create new mocks every time.
        
        # 1. Extra Safety Stock Branch (line 525)
        await bot_ai.accounting.record_cash_investment(test_company.id, 50000.0)
        
        # Mock strategy memory to give multiplier
        test_company.strategy_memory = {"stockouts": {"1": 10.0}, "adaptations": []} # High stockouts
        await db_session.commit()
        # Multiplier will be > 1.0 (test_apply_learned_adjustments handles this logic)
        
        await bot_ai._manage_inventory(test_company, logs)
        
        mock_engine.purchase_inventory.assert_called()
        call_args = mock_engine.purchase_inventory.call_args
        assert call_args.kwargs['quantity'] == 110

        # 2. Event Cost Modifier Branch (lines 537-547)
        mock_events = MagicMock()
        mock_events.get_cost_modifier = AsyncMock(return_value=1.5) # +50% cost
        
        mock_engine.purchase_inventory.reset_mock()
        logs = []
        await bot_ai._manage_inventory(test_company, logs, events_engine=mock_events)
        
        assert "Supply Chain Impact" in "".join(logs)
        assert "+50%" in "".join(logs)
        mock_engine.purchase_inventory.assert_called()
        assert mock_engine.purchase_inventory.call_args.kwargs['unit_cost'] == 15.0 # 10.0 * 1.5

        # 3. Skip Purchase Branch (viability=False) (lines 558-563)
        mock_events.get_cost_modifier = AsyncMock(return_value=10.0) # 10x cost -> Viability Fail
        mock_engine.purchase_inventory.reset_mock()
        logs = []
        
        await bot_ai._manage_inventory(test_company, logs, events_engine=mock_events)
        assert "SKIPPING" in "".join(logs)
        assert not mock_engine.purchase_inventory.called

        # 4. Not enough cash for 1 unit (lines 572-576)
        mock_events.get_cost_modifier = AsyncMock(return_value=10000.0) # Cost 100k
        # Force viability logic to PASS even with high cost, to hit "Not enough cash" block
        # We need to mock _evaluate_purchase_viability since it calls out
        with patch.object(bot_ai, '_evaluate_purchase_viability', return_value=(True, 1.0, "Force Pass")):
             mock_engine.purchase_inventory.reset_mock()
             logs = []
             await bot_ai._manage_inventory(test_company, logs, events_engine=mock_events)
             assert "Not enough cash" in "".join(logs)
             assert not mock_engine.purchase_inventory.called

        # 5. Exception handling (lines 614-617)
        mock_events.get_cost_modifier = AsyncMock(return_value=1.0)
        mock_engine.purchase_inventory.side_effect = Exception("DB Boom")
        logs = []
        await bot_ai._manage_inventory(test_company, logs)
        assert "Purchase failed: DB Boom" in "".join(logs)
        
        # 6. No reorder needed (qty=0) (line 527)
        mock_inv.get_reorder_quantity = AsyncMock(return_value=0)
        # Ensure calculated extra safety is also 0
        mock_inv.calculate_safety_stock = AsyncMock(return_value=0)
        test_company.strategy_memory = {} # Reset memory so no safety boost
        await db_session.commit()
        
        logs = []
        await bot_ai._manage_inventory(test_company, logs)
        assert "Inventory sufficient" in "".join(logs)


    async def test_make_decisions_entry_point(self, bot_ai, db_session, test_company):
        """Test main entry point calls sub-methods."""
        bot_ai._get_personality = MagicMock(return_value="balanced")
        bot_ai._adjust_pricing = AsyncMock()
        bot_ai._manage_inventory = AsyncMock()
        bot_ai._manage_branding = AsyncMock()
        
        await bot_ai.make_decisions(test_company)
        
        bot_ai._adjust_pricing.assert_awaited()
        bot_ai._manage_inventory.assert_awaited()
        bot_ai._manage_branding.assert_awaited()

    async def test_update_strategy_memory_initialization(self, bot_ai, db_session, test_company):
        """Test memory initialization if None."""
        test_company.strategy_memory = None
        await db_session.commit()
        
        await bot_ai._update_strategy_memory(test_company, [])
        assert test_company.strategy_memory is not None
        assert "stockouts" in test_company.strategy_memory

    async def test_update_strategy_memory_repeat_stockout(self, bot_ai, db_session, test_company, test_product):
        """Test logging for repeat stockouts."""
        # Setup: Product has existing memory of stockouts
        pid = str(test_product.id)
        test_company.strategy_memory = {
            "stockouts": {pid: 5.0},
            "adaptations": []
        }
        await db_session.commit()
        
        # Setup: Stockout condition (0 qty)
        inv = InventoryItem(company_id=test_company.id, product_id=test_product.id, quantity=0)
        db_session.add(inv)
        await db_session.commit()
        
        logs = []
        await bot_ai._update_strategy_memory(test_company, logs)
        
        # Should now be 5.9 (previous 5 + 1 - 0.1 decay)
        assert abs(test_company.strategy_memory["stockouts"][pid] - 5.9) < 0.01
        # Check log message
        assert f"Stockout #6 for {test_product.name}" in "".join(logs)
