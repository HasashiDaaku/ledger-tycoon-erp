"""
Core Accounting Logic for Ledger Tycoon

Implements double-entry accounting primitives and business logic.
"""

from typing import List, Dict, Tuple
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models import Account, Transaction, JournalEntry, AccountType, Company

class AccountingEngine:
    """Handles all accounting operations with double-entry bookkeeping."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_transaction(
        self, 
        company_id: int, 
        description: str, 
        entries: List[Tuple[int, float]]  # List of (account_id, amount) tuples
    ) -> Transaction:
        """
        Create a double-entry transaction.
        
        Args:
            company_id: The company making the transaction
            description: Human-readable description
            entries: List of (account_id, amount) where positive = debit, negative = credit
        
        Returns:
            The created Transaction object
        
        Raises:
            ValueError: If entries don't balance (sum != 0)
        """
        # Validate that debits = credits
        total = sum(amount for _, amount in entries)
        if abs(total) > 0.01:  # Allow for floating point errors
            raise ValueError(f"Transaction doesn't balance! Sum: {total}")
        
        # Create transaction
        transaction = Transaction(
            company_id=company_id,
            description=description,
            date=datetime.utcnow()
        )
        self.db.add(transaction)
        await self.db.flush()  # Get the transaction ID
        
        # Create journal entries
        for account_id, amount in entries:
            entry = JournalEntry(
                transaction_id=transaction.id,
                account_id=account_id,
                amount=amount
            )
            self.db.add(entry)
        
        await self.db.commit()
        return transaction

    def format_transaction_log(self, transaction: Transaction, entries: List[Tuple[int, float]]) -> str:
        """Format a transaction for the game log."""
        log = f"    📝 Transaction #{transaction.id}: {transaction.description}\n"
        for account_id, amount in entries:
            # This is a bit tricky because we only have IDs here, not names.
            # We would need to fetch account names or pass them in.
            # For performance, maybe just logging the amount is enough?
            # Or we can do a quick lookup if we have the cache.
            pass
        return log
    
    async def get_account_balance(self, account_id: int) -> float:
        """Calculate the current balance of an account."""
        result = await self.db.execute(
            select(func.sum(JournalEntry.amount))
            .where(JournalEntry.account_id == account_id)
        )
        balance = result.scalar() or 0.0
        return balance
    
    async def get_company_cash(self, company_id: int) -> float:
        """Get the cash balance for a company."""
        try:
            cash_account = await self._get_account_by_code(company_id, "1000")
            return await self.get_account_balance(cash_account.id)
        except Exception:
            return 0.0

    async def get_monthly_net_income(self, company_id: int) -> float:
        """
        Calculate net income for the current session state.
        Sum of all Revenue (4xxx) minus all Expenses (5xxx).
        """
        # Get all accounts for this company
        result = await self.db.execute(
            select(Account).where(Account.company_id == company_id)
        )
        accounts = result.scalars().all()
        
        revenue_total = 0.0
        expense_total = 0.0
        
        for acc in accounts:
            if acc.type == AccountType.REVENUE:
                # Credits are negative in double-entry, but revenue is usually a credit.
                # In this system, entries are (debit positive, credit negative).
                # So we want to subtract the balance to get a positive revenue number.
                revenue_total -= await self.get_account_balance(acc.id)
            elif acc.type == AccountType.EXPENSE:
                # Expenses are debits (positive)
                expense_total += await self.get_account_balance(acc.id)
        
        # Note: This returns lifetime net income currently. 
        # To get "Monthly", we would need to filter by transaction date or clear accounts.
        # For simplicity in this game, we'll use current account balances and the caller 
        # can track deltas if needed.
        return revenue_total - expense_total
    
    async def initialize_company_accounts(self, company_id: int) -> List[Account]:
        """Create standard chart of accounts for a new company."""
        
        standard_accounts = [
            # Assets (1000-1999)
            ("1000", "Cash", AccountType.ASSET),
            ("1100", "Accounts Receivable", AccountType.ASSET),
            ("1200", "Inventory", AccountType.ASSET),
            ("1500", "Warehouses", AccountType.ASSET),
            
            # Liabilities (2000-2999)
            ("2000", "Accounts Payable", AccountType.LIABILITY),
            ("2100", "Loans Payable", AccountType.LIABILITY),
            
            # Equity (3000-3999)
            ("3000", "Owner's Capital", AccountType.EQUITY),
            ("3100", "Retained Earnings", AccountType.EQUITY),
            
            # Revenue (4000-4999)
            ("4000", "Sales Revenue", AccountType.REVENUE),
            
            # Expenses (5000-5999)
            ("5000", "Cost of Goods Sold", AccountType.EXPENSE),
            ("5100", "Rent Expense", AccountType.EXPENSE),
            ("5200", "Marketing Expense", AccountType.EXPENSE),
            ("5300", "Logistics Expense", AccountType.EXPENSE),
        ]
        
        accounts = []
        for code, name, acc_type in standard_accounts:
            account = Account(
                code=f"{company_id}-{code}",  # Prefix with company_id for uniqueness
                name=name,
                type=acc_type,
                company_id=company_id
            )
            self.db.add(account)
            accounts.append(account)
        
        await self.db.commit()
        return accounts
    
    async def record_cash_investment(self, company_id: int, amount: float):
        """Record initial cash investment in company."""
        # Get accounts
        cash_account = await self._get_account_by_code(company_id, "1000")
        capital_account = await self._get_account_by_code(company_id, "3000")
        
        # Debit Cash, Credit Owner's Capital
        await self.create_transaction(
            company_id=company_id,
            description=f"Initial capital investment of ${amount:,.2f}",
            entries=[
                (cash_account.id, amount),      # Debit Cash
                (capital_account.id, -amount),  # Credit Capital
            ]
        )
    
    async def _get_account_by_code(self, company_id: int, code: str) -> Account:
        """Helper to get account by company and code."""
        result = await self.db.execute(
            select(Account)
            .where(Account.company_id == company_id)
            .where(Account.code == f"{company_id}-{code}")
        )
        return result.scalar_one()
