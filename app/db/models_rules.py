import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean, Integer, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

def now_utc() -> datetime:
    return datetime.utcnow()

class PricingRule(Base):
    __tablename__ = "pricing_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True, nullable=False)

    owned_site_id: Mapped[str] = mapped_column(String(36), ForeignKey("user_owned_sites.id"), index=True, nullable=False)
    competitor_site_id: Mapped[int] = mapped_column(Integer, ForeignKey("fpd_sites.site_id"), index=True, nullable=False)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, onupdate=now_utc, nullable=False)

    conditions = relationship("PricingRuleCondition", back_populates="rule", cascade="all, delete-orphan")

class PricingRuleCondition(Base):
    __tablename__ = "pricing_rule_conditions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rule_id: Mapped[str] = mapped_column(String(36), ForeignKey("pricing_rules.id"), index=True, nullable=False)

    own_fuel_id: Mapped[int] = mapped_column(Integer, ForeignKey("fpd_fuel_types.fuel_id"), nullable=False)
    competitor_fuel_id: Mapped[int] = mapped_column(Integer, ForeignKey("fpd_fuel_types.fuel_id"), nullable=False)

    direction: Mapped[str] = mapped_column(String(30), nullable=False)     # COMPETITOR_MINUS_OWN / OWN_MINUS_COMPETITOR
    comparator: Mapped[str] = mapped_column(String(10), nullable=False)    # GT,GTE,LT,LTE,ABS_GT,ABS_GTE
    threshold_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    require_both_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False)

    rule = relationship("PricingRule", back_populates="conditions")
