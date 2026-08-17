"""create_reminder — a DEVICE tool: the phone schedules the local notification.
The backend validates it and forwards the call to the phone."""
from pydantic import BaseModel, Field

from .base import Tool


class CreateReminderArgs(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    # ISO 8601 with offset; the model resolves relative times from the current
    # date-time injected into the prompt.
    dueAt: str | None = None


create_reminder_tool = Tool(
    name="create_reminder",
    description=(
        "Create a personal reminder for the user. Resolve relative times "
        "('tomorrow at 5 PM') into an absolute ISO 8601 datetime with offset for dueAt."
    ),
    parameters={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "What to remind the user about."},
            "dueAt": {
                "type": "string",
                "description": "ISO 8601 datetime with offset, e.g. 2026-08-14T17:00:00+05:30.",
            },
        },
        "required": ["text"],
        "additionalProperties": False,
    },
    args_model=CreateReminderArgs,
    confirmation="never",
    runs_on="device",
)
