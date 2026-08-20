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
from ..models import Automation, Preference, Reminder, Task
from ..services.push import send_push
from .celery_app import celery

logger = logging.getLogger("wiora.workflow")


def compose_briefing(db, user_id: str) -> str:
    """A proactive briefing built from Postgres data (no Google token needed):
    today's due reminders + open tasks. Calendar/email need the phone's token, so
    those stay in the on-demand /api/briefing."""
    now = datetime.now(timezone.utc)
    end = now.replace(hour=23, minute=59, second=59)
    rem = db.execute(
        select(Reminder).where(
            Reminder.user_id == user_id, Reminder.done.is_(False),
            Reminder.due_at.isnot(None), Reminder.due_at <= end,
        )
    ).scalars().all()
    tasks = db.execute(
        select(Task).where(Task.user_id == user_id, Task.done.is_(False))
    ).scalars().all()
    parts = []
    if rem:
        parts.append(f"{len(rem)} reminder(s) due today: " + "; ".join(r.text for r in rem[:5]))
    if tasks:
        parts.append(f"{len(tasks)} open task(s): " + "; ".join(t.text for t in tasks[:5]))
    return " ".join(parts) if parts else "Nothing scheduled — enjoy your day!"


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
    """Morning briefing push to every user with a registered device token — now with
    a real summary of today's reminders + tasks (calendar/email stay on-demand)."""
    sent = 0
    db = SessionLocal()
    try:
        tokens = db.execute(
            select(Preference).where(Preference.key == "fcmToken")
        ).scalars().all()
        for p in tokens:
            body = compose_briefing(db, p.user_id)
            if send_push(p.value, "Good morning ☀️", body):
                sent += 1
    finally:
        db.close()
    logger.info("send_daily_briefings: sent %d", sent)
    return sent


def _do_action(db, a: Automation) -> None:
    """Execute an automation's action."""
    from datetime import datetime as _dt, timezone as _tz

    if a.action_type == "briefing":
        pref = db.get(Preference, {"user_id": a.user_id, "key": "fcmToken"})
        if pref:
            send_push(pref.value, "Wiora briefing ☀️", compose_briefing(db, a.user_id))
    elif a.action_type == "reminder" and a.action_text:
        db.add(Reminder(user_id=a.user_id, text=a.action_text, due_at=_dt.now(_tz.utc)))
    elif a.action_type == "agent" and a.action_text:
        try:
            from ..agent.runner import run_agent
            from ..tools.base import ToolContext

            ctx = ToolContext(db=db, user_id=a.user_id)
            run_agent(db, a.user_id, a.action_text, ctx, _dt.now(_tz.utc).isoformat())
        except Exception as e:  # noqa: BLE001
            logger.warning("automation agent action failed: %s", e)


@celery.task
def run_due_automations() -> int:
    """Fire time-triggered automations whose HH:MM (UTC) has arrived, once per day.
    Runs every minute via beat."""
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    ran = 0
    db = SessionLocal()
    try:
        autos = db.execute(select(Automation).where(Automation.enabled.is_(True))).scalars().all()
        for a in autos:
            if a.hour != now.hour or a.minute != now.minute:
                continue
            if a.trigger_type == "weekly" and a.weekday is not None and a.weekday != now.weekday():
                continue
            if a.last_run_date == today:
                continue  # already ran today
            _do_action(db, a)
            a.last_run_date = today
            ran += 1
        db.commit()
    finally:
        db.close()
    logger.info("run_due_automations: ran %d", ran)
    return ran
