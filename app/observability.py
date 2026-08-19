"""Observability: structured logging + optional Sentry error tracking.

Both are safe no-ops when unconfigured — the app never depends on them. Sentry
only initialises when SENTRY_DSN is set AND sentry-sdk is installed."""
from __future__ import annotations

import logging

from .config import get_settings

settings = get_settings()


def setup_logging() -> None:
    """Configure root logging once, at the level from LOG_LEVEL."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def setup_sentry() -> bool:
    """Initialise Sentry if a DSN is set and the SDK is available. Returns whether
    it was enabled. Never raises — monitoring must not crash the app."""
    if not settings.sentry_dsn:
        return False
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            traces_sample_rate=0.1,
            send_default_pii=False,
        )
        logging.getLogger("wiora").info("Sentry error tracking enabled")
        return True
    except Exception as e:  # noqa: BLE001 — never let monitoring break startup
        logging.getLogger("wiora").warning("Sentry not enabled: %s", e)
        return False
