from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.models_notifications import UserDevice
from app.db.session import get_db

router = APIRouter(prefix="/me/notifications", tags=["notifications"])


# ----------------------------
# Expo token (mobile)
# ----------------------------
class ExpoTokenIn(BaseModel):
    expoPushToken: str


@router.post("/expo-token")
async def upsert_expo_token(
    payload: ExpoTokenIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    token = payload.expoPushToken.strip()
    if not token:
        raise HTTPException(status_code=400, detail="expoPushToken required")

    res = await db.execute(
        select(UserDevice).where(UserDevice.expo_push_token == token)
    )
    existing = res.scalar_one_or_none()

    if existing:
        existing.user_id = user.id
        existing.kind = "expo"
        existing.is_enabled = True
    else:
        db.add(
            UserDevice(
                user_id=user.id,
                kind="expo",
                expo_push_token=token,
                is_enabled=True,
            )
        )

    await db.commit()
    return {"ok": True}


# ----------------------------
# Web push (browser)
# ----------------------------
class WebPushIn(BaseModel):
    endpoint: str
    p256dh: str
    auth: str


@router.post("/webpush-subscription")
async def upsert_webpush(
    payload: WebPushIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    endpoint = payload.endpoint.strip()
    if not endpoint:
        raise HTTPException(status_code=400, detail="endpoint required")

    res = await db.execute(
        select(UserDevice).where(UserDevice.webpush_endpoint == endpoint)
    )
    existing = res.scalar_one_or_none()

    if existing:
        existing.user_id = user.id
        existing.kind = "webpush"
        existing.webpush_p256dh = payload.p256dh
        existing.webpush_auth = payload.auth
        existing.is_enabled = True
    else:
        db.add(
            UserDevice(
                user_id=user.id,
                kind="webpush",
                webpush_endpoint=endpoint,
                webpush_p256dh=payload.p256dh,
                webpush_auth=payload.auth,
                is_enabled=True,
            )
        )

    await db.commit()
    return {"ok": True}


# ----------------------------
# Register Device (unified)
# ----------------------------
class RegisterDeviceBody(BaseModel):
    platform: str = Field(..., description="ios | android | web")
    expo_push_token: Optional[str] = None
    web_push_subscription: Optional[Dict[str, Any]] = None
    device_id: Optional[str] = None
    app_version: Optional[str] = None


@router.post("/register-device")
async def register_device(
    body: RegisterDeviceBody,
    db: AsyncSession = Depends(get_db),
    me=Depends(get_current_user),
):
    platform = body.platform.strip().lower()

    # ----------------------------
    # Validation
    # ----------------------------
    if platform in ("ios", "android"):
        if not body.expo_push_token:
            raise HTTPException(
                status_code=400,
                detail="expo_push_token required for ios/android",
            )
        device_kind = "expo"

    elif platform == "web":
        if not body.web_push_subscription:
            raise HTTPException(
                status_code=400,
                detail="web_push_subscription required for web",
            )
        device_kind = "webpush"

    else:
        raise HTTPException(
            status_code=400,
            detail="platform must be ios|android|web",
        )

    # ----------------------------
    # Find existing device
    # ----------------------------
    existing: Optional[UserDevice] = None

    if body.expo_push_token:
        res = await db.execute(
            select(UserDevice).where(
                UserDevice.user_id == me.id,
                UserDevice.expo_push_token == body.expo_push_token,
            )
        )
        existing = res.scalars().first()

    if existing is None and body.device_id:
        res = await db.execute(
            select(UserDevice).where(
                UserDevice.user_id == me.id,
                UserDevice.device_id == body.device_id,
            )
        )
        existing = res.scalars().first()

    if existing is None:
        existing = UserDevice(
            user_id=me.id,
            kind=device_kind,   # ✅ FIX: SET KIND ON CREATE
        )
        db.add(existing)

    # ----------------------------
    # Update fields
    # ----------------------------
    existing.kind = device_kind            # ✅ ALWAYS SET
    existing.platform = platform
    existing.is_enabled = True

    if body.device_id:
        existing.device_id = body.device_id

    if body.app_version:
        existing.app_version = body.app_version

    if body.expo_push_token:
        existing.expo_push_token = body.expo_push_token

    if body.web_push_subscription:
        existing.web_push_subscription = body.web_push_subscription

    await db.commit()
    await db.refresh(existing)

    return {"ok": True, "device_id": existing.id}
