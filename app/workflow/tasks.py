"""Celery tasks: deliver due reminders + daily briefing push.

These read the DB directly (worker context, not a FastAPI request) and send push
via services/push. All side effects degrade gracefully: no FCM token or no
credentials → the task logs and moves on."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select

from .. import cache
from ..db import SessionLocal
from ..models import Preference, Reminder
from ..services.push import send_push
from .celery_app import celery

logger = logging.getLogger("wiora.workflow")


def _fcm_token(db, user_id: str) -> str | None:
    """Device push token, stored as a per-user preference (key 'fcmToken')."""
    row = db.get(Preference, {"user_id": user_id, "key": "fcmToken"})
    return row.value if row else None


@celery.task
def deliver_due_reminders() -> int:
    """Push any reminder whose time has arrived and hasn't been pushed yet.

    Dedup via a short-lived Redis key so a reminder fires once even though this
    runs every minute. Returns the number of pushes sent."""
    now = datetime.now(timezone.utc)
    sent = 0
    db = SessionLocal()
    try:
        due = db.execute(
            select(Reminder).where(Reminder.done.is_(False), Reminder.due_at.isnot(None))
        ).scalars().all()
        for r in due:
            if r.due_at and r.due_at <= now:
                if cache.cache_get(f"remsent:{r.id}"):
                    continue  # already pushed
                token = _fcm_token(db, r.user_id)
                if token and send_push(token, "Wiora reminder", r.text):
                    sent += 1
                    cache.cache_set(f"remsent:{r.id}", "1", ttl_seconds=86400)
    finally:
        db.close()
    logger.info("deliver_due_reminders: sent %d", sent)
    return sent


@celery.task
def send_daily_briefings() -> int:
    """Morning briefing push to every user with a registered device token.

    Scaffold: sends a nudge to open the app for the full briefing. Wire the real
    briefing generator (routers/briefing) here once per-user timezones are stored."""
    sent = 0
    db = SessionLocal()
    try:
        tokens = db.execute(
            select(Preference).where(Preference.key == "fcmToken")
        ).scalars().all()
        for p in tokens:
            if send_push(p.value, "Good morning ☀️", "Your Wiora daily briefing is ready."):
                sent += 1
    finally:
        db.close()
    logger.info("send_daily_briefings: sent %d", sent)
    return sent
