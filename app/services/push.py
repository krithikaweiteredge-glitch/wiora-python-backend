"""Push notifications via Firebase Cloud Messaging (FCM).

Optional + graceful: if no service-account credentials are configured (or
firebase-admin isn't installed), send_push is a safe no-op that returns False.
Enable with `pip install firebase-admin` plus EITHER
  - FCM_CREDENTIALS_JSON: the service-account JSON pasted as an env var
    (recommended on Render/hosts where you can't drop a file), or
  - FCM_CREDENTIALS_PATH: a path to the service-account JSON file."""
from __future__ import annotations

import json
import logging

from ..config import get_settings

settings = get_settings()
logger = logging.getLogger("wiora.push")

_app = None
_ready = False


def _load_credentials():
    """Build a firebase_admin Certificate from JSON-in-env or a file path.
    Returns the credential, or None if neither is configured/valid."""
    from firebase_admin import credentials

    raw = settings.fcm_credentials_json.strip()
    if raw:
        # Paste-as-env: accept the service-account JSON directly. Certificate()
        # takes a dict, so we parse the string first.
        return credentials.Certificate(json.loads(raw))
    if settings.fcm_credentials_path:
        return credentials.Certificate(settings.fcm_credentials_path)
    return None


def _ensure() -> bool:
    """Lazily initialise the Firebase Admin app. Returns whether push is usable."""
    global _app, _ready
    if _ready:
        return True
    if not (settings.fcm_credentials_json or settings.fcm_credentials_path):
        return False
    try:
        import firebase_admin

        cred = _load_credentials()
        if cred is None:
            return False
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
