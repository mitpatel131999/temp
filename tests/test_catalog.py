import pytest

@pytest.mark.anyio
async def test_catalog_endpoints(client):
    await client.post("/v1/admin/sync/master")

    r = await client.get("/v1/catalog/brands")
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)

    r = await client.get("/v1/catalog/fuels")
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)

    r = await client.get("/v1/catalog/sites/search", params={"q": "7"})
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)
