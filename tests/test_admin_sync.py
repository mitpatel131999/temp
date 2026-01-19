# tests/test_admin_sync.py
import pytest


@pytest.mark.anyio
async def test_sync_master_creates_reference_data(client):
    r = await client.post("/v1/admin/sync/master")
    assert r.status_code == 200, r.text

    data = r.json()
    # These keys match the response you showed: {"brands":..,"fuels":..,"regions":..,"sites":..}
    assert "brands" in data
    assert "fuels" in data
    assert "regions" in data
    assert "sites" in data

    # In our mock, it should insert 1 each
    assert data["brands"] == 1
    assert data["fuels"] == 1
    assert data["regions"] == 1
    assert data["sites"] == 1


@pytest.mark.anyio
async def test_sync_prices_inserts_latest_prices(client):
    # Ensure master exists first
    r1 = await client.post("/v1/admin/sync/master")
    assert r1.status_code == 200, r1.text

    r2 = await client.post("/v1/admin/sync/prices")
    assert r2.status_code == 200, r2.text

    data = r2.json()
    # You showed: {"fetched":6989,"updated":6989,"skipped_missing_site":0}
    assert "fetched" in data
    assert "updated" in data
    assert "skipped_missing_site" in data

    assert data["fetched"] == 1
    assert data["updated"] == 1
    assert data["skipped_missing_site"] == 0
