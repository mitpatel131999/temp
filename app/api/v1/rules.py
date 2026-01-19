# app/api/v1/rules.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_current_user
from app.db.session import get_db
from app.db.models_rules import PricingRule, PricingRuleCondition

# ✅ these two imports must match your project file names / model names
# If your class names differ, adjust them here only.
from app.db.models.stations  import UserOwnedSite  # must have: id, user_id, site_id, nickname, is_primary

try:
    # common pattern: stations.py contains Site model (site_id, name, ...)
    from app.db.models.master import Site  # must have: site_id, name
except Exception:
    Site = None  # fallback: site names will return None

router = APIRouter(prefix="/me/rules", tags=["rules"])

ALLOWED_DIR = {"COMPETITOR_MINUS_OWN", "OWN_MINUS_COMPETITOR"}
ALLOWED_COMP = {"GT", "GTE", "LT", "LTE", "ABS_GT", "ABS_GTE"}


# -------------------------
# Schemas
# -------------------------
class ConditionIn(BaseModel):
    ownFuelId: int
    competitorFuelId: int
    direction: str
    comparator: str
    thresholdCents: int = Field(ge=0)
    requireBothAvailable: bool = True


class RuleCreateIn(BaseModel):
    ownedSiteId: str  # FK to user_owned_sites.id
    competitorSiteId: int  # raw station/site_id
    name: str
    isEnabled: bool = True
    conditions: list[ConditionIn]


class RuleUpdateIn(BaseModel):
    # full replace OR partial update
    ownedSiteId: str | None = None
    competitorSiteId: int | None = None
    name: str | None = None
    isEnabled: bool | None = None
    conditions: list[ConditionIn] | None = None


# -------------------------
# Helpers
# -------------------------
def _validate_conditions(conditions: list[ConditionIn]) -> None:
    for c in conditions:
        if c.direction not in ALLOWED_DIR:
            raise HTTPException(400, detail=f"Invalid direction {c.direction}")
        if c.comparator not in ALLOWED_COMP:
            raise HTTPException(400, detail=f"Invalid comparator {c.comparator}")


async def _get_owned_site_or_404(db: AsyncSession, *, user_id: str, owned_site_id: str) -> UserOwnedSite:
    q = await db.execute(
        select(UserOwnedSite).where(
            UserOwnedSite.id == owned_site_id,
            UserOwnedSite.user_id == user_id,
        )
    )
    row = q.scalar_one_or_none()
    if not row:
        raise HTTPException(404, detail="Owned site not found")
    return row


async def _get_site_names_map(db: AsyncSession, site_ids: list[int]) -> dict[int, str | None]:
    if not site_ids:
        return {}
    if Site is None:
        return {sid: None for sid in site_ids}

    q = await db.execute(select(Site.site_id, Site.name).where(Site.site_id.in_(site_ids)))
    rows = q.all()
    out: dict[int, str | None] = {sid: None for sid in site_ids}
    for sid, name in rows:
        out[int(sid)] = name
    return out


async def _rule_to_out(db: AsyncSession, *, user_id: str, rule: PricingRule) -> dict:
    """
    Returns rule with:
    - owned site: id + real siteId + siteName
    - competitor: siteId + siteName
    - conditions (already selectinloaded)
    """
    owned = await _get_owned_site_or_404(db, user_id=user_id, owned_site_id=str(rule.owned_site_id))
    owned_site_id_int = int(owned.site_id)
    competitor_site_id_int = int(rule.competitor_site_id)

    names = await _get_site_names_map(db, [owned_site_id_int, competitor_site_id_int])

    return {
        "id": str(rule.id),
        "name": rule.name,
        "isEnabled": rule.is_enabled,
        # keep old fields for backward compatibility
        "ownedSiteId": str(rule.owned_site_id),
        "competitorSiteId": competitor_site_id_int,
        # ✅ new enriched fields
        "ownedSite": {
            "ownedSiteId": str(owned.id),
            "siteId": owned_site_id_int,
            "siteName": names.get(owned_site_id_int),
            "nickname": getattr(owned, "nickname", None),
            "isPrimary": bool(getattr(owned, "is_primary", False)),
        },
        "competitorSite": {
            "siteId": competitor_site_id_int,
            "siteName": names.get(competitor_site_id_int),
        },
        "conditions": [
            {
                "id": str(c.id),
                "ownFuelId": c.own_fuel_id,
                "competitorFuelId": c.competitor_fuel_id,
                "direction": c.direction,
                "comparator": c.comparator,
                "thresholdCents": c.threshold_cents,
                "requireBothAvailable": c.require_both_available,
            }
            for c in rule.conditions
        ],
    }


