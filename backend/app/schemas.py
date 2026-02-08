"""
Pydantic schemas for API request/response models
"""

from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# Company schemas
class CompanyBase(BaseModel):
    name: str

class CompanyCreate(CompanyBase):
    is_player: bool = False

class CompanyResponse(CompanyBase):
    id: int
    is_player: bool
    cash: Optional[float] = 0.0
    brand_equity: float = 1.0
    strategy_memory: Optional[dict] = {}
    personality: Optional[str] = "Unknown"
    
    class Config:
        from_attributes = True

# Account schemas
class AccountResponse(BaseModel):
    id: int
    name: str
    code: str
    type: str
    balance: Optional[float] = None
    
    class Config:
        from_attributes = True

# Transaction schemas
class JournalEntryResponse(BaseModel):
    account_id: int
    account_name: Optional[str] = None
    amount: float
    
    class Config:
        from_attributes = True

class TransactionResponse(BaseModel):
    id: int
    date: datetime
    description: str
    entries: List[JournalEntryResponse] = []
    
    class Config:
        from_attributes = True

# Game action schemas
class PurchaseInventoryRequest(BaseModel):
    product_id: int
    quantity: int
    unit_cost: float

class GameStateResponse(BaseModel):
    current_month: int
    current_year: int
    cash_balance: float
    companies: List[CompanyResponse]

class TurnResultResponse(BaseModel):
    month: int
    year: int
    events: List[str]
    logs: List[str] = []

class MarketHistoryResponse(BaseModel):
    id: int
    company_id: int
    product_id: int
    month: int
    year: int
    price: float
    units_sold: int
    revenue: float
    demand_captured: float
    
    class Config:
        from_attributes = True

class FinancialSnapshotResponse(BaseModel):
    id: int
    company_id: int
    month: int
    year: int
    cash_balance: float
    inventory_value: float
    total_assets: float
    total_equity: float
    net_income: Optional[float] = 0.0
    
    class Config:
        from_attributes = True
