import pytest
import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import Company, Product, Account, AccountType, CompanyProduct

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a fresh in-memory database for each test function.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()
    
    # Cleanup
    await engine.dispose()

@pytest.fixture(scope="function")
async def test_company(db_session: AsyncSession) -> Company:
    """Creates a basic test company."""
    company = Company(
        name="Test Corp",
        is_player=True,
        cash=100000.0,
        brand_equity=1.0
    )
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)
    return company

@pytest.fixture
async def test_product(db_session: AsyncSession):
    """Create a test product."""
    product = Product(
        name="Test Widget",
        sku="TEST-WIDGET-001",
        base_cost=10.0,
        base_price=20.0
    )
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)
    return product

@pytest.fixture
async def test_company_product(db_session: AsyncSession, test_company, test_product):
    """Link company to product."""
    cp = CompanyProduct(
        company_id=test_company.id,
        product_id=test_product.id,
        price=20.0
    )
    db_session.add(cp)
    await db_session.commit()
    await db_session.refresh(cp)
    return cp
