from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    FPD_BASE_URL: str = "https://fppdirectapi-prod.fuelpricesqld.com.au"
    FPD_TOKEN: str = "9d37f9ef-0bd3-4d42-acdc-b952a4aa4e4b"
    FPD_COUNTRY_ID: int = 21
    FPD_GEO_LEVEL: int = 3
    FPD_GEO_ID: int = 1

    DB_URL: str = "sqlite+aiosqlite:///./fuel.db"

    SYNC_PRICES_SECONDS: int = 120
    SYNC_MASTER_ON_START: bool = True

    class Config:
        env_file = ".env"

settings = Settings()
