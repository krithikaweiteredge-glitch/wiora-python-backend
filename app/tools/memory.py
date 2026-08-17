"""save_memory — cloud-first: writes durable memory to PostgreSQL via the Memory
Engine (runs on the backend)."""
from typing import Literal

from pydantic import BaseModel, Field

from ..memory.engine import save_memory
from .base import Tool, ToolContext


class SaveMemoryArgs(BaseModel):
    type: Literal["preference", "fact", "contact", "project", "other"]
    category: str | None = None
    value: str = Field(min_length=1, max_length=500)


def _execute(args: SaveMemoryArgs, ctx: ToolContext) -> str:
    save_memory(ctx.db, ctx.user_id, args.type, args.category, args.value)
    return f'Saved to memory: "{args.value}".'


save_memory_tool = Tool(
    name="save_memory",
    description=(
        "Save a durable long-term memory about the user — a lasting preference, a "
        "fact about them (name, role, company), or a contact/project note. Use when "
        "the user asks you to remember something or states such a durable fact. Never "
        "call this to ANSWER a question about what you know."
    ),
    parameters={
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "enum": ["preference", "fact", "contact", "project", "other"],
            },
            "category": {"type": "string", "description": "Optional grouping, e.g. 'email'."},
            "value": {"type": "string", "description": "The durable statement to remember."},
        },
        "required": ["type", "value"],
        "additionalProperties": False,
    },
    args_model=SaveMemoryArgs,
    confirmation="never",
    runs_on="backend",
    execute=_execute,
)
