from datetime import datetime
from sqlalchemy import Integer, Float, DateTime, Boolean, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class PriceLatest(Base):
    """
    Latest-only snapshot (NO history).
    One row per (site_id, fuel_id).
    """
    __tablename__ = "fpd_prices_latest"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(Integer, ForeignKey("fpd_sites.site_id"), nullable=False)
    fuel_id: Mapped[int] = mapped_column(Integer, ForeignKey("fpd_fuel_types.fuel_id"), nullable=False)

    price_raw: Mapped[float] = mapped_column(Float, nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)  # rounded for comparisons
    unavailable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    collection_method: Mapped[str] = mapped_column(String, default="", nullable=False)
    transaction_date_utc: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("site_id", "fuel_id", name="uq_latest_site_fuel"),)
