# app/db/session.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import event
from sqlalchemy.pool import StaticPool

DATABASE_URL = "sqlite+aiosqlite:///./fuel.db"
  # whatever you already use

connect_args = {}
engine_kwargs = {"future": True}

if DATABASE_URL.startswith("sqlite"):
    connect_args = {"timeout": 30, "check_same_thread": False}
    engine_kwargs["poolclass"] = StaticPool  # IMPORTANT for sqlite dev

engine = create_async_engine(DATABASE_URL, connect_args=connect_args, **engine_kwargs)

@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute("PRAGMA busy_timeout=30000;")  # 30 seconds
    cursor.close()

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
