"""Automation tools (blueprint V4): create/list/delete trigger→action rules.
V1 triggers are time-based (daily/weekly at HH:MM); a Celery beat task runs them."""
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select

from ..models import Automation
from .base import Tool, ToolContext


class CreateAutomationArgs(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    trigger_type: Literal["daily", "weekly"] = "daily"
    hour: int = Field(ge=0, le=23, default=8)
    minute: int = Field(ge=0, le=59, default=0)
    weekday: int | None = Field(default=None, ge=0, le=6)  # 0=Mon..6=Sun for weekly
    action_type: Literal["briefing", "reminder", "agent"]
    action_text: str | None = Field(default=None, max_length=500)


def _create(args: CreateAutomationArgs, ctx: ToolContext) -> str:
    a = Automation(
        user_id=ctx.user_id, name=args.name, trigger_type=args.trigger_type,
        hour=args.hour, minute=args.minute, weekday=args.weekday,
        action_type=args.action_type, action_text=args.action_text,
    )
    ctx.db.add(a)
    ctx.db.commit()
    when = f"{args.hour:02d}:{args.minute:02d}"
    freq = "daily" if args.trigger_type == "daily" else f"weekly (day {args.weekday})"
    return f'Automation "{args.name}" created: {args.action_type} {freq} at {when}.'


create_automation_tool = Tool(
    name="create_automation",
    description=(
        "Create a scheduled automation (trigger→action). Trigger is a time "
        "(daily or weekly at hour:minute, times in UTC). Action is one of: "
        "'briefing' (send the daily briefing), 'reminder' (create a reminder with "
        "action_text), or 'agent' (run a goal in action_text). Use for requests like "
        "'every morning at 8 give me my briefing'."
    ),
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "trigger_type": {"type": "string", "enum": ["daily", "weekly"]},
            "hour": {"type": "integer"},
            "minute": {"type": "integer"},
            "weekday": {"type": "integer", "description": "0=Mon..6=Sun (weekly only)."},
            "action_type": {"type": "string", "enum": ["briefing", "reminder", "agent"]},
            "action_text": {"type": "string", "description": "Reminder text or agent goal."},
        },
        "required": ["name", "action_type"],
        "additionalProperties": False,
    },
    args_model=CreateAutomationArgs,
    confirmation="never",
    runs_on="backend",
    execute=_create,
)


class NoArgs(BaseModel):
    pass


def _list(args: NoArgs, ctx: ToolContext) -> str:
    rows = ctx.db.execute(
        select(Automation).where(Automation.user_id == ctx.user_id)
    ).scalars().all()
    if not rows:
        return "No automations set up."
    out = []
    for a in rows:
        state = "on" if a.enabled else "off"
        out.append(f"#{a.id} [{state}] {a.name}: {a.action_type} {a.trigger_type} {a.hour:02d}:{a.minute:02d}")
    return "\n".join(out)


list_automations_tool = Tool(
    name="list_automations",
    description="List the user's automations.",
    parameters={"type": "object", "properties": {}, "additionalProperties": False},
    args_model=NoArgs,
    confirmation="never",
    runs_on="backend",
    execute=_list,
)


class DeleteAutomationArgs(BaseModel):
    automationId: int


def _delete(args: DeleteAutomationArgs, ctx: ToolContext) -> str:
    a = ctx.db.get(Automation, args.automationId)
    if a is None or a.user_id != ctx.user_id:
        return "That automation wasn't found."
    ctx.db.delete(a)
    ctx.db.commit()
    return f"Deleted automation #{args.automationId}."


delete_automation_tool = Tool(
    name="delete_automation",
    description="Delete an automation by its id (from list_automations).",
    parameters={
        "type": "object",
        "properties": {"automationId": {"type": "integer"}},
        "required": ["automationId"],
        "additionalProperties": False,
    },
    args_model=DeleteAutomationArgs,
    confirmation="never",
    runs_on="backend",
    execute=_delete,
)
