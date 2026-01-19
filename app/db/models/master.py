from datetime import datetime
from sqlalchemy import Integer, String, DateTime, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON
from app.db.base import Base

class Brand(Base):
    __tablename__ = "fpd_brands"
    brand_id: Mapped[int] = mapped_column(Integer, primary_key=True)  # BrandId
    name: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

class FuelType(Base):
    __tablename__ = "fpd_fuel_types"
    fuel_id: Mapped[int] = mapped_column(Integer, primary_key=True)  # FuelId
    name: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

class GeoRegion(Base):
    __tablename__ = "fpd_geo_regions"
    geo_region_id: Mapped[int] = mapped_column(Integer, primary_key=True)  # GeoRegionId
    geo_region_level: Mapped[int] = mapped_column(Integer, nullable=False)  # 1/2/3
    name: Mapped[str] = mapped_column(String, nullable=False)
    abbrev: Mapped[str] = mapped_column(String, default="", nullable=False)
    parent_geo_region_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

class Site(Base):
    __tablename__ = "fpd_sites"

    site_id: Mapped[int] = mapped_column(Integer, primary_key=True)  # "S"
    name: Mapped[str] = mapped_column(String, nullable=False)        # "N"
    address: Mapped[str] = mapped_column(String, nullable=False)     # "A"
    brand_id: Mapped[int] = mapped_column(Integer, ForeignKey("fpd_brands.brand_id"), nullable=False)  # "B"
    postcode: Mapped[str] = mapped_column(String, nullable=False)    # "P"

    g1_suburb_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # G1
    g2_city_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)    # G2
    g3_state_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)   # G3

    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)

    last_modified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # "M"
    google_place_id: Mapped[str | None] = mapped_column(String, nullable=True)         # "GPI"

    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # unknown keys
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    brand = relationship("Brand")