# -------------------------
# Create
# -------------------------
@router.post("")
async def create_rule(
    payload: RuleCreateIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    _validate_conditions(payload.conditions)

    # ensure owned site belongs to this user
    await _get_owned_site_or_404(db, user_id=user.id, owned_site_id=payload.ownedSiteId)

    rule = PricingRule(
        user_id=user.id,
        owned_site_id=payload.ownedSiteId,
        competitor_site_id=payload.competitorSiteId,
        name=payload.name,
        is_enabled=payload.isEnabled,
    )

    for c in payload.conditions:
        rule.conditions.append(
            PricingRuleCondition(
                own_fuel_id=c.ownFuelId,
                competitor_fuel_id=c.competitorFuelId,
                direction=c.direction,
                comparator=c.comparator,
                threshold_cents=c.thresholdCents,
                require_both_available=c.requireBothAvailable,
            )
        )

    db.add(rule)
    await db.commit()

    # reload with conditions safely
    q = await db.execute(
        select(PricingRule)
        .where(PricingRule.id == rule.id, PricingRule.user_id == user.id)
        .options(selectinload(PricingRule.conditions))
    )
    rule = q.scalar_one()

    return await _rule_to_out(db, user_id=user.id, rule=rule)


# -------------------------
# List
# -------------------------
@router.get("")
async def list_rules(
    ownedSiteId: str | None = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    stmt = (
        select(PricingRule)
        .where(PricingRule.user_id == user.id)
        .options(selectinload(PricingRule.conditions))
    )
    if ownedSiteId:
        stmt = stmt.where(PricingRule.owned_site_id == ownedSiteId)

    q = await db.execute(stmt)
    rules = q.scalars().all()

    out = []
    for r in rules:
        out.append(await _rule_to_out(db, user_id=user.id, rule=r))
    return out


# -------------------------
# Update (Edit)
# -------------------------

@router.patch("/{rule_id}")
async def patch_rule(
    rule_id: str,
    payload: RuleUpdateIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    # Reuse the exact same logic as PUT
    return await update_rule(rule_id=rule_id, payload=payload, db=db, user=user)


#@router.put("/{rule_id}")
async def update_rule(
    rule_id: str,
    payload: RuleUpdateIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    q = await db.execute(
        select(PricingRule)
        .where(PricingRule.id == rule_id, PricingRule.user_id == user.id)
        .options(selectinload(PricingRule.conditions))
    )
    rule = q.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, detail="Rule not found")

    # validate + apply updates
    if payload.ownedSiteId is not None:
        await _get_owned_site_or_404(db, user_id=user.id, owned_site_id=payload.ownedSiteId)
        rule.owned_site_id = payload.ownedSiteId

    if payload.competitorSiteId is not None:
        rule.competitor_site_id = payload.competitorSiteId

    if payload.name is not None:
        rule.name = payload.name

    if payload.isEnabled is not None:
        rule.is_enabled = payload.isEnabled

    if payload.conditions is not None:
        _validate_conditions(payload.conditions)

        # Replace all existing conditions (safe + simple)
        for c in list(rule.conditions):
            await db.delete(c)
        rule.conditions = []

        for c in payload.conditions:
            rule.conditions.append(
                PricingRuleCondition(
                    own_fuel_id=c.ownFuelId,
                    competitor_fuel_id=c.competitorFuelId,
                    direction=c.direction,
                    comparator=c.comparator,
                    threshold_cents=c.thresholdCents,
                    require_both_available=c.requireBothAvailable,
                )
            )

    await db.commit()

    # reload with conditions safely
    q2 = await db.execute(
        select(PricingRule)
        .where(PricingRule.id == rule_id, PricingRule.user_id == user.id)
        .options(selectinload(PricingRule.conditions))
    )
    rule = q2.scalar_one()

    return await _rule_to_out(db, user_id=user.id, rule=rule)


# -------------------------
# Delete
# -------------------------
@router.delete("/{rule_id}")
async def delete_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    q = await db.execute(
        select(PricingRule).where(PricingRule.id == rule_id, PricingRule.user_id == user.id)
    )
    rule = q.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, detail="Rule not found")

    await db.delete(rule)
    await db.commit()
    return {"ok": True, "deletedRuleId": rule_id}
