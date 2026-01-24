# app/notifications/alert_scheduler.py
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal
from app.db.models_rules import PricingRule, PricingRuleCondition as RuleCondition
from app.db.models.stations import UserOwnedSite as OwnedSite
from app.db.models_notifications import UserDevice as NotificationDevice, RuleAlertState
from app.services.push_service import send_expo_push, send_web_push


POLL_SECONDS = 60          # evaluate every 60s (match your front-end POLL_MS)
COOLDOWN_MINUTES = 30      # notify again only after cooldown if still triggered


def _cmp_triggered(diff_raw: int, comparator: str, threshold_raw: int) -> bool:
    # raw values in your system: 1543 => 154.3c
    if comparator == "GT":
        return diff_raw > threshold_raw
    if comparator == "GTE":
        return diff_raw >= threshold_raw
    if comparator == "LT":
        return diff_raw < threshold_raw
    if comparator == "LTE":
        return diff_raw <= threshold_raw
    if comparator == "ABS_GT":
        return abs(diff_raw) > threshold_raw
    if comparator == "ABS_GTE":
        return abs(diff_raw) >= threshold_raw
    return False


async def _fetch_latest_raw_price(session: AsyncSession, site_id: int, fuel_id: int) -> Optional[int]:
    """
    IMPORTANT:
    You said you already expose GET /v1/prices/latest.
    Best practice is to call the internal price service function directly,
    but since that code isn't in the uploaded files, keep a single place
    to plug it in.

    Replace this implementation with your internal latest-price lookup.
    """
    # ---- IMPLEMENT YOUR REAL LOOKUP HERE ----
    # Example (pseudo):
    # row = await session.execute(select(Price).where(...).order_by(Price.recorded_at.desc()).limit(1))
    # return row.scalar_one_or_none().price_cents_raw

    return None  # <-- replace


async def _get_user_devices(session: AsyncSession, user_id: str) -> Tuple[List[str], List[dict]]:
    """
    Returns (expo_tokens, webpush_subscriptions)
    """
    res = await session.execute(
        select(NotificationDevice).where(NotificationDevice.user_id == user_id)
    )
    devices = res.scalars().all()

    expo_tokens: List[str] = []
    webpush_subs: List[dict] = []

    for d in devices:
        if d.platform == "expo" and d.push_token:
            expo_tokens.append(d.push_token)
        elif d.platform == "webpush" and d.web_push_subscription:
            # stored as JSON string in your model
            try:
                import json
                webpush_subs.append(json.loads(d.web_push_subscription))
            except Exception:
                pass

    return expo_tokens, webpush_subs


async def _upsert_state(
    session: AsyncSession,
    user_id: str,
    rule_id: str,
    condition_id: str,
) -> RuleAlertState:
    q = await session.execute(
        select(RuleAlertState).where(
            RuleAlertState.user_id == user_id,
            RuleAlertState.rule_id == rule_id,
            RuleAlertState.condition_id == condition_id,
        )
    )
    st = q.scalar_one_or_none()
    if st:
        return st

    st = RuleAlertState(
        user_id=user_id,
        rule_id=rule_id,
        condition_id=condition_id,
        is_currently_triggered=False,
        last_triggered_at=None,
        last_notified_at=None,
    )
    session.add(st)
    await session.flush()
    return st


async def evaluate_and_notify_once() -> None:
    """
    One scheduler tick:
    - query enabled rules
    - compute triggered state per condition
    - spam control:
        send when NOT triggered -> triggered
        OR triggered again after cooldown
    """
    now = datetime.now(timezone.utc)
    cooldown = timedelta(minutes=COOLDOWN_MINUTES)

    async with SessionLocal() as session:
        # Load enabled rules + owned sites in one go
        rules_res = await session.execute(
            select(PricingRule).where(PricingRule.is_enabled == True)  # noqa
        )
        rules = rules_res.scalars().all()
        if not rules:
            return

        # Pre-load owned sites referenced by rules
        owned_site_ids = list({r.owned_site_id for r in rules if r.owned_site_id})
        owned_map: Dict[str, OwnedSite] = {}
        if owned_site_ids:
            owned_res = await session.execute(
                select(OwnedSite).where(OwnedSite.id.in_(owned_site_ids))
            )
            for os in owned_res.scalars().all():
                owned_map[os.id] = os

        # Pre-load conditions
        rule_ids = [r.id for r in rules]
        cond_res = await session.execute(
            select(RuleCondition).where(RuleCondition.rule_id.in_(rule_ids))
        )
        conditions_by_rule: Dict[str, List[RuleCondition]] = {}
        for c in cond_res.scalars().all():
            conditions_by_rule.setdefault(c.rule_id, []).append(c)

        # Iterate rules
        for rule in rules:
            owned = owned_map.get(rule.owned_site_id)
            if not owned:
                continue

            user_id = owned.user_id  # OwnedSite.user_id exists in your model
            rule_conditions = conditions_by_rule.get(rule.id, [])
            if not rule_conditions:
                continue

            # Evaluate each condition
            for cond in rule_conditions:
                # Fetch latest prices RAW (1543 = 154.3c)
                own_raw = await _fetch_latest_raw_price(session, owned.site_id, cond.own_fuel_id)
                comp_raw = await _fetch_latest_raw_price(session, rule.competitor_site_id, cond.competitor_fuel_id)

                # If require both available and missing → treat as not triggered
                if cond.require_both_available and (own_raw is None or comp_raw is None):
                    triggered = False
                else:
                    # If either missing → not triggered
                    if own_raw is None or comp_raw is None:
                        triggered = False
                    else:
                        diff_raw = (comp_raw - own_raw) if cond.direction == "COMPETITOR_MINUS_OWN" else (own_raw - comp_raw)
                        triggered = _cmp_triggered(diff_raw, cond.comparator, cond.threshold_cents)

                st = await _upsert_state(session, user_id=user_id, rule_id=rule.id, condition_id=cond.id)

                # Decide notify
                should_notify = False
                if triggered and not st.is_currently_triggered:
                    # transition: not triggered -> triggered
                    should_notify = True
                elif triggered and st.is_currently_triggered:
                    # still triggered: notify again only after cooldown
                    if st.last_notified_at is None or (now - st.last_notified_at) >= cooldown:
                        should_notify = True

                # Update state
                if triggered and not st.is_currently_triggered:
                    st.last_triggered_at = now
                st.is_currently_triggered = triggered

                if should_notify:
                    title = "Fuel alert triggered"
                    body = f"Rule triggered for site {owned.site_id} vs competitor {rule.competitor_site_id}"
                    data = {
                        "ruleId": rule.id,
                        "conditionId": cond.id,
                        "ownedSiteId": owned.id,
                        "ownedSite": owned.site_id,
                        "competitorSite": rule.competitor_site_id,
                    }

                    expo_tokens, web_subs = await _get_user_devices(session, user_id=user_id)

                    # Send expo push (iOS/Android)
                    await send_expo_push(expo_tokens, title=title, body=body, data=data)

                    # Optional web push
                    if web_subs:
                        send_web_push(web_subs, title=title, body=body, data=data)

                    st.last_notified_at = now

                await session.commit()


async def start_alert_scheduler() -> None:
    """
    Runs forever inside your FastAPI lifespan task.
    """
    while True:
        try:
            await evaluate_and_notify_once()
        except Exception:
            # keep scheduler alive
            pass
        await asyncio.sleep(POLL_SECONDS)
