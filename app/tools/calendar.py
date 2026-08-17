"""Google Calendar tools (backend). ISO string args only (avoids Groq's strict
number-as-string rejection)."""
from pydantic import BaseModel, Field

from ..services.calendar import (
    create_event,
    delete_event,
    find_free_slots,
    list_events,
    update_event,
)
from .base import Tool, ToolContext

NOT_CONNECTED = "Google Calendar is not connected. Ask the user to connect Google in Settings first."


class WindowArgs(BaseModel):
    timeMin: str = Field(min_length=1, max_length=40)
    timeMax: str = Field(min_length=1, max_length=40)


def _events(args: WindowArgs, ctx: ToolContext) -> str:
    if not ctx.google_access_token:
        return NOT_CONNECTED
    evs = list_events(ctx.google_access_token, args.timeMin, args.timeMax, 10)
    if not evs:
        return "No events in that time range."
    # Include the event id so update/cancel can reference a specific event.
    return "\n".join(
        f"id:{e['id']} | {e['start']} → {e['end']} | {e['summary']}"
        + (f" @ {e['location']}" if e["location"] else "")
        for e in evs
    )


get_calendar_events_tool = Tool(
    name="get_calendar_events",
    description="List calendar events between two ISO 8601 datetimes (with offset).",
    parameters={
        "type": "object",
        "properties": {"timeMin": {"type": "string"}, "timeMax": {"type": "string"}},
        "required": ["timeMin", "timeMax"],
        "additionalProperties": False,
    },
    args_model=WindowArgs,
    confirmation="never",
    runs_on="backend",
    execute=_events,
)


def _free(args: WindowArgs, ctx: ToolContext) -> str:
    if not ctx.google_access_token:
        return NOT_CONNECTED
    slots = find_free_slots(ctx.google_access_token, args.timeMin, args.timeMax, 30)
    if not slots:
        return "No free slots of 30+ minutes in that window."
    return "\n".join(f"{s['start']} → {s['end']}" for s in slots)


find_free_time_tool = Tool(
    name="find_free_time",
    description="Find free 30-minute+ gaps between two ISO 8601 datetimes.",
    parameters={
        "type": "object",
        "properties": {"timeMin": {"type": "string"}, "timeMax": {"type": "string"}},
        "required": ["timeMin", "timeMax"],
        "additionalProperties": False,
    },
    args_model=WindowArgs,
    confirmation="never",
    runs_on="backend",
    execute=_free,
)


class CreateEventArgs(BaseModel):
    summary: str = Field(min_length=1, max_length=300)
    start: str = Field(min_length=1, max_length=40)
    end: str = Field(min_length=1, max_length=40)
    location: str | None = None


def _create(args: CreateEventArgs, ctx: ToolContext) -> str:
    if not ctx.google_access_token:
        return NOT_CONNECTED
    link = create_event(
        ctx.google_access_token, args.summary, args.start, args.end, ctx.timezone or "UTC", args.location
    )
    return f'Event "{args.summary}" created for {args.start}. {link}'.strip()


create_calendar_event_tool = Tool(
    name="create_calendar_event",
    description="Create a calendar event. start/end are ISO 8601 datetimes with offset.",
    parameters={
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "start": {"type": "string"},
            "end": {"type": "string"},
            "location": {"type": "string"},
        },
        "required": ["summary", "start", "end"],
        "additionalProperties": False,
    },
    args_model=CreateEventArgs,
    confirmation="sensitive",
    runs_on="backend",
    execute=_create,
)


class UpdateEventArgs(BaseModel):
    eventId: str = Field(min_length=1, max_length=1024)
    summary: str | None = None
    start: str | None = None
    end: str | None = None
    location: str | None = None


def _update(args: UpdateEventArgs, ctx: ToolContext) -> str:
    if not ctx.google_access_token:
        return NOT_CONNECTED
    update_event(
        ctx.google_access_token,
        args.eventId,
        ctx.timezone or "UTC",
        args.summary,
        args.start,
        args.end,
        args.location,
    )
    return "Event updated."


update_calendar_event_tool = Tool(
    name="update_calendar_event",
    description=(
        "Reschedule or edit an existing event by its eventId (from get_calendar_events). "
        "Provide only the fields to change. Requires confirmation."
    ),
    parameters={
        "type": "object",
        "properties": {
            "eventId": {"type": "string"},
            "summary": {"type": "string"},
            "start": {"type": "string"},
            "end": {"type": "string"},
            "location": {"type": "string"},
        },
        "required": ["eventId"],
        "additionalProperties": False,
    },
    args_model=UpdateEventArgs,
    confirmation="always",
    runs_on="backend",
    execute=_update,
)


class CancelEventArgs(BaseModel):
    eventId: str = Field(min_length=1, max_length=1024)


def _cancel(args: CancelEventArgs, ctx: ToolContext) -> str:
    if not ctx.google_access_token:
        return NOT_CONNECTED
    delete_event(ctx.google_access_token, args.eventId)
    return "Event cancelled."


cancel_calendar_event_tool = Tool(
    name="cancel_calendar_event",
    description=(
        "Cancel/delete an event by its eventId (from get_calendar_events). "
        "This is irreversible and requires confirmation."
    ),
    parameters={
        "type": "object",
        "properties": {"eventId": {"type": "string"}},
        "required": ["eventId"],
        "additionalProperties": False,
    },
    args_model=CancelEventArgs,
    confirmation="always",
    runs_on="backend",
    execute=_cancel,
)
