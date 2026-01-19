# tests/conftest.py
import os
import tempfile
import pytest
from httpx import AsyncClient

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.base import Base

# ✅ Adjust this import if your project uses a different dependency function
from app.db.session import get_db  # dependency used by routes


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def test_db_url():
    # Use a real file (NOT :memory:) because async + sqlite + multiple connections can lock.
    fd, path = tempfile.mkstemp(prefix="test_fuel_", suffix=".db")
    os.close(fd)
    return f"sqlite+aiosqlite:///{path}"


@pytest.fixture(scope="session")
async def test_engine(test_db_url):
    engine = create_async_engine(
        test_db_url,
        future=True,
        echo=False,
        connect_args={"timeout": 30},  # helps reduce sqlite lock issues
    )

    # Create tables once
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()

@pytest.fixture()
async def db_session(test_engine):
    async with test_engine.connect() as conn:
        trans = await conn.begin()

        async_session = sessionmaker(
            bind=conn,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        async with async_session() as session:
            yield session

        await trans.rollback()





@pytest.fixture()
async def client(db_session, monkeypatch):
    # Override DB dependency
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    # ---------------------------
    # Mock Fuel API client
    # ---------------------------
    from app.fpd.client import FPDClient

    async def mock_get_json(self, path: str, params=None):
        p = path.lower()

        if "getcountrybrands" in p:
            return {"Brands": [{"BrandId": 113, "Name": "7 Eleven"}]}

        if "getcountryfueltypes" in p:
            return {"Fuels": [{"FuelId": 2, "Name": "Unleaded"}]}

        if "getcountrygeographicregions" in p:
            return {
                "GeographicRegions": [
                    {
                        "GeoRegionLevel": 3,
                        "GeoRegionId": 1,
                        "Name": "Queensland",
                        "Abbrev": "QLD",
                        "GeoRegionParentId": None,
                    }
                ]
            }

        if "getfullsitedetails" in p:
            return {
                "S": [
                    {
                        "S": 61401007,
                        "A": "Pacific Highway",
                        "N": "7-Eleven Coomera",
                        "B": 113,
                        "P": "4209",
                        "G1": 111,
                        "G2": 222,
                        "G3": 1,
                        "Lat": -27.868671,
                        "Lng": 153.314236,
                        "M": "2019-07-15T05:32:17.627",
                        "GPI": "ChIJoflAeuATkWsRPZIMVJfb9yE",
                    }
                ]
            }

        if "getsitesprices" in p:
            return {
                "SitePrices": [
                    {
                        "SiteId": 61401007,
                        "FuelId": 2,
                        "CollectionMethod": "Q",
                        "TransactionDateUtc": "2026-01-16T05:25:00",
                        "Price": 2119.0,
                    }
                ]
            }

        raise AssertionError(f"Unexpected FPD path: {path}")

    # ✅ monkeypatch MUST be called here
    monkeypatch.setattr(FPDClient, "get_json", mock_get_json, raising=True)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
