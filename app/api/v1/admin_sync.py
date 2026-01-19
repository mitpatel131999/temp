from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.ingestion.service import IngestionService
from app.ingestion.lock import INGESTION_LOCK

router = APIRouter()
svc = IngestionService()

@router.post("/admin/sync/master")
async def sync_master(db: AsyncSession = Depends(get_db)):
    async with INGESTION_LOCK:
        return await svc.sync_master(db)

@router.post("/admin/sync/prices")
async def sync_prices(db: AsyncSession = Depends(get_db)):
    async with INGESTION_LOCK:
        return await svc.sync_prices_latest(db)
