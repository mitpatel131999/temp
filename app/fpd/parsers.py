from datetime import datetime

def parse_dt(val) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    s = str(val)
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        try:
            return datetime.fromisoformat(s.replace(" ", "T"))
        except Exception:
            return None

def unwrap_list(payload, possible_keys: list[str]) -> list:
    """
    Some endpoints return { "X": [ ... ] }.
    Some may return [ ... ].
    """
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for k in possible_keys:
            v = payload.get(k)
            if isinstance(v, list):
                return v
    return []
