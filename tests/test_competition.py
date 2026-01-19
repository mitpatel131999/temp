import pytest

@pytest.mark.anyio
async def test_competition_endpoint_placeholder(client):
    r = await client.get("/v1/competition/compare")
    assert r.status_code in (404, 501)
