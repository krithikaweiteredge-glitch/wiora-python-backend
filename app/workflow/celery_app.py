"""Celery application + beat schedule.

Run (needs a Redis broker at REDIS_URL / CELERY_BROKER_URL):
    celery -A app.workflow.celery_app.celery worker --loglevel=info
    celery -A app.workflow.celery_app.celery beat --loglevel=info
"""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from ..config import get_settings

settings = get_settings()

# Fall back to a local broker so importing this module never fails even when
# REDIS_URL is unset; the worker simply won't connect until a real broker is set.
_broker = settings.broker_url or "redis://localhost:6379/0"

celery = Celery("wiora", broker=_broker, backend=_broker)
celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    beat_schedule={
        # Deliver reminders whose time has arrived — every minute.
        "deliver-due-reminders": {
            "task": "app.workflow.tasks.deliver_due_reminders",
            "schedule": 60.0,
        },
        # Morning briefing push — 7:00 UTC daily (adjust per user tz later).
        "daily-briefing-push": {
            "task": "app.workflow.tasks.send_daily_briefings",
            "schedule": crontab(hour=7, minute=0),
        },
        # Fire time-triggered automations — every minute.
        "run-automations": {
            "task": "app.workflow.tasks.run_due_automations",
            "schedule": 60.0,
        },
    },
)

# Ensure tasks are registered when the worker imports this module.
from . import tasks  # noqa: E402,F401
