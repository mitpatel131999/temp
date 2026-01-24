from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Any, Dict, Optional
from app.db.session import get_db
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.session import get_db
from app.db.models_notifications import UserDevice

router = APIRouter(prefix="/me/notifications", tags=["notifications"])

class ExpoTokenIn(BaseModel):
    expoPushToken: str

@router.post("/expo-token")
async def upsert_expo_token(
    payload: ExpoTokenIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    token = payload.expoPushToken.strip()
    q = await db.execute(select(UserDevice).where(UserDevice.expo_push_token == token))
    existing = q.scalar_one_or_none()

    if existing:
        existing.user_id = user.id
        existing.kind = "expo"
        existing.is_enabled = True
    else:
        db.add(UserDevice(user_id=user.id, kind="expo", expo_push_token=token, is_enabled=True))

    await db.commit()
    return {"ok": True}


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

    q = await db.execute(select(UserDevice).where(UserDevice.webpush_endpoint == endpoint))
    existing = q.scalar_one_or_none()

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


# app/api/v1/notifications.py



class RegisterDeviceBody(BaseModel):
    platform: str = Field(..., description="ios | android | web")
    expo_push_token: Optional[str] = None
    web_push_subscription: Optional[Dict[str, Any]] = None
    device_id: Optional[str] = None
    app_version: Optional[str] = None


@router.post("/register-device")
def register_device(body: RegisterDeviceBody, db: Session = Depends(get_db), me=Depends(get_current_user)):
    # basic validation
    if body.platform in ("ios", "android"):
        if not body.expo_push_token:
            raise HTTPException(status_code=400, detail="expo_push_token required for ios/android")
    elif body.platform == "web":
        if not body.web_push_subscription:
            raise HTTPException(status_code=400, detail="web_push_subscription required for web")
    else:
        raise HTTPException(status_code=400, detail="platform must be ios|android|web")

    # Upsert logic:
    # Prefer matching by expo token or device_id so you don't create duplicates
    q = db.query(UserDevice).filter(UserDevice.user_id == me.id)

    existing = None
    if body.expo_push_token:
        existing = q.filter(UserDevice.expo_push_token == body.expo_push_token).first()
    if existing is None and body.device_id:
        existing = q.filter(UserDevice.device_id == body.device_id).first()

    if existing is None:
        existing = UserDevice(user_id=me.id)

    existing.platform = body.platform
    if body.device_id is not None:
        existing.device_id = body.device_id
    if body.app_version is not None:
        existing.app_version = body.app_version

    if body.expo_push_token:
        existing.expo_push_token = body.expo_push_token

    if body.web_push_subscription:
        existing.web_push_subscription = body.web_push_subscription

    db.add(existing)
    db.commit()
    db.refresh(existing)

    return {"ok": True, "device_id": existing.id}
