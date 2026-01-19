import asyncio
from app.core.settings import settings
from app.db.session import SessionLocal
from app.ingestion.service import IngestionService
from app.ingestion.lock import INGESTION_LOCK

async def start_scheduler():
    svc = IngestionService()

    if settings.SYNC_MASTER_ON_START:
        async with SessionLocal() as db:
            async with INGESTION_LOCK:
                try:
                    await svc.sync_master(db)
                except Exception:
                    pass

    while True:
        try:
            async with SessionLocal() as db:
                async with INGESTION_LOCK:
                    await svc.sync_prices_latest(db)
        except Exception:
            pass

        await asyncio.sleep(settings.SYNC_PRICES_SECONDS)
