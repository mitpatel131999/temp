# app/db/models_notifications.py
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

def now_utc() -> datetime:
    return datetime.utcnow()

class UserDevice(Base):
    __tablename__ = "user_devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True, nullable=False)

    # "expo" or "webpush"
    kind: Mapped[str] = mapped_column(String(20), index=True, nullable=False)

    # Expo:
    expo_push_token: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)

    # WebPush:
    webpush_endpoint: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    webpush_p256dh: Mapped[str | None] = mapped_column(Text, nullable=True)
    webpush_auth: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, onupdate=now_utc, nullable=False)


# app/db/models_notifications.py (same file, add this)
from sqlalchemy import Integer

class RuleAlertState(Base):
    __tablename__ = "rule_alert_state"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True, nullable=False)

    rule_id: Mapped[str] = mapped_column(String(36), ForeignKey("pricing_rules.id"), index=True, nullable=False)
    condition_id: Mapped[str] = mapped_column(String(36), ForeignKey("pricing_rule_conditions.id"), index=True, nullable=False)

    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # optional: store last diff that triggered
    last_diff_raw: Mapped[int | None] = mapped_column(Integer, nullable=True)
