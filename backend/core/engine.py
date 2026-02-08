"""
Game Engine for Ledger Tycoon

Manages the game loop, turn processing, and game state.
"""

from typing import List, Dict
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models import Company, Product, Warehouse, InventoryItem, CompanyProduct, FinancialSnapshot, JournalEntry, Account, AccountType
from core.accounting import AccountingEngine
from core.market import MarketEngine
import random

class GameEngine:
    """Main game engine that processes turns and manages game state."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.accounting = AccountingEngine(db)
        self.market = MarketEngine(db)
        self.current_month = 1
        self.current_year = 2026
    
    async def load_state(self):
        """Load game state from database."""
        from app.models import GameState
        result = await self.db.execute(select(GameState))
        state = result.scalar_one_or_none()
        if state:
            self.current_month = state.current_month
            self.current_year = state.current_year
        else:
            # Create initial state
            state = GameState(current_month=1, current_year=2026)
            self.db.add(state)
            await self.db.commit()
            self.current_month = 1
            self.current_year = 2026

    async def initialize_game(self) -> Company:
        """Initialize a new game with player company and bot competitors."""
        # Clear all existing game data to allow restarting
        from sqlalchemy import delete
        from app.models import Account, Transaction, JournalEntry, Warehouse, InventoryItem, CompanyProduct, GameState
        
        # Delete in reverse order of dependencies
        await self.db.execute(delete(JournalEntry))
        await self.db.execute(delete(Transaction))
        await self.db.execute(delete(Account))
        await self.db.execute(delete(InventoryItem))
        await self.db.execute(delete(CompanyProduct))
        await self.db.execute(delete(Warehouse))
        await self.db.execute(delete(Product))
        await self.db.execute(delete(Company))
        await self.db.execute(delete(GameState))
        
        # Clear market events
        from app.models import MarketEvent
        await self.db.execute(delete(MarketEvent))
        
        # Reset game state
        state = GameState(current_month=1, current_year=2026)
        self.db.add(state)
        await self.db.commit()
        
        self.current_month = 1
        self.current_year = 2026
        await self.db.commit()
        
        # Create player company
        player_company = Company(
            name="Player Corp",
            is_player=True
        )
        self.db.add(player_company)
        await self.db.flush()
        
        # Initialize chart of accounts
        await self.accounting.initialize_company_accounts(player_company.id)
        
        # Give player starting capital
        await self.accounting.record_cash_investment(player_company.id, 100_000.00)
        
        # Create initial warehouse
        warehouse = Warehouse(
            name="Main Warehouse",
            location="Central",
            capacity=1000,
            monthly_cost=5000.00,
            company_id=player_company.id
        )
        self.db.add(warehouse)
        
        # Create some bot companies
        bot_names = ["TechCorp Inc", "Global Traders", "SmartBiz Ltd"]
        for bot_name in bot_names:
            bot = Company(name=bot_name, is_player=False)
            self.db.add(bot)
            await self.db.flush()
            await self.accounting.initialize_company_accounts(bot.id)
            await self.accounting.record_cash_investment(bot.id, 100_000.00)
        
        # Create some products
        products = [
            ("WIDGET-001", "Basic Widget", 10.00, 20.00),
            ("GADGET-002", "Premium Gadget", 50.00, 100.00),
            ("TOOL-003", "Professional Tool", 30.00, 60.00),
        ]
        
        created_products = []
        for sku, name, base_cost, base_price in products:
            product = Product(
                sku=sku,
                name=name,
                base_cost=base_cost,
                base_price=base_price
            )
            self.db.add(product)
            created_products.append((product, base_cost, base_price))
        
        await self.db.flush()  # Get product IDs
        
        # Create CompanyProduct entries for all companies
        all_companies_result = await self.db.execute(select(Company))
        all_companies = all_companies_result.scalars().all()
        
        for company in all_companies:
            for product, base_cost, base_price in created_products:
                # Set initial price at base_price for all companies
                company_product = CompanyProduct(
                    company_id=company.id,
                    product_id=product.id,
                    price=base_price
                )
                self.db.add(company_product)
        
        await self.db.commit()
        
        # Initialize bot inventory to prevent Month 1 unfair advantage
        from core.inventory_manager import InventoryManager
        from core.bot_ai import BotAI
        
        inv_mgr = InventoryManager(self.db)
        bot_ai = BotAI(self.db)
        
        for company in all_companies:
            if not company.is_player:  # Only for bot companies
                for product, base_cost, base_price in created_products:
                    # Get recommended starting inventory (forecast will use market average since no history)
                    recommended_qty = await inv_mgr.get_reorder_quantity(
                        company_id=company.id,
                        product_id=product.id
                    )
                    
                    # Purchase initial inventory
                    if recommended_qty > 0:
                        await self.purchase_inventory(
                            company_id=company.id,
                            product_id=product.id,
                            quantity=recommended_qty,
                            unit_cost=base_cost
                        )
        
        await self.db.commit()
        return player_company
    
    async def process_turn(self) -> Dict:
        """Process one turn (month) of the game."""
        from sqlalchemy import delete
        from app.models import FinancialSnapshot, MarketHistory

        # Robustness: Clear any existing snapshots/history for this specific turn at the START 
        # to ensure we don't wipe data recorded *during* this turn's processing.
        await self.db.execute(delete(FinancialSnapshot).where(FinancialSnapshot.month == self.current_month, FinancialSnapshot.year == self.current_year))
        await self.db.execute(delete(MarketHistory).where(MarketHistory.month == self.current_month, MarketHistory.year == self.current_year))

        events = []
        logs = []
        
        def log(msg):
            print(msg)
            logs.append(msg)
        
        log("\n" + "="*80)
        log(f"🎮 PROCESSING TURN: {self.current_month}/{self.current_year}")
        log("="*80)
        
        # Initialize market events engine
        from core.market_events import MarketEventsEngine
        events_engine = MarketEventsEngine(self.db, self.current_month, self.current_year)
        
        # Trigger new random events
        new_events = await events_engine.trigger_random_events()
        if new_events:
            log("\n📰 NEW MARKET EVENTS:")
            for event in new_events:
                emoji = "🎉" if "Boom" in event.description else "⚠️" if "Disruption" in event.description else "📉"
                log(f"  {emoji} {event.description}")
        
        # Display active market conditions
        active_events = await events_engine.get_active_events()
        if active_events:
            log("\n📊 ACTIVE MARKET CONDITIONS:")
            for event in active_events:
                duration_text = f"({event.duration_months} month{'s' if event.duration_months > 1 else ''} remaining)"
                log(f"  - {event.description} {duration_text}")
        
        # Log Price Elasticity
        log(f"  ⚡ Market Price Elasticity: {self.market.price_elasticity} (Sensitivity to price changes)")
        
        # Get all companies
        result = await self.db.execute(select(Company))
        companies = result.scalars().all()
        
        log(f"\n📊 Companies in game: {len(companies)}")
        for company in companies:
            cash = await self.accounting.get_company_cash(company.id)
            log(f"  - {company.name} ({'PLAYER' if company.is_player else 'BOT'}): Cash = ${cash:,.2f}")
        
        # Get all products
        result = await self.db.execute(select(Product))
        products = result.scalars().all()
        
        log(f"\n📦 Products: {len(products)}")
        for product in products:
            log(f"  - {product.name} (SKU: {product.sku}): Base Cost=${product.base_cost}, Base Price=${product.base_price}")
        
        # Process sales for each product
        log("\n💰 PROCESSING SALES:")
        for product in products:
            log(f"\n  Product: {product.name}")
            
            # Get all company prices for this product
            result = await self.db.execute(
                select(CompanyProduct, Company)
                .join(Company, Company.id == CompanyProduct.company_id)
                .where(CompanyProduct.product_id == product.id)
            )
            company_products = result.all()
            
            company_prices = {}
            for cp, company in company_products:
                company_prices[company.id] = cp.price
                log(f"    {company.name}: Price=${cp.price:.2f}")
            
            # Calculate Average Market Price
            if company_prices:
                avg_price = sum(company_prices.values()) / len(company_prices)
                log(f"    📊 Average Market Price: ${avg_price:.2f}")
            
            # Calculate market demand
            demand = await self.market.calculate_market_demand(
                product.id, 
                events_engine=events_engine,
                logs=logs
            )
            log(f"    📈 Final Market Demand: {int(demand)} units")
            
            # Distribute sales
            sales_distribution = await self.market.distribute_sales(
                product.id,
                demand
            )
            
            # Calculate Total Market Sales and Share
            total_market_units = sum(int(u) for u in sales_distribution.values())
            
            log(f"    📊 Sales Distribution (Total Market: {total_market_units} units):")
            for company_id, units_sold_float in sales_distribution.items():
                units_sold = int(units_sold_float)
                company = next(c for c in companies if c.id == company_id)
                price = company_prices[company_id]
                revenue = units_sold * price
                
                # Calculate Market Share %
                share_pct = (units_sold / total_market_units * 100) if total_market_units > 0 else 0
                
                log(f"      {company.name}: {units_sold} units ({share_pct:.1f}%) × ${price:.2f} = ${revenue:,.2f}")
            
            # Process sales for each company
            await self.market.process_product_sales(
                product_id=product.id,
                sales_distribution=sales_distribution,
                company_prices=company_prices,
                month=self.current_month,
                year=self.current_year,
                db=self.db,
                logs=logs
            )
        
        # Process warehouse costs
        await self._process_warehouse_costs(logs)
        
        # Bot AI decisions
        log("\n🤖 BOT AI DECISIONS:")
        from core.bot_ai import BotAI
        for company in companies:
            if not company.is_player:
                log(f"\n  {company.name}:")
                bot_ai = BotAI(self.db)
                # 1. Learn from previous turn (before making new decisions)
                await bot_ai._update_strategy_memory(company, logs)
                # 2. Make new decisions based on updated memory
                await bot_ai.make_decisions(company, logs, events_engine=events_engine)  # Pass logs list and events_engine
        
        
        # Record Financial Snapshots (End of Month State)
        await self._record_financial_snapshots(self.current_month, self.current_year, logs)
        
        # Update market event durations (decrement and clean up expired events)
        await events_engine.update_event_durations()

        # Advance time
        self.current_month += 1
        if self.current_month > 12:
            self.current_month = 1
            self.current_year += 1
            events.append(f"🎉 New Year: {self.current_year}")
    
        # Update database state
        from app.models import GameState
        result = await self.db.execute(select(GameState))
        state = result.scalar_one()
        state.current_month = self.current_month
        state.current_year = self.current_year
        
        log(f"\n⏰ Advanced to: {self.current_month}/{self.current_year}")

        # Update brand equity durations (decay)
        await self._apply_brand_decay(logs)
        
        # New: Branding & Competitive Advantage Report
        await self._record_brand_report(logs)
        
        # New: Strategy Evolution Report accounts for learning
        await self._record_strategy_evolution(logs)
        
        await self.db.commit()
        
        # New: Branding & Competitive Advantage Report
        await self._record_brand_report(logs)

        # New: General Ledger Report for Verification
        await self._log_general_ledger(logs)
        
        # Final state
        log("\n📊 FINAL SUMMARY:")
        for company in companies:
            cash = await self.accounting.get_company_cash(company.id)
            log(f"  {company.name}: Cash = ${cash:,.2f}")
        
        log("="*80 + "\n")
        
        return {
            "month": self.current_month,
            "year": self.current_year,
            "events": events,
            "logs": logs
        }
    
    async def _process_warehouse_costs(self, logs: List[str] = None):
        """Deduct monthly warehouse rent from all companies."""
        if logs is not None:
            title = "\n🏭 WAREHOUSE COSTS:"
            print(title)
            logs.append(title)
            
        result = await self.db.execute(select(Warehouse))
        warehouses = result.scalars().all()
        
        for warehouse in warehouses:
            # Get accounts
            cash_acc = await self.accounting._get_account_by_code(warehouse.company_id, "1000")
            rent_exp_acc = await self.accounting._get_account_by_code(warehouse.company_id, "5100")
            
            # Record rent expense
            await self.accounting.create_transaction(
                company_id=warehouse.company_id,
                description=f"Warehouse rent - {warehouse.name}",
                entries=[
                    (rent_exp_acc.id, warehouse.monthly_cost),   # Debit Expense
                    (cash_acc.id, -warehouse.monthly_cost),      # Credit Cash
                ]
            )
            
            if logs is not None:
                log_msg = f"    Build/Rent: {warehouse.name} (-${warehouse.monthly_cost:,.2f})"
                print(log_msg)
                logs.append(log_msg)
    

    
    async def _process_bot_decisions(self):
        """AI decides what bots should do this turn."""
        from core.bot_ai import BotAI
        
        result = await self.db.execute(
            select(Company).where(Company.is_player == False)
        )
        bots = result.scalars().all()
        
        bot_ai = BotAI(self.db)
        for bot in bots:
            await bot_ai.make_decisions(bot)
    
    async def purchase_inventory(
        self, 
        company_id: int, 
        product_id: int, 
        quantity: int, 
        unit_cost: float
    ):
        """
        Purchase inventory for a company.
        
        Records:
        - Debit Inventory
        - Credit Cash (or Credit Accounts Payable if on credit)
        """
        total_cost = quantity * unit_cost
        
        # Get accounts
        inventory_acc = await self.accounting._get_account_by_code(company_id, "1200")
        cash_acc = await self.accounting._get_account_by_code(company_id, "1000")
        
        # Record purchase
        await self.accounting.create_transaction(
            company_id=company_id,
            description=f"Purchase {quantity} units",
            entries=[
                (inventory_acc.id, total_cost),   # Debit Inventory
                (cash_acc.id, -total_cost),       # Credit Cash
            ]
        )
        
        # Update inventory tracking
        # Find or create inventory item
        result = await self.db.execute(
            select(InventoryItem)
            .where(InventoryItem.company_id == company_id)
            .where(InventoryItem.product_id == product_id)
            .with_for_update()
        )
        inv_item = result.scalar_one_or_none()
        
        if inv_item:
            # Update WAC (Weighted Average Cost)
            old_qty = inv_item.quantity
            old_total = old_qty * inv_item.wac
            new_total = old_total + total_cost
            inv_item.quantity += quantity
            inv_item.wac = new_total / inv_item.quantity
            
            # Log WAC calculation
            if old_qty == 0:
                 print(f"    📦 WAC INITIALIZATION (First Stock): {product_id} | Buy: {quantity} @ ${unit_cost:.2f}")
                 print(f"    🧮 Initial WAC: ${inv_item.wac:.2f}")
            else:
                 print(f"    📦 WAC UPDATE: {product_id} | Old WAC: ${old_total/old_qty:.2f} | New Buy: {quantity} @ ${unit_cost:.2f}")
                 print(f"    🧮 New WAC: ${new_total:.2f} / {inv_item.quantity} units = ${inv_item.wac:.2f}")
        else:
            # Create new inventory item
            inv_item = InventoryItem(
                company_id=company_id,
                product_id=product_id,
                quantity=quantity,
                wac=unit_cost,
                warehouse_id=None  # TODO: assign to specific warehouse
            )
            self.db.add(inv_item)
            
            # Log WAC initialization
            print(f"    📦 WAC INITIALIZATION: {product_id} | New Item Created | Buy: {quantity} @ ${unit_cost:.2f}")
            print(f"    🧮 Initial WAC: ${unit_cost:.2f}")
        
        await self.db.commit()

    async def _record_financial_snapshots(self, month: int, year: int, logs: List[str] = None):
        """Record financial state for all companies."""
        from app.models import FinancialSnapshot, InventoryItem, Company, MarketHistory
        
        if logs is not None:
            title = "\n📈 FINANCIAL HEALTH SNAPSHOTS:"
            print(title)
            logs.append(title)
            
        result = await self.db.execute(select(Company))
        companies = result.scalars().all()
        
        for company in companies:
            # Calculate metrics
            cash = await self.accounting.get_company_cash(company.id)
            
            # Calculate inventory value
            inv_value = 0.0
            inv_result = await self.db.execute(
                select(InventoryItem).where(InventoryItem.company_id == company.id)
            )
            items = inv_result.scalars().all()
            for item in items:
                inv_value += item.quantity * item.wac
            
            total_assets = cash + inv_value
            total_equity = total_assets # Simplify: Equity = Assets (assuming 0 liabilities)
            
            # Calculate Cumulative Profit (Net Income)
            net_income = await self.accounting.get_monthly_net_income(company.id)
            
            # --- New: Calculate Profit Margin & ROI ---
            # Need Revenue and Equity/Capital base
            
            # Get Revenue sum (Account type REVENUE or code 4xxx)
            # Direct query for efficiency
            stmt = (
                select(func.sum(JournalEntry.amount))
                .join(Account, Account.id == JournalEntry.account_id)
                .where(Account.company_id == company.id)
                .where(Account.type == "REVENUE") # Or code startswith '4'
            )
            revenue_val = (await self.db.execute(stmt)).scalar() or 0.0
            # Revenue is Credit (negative), convert to + for ratio
            revenue_abs = abs(revenue_val)
            
            profit_margin = 0.0
            if revenue_abs > 0:
                profit_margin = (net_income / revenue_abs) * 100
                
            # ROI = Net Income / Total Investment (Owner's Capital)
            # Fetch Capital Account (3000)
            stmt_cap = (
                 select(func.sum(JournalEntry.amount))
                .join(Account, Account.id == JournalEntry.account_id)
                .where(Account.company_id == company.id)
                .where(Account.code.endswith("-3000"))
            )
            capital_val = (await self.db.execute(stmt_cap)).scalar() or 0.0
            capital_abs = abs(capital_val)
            
            roi = 0.0
            if capital_abs > 0:
                roi = (net_income / capital_abs) * 100
                
            # ------------------------------------------
            
            snapshot = FinancialSnapshot(
                company_id=company.id,
                month=month,
                year=year,
                cash_balance=cash,
                inventory_value=inv_value,
                total_assets=total_assets,
                total_equity=total_equity,
                net_income=net_income
            )
            self.db.add(snapshot)
            
            if logs is not None:
                # Add highlighting for player company to match dashboard focus
                prefix = "  ⭐ " if company.is_player else "    "
                
                # Format with new metrics
                log_msg = (
                    f"{prefix}{company.name}: "
                    f"Assets=${total_assets:,.2f} (Cash=${cash:,.2f}, Inv=${inv_value:,.2f}), "
                    f"Equity=${total_equity:,.2f}, "
                    f"Total Profit=${net_income:,.2f} "
                    f"| Margin: {profit_margin:.1f}% | ROI: {roi:.1f}%"
                )
                print(log_msg)
                logs.append(log_msg)

        # After all snapshots, generate a structured, AI-readable summary block
        if logs is not None:
            summary_header = "\n📊 MONTHLY ANALYTICAL SUMMARY (COPY-PASTE READY):"
            logs.append(summary_header)
            logs.append(f"PERIOD: {month}/{year}")
            logs.append("-" * 50)
            
            # Re-fetch everything for a clean summary
            from app.models import Product, CompanyProduct, MarketHistory
            products_res = await self.db.execute(select(Product))
            all_products = products_res.scalars().all()
            
            for p in all_products:
                # Get history for this product
                history_res = await self.db.execute(
                    select(MarketHistory, Company)
                    .join(Company, Company.id == MarketHistory.company_id)
                    .where(MarketHistory.product_id == p.id, MarketHistory.month == month, MarketHistory.year == year)
                )
                history_data = history_res.all()
                
                # Calculate metrics
                total_p_units = sum(h.units_sold for h, c in history_data)
                total_p_demand = sum(h.demand_captured for h, c in history_data)
                avg_p_price = sum(h.price for h, c in history_data) / len(history_data) if history_data else 0
                
                logs.append(f"PRODUCT: {p.name}")
                logs.append(f"  Avg Price: ${avg_p_price:.2f} | Total Demand: {int(total_p_demand)} | Total Sales: {total_p_units}")
                
                for h, company in history_data:
                    share = (h.units_sold / total_p_units * 100) if total_p_units > 0 else 0
                    logs.append(f"    [{company.name}] Price: {h.price:.2f} | Sales: {h.units_sold} | Share: {share:.1f}%")

            logs.append("-" * 50)
            logs.append("FINANCIAL SNAPSHOT (ALL COMPANIES):")
            for company in companies:
                cash = await self.accounting.get_company_cash(company.id)
                net_income = await self.accounting.get_monthly_net_income(company.id)
                inv_res = await self.db.execute(select(InventoryItem).where(InventoryItem.company_id == company.id))
                inv_val = sum(item.quantity * item.wac for item in inv_res.scalars().all())
                assets = cash + inv_val
                
                # --- Metrics Logic duplicated for summary ---
                stmt_rev = (
                    select(func.sum(JournalEntry.amount))
                    .join(Account, Account.id == JournalEntry.account_id)
                    .where(Account.company_id == company.id)
                    .where(Account.type == "REVENUE")
                )
                revenue_val = (await self.db.execute(stmt_rev)).scalar() or 0.0
                revenue_abs = abs(revenue_val)
                
                stmt_cap = (
                     select(func.sum(JournalEntry.amount))
                    .join(Account, Account.id == JournalEntry.account_id)
                    .where(Account.company_id == company.id)
                    .where(Account.code.endswith("-3000"))
                )
                capital_val = (await self.db.execute(stmt_cap)).scalar() or 0.0
                capital_abs = abs(capital_val)
                
                margin = (net_income / revenue_abs * 100) if revenue_abs > 0 else 0.0
                roi = (net_income / capital_abs * 100) if capital_abs > 0 else 0.0
                # ---------------------------------------------
                
                logs.append(f"  [{company.name}] Cash: {cash:.2f} | Assets: {assets:.2f} | Profit: {net_income:.2f} | Margin: {margin:.1f}% | ROI: {roi:.1f}%")
            logs.append("=" * 50 + "\n")

    async def _apply_brand_decay(self, logs: List[str] = None):
        """Apply monthly decay to brand equity to force continuous investment."""
        result = await self.db.execute(select(Company))
        companies = result.scalars().all()
        
        if logs is not None:
            title = "\n📉 BRAND EQUITY DECAY:"
            print(title)
            logs.append(title)
            
        for company in companies:
            if company.brand_equity > 1.0:
                old_brand = company.brand_equity
                # 10% decay per month, floor at 1.0
                decay_amt = (company.brand_equity - 1.0) * 0.10
                company.brand_equity = max(1.0, company.brand_equity - decay_amt)
                
                if logs is not None:
                    msg = f"    {company.name}: {old_brand:.2f} → {company.brand_equity:.2f} (-{decay_amt:.2f} decay)"
                    print(msg)
                    logs.append(msg)

    async def _record_brand_report(self, logs: List[str]):
        """Special log section for competitive branding analysis."""
        result = await self.db.execute(select(Company).order_by(Company.brand_equity.desc()))
        companies = result.scalars().all()
        
        header = "\n🏆 MARKET COMPETITIVENESS & BRANDING:"
        print(header)
        logs.append(header)
        
        for company in companies:
            # Calculate how much "extra" market share they get per price unit
            # Advantage = (Brand Equity - 1.0) * 100%
            advantage = (company.brand_equity - 1.0) * 100
            msg = f"  - {company.name}: Brand Equity {company.brand_equity:.2f} ({advantage:+.1f}% Market Weight Advantage)"
            print(msg)
            logs.append(msg)

    async def _record_strategy_evolution(self, logs: List[str]):
        """Log how bot strategies are evolving based on memory."""
        result = await self.db.execute(select(Company).where(Company.is_player == False))
        bots = result.scalars().all()
        
        header = "\n🧠 STRATEGY EVOLUTION REPORT:"
        print(header)
        logs.append(header)
        
        from core.bot_ai import BotAI
        bot_ai = BotAI(self.db)
        
        for bot in bots:
            personality = bot_ai._get_personality(bot)
            memory = bot.strategy_memory
            
            if not memory:
                msg = f"  {bot.name} ({personality}): No history yet."
                print(msg)
                logs.append(msg)
                continue
                
            # Summarize memory state
            stockouts = memory.get("stockouts", {})
            total_stockouts = sum(stockouts.values())
            
            regrets = memory.get("pricing_regret", {})
            total_regret = sum(regrets.values())
            
            waste = memory.get("inventory_waste", {})
            total_waste = sum(waste.values())
            
            msg_header = f"  {bot.name} ({personality} strategy):"
            print(msg_header)
            logs.append(msg_header)

            # Log Brand Equity
            log_brand = f"    🌐 Brand Presence: {bot.brand_equity:.2f}x Multiplier"
            print(log_brand)
            logs.append(log_brand)
            
            # Check for problems
            has_problems = False

            if total_stockouts > 0:
                has_problems = True
                # Format stockout details
                details = []
                for pid, count in stockouts.items():
                    if count >= 1.0: # Filter out decayed fractional values
                        # Get product name (inefficient but safe)
                        prod_res = await self.db.execute(select(Product).where(Product.id == int(pid)))
                        prod = prod_res.scalar_one()
                        details.append(f"{prod.name}: {count:.1f}x")
                
                if details:
                    msg_mem = f"    ⚠️  Stockout Memory: {', '.join(details)}"
                    print(msg_mem)
                    logs.append(msg_mem)

            if total_regret > 0:
                has_problems = True
                affected_prods = len(regrets)
                msg_regret = f"    📉 Pricing Errors: Detected in {affected_prods} products ({int(total_regret)} cumulative instances)."
                print(msg_regret)
                logs.append(msg_regret)

            if total_waste > 0:
                has_problems = True
                msg_waste = f"    🗑️  Inventory Waste: Sluggish movement detected in {int(total_waste)} instances."
                print(msg_waste)
                logs.append(msg_waste)
            
            if not has_problems:
                msg_smooth = "    ✅ Operations: Smooth (No stockouts, waste, or pricing errors)"
                print(msg_smooth)
                logs.append(msg_smooth)
            
            # Show active adaptations
            adjustments = await bot_ai._apply_learned_adjustments(bot, personality, logs=[])
            
            safety = adjustments.get("safety_stock_multiplier", 1.0)
            margin = adjustments.get("margin_offset", 0.0)
            marketing = adjustments.get("marketing_budget_offset", 0.0)
            
            if safety != 1.0 or margin != 0.0 or marketing != 0.0:
                drift_msg = f"    🔄 Active Adaptations:"
                if safety != 1.0:
                    drift_msg += f" Safety Stock {int(safety*100)}% |"
                if margin != 0.0:
                    drift_msg += f" Margin {margin:+.0%} |"
                if marketing != 0.0:
                    drift_msg += f" Marketing {marketing:+.0%} |"
                
                print(drift_msg)
                logs.append(drift_msg)
            else:
                msg_stable = "    ✅ Strategy Stable (No active adaptations)"
                print(msg_stable)
                logs.append(msg_stable)

    async def _log_general_ledger(self, logs: List[str]):
        """
        Log the General Ledger (Trial Balance) for AI verification.
        
        This outputs a structured table of all account balances and verifies 
        the fundamental accounting equation (Debits = Credits).
        """
        from app.models import Account
        from sqlalchemy import select
        
        header = "\n📒 GENERAL LEDGER REPORT (Trial Balance):"
        print(header)
        logs.append(header)
        
        # Get all companies
        result = await self.db.execute(select(Company))
        companies = result.scalars().all()
        
        for company in companies:
            # Highlight player company
            prefix = "⭐ " if company.is_player else "  "
            type_label = "(PLAYER)" if company.is_player else "(BOT)"
            company_header = f"{prefix}{company.name} {type_label}"
            print(company_header)
            logs.append(company_header)
            
            # Get accounts
            acc_result = await self.db.execute(
                select(Account).where(Account.company_id == company.id).order_by(Account.code)
            )
            accounts = acc_result.scalars().all()
            
            # Track totals for verification
            total_debits = 0.0
            total_credits = 0.0
            
            # Header row for clarity
            table_header = "    Code | Account Name              | Type      | Balance"
            print(table_header)
            logs.append(table_header)
            logs.append("    " + "-" * 60)
            
            for acc in accounts:
                # Calculate balance dynamically
                balance = await self.accounting.get_account_balance(acc.id)
                
                if balance == 0:
                    continue
                
                # Accounting Logic:
                # Assets & Expenses: Positive Balance = Debit
                # Liabilities, Equity, Revenue: Positive Balance = Credit (stored as negative in DB?)
                # actually get_account_balance returns the sum of amounts.
                # In our system:
                # Debits are positive, Credits are negative.
                # So if balance is positive, it's a Debit balance. If negative, Credit balance.
                
                line = f"    {acc.code:<4} | {acc.name:<25} | {acc.type:<9} | ${balance:,.2f}"
                print(line)
                logs.append(line)
            
            # Verify accounting equation
            # We need to fetch balances for ALL accounts to sum them up correctly
            # (The loop above skips 0 balances, but that's fine for sum)
            net_balance = 0.0
            for acc in accounts:
                 net_balance += await self.accounting.get_account_balance(acc.id)
            
            # Status check
            status_icon = "✅" if abs(net_balance) < 0.01 else "❌"
            status_msg = "BALANCED" if abs(net_balance) < 0.01 else f"IMBALANCED ({net_balance})"
            
            summary = f"    {status_icon} Net Verification: ${net_balance:.2f} -> {status_msg}"
            print(summary)
            logs.append(summary)
            print("    " + "=" * 60)
            logs.append("    " + "=" * 60)
