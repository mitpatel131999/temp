from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.db.models.prices import PriceLatest

router = APIRouter()


@router.get("/prices/latest")
async def latest(site_id: int, fuel_id: int, db: AsyncSession = Depends(get_db)):
    row = (await db.execute(
        select(PriceLatest).where(PriceLatest.site_id == site_id, PriceLatest.fuel_id == fuel_id)
    )).scalar_one_or_none()

    if not row:
        return {"found": False}

    return {
        "found": True,
        "SiteId": row.site_id,
        "FuelId": row.fuel_id,
        "Price": row.price_raw,
        "PriceCents": row.price_cents,
        "Unavailable": row.unavailable,
        "TransactionDateUtc": row.transaction_date_utc.isoformat(),
        "CollectionMethod": row.collection_method,
        "IngestedAt": row.ingested_at.isoformat(),
    }


from fastapi import Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models.prices import PriceLatest
from app.db.models.master import FuelType as MasterFuel

@router.get("/latest/by-site")
async def latest_prices_by_site(
    siteId: int = Query(..., description="MasterSite ID"),
    db: AsyncSession = Depends(get_db),
):
    q = await db.execute(select(PriceLatest).where(PriceLatest.site_id == siteId))
    rows = q.scalars().all()
    if not rows:
        return []

    fuel_ids = list({r.fuel_id for r in rows})
    fq = await db.execute(select(MasterFuel).where(MasterFuel.id.in_(fuel_ids)))
    fuel_map = {f.id: f for f in fq.scalars().all()}

    out = []
    for r in rows:
        f = fuel_map.get(r.fuel_id)
        out.append(
            {
                "siteId": r.site_id,
                "fuelId": r.fuel_id,
                "fuelName": f.name if f else None,
                "fuelCode": f.code if f else None,
                "priceCents": r.price_cents,
                "unavailable": r.unavailable,
                "updatedAt": r.updated_at.isoformat() if r.updated_at else None,
            }
        )
    return out
