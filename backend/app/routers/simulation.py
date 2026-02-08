"""
API Router for game simulation endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.database import get_db
from app.schemas import (
    GameStateResponse, 
    TurnResultResponse, 
    PurchaseInventoryRequest,
    CompanyResponse,
    MarketHistoryResponse,
    FinancialSnapshotResponse
)
from app.models import Company, Product, CompanyProduct, MarketHistory, FinancialSnapshot
from core.engine import GameEngine

router = APIRouter(prefix="/game", tags=["game"])

@router.get("/history/market", response_model=List[MarketHistoryResponse])
async def get_market_history(
    company_id: int = None,
    product_id: int = None,
    db: AsyncSession = Depends(get_db)
):
    """Get market history up to current game state."""
    # Get current game state to filter out future data
    engine = GameEngine(db)
    await engine.load_state()
    
    query = select(MarketHistory).order_by(MarketHistory.year, MarketHistory.month)
    
    # Filter by current game time (exclude future months from previous sessions)
    query = query.where(
        (MarketHistory.year < engine.current_year) |
        ((MarketHistory.year == engine.current_year) & (MarketHistory.month < engine.current_month))
    )
    
    if company_id:
        query = query.where(MarketHistory.company_id == company_id)
    if product_id:
        query = query.where(MarketHistory.product_id == product_id)
    
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/history/financial", response_model=List[FinancialSnapshotResponse])
async def get_financial_history(
    company_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get financial history for a company up to current game state."""
    # Get current game state to filter out future data
    engine = GameEngine(db)
    await engine.load_state()
    
    query = select(FinancialSnapshot).where(FinancialSnapshot.company_id == company_id)
    
    # Filter by current game time (exclude future months from previous sessions)
    query = query.where(
        (FinancialSnapshot.year < engine.current_year) |
        ((FinancialSnapshot.year == engine.current_year) & (FinancialSnapshot.month < engine.current_month))
    )
    
    query = query.order_by(FinancialSnapshot.year, FinancialSnapshot.month)
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/start")
async def start_game(db: AsyncSession = Depends(get_db)):
    """Initialize a new game."""
    try:
        engine = GameEngine(db)
        player_company = await engine.initialize_game()
        
        return {
            "message": "Game started!",
            "company_id": player_company.id,
            "company_name": player_company.name
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error starting game: {str(e)}")

@router.get("/state", response_model=GameStateResponse)
async def get_game_state(db: AsyncSession = Depends(get_db)):
    """Get current game state."""
    engine = GameEngine(db)
    await engine.load_state()
    
    # Get all companies
    result = await db.execute(select(Company))
    companies = result.scalars().all()
    
    # Get player company
    player = next((c for c in companies if c.is_player), None)
    if not player:
        raise HTTPException(status_code=404, detail="No player company found. Start a new game!")
    
    cash_balance = await engine.accounting.get_company_cash(player.id)
    
    # Prepare enhanced company responses
    from core.bot_ai import BotAI
    bot_ai = BotAI(db)
    
    company_responses = []
    for c in companies:
        # Get cash for each company
        c_cash = await engine.accounting.get_company_cash(c.id)
        
        # Get personality
        personality = "Player"
        if not c.is_player:
            personality = bot_ai._get_personality(c)
            
        company_responses.append(
            CompanyResponse(
                id=c.id,
                name=c.name,
                is_player=c.is_player,
                cash=c_cash,
                brand_equity=c.brand_equity,
                strategy_memory=c.strategy_memory,
                personality=personality
            )
        )
    
    return GameStateResponse(
        current_month=engine.current_month,
        current_year=engine.current_year,
        cash_balance=cash_balance,
        companies=company_responses
    )

@router.post("/turn", response_model=TurnResultResponse)
async def advance_turn(
    db: AsyncSession = Depends(get_db)
):
    """Advance to the next turn (month)."""
    engine = GameEngine(db)
    await engine.load_state()
    result = await engine.process_turn()
    
    return TurnResultResponse(
        month=result["month"],
        year=result["year"],
        events=result["events"],
        logs=result.get("logs", [])
    )

@router.post("/purchase")
async def purchase_inventory(
    request: PurchaseInventoryRequest,
    db: AsyncSession = Depends(get_db)
):
    """Purchase inventory for the player company."""
    # Get player company
    result = await db.execute(select(Company).where(Company.is_player == True))
    player = result.scalar_one_or_none()
    
    if not player:
        raise HTTPException(status_code=404, detail="Player company not found")
    
    engine = GameEngine(db)
    await engine.purchase_inventory(
        company_id=player.id,
        product_id=request.product_id,
        quantity=request.quantity,
        unit_cost=request.unit_cost
    )
    
    return {"message": f"Purchased {request.quantity} units"}

@router.post("/set-price")
async def set_product_price(
    product_id: int,
    price: float,
    db: AsyncSession = Depends(get_db)
):
    """Set the selling price for a product (player company only)."""
    # Get player company
    result = await db.execute(select(Company).where(Company.is_player == True))
    player = result.scalar_one_or_none()
    
    if not player:
        raise HTTPException(status_code=404, detail="Player company not found")
    
    # Get or create CompanyProduct
    result = await db.execute(
        select(CompanyProduct)
        .where(CompanyProduct.company_id == player.id)
        .where(CompanyProduct.product_id == product_id)
    )
    cp = result.scalar_one_or_none()
    
    if not cp:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Validate price
    if price < 0:
        raise HTTPException(status_code=400, detail="Price must be positive")
    
    cp.price = price
    await db.commit()
    
    return {"message": f"Price set to ${price:.2f}"}

@router.get("/products")
async def get_products(db: AsyncSession = Depends(get_db)):
    """Get all products with player's current pricing."""
    # Get player company
    result = await db.execute(select(Company).where(Company.is_player == True))
    player = result.scalar_one_or_none()
    
    if not player:
        raise HTTPException(status_code=404, detail="Player company not found")
    
    # Get all products with player's pricing
    result = await db.execute(
        select(Product, CompanyProduct)
        .join(CompanyProduct, CompanyProduct.product_id == Product.id)
        .where(CompanyProduct.company_id == player.id)
    )
    rows = result.all()
    
    products = []
    for product, cp in rows:
        products.append({
            "id": product.id,
            "name": product.name,
            "sku": product.sku,
            "base_cost": product.base_cost,
            "base_price": product.base_price,
            "your_price": cp.price,
            "units_sold": cp.units_sold,
            "revenue": cp.revenue
        })
    
    return products

@router.get("/inventory")
async def get_inventory(db: AsyncSession = Depends(get_db)):
    """Get inventory items for the player company."""
    from app.models import InventoryItem
    
    # Get player company
    result = await db.execute(select(Company).where(Company.is_player == True))
    player = result.scalar_one_or_none()
    
    if not player:
        raise HTTPException(status_code=404, detail="Player company not found")
    
    # Get all inventory items with product details
    result = await db.execute(
        select(InventoryItem, Product)
        .join(Product, Product.id == InventoryItem.product_id)
        .where(InventoryItem.company_id == player.id)
    )
    rows = result.all()
    
    inventory = []
    for inv_item, product in rows:
        total_value = inv_item.quantity * inv_item.wac
        inventory.append({
            "product_id": product.id,
            "product_name": product.name,
            "sku": product.sku,
            "quantity": inv_item.quantity,
            "wac": inv_item.wac,  # Weighted Average Cost
            "total_value": total_value
        })
    
    return inventory
