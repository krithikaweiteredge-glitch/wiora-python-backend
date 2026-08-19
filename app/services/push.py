"""Push notifications via Firebase Cloud Messaging (FCM).

Optional + graceful: if no service-account credentials are configured (or
firebase-admin isn't installed), send_push is a safe no-op that returns False.
Enable with:  pip install firebase-admin  +  set FCM_CREDENTIALS_PATH."""
from __future__ import annotations

import logging

from ..config import get_settings

settings = get_settings()
logger = logging.getLogger("wiora.push")

_app = None
_ready = False


def _ensure() -> bool:
    """Lazily initialise the Firebase Admin app. Returns whether push is usable."""
    global _app, _ready
    if _ready:
        return True
    if not settings.fcm_credentials_path:
        return False
    try:
        import firebase_admin
        from firebase_admin import credentials

        cred = credentials.Certificate(settings.fcm_credentials_path)
        _app = firebase_admin.initialize_app(cred)
        _ready = True
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning("FCM not initialised: %s", e)
        return False


def send_push(device_token: str, title: str, body: str) -> bool:
    """Send one push. Returns True if handed to FCM, False if disabled/failed."""
    if not device_token or not _ensure():
        return False
    try:
        from firebase_admin import messaging

        messaging.send(
            messaging.Message(
                token=device_token,
                notification=messaging.Notification(title=title, body=body),
            )
        )
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning("push send failed: %s", e)
        return False
