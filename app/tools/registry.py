"""Tool registry + validation + backend execution (blueprint §7)."""
from __future__ import annotations

from dataclasses import dataclass

from .base import Tool, ToolContext
from .calendar import (
    cancel_calendar_event_tool,
    create_calendar_event_tool,
    find_free_time_tool,
    get_calendar_events_tool,
    update_calendar_event_tool,
)
from .gmail import (
    create_email_draft_tool,
    read_email_tool,
    search_email_tool,
    send_email_tool,
)
from .memory import save_memory_tool
from .reminder import create_reminder_tool
from .contacts import search_contact_tool
from .tasks import complete_task_tool, create_task_tool, list_tasks_tool
from .documents import search_documents_tool

_TOOLS: list[Tool] = [
    save_memory_tool,
    create_reminder_tool,
    search_email_tool,
    read_email_tool,
    create_email_draft_tool,
    send_email_tool,
    get_calendar_events_tool,
    find_free_time_tool,
    create_calendar_event_tool,
    update_calendar_event_tool,
    cancel_calendar_event_tool,
    search_contact_tool,
    create_task_tool,
    list_tasks_tool,
    complete_task_tool,
    search_documents_tool,
]
REGISTRY: dict[str, Tool] = {t.name: t for t in _TOOLS}


def tool_specs() -> list[dict]:
    return [t.spec() for t in _TOOLS]


@dataclass
class ValidatedCall:
    name: str
    args: dict
    confirmation: str
    runs_on: str


def validate_call(name: str, raw_args: dict) -> ValidatedCall | None:
    tool = REGISTRY.get(name)
    if tool is None:
        return None
    parsed = tool.validate(raw_args)
    if parsed is None:
        return None
    return ValidatedCall(
        name=name,
        args=parsed.model_dump(),
        confirmation=tool.confirmation,
        runs_on=tool.runs_on,
    )


def execute_backend(call: ValidatedCall, ctx: ToolContext) -> str:
    tool = REGISTRY.get(call.name)
    if tool is None or tool.execute is None:
        return f"Tool {call.name} cannot run on the server."
    try:
        return tool.execute(tool.args_model(**call.args), ctx)
    except Exception as e:  # noqa: BLE001
        return f"Tool {call.name} failed: {e}"
