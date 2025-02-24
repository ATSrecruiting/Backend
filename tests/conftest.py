import pytest
from fastapi import FastAPI
from httpx import ASGITransport
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from db.models import Base
from router import vacancies, recruiter
from db.session import get_db, engine
import asyncio

TestingSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)


async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session


app = FastAPI()
app.include_router(vacancies.router)
app.include_router(recruiter.router)
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.run_until_complete(loop.shutdown_asyncgens())
    loop.close()


@pytest_asyncio.fixture(scope="module", autouse=True)
async def prepare_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Removed table dropping to avoid deleting real DB tables.
    await engine.dispose()


transport = ASGITransport(app=app)


