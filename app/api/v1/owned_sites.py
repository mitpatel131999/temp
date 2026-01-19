from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.session import get_db
from app.db.models.stations import UserOwnedSite  # <-- you must have this model/table

router = APIRouter(prefix="/me/owned-sites", tags=["owned-sites"])


class OwnedSiteCreateIn(BaseModel):
    siteId: int
    nickname: str | None = None
    isPrimary: bool = False


class OwnedSiteUpdateIn(BaseModel):
    nickname: str | None = None
    isPrimary: bool | None = None


@router.get("")
async def list_owned_sites(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    q = await db.execute(
        select(UserOwnedSite).where(UserOwnedSite.user_id == user.id)
    )
    rows = q.scalars().all()
    return [
        {
            "id": r.id,
            "siteId": r.site_id,
            "nickname": r.nickname,
            "isPrimary": bool(r.is_primary),
        }
        for r in rows
    ]


@router.post("")
async def create_owned_site(
    payload: OwnedSiteCreateIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    # Optional: prevent duplicates for same user+site
    existing = (
        await db.execute(
            select(UserOwnedSite).where(
                UserOwnedSite.user_id == user.id,
                UserOwnedSite.site_id == payload.siteId,
            )
        )
    ).scalar_one_or_none()
    if existing:
        return {
            "id": existing.id,
            "siteId": existing.site_id,
            "nickname": existing.nickname,
            "isPrimary": bool(existing.is_primary),
        }

    new_id = str(uuid.uuid4())

    # If setting as primary, clear old primary
    if payload.isPrimary:
        await db.execute(
            update(UserOwnedSite)
            .where(UserOwnedSite.user_id == user.id)
            .values(is_primary=0)
        )

    row = UserOwnedSite(
        id=new_id,
        user_id=user.id,
        site_id=payload.siteId,
        nickname=payload.nickname or "",
        is_primary=1 if payload.isPrimary else 0,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    return {
        "id": row.id,
        "siteId": row.site_id,
        "nickname": row.nickname,
        "isPrimary": bool(row.is_primary),
    }


@router.patch("/{owned_site_id}")
async def update_owned_site(
    owned_site_id: str,
    payload: OwnedSiteUpdateIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    row = (
        await db.execute(
            select(UserOwnedSite).where(
                UserOwnedSite.id == owned_site_id,
                UserOwnedSite.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(404, detail="Owned site not found")

    if payload.isPrimary is True:
        await db.execute(
            update(UserOwnedSite)
            .where(UserOwnedSite.user_id == user.id)
            .values(is_primary=0)
        )
        row.is_primary = 1
    elif payload.isPrimary is False:
        row.is_primary = 0

    if payload.nickname is not None:
        row.nickname = payload.nickname

    await db.commit()
    await db.refresh(row)

    return {
        "id": row.id,
        "siteId": row.site_id,
        "nickname": row.nickname,
        "isPrimary": bool(row.is_primary),
    }


@router.delete("/{owned_site_id}")
async def delete_owned_site(
    owned_site_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    # Only delete if owned by user
    row = (
        await db.execute(
            select(UserOwnedSite).where(
                UserOwnedSite.id == owned_site_id,
                UserOwnedSite.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(404, detail="Owned site not found")

    await db.execute(
        delete(UserOwnedSite).where(
            UserOwnedSite.id == owned_site_id,
            UserOwnedSite.user_id == user.id,
        )
    )
    await db.commit()
    return {"deleted": True, "id": owned_site_id}
