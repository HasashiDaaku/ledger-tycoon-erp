import pytest
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from core.accounting import AccountingEngine
from app.models import AccountType

@pytest.mark.asyncio
class TestAccountingEngine:

    async def test_initialize_company_accounts(self, db_session: AsyncSession, test_company):
        """Test that a new company gets a standard chart of accounts."""
        engine = AccountingEngine(db_session)
        accounts = await engine.initialize_company_accounts(test_company.id)
        
        assert len(accounts) > 0
        assert any(a.name == "Cash" and a.type == AccountType.ASSET for a in accounts)
        assert any(a.name == "Sales Revenue" and a.type == AccountType.REVENUE for a in accounts)

    async def test_create_transaction_success(self, db_session: AsyncSession, test_company):
        """Test creating a valid balanced transaction."""
        engine = AccountingEngine(db_session)
        await engine.initialize_company_accounts(test_company.id)
        
        # Get accounts
        cash = await engine._get_account_by_code(test_company.id, "1000")
        revenue = await engine._get_account_by_code(test_company.id, "4000")
        
        # Create transaction: Debit Cash $500, Credit Revenue $500
        entries = [
            (cash.id, 500.0),
            (revenue.id, -500.0)
        ]
        
        tx = await engine.create_transaction(test_company.id, "Test Sale", entries)
        
        assert tx.id is not None
        assert tx.description == "Test Sale"
        
        # Verify balances
        cash_balance = await engine.get_account_balance(cash.id)
        # Revenue balance is negative (credit), but get_account_balance sums amounts
        revenue_balance = await engine.get_account_balance(revenue.id)
        
        assert cash_balance == 500.0
        assert revenue_balance == -500.0

    async def test_create_transaction_unbalanced(self, db_session: AsyncSession, test_company):
        """Test that unbalanced transactions raise ValueError."""
        engine = AccountingEngine(db_session)
        await engine.initialize_company_accounts(test_company.id)
        
        cash = await engine._get_account_by_code(test_company.id, "1000")
        
        # Unbalanced entry: Debit Cash $100, no credit
        entries = [
            (cash.id, 100.0)
        ]
        
        with pytest.raises(ValueError, match="Transaction doesn't balance"):
            await engine.create_transaction(test_company.id, "Bad Tx", entries)

    async def test_get_company_cash(self, db_session: AsyncSession, test_company):
        """Test helper method for getting cash balance."""
        engine = AccountingEngine(db_session)
        await engine.initialize_company_accounts(test_company.id)
        
        # Initial cash should be 0 (until investment recorded)
        cash = await engine.get_company_cash(test_company.id)
        assert cash == 0.0
        
        # Record investment
        await engine.record_cash_investment(test_company.id, 50000.0)
        
        cash = await engine.get_company_cash(test_company.id)
        assert cash == 50000.0

    async def test_get_company_cash_error(self, db_session: AsyncSession, test_company):
        """Test validation when accounts don't exist (triggers try/except block)."""
        engine = AccountingEngine(db_session)
        # Note: We do NOT call initialize_company_accounts here
        
        # Should return 0.0 when account lookup fails
        cash = await engine.get_company_cash(test_company.id)
        assert cash == 0.0

    async def test_format_transaction_log(self, db_session: AsyncSession, test_company):
        """Test the string formatting of transaction logs."""
        engine = AccountingEngine(db_session)
        await engine.initialize_company_accounts(test_company.id)
        
        cash = await engine._get_account_by_code(test_company.id, "1000")
        revenue = await engine._get_account_by_code(test_company.id, "4000")
        
        entries = [(cash.id, 100.0), (revenue.id, -100.0)]
        tx = await engine.create_transaction(test_company.id, "Log Test", entries)
        
        log = engine.format_transaction_log(tx, entries)
        
        # Verify basic structure matches f-string in code
        assert f"Transaction #{tx.id}: Log Test" in log
        assert "📝" in log

    async def test_get_monthly_net_income(self, db_session: AsyncSession, test_company):
        """Test calculation of net income (Revenue - Expenses)."""
        engine = AccountingEngine(db_session)
        await engine.initialize_company_accounts(test_company.id)
        
        cash = await engine._get_account_by_code(test_company.id, "1000")
        revenue = await engine._get_account_by_code(test_company.id, "4000")
        expense = await engine._get_account_by_code(test_company.id, "5000") # COGS
        
        # 1. Earn Revenue: $1000
        await engine.create_transaction(
            test_company.id, 
            "Sale", 
            [(cash.id, 1000.0), (revenue.id, -1000.0)]
        )
        
        # 2. Incur Expense: $400
        await engine.create_transaction(
            test_company.id, 
            "Cost", 
            [(expense.id, 400.0), (cash.id, -400.0)]
        )
        
        # Net Income should be 1000 - 400 = 600
        net_income = await engine.get_monthly_net_income(test_company.id)
        assert net_income == 600.0
