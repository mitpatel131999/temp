from fastapi import APIRouter, Depends
from pydantic import BaseModel
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
