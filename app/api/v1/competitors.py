# app/api/v1/competitors.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.auth.deps import get_current_user
from app.db.models.stations import UserOwnedSite
from app.db.models.master import Site

router = APIRouter(prefix="/me/owned-sites", tags=["competitors"])


@router.get("/{owned_site_id}/competitors")
async def suggest_competitors(
    owned_site_id: str,
    limit: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    # confirm ownership
    oq = await db.execute(
        select(UserOwnedSite).where(
            UserOwnedSite.id == owned_site_id,
            UserOwnedSite.user_id == user.id,
        )
    )
    owned = oq.scalar_one_or_none()
    if not owned:
        raise HTTPException(status_code=404, detail="Owned site not found")

    # load owned site details
    sq = await db.execute(select(Site).where(Site.id == owned.site_id))
    site = sq.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Master site not found")

    # suggest: same postcode, not itself
    cq = await db.execute(
        select(MasterSite)
        .where(MasterSite.postcode == site.postcode, MasterSite.id != site.id)
        .limit(limit)
    )
    competitors = cq.scalars().all()

    return [
        {
            "siteId": s.id,
            "name": s.name,
            "brandId": s.brand_id,
            "address": s.address,
            "suburb": s.suburb,
            "state": s.state,
            "postcode": s.postcode,
            "lat": s.lat,
            "lng": s.lng,
        }
        for s in competitors
    ]
