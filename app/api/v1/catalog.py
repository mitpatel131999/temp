from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from math import cos, radians, asin, sqrt
from typing import Optional

from app.db.session import get_db
from app.db.models.master import Brand, FuelType, Site
from app.db.models.prices import PriceLatest

router = APIRouter()

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def _parse_csv_ints(s: Optional[str]) -> list[int]:
    if not s:
        return []
    out: list[int] = []
    for part in str(s).split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except Exception:
            # ignore bad values, or raise if you want strict
            pass
    return out

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    # Earth radius in km
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = (
        (asin(sqrt(max(0.0, min(1.0,
            (sin := (lambda x: __import__("math").sin(x)))(dlat / 2) ** 2
        )))) ** 2)
    )

    # The above is overly complex; keep it simple:
    # a = sin(dlat/2)^2 + cos(lat1)*cos(lat2)*sin(dlon/2)^2
    # We'll implement that cleanly:

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))
    return R * c


# ------------------------------------------------------------
# Nearby sites (map dashboard)
# ------------------------------------------------------------
@router.get("/catalog/sites/nearby")
async def sites_nearby(
    lat: float = Query(...),
    lng: float = Query(...),
    radius_km: float = Query(5.0, gt=0.0001, le=100.0),
    limit: int = Query(250, ge=1, le=500),
    include_prices: bool = Query(False),
    # IMPORTANT: accept comma-separated "2,4,5"
    fuel_ids: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    # 1) bounding box filter (fast)
    # ~111km per degree latitude
    dlat = radius_km / 111.0
    # longitude shrinks with latitude
    dlng = radius_km / max(1e-6, (111.0 * cos(radians(lat))))

    min_lat, max_lat = lat - dlat, lat + dlat
    min_lng, max_lng = lng - dlng, lng + dlng

    stmt = (
        select(Site)
        .where(Site.lat.isnot(None))
        .where(Site.lng.isnot(None))
        .where(Site.lat.between(min_lat, max_lat))
        .where(Site.lng.between(min_lng, max_lng))
        .limit(limit * 5)  # grab extra, we'll filter precisely by radius
    )

    rows = (await db.execute(stmt)).scalars().all()

    # 2) precise radius filter + distance sort
    sites_with_dist = []
    for s in rows:
        try:
            d = _haversine_km(lat, lng, float(s.lat), float(s.lng))
        except Exception:
            continue
        if d <= radius_km:
            sites_with_dist.append((s, d))

    sites_with_dist.sort(key=lambda x: x[1])
    sites_with_dist = sites_with_dist[:limit]

    site_ids = [int(s.site_id) for s, _ in sites_with_dist]

    # 3) Prices (optional)
    prices_map: dict[int, list[dict]] = {sid: [] for sid in site_ids}

    if include_prices and site_ids:
        fids = _parse_csv_ints(fuel_ids)

        # if no fuel_ids provided, show ALL fuel types available for these sites
        price_stmt = select(PriceLatest).where(PriceLatest.site_id.in_(site_ids))
        if fids:
            price_stmt = price_stmt.where(PriceLatest.fuel_id.in_(fids))

        price_rows = (await db.execute(price_stmt)).scalars().all()

        # fuel names lookup
        fuel_id_set = sorted({int(p.fuel_id) for p in price_rows})
        fuel_name_map: dict[int, str] = {}
        if fuel_id_set:
            fuel_rows = (await db.execute(select(FuelType).where(FuelType.fuel_id.in_(fuel_id_set)))).scalars().all()
            fuel_name_map = {int(f.fuel_id): f.name for f in fuel_rows}

        for p in price_rows:
            sid = int(p.site_id)
            fid = int(p.fuel_id)

            # if you want to hide unavailable rows:
            # if p.unavailable: continue

            prices_map.setdefault(sid, []).append(
                {
                    "fuelId": fid,
                    "fuelName": fuel_name_map.get(fid),
                    "priceCents": int(p.price_cents) if p.price_cents is not None else None,
                    "unavailable": bool(p.unavailable),
                    "recordedAt": p.transaction_date_utc.isoformat() if p.transaction_date_utc else None,
                }
            )

        # stable order by fuelId
        for sid in prices_map:
            prices_map[sid].sort(key=lambda x: (x["fuelId"] or 0))

    # 4) Response
    return {
        "center": {"lat": lat, "lng": lng},
        "radiusKm": radius_km,
        "count": len(sites_with_dist),
        "sites": [
            {
                "siteId": int(s.site_id),
                "name": s.name,
                "brandId": s.brand_id,
                "address": s.address,
                "postcode": s.postcode,
                "lat": float(s.lat),
                "lng": float(s.lng),
                "distanceKm": round(d, 3),
                "prices": prices_map.get(int(s.site_id), []) if include_prices else None,
            }
            for (s, d) in sites_with_dist
        ],
    }

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
    limit: int = Query(20, ge=1, le=500),
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
            "G1SuburbId": s.g1_suburb_id,
            "G2CityId": s.g2_city_id,
            "G3StateId": s.g3_state_id,
            "Lat": s.lat,
            "Lng": s.lng,
        }
        for s in rows
    ]


@router.get("/catalog/sites/{site_id}")
async def get_site(site_id: int, db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(Site).where(Site.site_id == site_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Site not found")

    # IMPORTANT: your Site model does NOT have suburb/state names.
    # Return ids instead (frontend can still show name using "Name" or later we can join lookup tables).
    return {
        "siteId": row.site_id,
        "name": row.name,
        "brandId": row.brand_id,
        "address": row.address,
        "postcode": row.postcode,
        "g1SuburbId": row.g1_suburb_id,
        "g2CityId": row.g2_city_id,
        "g3StateId": row.g3_state_id,
        "lat": row.lat,
        "lng": row.lng,
    }


@router.get("/catalog/sites/{site_id}/fuels")
async def fuels_available_for_site(site_id: int, db: AsyncSession = Depends(get_db)):
    # fuels available = those with non-unavailable latest rows
    q = await db.execute(
        select(PriceLatest.fuel_id)
        .where(PriceLatest.site_id == site_id)
        .where(PriceLatest.unavailable == False)  # noqa: E712
        .distinct()
    )
    fuel_ids = [r[0] for r in q.all()]
    if not fuel_ids:
        return []

    fq = await db.execute(select(FuelType).where(FuelType.fuel_id.in_(fuel_ids)))
    fuels = fq.scalars().all()

    return [{"fuelId": f.fuel_id, "name": f.name} for f in fuels]




