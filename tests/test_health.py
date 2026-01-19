# tests/test_health.py
import pytest

@pytest.mark.anyio
async def test_health(client):
    r = await client.get("/v1/health")
    assert r.status_code == 200, r.text
    data = r.json()

    # your health endpoint returns {"ok": True}
    assert data.get("ok") is True
