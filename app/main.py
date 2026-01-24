import asyncio
from fastapi import FastAPI
from app.api.router import api
from app.db.init_db import init_db
from app.ingestion.scheduler import start_scheduler
from fastapi.middleware.cors import CORSMiddleware
from app.notifications.alert_scheduler import start_alert_scheduler

app = FastAPI(title="Fuel App Backend (Ingestion-first)")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(api)

@app.on_event("startup")
async def on_startup():
    await init_db()
    # start ingestion scheduler in background
    asyncio.create_task(start_scheduler())
    asyncio.create_task(start_alert_scheduler())
