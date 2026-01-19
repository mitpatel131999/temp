from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.settings import settings
from app.fpd.client import FPDClient
from app.fpd.parsers import unwrap_list, parse_dt
from app.db.models.master import Brand, FuelType, GeoRegion, Site
from app.db.models.prices import PriceLatest

class IngestionService:
    def __init__(self) -> None:
        self.client = FPDClient()

    async def sync_master(self, db: AsyncSession) -> dict:
        """
        Refresh reference tables: brands, fuels, regions, sites.
        """
        now = datetime.utcnow()
        country_id = settings.FPD_COUNTRY_ID

        # BRANDS
        brands_payload = await self.client.get_brands(country_id)
        brands = unwrap_list(brands_payload, ["Brands"])
        for b in brands:
            bid = int(b["BrandId"])
            name = str(b["Name"])
            obj = await db.get(Brand, bid)
            if obj:
                obj.name = name
                obj.updated_at = now
            else:
                db.add(Brand(brand_id=bid, name=name, updated_at=now))

        # FUELS
        fuels_payload = await self.client.get_fuels(country_id)
        fuels = unwrap_list(fuels_payload, ["Fuels"])
        for f in fuels:
            fid = int(f["FuelId"])
            name = str(f["Name"])
            obj = await db.get(FuelType, fid)
            if obj:
                obj.name = name
                obj.updated_at = now
            else:
                db.add(FuelType(fuel_id=fid, name=name, updated_at=now))

        # REGIONS
        regions_payload = await self.client.get_regions(country_id)
        regions = unwrap_list(regions_payload, ["GeographicRegions"])
        for r in regions:
            rid = int(r["GeoRegionId"])
            obj = await db.get(GeoRegion, rid)
            if obj:
                obj.geo_region_level = int(r["GeoRegionLevel"])
                obj.name = str(r["Name"])
                obj.abbrev = str(r.get("Abbrev") or "")
                obj.parent_geo_region_id = r.get("GeoRegionParentId")
                obj.updated_at = now
            else:
                db.add(
                    GeoRegion(
                        geo_region_id=rid,
                        geo_region_level=int(r["GeoRegionLevel"]),
                        name=str(r["Name"]),
                        abbrev=str(r.get("Abbrev") or ""),
                        parent_geo_region_id=r.get("GeoRegionParentId"),
                        updated_at=now,
                    )
                )

        await db.commit()

        # SITES
        sites_payload = await self.client.get_sites_full(
            country_id,
            settings.FPD_GEO_LEVEL,
            settings.FPD_GEO_ID,
        )
        sites = unwrap_list(sites_payload, ["S"])

        for s in sites:
            site_id = int(s["S"])
            brand_id = int(s["B"])

            # ensure brand exists (avoid FK issues if API order weird)
            if not await db.get(Brand, brand_id):
                db.add(Brand(brand_id=brand_id, name=f"Brand {brand_id}", updated_at=now))
                await db.flush()

            known = {"S","A","N","B","P","G1","G2","G3","G4","G5","Lat","Lng","M","GPI"}
            extra = {k: v for k, v in s.items() if k not in known}

            obj = await db.get(Site, site_id)
            if obj:
                obj.name = str(s.get("N") or "")
                obj.address = str(s.get("A") or "")
                obj.brand_id = brand_id
                obj.postcode = str(s.get("P") or "")
                obj.g1_suburb_id = int(s.get("G1") or 0)
                obj.g2_city_id = int(s.get("G2") or 0)
                obj.g3_state_id = int(s.get("G3") or 0)
                obj.lat = s.get("Lat")
                obj.lng = s.get("Lng")
                obj.last_modified_at = parse_dt(s.get("M"))
                obj.google_place_id = s.get("GPI")
                obj.extra = extra or None
                obj.updated_at = now
            else:
                db.add(
                    Site(
                        site_id=site_id,
                        name=str(s.get("N") or ""),
                        address=str(s.get("A") or ""),
                        brand_id=brand_id,
                        postcode=str(s.get("P") or ""),
                        g1_suburb_id=int(s.get("G1") or 0),
                        g2_city_id=int(s.get("G2") or 0),
                        g3_state_id=int(s.get("G3") or 0),
                        lat=s.get("Lat"),
                        lng=s.get("Lng"),
                        last_modified_at=parse_dt(s.get("M")),
                        google_place_id=s.get("GPI"),
                        extra=extra or None,
                        updated_at=now,
                    )
                )

        await db.commit()
        return {"brands": len(brands), "fuels": len(fuels), "regions": len(regions), "sites": len(sites)}

    async def sync_prices_latest(self, db: AsyncSession) -> dict:
        """
        Refresh latest prices snapshot (no history).
        """
        payload = await self.client.get_site_prices(
            settings.FPD_COUNTRY_ID, settings.FPD_GEO_LEVEL, settings.FPD_GEO_ID
        )
        items = unwrap_list(payload, ["SitePrices"])  # supports array or wrapper

        now = datetime.utcnow()
        updated = 0
        skipped_missing_site = 0

        for p in items:
            site_id = int(p["SiteId"])
            fuel_id = int(p["FuelId"])
            dt = parse_dt(p.get("TransactionDateUtc"))
            if not dt:
                continue

            # must have site in DB (sync master first)
            if not await db.get(Site, site_id):
                skipped_missing_site += 1
                continue

            # ensure fuel exists
            if not await db.get(FuelType, fuel_id):
                db.add(FuelType(fuel_id=fuel_id, name=f"Fuel {fuel_id}", updated_at=now))
                await db.flush()

            price_raw = float(p["Price"])
            unavailable = (price_raw == 9999.0)
            price_cents = int(round(price_raw))
            collection_method = str(p.get("CollectionMethod") or "")

            q = await db.execute(
                select(PriceLatest).where(PriceLatest.site_id == site_id, PriceLatest.fuel_id == fuel_id)
            )
            existing = q.scalar_one_or_none()

            if existing:
                existing.price_raw = price_raw
                existing.price_cents = price_cents
                existing.unavailable = unavailable
                existing.collection_method = collection_method
                existing.transaction_date_utc = dt
                existing.ingested_at = now
            else:
                db.add(
                    PriceLatest(
                        site_id=site_id,
                        fuel_id=fuel_id,
                        price_raw=price_raw,
                        price_cents=price_cents,
                        unavailable=unavailable,
                        collection_method=collection_method,
                        transaction_date_utc=dt,
                        ingested_at=now,
                    )
                )
            updated += 1

        await db.commit()
        return {"fetched": len(items), "updated": updated, "skipped_missing_site": skipped_missing_site}
