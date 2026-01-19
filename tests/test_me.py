import pytest

@pytest.mark.anyio
async def test_me_requires_auth(client):
    r = await client.get("/v1/me")
    assert r.status_code in (401, 403)

@pytest.mark.anyio
async def test_me_with_token(client):
    # Register
    r1 = await client.post(
        "/v1/auth/register",
        json={
            "email": "me@test.com",
            "password": "Passw0rd!",
            "displayName": "Me User"
        },
    )
    token = r1.json()["accessToken"]

    r2 = await client.get(
        "/v1/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert r2.status_code == 200
    data = r2.json()
    assert "email" in data
