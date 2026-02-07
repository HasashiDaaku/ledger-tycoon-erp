"""
API Router for ledger/accounting endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List

from app.database import get_db
from app.schemas import AccountResponse, TransactionResponse, JournalEntryResponse
from app.models import Company, Account, Transaction, JournalEntry
from core.accounting import AccountingEngine
from core.reports import ReportsEngine

router = APIRouter(prefix="/ledger", tags=["ledger"])

@router.get("/accounts", response_model=List[AccountResponse])
async def get_accounts(db: AsyncSession = Depends(get_db)):
    """Get all accounts for the player company with balances."""
    # Get player company
    result = await db.execute(select(Company).where(Company.is_player == True))
    player = result.scalar_one_or_none()
    
    if not player:
        raise HTTPException(status_code=404, detail="Player company not found")
    
    # Get all accounts
    result = await db.execute(
        select(Account).where(Account.company_id == player.id)
    )
    accounts = result.scalars().all()
    
    # Calculate balances
    engine = AccountingEngine(db)
    account_responses = []
    for account in accounts:
        balance = await engine.get_account_balance(account.id)
        acc_dict = {
            "id": account.id,
            "name": account.name,
            "code": account.code,
            "type": account.type.value,
            "balance": balance
        }
        account_responses.append(AccountResponse(**acc_dict))
    
    return account_responses

@router.get("/transactions", response_model=List[TransactionResponse])
async def get_transactions(db: AsyncSession = Depends(get_db)):
    """Get all transactions for the player company."""
    # Get player company
    result = await db.execute(select(Company).where(Company.is_player == True))
    player = result.scalar_one_or_none()
    
    if not player:
        raise HTTPException(status_code=404, detail="Player company not found")
    
    # Get transactions with entries
    result = await db.execute(
        select(Transaction)
        .where(Transaction.company_id == player.id)
        .options(selectinload(Transaction.entries).selectinload(JournalEntry.account))
        .order_by(Transaction.date.desc())
    )
    transactions = result.scalars().all()
    
    # Format response
    trans_responses = []
    for trans in transactions:
        entries = [
            JournalEntryResponse(
                account_id=entry.account_id,
                account_name=entry.account.name,
                amount=entry.amount
            )
            for entry in trans.entries
        ]
        
        trans_responses.append(
            TransactionResponse(
                id=trans.id,
                date=trans.date,
                description=trans.description,
                entries=entries
            )
        )
    
    return trans_responses

@router.get("/balance-sheet")
async def get_balance_sheet(db: AsyncSession = Depends(get_db)):
    """Generate balance sheet for the player company."""
    # Get player company
    result = await db.execute(select(Company).where(Company.is_player == True))
    player = result.scalar_one_or_none()
    
    if not player:
        raise HTTPException(status_code=404, detail="Player company not found")
    
    reports = ReportsEngine(db)
    balance_sheet = await reports.generate_balance_sheet(player.id)
    
    return balance_sheet

@router.get("/income-statement")
async def get_income_statement(db: AsyncSession = Depends(get_db)):
    """Generate income statement for the player company."""
    # Get player company
    result = await db.execute(select(Company).where(Company.is_player == True))
    player = result.scalar_one_or_none()
    
    if not player:
        raise HTTPException(status_code=404, detail="Player company not found")
    
    reports = ReportsEngine(db)
    income_statement = await reports.generate_income_statement(player.id)
    
    return income_statement

@router.get("/metrics")
async def get_key_metrics(db: AsyncSession = Depends(get_db)):
    """Get key financial metrics for the player company."""
    # Get player company
    result = await db.execute(select(Company).where(Company.is_player == True))
    player = result.scalar_one_or_none()
    
    if not player:
        raise HTTPException(status_code=404, detail="Player company not found")
    
    reports = ReportsEngine(db)
    metrics = await reports.get_key_metrics(player.id)
    
    return metrics
