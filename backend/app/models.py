from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, DateTime, Float, Enum as SQLEnum, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from .database import Base

class AccountType(str, enum.Enum):
    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    REVENUE = "REVENUE"
    EXPENSE = "EXPENSE"

class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    code = Column(String, unique=True, index=True) # e.g. "1000" for Cash
    type = Column(SQLEnum(AccountType))
    company_id = Column(Integer, ForeignKey("companies.id"))
    
    # Relationships
    company = relationship("Company", back_populates="accounts")
    journal_entries = relationship("JournalEntry", back_populates="account")

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, default=datetime.utcnow)
    description = Column(String)
    company_id = Column(Integer, ForeignKey("companies.id"))

    company = relationship("Company", back_populates="transactions")
    journal_entries = relationship("JournalEntry", back_populates="transaction")

class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"))
    account_id = Column(Integer, ForeignKey("accounts.id"))
    amount = Column(Float) # Positive for Debit, Negative for Credit? Or use explicit Debit/Credit columns?
                           # Convention: Positive = Debit, Negative = Credit. Sum must be 0.
    
    transaction = relationship("Transaction", back_populates="journal_entries")
    account = relationship("Account", back_populates="journal_entries")

class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)  # Removed unique=True
    is_player = Column(Boolean, default=False)
    brand_equity = Column(Float, default=1.0) # Base multiplier for market share
    cash = Column(Float, default=0.0) # Redundant but good for quick access? No, calculate from Ledger.
    strategy_memory = Column(JSON, default=lambda: {
        "stockouts": {},      # {product_id: count}
        "pricing_regret": {}, # {product_id: cumulative_regret_score}
        "inventory_waste": {},# {product_id: units_unsold_for_3+_turns}
        "adaptations": []     # [{turn, reason, adjustment}]
    })
    
    accounts = relationship("Account", back_populates="company")
    transactions = relationship("Transaction", back_populates="company")
    warehouses = relationship("Warehouse", back_populates="company")
    inventory = relationship("InventoryItem", back_populates="company")

class Warehouse(Base):
    __tablename__ = "warehouses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    location = Column(String)
    capacity = Column(Integer)
    monthly_cost = Column(Float)
    company_id = Column(Integer, ForeignKey("companies.id"))

    company = relationship("Company", back_populates="warehouses")
    inventory = relationship("InventoryItem", back_populates="warehouse")

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    sku = Column(String, unique=True, index=True)
    base_cost = Column(Float) # Market base cost
    base_price = Column(Float) # Market base price

class CompanyProduct(Base):
    __tablename__ = "company_products"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    price = Column(Float, default=0.0)  # Selling price set by company
    units_sold = Column(Integer, default=0)  # Total units sold (cumulative)
    revenue = Column(Float, default=0.0)  # Total revenue (cumulative)
    
    company = relationship("Company")
    product = relationship("Product")

class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"))
    quantity = Column(Integer, default=0)
    wac = Column(Float, default=0.0) # Weighted Average Cost
    
    company = relationship("Company", back_populates="inventory")
    product = relationship("Product")
    warehouse = relationship("Warehouse", back_populates="inventory")

class GameState(Base):
    __tablename__ = "game_state"

    id = Column(Integer, primary_key=True, index=True)
    current_month = Column(Integer, default=1)
    current_year = Column(Integer, default=2026)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # The 'product' relationship here seems out of place for a global GameState.
    # Assuming it's a typo or placeholder, I'll remove it as it would cause an error
    # without a ForeignKey or context for what 'product' refers to in GameState.
    # If it's intended, it needs a product_id column and ForeignKey.
    # For now, I'll omit it to ensure the model is syntactically correct and functional.
    # product = relationship("Product")

class MarketHistory(Base):
    """Tracks historical market data per product per turn."""
    __tablename__ = "market_history"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    month = Column(Integer)
    year = Column(Integer)
    
    price = Column(Float)
    units_sold = Column(Integer)
    revenue = Column(Float)
    demand_captured = Column(Float) # Raw demand allocated
    
    company = relationship("Company")
    product = relationship("Product")

class FinancialSnapshot(Base):
    """Tracks historical financial health per company per turn."""
    __tablename__ = "financial_snapshots"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    month = Column(Integer)
    year = Column(Integer)
    
    cash_balance = Column(Float)
    inventory_value = Column(Float) # Estimated value of all inventory
    total_assets = Column(Float)
    total_equity = Column(Float)
    net_income = Column(Float) # Profit for this specific month
    
    company = relationship("Company")

class MarketEvent(Base):
    """Tracks active market events and their effects."""
    __tablename__ = "market_events"
    
    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String)  # "ECONOMIC_BOOM", "RECESSION", "SUPPLY_DISRUPTION", "SEASONAL", "DECISION_EVENT"
    start_month = Column(Integer)
    start_year = Column(Integer)
    duration_months = Column(Integer)  # Remaining duration
    intensity = Column(Float)  # Multiplier: 1.25 for +25%, 0.80 for -20%, etc
    affected_product_id = Column(Integer, ForeignKey("products.id"), nullable=True)  # Null for economy-wide
    description = Column(String)
    
    # Decision Event fields
    requires_player_decision = Column(Boolean, default=False)
    decision_deadline_month = Column(Integer, nullable=True)
    decision_deadline_year = Column(Integer, nullable=True)
    player_decision = Column(String, nullable=True)  # "CHOICE_A", "CHOICE_B", etc.
    decision_made = Column(Boolean, default=False)
    event_data = Column(JSON, nullable=True)  # Stores event details, choices, and effects
    
    product = relationship("Product")

