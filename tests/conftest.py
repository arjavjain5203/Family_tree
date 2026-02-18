import os

# Set dummy env vars for testing
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["TWILIO_ACCOUNT_SID"] = "AC_TEST"
os.environ["TWILIO_AUTH_TOKEN"] = "AUTH_TEST"
os.environ["TWILIO_PHONE_NUMBER"] = "whatsapp:+14155238886"

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from app.main import app
from app.config import get_settings
# Import models to ensure they are registered with Base.metadata
from app.models.user import User
from app.models.tree import Tree, TreeAccess
from app.models.member import Member, Relationship
from app.models.event import Event

# Use SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(
    class_=AsyncSession, autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
)

async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session

app.dependency_overrides[get_db] = override_get_db

@pytest_asyncio.fixture(scope="module")
async def prepare_database():
    print(f"Creating tables: {Base.metadata.tables.keys()}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture(scope="function")
async def db_session(prepare_database):
    async with TestingSessionLocal() as session:
        yield session

@pytest_asyncio.fixture(scope="module")
async def client(prepare_database):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
