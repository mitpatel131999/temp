from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.db.models.master import Brand, FuelType, Site

from sqlalchemy import select
from app.db.models.master import Site, FuelType
from app.db.models.prices import PriceLatest

router = APIRouter()

@router.get("/catalog/brands")
async def brands(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Brand).order_by(Brand.name))).scalars().all()
    return [{"BrandId": r.brand_id, "Name": r.name} for r in rows]

@router.get("/catalog/fuels")
async def fuels(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(FuelType).order_by(FuelType.fuel_id))).scalars().all()
    return [{"FuelId": r.fuel_id, "Name": r.name} for r in rows]

@router.get("/catalog/sites/search")
async def site_search(
    q: str = Query("", max_length=100),
    brand_id: int | None = None,
    g3: int | None = None,
    g2: int | None = None,
    g1: int | None = None,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Site)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((Site.name.like(like)) | (Site.address.like(like)))
    if brand_id is not None:
        stmt = stmt.where(Site.brand_id == brand_id)
    if g3 is not None:
        stmt = stmt.where(Site.g3_state_id == g3)
    if g2 is not None:
        stmt = stmt.where(Site.g2_city_id == g2)
    if g1 is not None:
        stmt = stmt.where(Site.g1_suburb_id == g1)

    rows = (await db.execute(stmt.order_by(Site.name).limit(limit))).scalars().all()
    return [
        {
            "SiteId": s.site_id,
            "Name": s.name,
            "Address": s.address,
            "BrandId": s.brand_id,
            "Postcode": s.postcode,
            "G1": s.g1_suburb_id,
            "G2": s.g2_city_id,
            "G3": s.g3_state_id,
            "Lat": s.lat,
            "Lng": s.lng,
        }
        for s in rows
    ]

@router.get("/catalog/sites/{site_id}")
async def get_site(site_id: int, db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(Site).where(Site.site_id == site_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(404, detail="Site not found")

    return {
        "siteId": row.site_id,
        "name": row.name,
        "brandId": row.brand_id,
        "address": row.address,
        "suburb": row.suburb,
        "state": row.state,
        "postcode": row.postcode,
        "lat": row.lat,
        "lng": row.lng,
    }


@router.get("/catalog/sites/{site_id}/fuels")
async def fuels_available_for_site(site_id: int, db: AsyncSession = Depends(get_db)):
    # available fuels = those we have latest rows for (optionally exclude unavailable)
    q = await db.execute(
        select(PriceLatest.fuel_id)
        .where(PriceLatest.site_id == site_id)
        .where(PriceLatest.unavailable == False)  # noqa: E712
        .distinct()
    )
    fuel_ids = [r[0] for r in q.all()]

    if not fuel_ids:
        return []

    fq = await db.execute(select(Fuel).where(Fuel.fuel_id.in_(fuel_ids)))
    fuels = fq.scalars().all()

    return [
        {
            "fuelId": f.fuel_id,
            "name": f.name,
            "code": getattr(f, "code", None),
        }
        for f in fuels
    ]


from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models.master import Site, FuelType
from app.db.models.prices import PriceLatest  # same model you use in prices router

@router.get("/sites/{site_id}")
async def get_site(site_id: int, db: AsyncSession = Depends(get_db)):
    q = await db.execute(select(Site).where(Site.id == site_id))
    s = q.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Site not found")

    return {
        "id": s.id,
        "name": s.name,
        "brandId": s.brand_id,
        "address": s.address,
        "suburb": s.suburb,
        "state": s.state,
        "postcode": s.postcode,
        "lat": s.lat,
        "lng": s.lng,
    }


@router.get("/sites/{site_id}/fuels")
async def get_site_fuels(site_id: int, db: AsyncSession = Depends(get_db)):
    """
    Returns fuels that are actually available at the site, inferred from PriceLatest.
    """
    q = await db.execute(
        select(PriceLatest.fuel_id).where(
            PriceLatest.site_id == site_id,
            PriceLatest.unavailable == False,  # noqa: E712
        )
    )
    fuel_ids = [row[0] for row in q.all()]
    if not fuel_ids:
        return []

    fq = await db.execute(select(FuelType).where(FuelType.id.in_(fuel_ids)))
    fuels = fq.scalars().all()

    return [{"id": f.id, "name": f.name, "code": f.code} for f in fuels]
