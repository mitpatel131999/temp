# tests/test_prices.py
import pytest


@pytest.mark.anyio
async def test_get_latest_price_found(client):
    # Master + prices
    await client.post("/v1/admin/sync/master")
    await client.post("/v1/admin/sync/prices")

    r = await client.get("/v1/prices/latest", params={"site_id": 61401007, "fuel_id": 2})
    assert r.status_code == 200, r.text

    data = r.json()
    assert data["found"] is True
    assert data["SiteId"] == 61401007
    assert data["FuelId"] == 2
    assert data["PriceCents"] == 2119
    assert data["Unavailable"] is False
    assert data["CollectionMethod"] == "Q"


@pytest.mark.anyio
async def test_get_latest_price_not_found(client):
    await client.post("/v1/admin/sync/master")
    # Don't sync prices, so it should be missing

    r = await client.get("/v1/prices/latest", params={"site_id": 61401007, "fuel_id": 2})
    assert r.status_code == 200, r.text

    data = r.json()
    assert data["found"] is False
