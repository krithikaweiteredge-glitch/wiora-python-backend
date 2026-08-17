"""Daily Briefing (blueprint V2 §9): a personalized morning summary of the user's
day — today's calendar events, pending tasks and reminders due — plus a short,
warm natural-language summary from the assistant. Reads existing data only; no
new infrastructure needed."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.service import ai_service
from ..auth import current_user
from ..db import get_db
from ..models import Reminder, Task
from ..schemas import BriefingEvent, BriefingItem, BriefingOut, BriefingRequest
from ..services import calendar as cal

router = APIRouter()


def _parse_now(client_now: str | None) -> datetime:
    """The phone's local time (with offset) so 'today' is the user's day, not UTC."""
    if client_now:
        try:
            return datetime.fromisoformat(client_now.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _greeting(hour: int) -> str:
    if hour < 12:
        return "Good morning"
    if hour < 17:
        return "Good afternoon"
    return "Good evening"


def _summarize(
    greeting: str,
    date_label: str,
    events: list[BriefingEvent],
    tasks: list[BriefingItem],
    reminders: list[BriefingItem],
    calendar_connected: bool,
) -> str:
    lines = [f"{greeting}. Today is {date_label}."]
    if events:
        lines.append("Calendar today:")
        for e in events:
            loc = f" — {e.location}" if e.location else ""
            lines.append(f"- {e.summary} (starts {e.start}){loc}")
    elif calendar_connected:
        lines.append("Calendar today: nothing scheduled.")
    else:
        lines.append("Calendar: not connected.")
    if reminders:
        lines.append("Reminders due:")
        lines += [f"- {r.text}" for r in reminders]
    if tasks:
        lines.append("Pending tasks:")
        lines += [f"- {t.text}" for t in tasks]
    data = "\n".join(lines)

    system = (
        "You are Wiora, a warm, upbeat personal assistant giving a short morning "
        "briefing. In 2-4 friendly sentences, summarize the user's day from the data "
        "below — highlight what matters most, be encouraging, and don't just repeat "
        "every item verbatim. If the day is empty, say it looks open and offer to help "
        "plan it. Speak directly to the user."
    )
    try:
        text = ai_service.generate(system, [{"role": "user", "content": data}])
        return text or data
    except Exception:
        return data


@router.post("/api/briefing", response_model=BriefingOut)
def daily_briefing(
    body: BriefingRequest,
    user_id: str = Depends(current_user),
    db: Session = Depends(get_db),
):
    now = _parse_now(body.clientNow)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    date_label = now.strftime("%A, %d %B")
    greeting = _greeting(now.hour)

    # --- Today's calendar events (needs the phone's Google token) ---
    events: list[BriefingEvent] = []
    calendar_connected = bool(body.googleAccessToken)
    if body.googleAccessToken:
        try:
            for e in cal.list_events(
                body.googleAccessToken, start.isoformat(), end.isoformat(), max_results=15
            ):
                events.append(
                    BriefingEvent(
                        summary=e.get("summary", "(no title)"),
                        start=e.get("start", ""),
                        location=e.get("location", ""),
                    )
                )
        except Exception:
            calendar_connected = False  # token expired / not granted calendar scope

    # --- Reminders due today or overdue, not yet done ---
    rem_rows = db.execute(
        select(Reminder).where(Reminder.user_id == user_id, Reminder.done.is_(False))
    ).scalars().all()
    due = [r for r in rem_rows if r.due_at is not None and r.due_at < end]
    due.sort(key=lambda r: r.due_at)
    reminders = [BriefingItem(id=r.id, text=r.text, dueAt=r.due_at.isoformat()) for r in due]

    # --- Pending tasks (most recent first, capped) ---
    task_rows = db.execute(
        select(Task)
        .where(Task.user_id == user_id, Task.done.is_(False))
        .order_by(Task.id.desc())
        .limit(10)
    ).scalars().all()
    tasks = [
        BriefingItem(id=t.id, text=t.text, dueAt=t.due_at.isoformat() if t.due_at else None)
        for t in task_rows
    ]

    summary = _summarize(greeting, date_label, events, tasks, reminders, calendar_connected)

    return BriefingOut(
        greeting=greeting,
        dateLabel=date_label,
        summary=summary,
        events=events,
        tasks=tasks,
        reminders=reminders,
    )
