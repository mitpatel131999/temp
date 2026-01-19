# tests/test_auth.py
import pytest


@pytest.mark.anyio
async def test_register_login_me(client):
    # register
    r1 = await client.post(
        "/v1/auth/register",
        json={"email": "test@example.com", "password": "Passw0rd!", "displayName": "Test"},
    )
    assert r1.status_code == 200, r1.text
    reg = r1.json()
    assert "accessToken" in reg

    # login
    r2 = await client.post("/v1/auth/login", json={"email": "test@example.com", "password": "Passw0rd!"})
    assert r2.status_code == 200, r2.text
    login = r2.json()
    assert "accessToken" in login

    token = login["accessToken"]

    # me
    r3 = await client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert r3.status_code == 200, r3.text
    me = r3.json()
    assert me["email"] == "test@example.com"
