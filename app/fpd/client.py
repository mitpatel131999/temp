import httpx
from app.core.settings import settings

class FPDClient:
    def __init__(self) -> None:
        self.base = settings.FPD_BASE_URL.rstrip("/")

    def _headers(self) -> dict:
        # Required format:
        # Authorization: FPDAPI SubscriberToken=<token>
        return {"Authorization": f"FPDAPI SubscriberToken={settings.FPD_TOKEN}"}

    async def get_json(self, path: str, params: dict | None = None):
        url = f"{self.base}{path}"
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.get(url, params=params, headers=self._headers())
            r.raise_for_status()
            return r.json()

    async def get_brands(self, country_id: int):
        return await self.get_json("/Subscriber/GetCountryBrands", {"countryId": country_id})

    async def get_fuels(self, country_id: int):
        return await self.get_json("/Subscriber/GetCountryFuelTypes", {"countryId": country_id})

    async def get_regions(self, country_id: int):
        return await self.get_json("/Subscriber/GetCountryGeographicRegions", {"countryId": country_id})

    async def get_sites_full(self, country_id: int, geo_level: int, geo_id: int):
        return await self.get_json(
            "/Subscriber/GetFullSiteDetails",
            {"countryId": country_id, "geoRegionLevel": geo_level, "geoRegionId": geo_id},
        )

    async def get_site_prices(self, country_id: int, geo_level: int, geo_id: int):
        return await self.get_json(
            "/Price/GetSitesPrices",
            {"countryId": country_id, "geoRegionLevel": geo_level, "geoRegionId": geo_id},
        )
