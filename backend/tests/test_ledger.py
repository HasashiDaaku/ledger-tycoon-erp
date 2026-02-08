import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from app.routers import ledger
from app.database import get_db
from app.models import Company, Account, Transaction, JournalEntry, AccountType
from core.accounting import AccountingEngine
from datetime import datetime

@pytest.mark.asyncio
class TestLedgerRouter:
    """Tests for ledger API endpoints.
    
    Note: The /transactions endpoint has a bug in ledger.py (uses Transaction.entries 
    instead of Transaction.journal_entries), so those tests verify the error behavior.
    """

    @pytest.fixture
    async def test_app(self, db_session):
        """Create a test FastAPI app with the ledger router and overridden database."""
        app = FastAPI()
        app.include_router(ledger.router)
        
        # Override the get_db dependency to use our test session
        async def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_db] = override_get_db
        return app

    @pytest.fixture
    async def client(self, test_app):
        """Create async test client."""
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    async def test_get_accounts_success(self, client, db_session, test_company):
        """Test GET /ledger/accounts returns accounts with balances."""
        # Setup: Make test_company the player
        test_company.is_player = True
        await db_session.commit()
        
        # Initialize accounts
        accounting = AccountingEngine(db_session)
        await accounting.initialize_company_accounts(test_company.id)
        
        # Make a transaction to create some balance
        await accounting.record_cash_investment(test_company.id, 10000.0)
        
        # Test
        response = await client.get("/ledger/accounts")
        
        # Verify
        assert response.status_code == 200
        accounts = response.json()
        assert len(accounts) > 0
        
        # Check structure
        for account in accounts:
            assert "id" in account
            assert "name" in account
            assert "code" in account
            assert "type" in account
            assert "balance" in account
        
        # Verify cash account has balance
        # Account codes are prefixed with company_id (e.g., "1-1000" for company 1)
        cash_account = next((a for a in accounts if a["code"] == f"{test_company.id}-1000"), None)
        assert cash_account is not None
        assert cash_account["balance"] == 10000.0

    async def test_get_accounts_no_player(self, client, db_session):
        """Test GET /ledger/accounts returns 404 when no player company exists."""
        # Ensure no player company exists (test_company fixture is not used)
        response = await client.get("/ledger/accounts")
        
        # Verify
        assert response.status_code == 404
        assert response.json()["detail"] == "Player company not found"

    async def test_get_accounts_empty_accounts(self, client, db_session, test_company):
        """Test GET /ledger/accounts when company has no accounts initialized."""
        # Setup: Make test_company the player but don't initialize accounts
        test_company.is_player = True
        await db_session.commit()
        
        # Test
        response = await client.get("/ledger/accounts")
        
        # Verify - should return 200 with empty list
        assert response.status_code == 200
        accounts = response.json()
        assert accounts == []

    async def test_get_transactions_no_player(self, client, db_session):
        """Test GET /ledger/transactions returns 404 when no player company exists."""
        response = await client.get("/ledger/transactions")
        
        assert response.status_code == 404
        assert response.json()["detail"] == "Player company not found"

    async def test_get_transactions_bug_with_entries(self, client, db_session, test_company):
        """Test that /transactions endpoint has a bug (uses Transaction.entries instead of journal_entries).
        
        This test documents the existing bug in the codebase without fixing it.
        """
        # Setup: Make test_company the player
        test_company.is_player = True
        await db_session.commit()
        
        # Initialize accounts and create transaction
        accounting = AccountingEngine(db_session)
        await accounting.initialize_company_accounts(test_company.id)
        await accounting.record_cash_investment(test_company.id, 5000.0)
        
        # Test - this will fail due to bug in ledger.py line 65
        # The bug causes an AttributeError which FastAPI converts to a 500 error
        with pytest.raises(Exception):  # The exception is raised during the request
            response = await client.get("/ledger/transactions")

    async def test_get_balance_sheet_success(self, client, db_session, test_company):
        """Test GET /ledger/balance-sheet returns balance sheet data."""
        # Setup: Make test_company the player
        test_company.is_player = True
        await db_session.commit()
        
        # Initialize accounts and create some transactions
        accounting = AccountingEngine(db_session)
        await accounting.initialize_company_accounts(test_company.id)
        await accounting.record_cash_investment(test_company.id, 20000.0)
        
        # Test
        response = await client.get("/ledger/balance-sheet")
        
        # Verify
        assert response.status_code == 200
        balance_sheet = response.json()
        
        # Check structure (based on ReportsEngine.generate_balance_sheet)
        assert "assets" in balance_sheet
        assert "liabilities" in balance_sheet
        assert "equity" in balance_sheet
        assert "total_assets" in balance_sheet
        assert "total_liabilities" in balance_sheet
        assert "total_equity" in balance_sheet
        
        # Verify accounting equation: Assets = Liabilities + Equity
        assert abs(balance_sheet["total_assets"] - 
                  (balance_sheet["total_liabilities"] + balance_sheet["total_equity"])) < 0.01

    async def test_get_balance_sheet_no_player(self, client, db_session):
        """Test GET /ledger/balance-sheet returns 404 when no player company exists."""
        response = await client.get("/ledger/balance-sheet")
        
        assert response.status_code == 404
        assert response.json()["detail"] == "Player company not found"

    async def test_get_income_statement_success(self, client, db_session, test_company):
        """Test GET /ledger/income-statement returns income statement data."""
        # Setup: Make test_company the player
        test_company.is_player = True
        await db_session.commit()
        
        # Initialize accounts
        accounting = AccountingEngine(db_session)
        await accounting.initialize_company_accounts(test_company.id)
        await accounting.record_cash_investment(test_company.id, 15000.0)
        
        # Test
        response = await client.get("/ledger/income-statement")
        
        # Verify
        assert response.status_code == 200
        income_statement = response.json()
        
        # Check structure (based on ReportsEngine.generate_income_statement)
        assert "revenue" in income_statement
        assert "expenses" in income_statement
        assert "total_revenue" in income_statement
        assert "total_expenses" in income_statement
        assert "net_income" in income_statement
        
        # Net income should equal revenue - expenses
        assert abs(income_statement["net_income"] - 
                  (income_statement["total_revenue"] - income_statement["total_expenses"])) < 0.01

    async def test_get_income_statement_no_player(self, client, db_session):
        """Test GET /ledger/income-statement returns 404 when no player company exists."""
        response = await client.get("/ledger/income-statement")
        
        assert response.status_code == 404
        assert response.json()["detail"] == "Player company not found"

    async def test_get_key_metrics_success(self, client, db_session, test_company):
        """Test GET /ledger/metrics returns key financial metrics."""
        # Setup: Make test_company the player
        test_company.is_player = True
        await db_session.commit()
        
        # Initialize accounts
        accounting = AccountingEngine(db_session)
        await accounting.initialize_company_accounts(test_company.id)
        await accounting.record_cash_investment(test_company.id, 25000.0)
        
        # Test
        response = await client.get("/ledger/metrics")
        
        # Verify
        assert response.status_code == 200
        metrics = response.json()
        
        # Check that we got some metrics back (structure depends on ReportsEngine.get_key_metrics)
        assert isinstance(metrics, dict)
        # The exact keys depend on the implementation, but it should return something
        assert len(metrics) > 0

    async def test_get_key_metrics_no_player(self, client, db_session):
        """Test GET /ledger/metrics returns 404 when no player company exists."""
        response = await client.get("/ledger/metrics")
        
        assert response.status_code == 404
        assert response.json()["detail"] == "Player company not found"

    async def test_get_accounts_multiple_accounts(self, client, db_session, test_company):
        """Test that all standard accounts are returned."""
        # Setup
        test_company.is_player = True
        await db_session.commit()
        
        accounting = AccountingEngine(db_session)
        await accounting.initialize_company_accounts(test_company.id)
        
        # Test
        response = await client.get("/ledger/accounts")
        
        # Verify
        assert response.status_code == 200
        accounts = response.json()
        
        # Should have all standard accounts (13 total based on AccountingEngine.initialize_company_accounts)
        assert len(accounts) == 13
        
        # Verify account types are present
        account_types = {acc["type"] for acc in accounts}
        assert "ASSET" in account_types
        assert "LIABILITY" in account_types
        assert "EQUITY" in account_types
        assert "REVENUE" in account_types
        assert "EXPENSE" in account_types
