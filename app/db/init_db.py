# app/db/init_db.py
from app.db.base import Base
from app.db.session import engine

# IMPORTANT: import models so SQLAlchemy registers tables before create_all()
from app.db.models import master, prices, stations
from app.db import models_user, models_rules, models_notifications

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
