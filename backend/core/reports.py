"""
Financial Reports Generator for Ledger Tycoon

Generates Balance Sheet, Income Statement, and financial metrics.
"""

from typing import Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models import Account, AccountType, JournalEntry
from core.accounting import AccountingEngine

class ReportsEngine:
    """Generates financial reports and metrics."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.accounting = AccountingEngine(db)
    
    async def generate_balance_sheet(self, company_id: int) -> Dict:
        """
        Generate Balance Sheet for a company.
        
        Assets = Liabilities + Equity
        """
        # Get all accounts by type
        result = await self.db.execute(
            select(Account).where(Account.company_id == company_id)
        )
        accounts = result.scalars().all()
        
        assets = []
        liabilities = []
        equity = []
        
        for account in accounts:
            balance = await self.accounting.get_account_balance(account.id)
            
            account_data = {
                "name": account.name,
                "code": account.code,
                "balance": balance
            }
            
            if account.type == AccountType.ASSET:
                assets.append(account_data)
            elif account.type == AccountType.LIABILITY:
                liabilities.append(account_data)
            elif account.type == AccountType.EQUITY:
                equity.append(account_data)
        
        total_assets = sum(a["balance"] for a in assets)
        total_liabilities = sum(abs(l["balance"]) for l in liabilities)
        total_equity = sum(abs(e["balance"]) for e in equity)
        
        return {
            "assets": assets,
            "total_assets": total_assets,
            "liabilities": liabilities,
            "total_liabilities": total_liabilities,
            "equity": equity,
            "total_equity": total_equity,
            "balanced": abs(total_assets - (total_liabilities + total_equity)) < 0.01
        }
    
    async def generate_income_statement(self, company_id: int) -> Dict:
        """
        Generate Income Statement for a company.
        
        Net Income = Revenue - Expenses
        """
        # Get revenue and expense accounts
        result = await self.db.execute(
            select(Account).where(Account.company_id == company_id)
        )
        accounts = result.scalars().all()
        
        revenue_accounts = []
        expense_accounts = []
        
        for account in accounts:
            balance = await self.accounting.get_account_balance(account.id)
            
            account_data = {
                "name": account.name,
                "code": account.code,
                "amount": abs(balance)
            }
            
            if account.type == AccountType.REVENUE:
                revenue_accounts.append(account_data)
            elif account.type == AccountType.EXPENSE:
                expense_accounts.append(account_data)
        
        total_revenue = sum(r["amount"] for r in revenue_accounts)
        total_expenses = sum(e["amount"] for e in expense_accounts)
        net_income = total_revenue - total_expenses
        
        return {
            "revenue": revenue_accounts,
            "total_revenue": total_revenue,
            "expenses": expense_accounts,
            "total_expenses": total_expenses,
            "net_income": net_income,
            "profit_margin": (net_income / total_revenue * 100) if total_revenue > 0 else 0
        }
    
    async def get_key_metrics(self, company_id: int) -> Dict:
        """Calculate key financial metrics."""
        balance_sheet = await self.generate_balance_sheet(company_id)
        income_statement = await self.generate_income_statement(company_id)
        
        cash_balance = await self.accounting.get_company_cash(company_id)
        
        # Calculate metrics
        total_assets = balance_sheet["total_assets"]
        total_liabilities = balance_sheet["total_liabilities"]
        net_income = income_statement["net_income"]
        
        return {
            "cash_balance": cash_balance,
            "net_worth": total_assets - total_liabilities,
            "profit_margin": income_statement["profit_margin"],
            "roi": (net_income / total_assets * 100) if total_assets > 0 else 0,
            "debt_ratio": (total_liabilities / total_assets) if total_assets > 0 else 0
        }
