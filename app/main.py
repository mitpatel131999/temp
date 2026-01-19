import asyncio
from fastapi import FastAPI
from app.api.router import api
from app.db.init_db import init_db
from app.ingestion.scheduler import start_scheduler

app = FastAPI(title="Fuel App Backend (Ingestion-first)")
app.include_router(api)

@app.on_event("startup")
async def on_startup():
    await init_db()
    # start ingestion scheduler in background
    asyncio.create_task(start_scheduler())
