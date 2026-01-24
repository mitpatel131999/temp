# app/services/push_service.py
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import httpx

try:
    from pywebpush import webpush  # type: ignore
except Exception:
    webpush = None

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"

VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_SUBJECT = os.getenv("VAPID_SUBJECT", "mailto:admin@example.com")


def _is_expo_token(t: str) -> bool:
    return isinstance(t, str) and (t.startswith("ExponentPushToken[") or t.startswith("ExpoPushToken["))


def _build_expo_message(
    token: str,
    title: str,
    body: str,
    data: Dict[str, Any],
    *,
    # Alert tuning:
    sound: str = "default",  # "default" OR "alert.wav" / "alert.mp3" (custom only works in EAS builds)
    channel_id: str = "alerts",  # MUST match Android channel you create in app
    ttl_seconds: int = 60 * 30,  # 30 minutes
    badge: Optional[int] = None,  # iOS badge number (optional)
) -> Dict[str, Any]:
    """
    Expo push payload that works on:
    ✅ iOS / Android (standalone builds)
    ✅ Expo Go (with some limitations)
    ✅ app closed / killed (as long as permissions granted + token valid)

    Notes:
    - Android "channelId" is critical for loud alerts & custom sounds.
    - iOS custom sounds require the sound file bundled in the app build.
    """
    msg: Dict[str, Any] = {
        "to": token,
        "title": title,
        "body": body,
        "data": data,
        # Works for both platforms; custom only if bundled:
        "sound": sound,

        # Delivery tuning:
        "priority": "high",
        "ttl": ttl_seconds,
    }

    # Android-specific (best-effort; ignored elsewhere)
    msg["channelId"] = channel_id

    # iOS-specific (best-effort; ignored elsewhere)
    if badge is not None:
        msg["badge"] = badge

    # Some clients support these (safe to include; ignored if unsupported)
    # msg["subtitle"] = "Fuel Alert"
    # msg["categoryId"] = "ALERTS"  # If you implement iOS categories/actions
    # msg["mutableContent"] = True  # For rich notifications (images) if configured

    return msg


async def send_expo_push(
    expo_tokens: List[str],
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None,
    *,
    # 👇 Add these options so your scheduler can request "ALERT" behavior
    is_alert: bool = True,
    # If you bundle a custom sound in EAS builds, set this to "alert.wav" (recommended)
    custom_sound_name: Optional[str] = None,
    android_channel_id: str = "alerts",
    ttl_seconds: int = 60 * 30,
    badge: Optional[int] = None,
) -> None:
    """
    Sends push via Expo service.

    IMPORTANT:
    - Expo Go: many things work, but custom sounds/channels can be limited.
    - Standalone builds (EAS): full support for channels + custom sounds (if configured).
    """
    if not expo_tokens:
        return

    expo_tokens = [t for t in expo_tokens if _is_expo_token(t)]
    if not expo_tokens:
        return

    payload_data = data or {}

    # Decide sound:
    # - For alert: default sound works everywhere.
    # - Custom sound only works if bundled in the native app build.
    sound = "default"
    if is_alert and custom_sound_name:
        sound = custom_sound_name  # e.g. "alert.wav" or "alert.mp3"

    messages: List[Dict[str, Any]] = []
    for token in expo_tokens:
        messages.append(
            _build_expo_message(
                token=token,
                title=title,
                body=body,
                data=payload_data,
                sound=sound,
                channel_id=android_channel_id,
                ttl_seconds=ttl_seconds,
                badge=badge,
            )
        )

    async with httpx.AsyncClient(timeout=15) as client:
        # Expo recommends chunking
        for i in range(0, len(messages), 100):
            chunk = messages[i : i + 100]
            r = await client.post(EXPO_PUSH_URL, json=chunk)
            r.raise_for_status()

            resp = r.json()
            tickets = resp.get("data", [])

            # If any tickets are errors, log + cleanup token in DB
            for t in tickets:
                if t.get("status") == "error":
                    # TODO: log t and disable token in DB if DeviceNotRegistered
                    # Example:
                    # {"status":"error","message":"DeviceNotRegistered","details":{...}}
                    pass


def send_web_push(
    subscriptions: List[Dict[str, Any]],
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Browser push (Chrome/Edge/Firefox + Safari PWA with iOS 16.4+ limitations).

    NOTE:
    - Browsers generally ignore custom sounds.
    - OS controls sound.
    """
    if not subscriptions or webpush is None:
        return
    if not (VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY):
        return

    payload = json.dumps({"title": title, "body": body, "data": data or {}})

    for sub in subscriptions:
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": VAPID_SUBJECT},
            )
        except Exception:
            # TODO: log + possibly delete invalid subscription from DB
            pass
