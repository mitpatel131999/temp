# db/models/stations.py
import uuid
from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

class UserOwnedSite(Base):
    __tablename__ = "user_owned_sites"   # ✅ MUST match this exact string

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
    )

    site_id: Mapped[int] = mapped_column(nullable=False)  # later FK to fpd_sites.site_id
    nickname: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
