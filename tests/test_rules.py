# tests/test_rules.py
import uuid

import pytest
from sqlalchemy import text


# ---------------------------
# Helpers
# ---------------------------

async def _register_and_login(client) -> str:
    """
    Register a NEW user and return an access token.
    We generate a unique email every run so tests don't depend on prior DB state.
    """
    email = f"rule_{uuid.uuid4().hex[:10]}@test.com"
    password = "Passw0rd!"

    r1 = await client.post(
        "/v1/auth/register",
        json={"email": email, "password": password, "displayName": "Rule Test"},
    )
    assert r1.status_code == 200, r1.text

    r2 = await client.post(
        "/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r2.status_code == 200, r2.text

    data = r2.json()
    assert "accessToken" in data, r2.text
    return data["accessToken"]


async def _me(client, token: str) -> dict:
    r = await client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    return r.json()


async def _insert_owned_site(db_session, *, user_id: str, site_id: int) -> str:
    """
    Inserts into user_owned_sites.
    Required because PricingRule.owned_site_id -> user_owned_sites.id (FK).
    Returns owned_site_id (uuid string).
    """
    owned_site_id = str(uuid.uuid4())

    await db_session.execute(
        text(
            """
            INSERT INTO user_owned_sites (id, user_id, site_id, nickname, is_primary)
            VALUES (:id, :user_id, :site_id, :nickname, :is_primary)
            """
        ),
        {
            "id": owned_site_id,
            "user_id": user_id,
            "site_id": site_id,
            "nickname": "My Site",
            "is_primary": 1,
        },
    )
    await db_session.commit()
    return owned_site_id


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------
# Tests
# ---------------------------

@pytest.mark.anyio
async def test_create_and_list_rules(client, db_session):
    token = await _register_and_login(client)
    me = await _me(client, token)
    user_id = me["id"]

    # ensure reference data exists (brands, fuels, sites, etc.)
    r = await client.post("/v1/admin/sync/master")
    assert r.status_code == 200, r.text

    owned_site_id = await _insert_owned_site(db_session, user_id=user_id, site_id=61401007)

    # NOTE:
    # rules.py allows ONLY:
    # direction in {"COMPETITOR_MINUS_OWN", "OWN_MINUS_COMPETITOR"}
    # comparator in {"GT","GTE","LT","LTE","ABS_GT","ABS_GTE"}
    payload = {
        "ownedSiteId": owned_site_id,
        "competitorSiteId": 61401007,
        "name": "Test Rule",
        "isEnabled": True,
        "conditions": [
            {
                "ownFuelId": 2,
                "competitorFuelId": 2,
                "direction": "COMPETITOR_MINUS_OWN",
                "comparator": "LT",
                "thresholdCents": 5,
                "requireBothAvailable": True,
            }
        ],
    }

    r = await client.post("/v1/me/rules", json=payload, headers=_auth_headers(token))
    assert r.status_code == 200, r.text

    created = r.json()
    assert "id" in created
    assert created.get("name") == "Test Rule"
    assert created.get("isEnabled") is True
    # your API returns an integer count for "conditions"
    assert created.get("conditions") == 1

    # list rules
    r = await client.get("/v1/me/rules", headers=_auth_headers(token))
    assert r.status_code == 200, r.text

    rules = r.json()
    assert isinstance(rules, list)
    assert any(x.get("id") == created["id"] for x in rules)


@pytest.mark.anyio
async def test_create_rule_invalid_comparator_returns_400(client, db_session):
    token = await _register_and_login(client)
    me = await _me(client, token)
    user_id = me["id"]

    owned_site_id = await _insert_owned_site(db_session, user_id=user_id, site_id=61401007)

    payload = {
        "ownedSiteId": owned_site_id,
        "competitorSiteId": 61401007,
        "name": "Bad Comparator Rule",
        "isEnabled": True,
        "conditions": [
            {
                "ownFuelId": 2,
                "competitorFuelId": 2,
                "direction": "COMPETITOR_MINUS_OWN",
                "comparator": "NOT_REAL",  # invalid
                "thresholdCents": 5,
                "requireBothAvailable": True,
            }
        ],
    }

    r = await client.post("/v1/me/rules", json=payload, headers=_auth_headers(token))
    assert r.status_code == 400, r.text
    assert "Invalid comparator" in r.text


@pytest.mark.anyio
async def test_create_rule_invalid_direction_returns_400(client, db_session):
    token = await _register_and_login(client)
    me = await _me(client, token)
    user_id = me["id"]

    owned_site_id = await _insert_owned_site(db_session, user_id=user_id, site_id=61401007)

    payload = {
        "ownedSiteId": owned_site_id,
        "competitorSiteId": 61401007,
        "name": "Bad Direction Rule",
        "isEnabled": True,
        "conditions": [
            {
                "ownFuelId": 2,
                "competitorFuelId": 2,
                "direction": "BELOW",  # invalid for your API
                "comparator": "LT",
                "thresholdCents": 5,
                "requireBothAvailable": True,
            }
        ],
    }

    r = await client.post("/v1/me/rules", json=payload, headers=_auth_headers(token))
    assert r.status_code == 400, r.text
    assert "Invalid direction" in r.text
