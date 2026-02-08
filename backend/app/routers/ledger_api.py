
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.models import Company, Account, Transaction, JournalEntry

router = APIRouter(
    prefix="/ledger",
    tags=["Ledger"]
)

@router.get("/journal-entries/{company_id}")
async def get_journal_entries(
    company_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """
    Fetch journal entries for a company, optionally filtered by date.
    Returns: List of transactions with their journal entries (debits/credits).
    """
    # Verify company exists
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    query = select(Transaction).where(Transaction.company_id == company_id)
    
    if start_date:
        query = query.where(Transaction.date >= start_date)
    if end_date:
        query = query.where(Transaction.date <= end_date)
        
    # Eager load journal entries
    query = query.order_by(desc(Transaction.date), desc(Transaction.id)).limit(limit)
    
    # We need to join with JournalEntry and Account to get full details
    # But for a simple list, let's fetch transactions and let generic relationship loading handle it?
    # No, generic relationships are tricky in async. Let's do an explicit join or selectinload.
    from sqlalchemy.orm import selectinload
    query = query.options(
        selectinload(Transaction.journal_entries).selectinload(JournalEntry.account)
    )
    
    result = await db.execute(query)
    transactions = result.scalars().all()
    
    return transactions

@router.get("/general-ledger/{company_id}")
async def get_general_ledger(
    company_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Fetch the General Ledger summary (Trial Balance style).
    Returns: List of accounts with current debit/credit balances.
    """
    # Verify company exists
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Query to fetch accounts and their calculated balances
    # SQL equivalent: SELECT accounts.*, SUM(journal_entries.amount) FROM accounts LEFT JOIN journal_entries ON ... GROUP BY accounts.id
    stmt = (
        select(Account, func.coalesce(func.sum(JournalEntry.amount), 0.0).label("balance"))
        .outerjoin(JournalEntry, JournalEntry.account_id == Account.id)
        .where(Account.company_id == company_id)
        .group_by(Account.id)
        .order_by(Account.code)
    )
    
    result = await db.execute(stmt)
    rows = result.all()
    
    ledger = []
    
    for account, balance in rows:
        ledger.append({
            "account_id": account.id,
            "code": account.code,
            "name": account.name,
            "type": account.type,
            "company_id": account.company_id,
            "balance": balance
        })
        
    return ledger

@router.get("/metrics")
async def get_metrics(
    db: AsyncSession = Depends(get_db)
):
    """
    Fetch key financial metrics for the player company (ID 1).
    """
    company_id = 1 # Player Company
    
    # helper to get balance sum for a specific account code suffix
    async def get_balance(code_suffix: str):
        result = await db.execute(
            select(func.sum(JournalEntry.amount))
            .join(Account, Account.id == JournalEntry.account_id)
            .where(Account.company_id == company_id)
            .where(Account.code.endswith(f"-{code_suffix}"))
        )
        return result.scalar() or 0.0

    # 1. Cash Balance (Account 1000)
    cash_balance = await get_balance("1000")
    
    # 2. Net Worth (Total Assets - Total Liabilities)
    # Assets: Cash (1000) + AR (1100) + Inventory (1200) + Facilities (1500)
    # Liabilities: AP (2000) + Loans (2100)
    # For now, let's just sum all ASSET accounts and subtract all LIABILITY accounts
    
    # Get all account balances typified
    stmt = (
        select(Account.type, func.sum(JournalEntry.amount))
        .join(Account, Account.id == JournalEntry.account_id)
        .where(Account.company_id == company_id)
        .group_by(Account.type)
    )
    type_balances = (await db.execute(stmt)).all()
    
    assets = 0.0
    liabilities = 0.0
    equity = 0.0
    revenue = 0.0 # Credits are negative
    expenses = 0.0 # Debits are positive
    
    from app.models import AccountType
    
    for acc_type, balance in type_balances:
        if acc_type == AccountType.ASSET:
            assets += balance
        elif acc_type == AccountType.LIABILITY:
            liabilities += balance # Should be negative if credit normal
        elif acc_type == AccountType.EQUITY:
            equity += balance # Should be negative
        elif acc_type == AccountType.REVENUE:
            revenue += balance # Should be negative
        elif acc_type == AccountType.EXPENSE:
            expenses += balance
            
    # Net Worth = Assets - Liabilities (since Liabilities are negative, Assets + Liabilities? No, let's stick to standard accounting eq)
    # In this DB: Debits +, Credits -
    # Assets (Debit +)
    # Liabilities (Credit -)
    # Net Worth = Assets + Liabilities (e.g. 100 + (-50) = 50)
    net_worth = assets + liabilities 
    
    # 3. Profit Margin
    # Net Income = Revenue (negative) + Expenses (positive). 
    # Wait, Revenue is credit (-), Exp is debit (+)
    # Net Income (Profit) should be Credit (-). 
    # e.g. Rev -100, Exp +80 = -20 (Profit of 20)
    net_income_val = revenue + expenses
    # Convert to positive for display if profit
    net_income = -net_income_val
    
    # Revenue is negative, make positive for calculation
    abs_revenue = abs(revenue)
    
    profit_margin = 0.0
    if abs_revenue > 0:
        profit_margin = (net_income / abs_revenue) * 100
        
    # 4. ROI
    # ROI = Net Income / Total Investment
    # Investment = Owner's Capital (Account 3000)
    owners_capital = await get_balance("3000")
    # Capital is Credit (-100,000). Make positive.
    abs_capital = abs(owners_capital)
    
    roi = 0.0
    if abs_capital > 0:
        roi = (net_income / abs_capital) * 100

    return {
        "cash_balance": cash_balance,
        "net_worth": net_worth,
        "profit_margin": profit_margin,
        "roi": roi
    }
