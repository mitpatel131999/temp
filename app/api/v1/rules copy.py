from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_current_user
from app.db.session import get_db
from app.db.models_rules import PricingRule, PricingRuleCondition

router = APIRouter(prefix="/me/rules", tags=["rules"])

ALLOWED_DIR = {"COMPETITOR_MINUS_OWN", "OWN_MINUS_COMPETITOR"}
ALLOWED_COMP = {"GT","GTE","LT","LTE","ABS_GT","ABS_GTE"}

class ConditionIn(BaseModel):
    ownFuelId: int
    competitorFuelId: int
    direction: str
    comparator: str
    thresholdCents: int = Field(ge=0)
    requireBothAvailable: bool = True

class RuleCreateIn(BaseModel):
    ownedSiteId: str
    competitorSiteId: int
    name: str
    isEnabled: bool = True
    conditions: list[ConditionIn]

@router.post("")
async def create_rule(
    payload: RuleCreateIn,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    for c in payload.conditions:
        if c.direction not in ALLOWED_DIR:
            raise HTTPException(400, detail=f"Invalid direction {c.direction}")
        if c.comparator not in ALLOWED_COMP:
            raise HTTPException(400, detail=f"Invalid comparator {c.comparator}")

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
    await db.refresh(rule)

    # ✅ don’t touch rule.conditions (can trigger async lazy load)
    return {
        "id": rule.id,
        "name": rule.name,
        "isEnabled": rule.is_enabled,
        "conditions": len(payload.conditions),
    }

@router.get("")
async def list_rules(
    ownedSiteId: str | None = None,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    stmt = (
        select(PricingRule)
        .where(PricingRule.user_id == user.id)
        .options(selectinload(PricingRule.conditions))  # ✅ async-safe load
    )

    if ownedSiteId:
        stmt = stmt.where(PricingRule.owned_site_id == ownedSiteId)

    q = await db.execute(stmt)
    rules = q.scalars().all()

    out = []
    for r in rules:
        out.append({
            "id": r.id,
            "ownedSiteId": r.owned_site_id,
            "competitorSiteId": r.competitor_site_id,
            "name": r.name,
            "isEnabled": r.is_enabled,
            "conditions": [
                {
                    "id": c.id,
                    "ownFuelId": c.own_fuel_id,
                    "competitorFuelId": c.competitor_fuel_id,
                    "direction": c.direction,
                    "comparator": c.comparator,
                    "thresholdCents": c.threshold_cents,
                    "requireBothAvailable": c.require_both_available,
                } for c in r.conditions
            ],
        })

    return out
