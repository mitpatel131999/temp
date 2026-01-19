# tests/test_rule_conflicts.py
import pytest


@pytest.mark.anyio
async def test_rule_conflicts_endpoint_behaviour(client):
    """
    Your app may or may not expose /v1/rules/conflicts yet.

    This test is written to be:
    - STRICT if the endpoint exists (must return a JSON list)
    - TOLERANT if the endpoint is not implemented yet (404 is acceptable)
    """

    r = await client.get("/v1/rules/conflicts")

    # Acceptable:
    # - 200 => endpoint exists
    # - 404 => endpoint not implemented yet
    assert r.status_code in (200, 404), r.text

    if r.status_code == 404:
        # Not implemented yet — test passes
        return

    # If it exists, validate response shape
    data = r.json()
    assert isinstance(data, list), f"Expected list, got {type(data)}: {data}"

    # Optional: validate structure if list is non-empty (safe checks only)
    if len(data) > 0:
        item = data[0]
        assert isinstance(item, dict), f"Expected dict items, got {type(item)}: {item}"

        # Common fields you may include later (don't hard-fail if missing)
        # If you want strict checks, tell me your exact response schema.
        for key in ["ruleId", "conflictType", "message"]:
            if key in item:
                assert item[key] is not None
