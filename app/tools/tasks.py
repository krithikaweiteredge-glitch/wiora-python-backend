"""Task tools (backend) — a to-do list stored in Postgres (blueprint V2)."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select

from ..models import Task
from .base import Tool, ToolContext


class CreateTaskArgs(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    dueAt: str | None = None  # ISO 8601
    repeat: Literal["none", "daily", "weekly", "monthly"] = "none"


def _create(args: CreateTaskArgs, ctx: ToolContext) -> str:
    due = None
    if args.dueAt:
        try:
            due = datetime.fromisoformat(args.dueAt.replace("Z", "+00:00"))
        except ValueError:
            due = None
    ctx.db.add(Task(user_id=ctx.user_id, text=args.text, due_at=due, repeat=args.repeat))
    ctx.db.commit()
    suffix = f" (repeats {args.repeat})" if args.repeat != "none" else ""
    return f'Task added: "{args.text}"{suffix}.'


create_task_tool = Tool(
    name="create_task",
    description="Add a to-do task for the user. Optionally give a due date (ISO 8601) "
    "and a repeat (daily/weekly/monthly) for recurring tasks.",
    parameters={
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "dueAt": {"type": "string", "description": "ISO 8601 due datetime (optional)."},
            "repeat": {
                "type": "string",
                "enum": ["none", "daily", "weekly", "monthly"],
                "description": "Recurrence; 'none' for a one-off task.",
            },
        },
        "required": ["text"],
        "additionalProperties": False,
    },
    args_model=CreateTaskArgs,
    confirmation="never",
    runs_on="backend",
    execute=_create,
)


class NoArgs(BaseModel):
    pass


def _list(args: NoArgs, ctx: ToolContext) -> str:
    rows = ctx.db.execute(
        select(Task).where(Task.user_id == ctx.user_id, Task.done == False).order_by(Task.id.desc())  # noqa: E712
    ).scalars().all()
    if not rows:
        return "You have no open tasks."
    return "\n".join(f"#{t.id} {t.text}" + (f" (due {t.due_at.isoformat()})" if t.due_at else "") for t in rows)


list_tasks_tool = Tool(
    name="list_tasks",
    description="List the user's open (not-done) tasks.",
    parameters={"type": "object", "properties": {}, "additionalProperties": False},
    args_model=NoArgs,
    confirmation="never",
    runs_on="backend",
    execute=_list,
)


class CompleteTaskArgs(BaseModel):
    taskId: int


def _complete(args: CompleteTaskArgs, ctx: ToolContext) -> str:
    t = ctx.db.get(Task, args.taskId)
    if t is None or t.user_id != ctx.user_id:
        return "That task wasn't found."
    t.done = True
    ctx.db.commit()
    return f'Marked task #{args.taskId} done: "{t.text}".'


complete_task_tool = Tool(
    name="complete_task",
    description="Mark a task done by its id (from list_tasks).",
    parameters={
        "type": "object",
        "properties": {"taskId": {"type": "integer"}},
        "required": ["taskId"],
        "additionalProperties": False,
    },
    args_model=CompleteTaskArgs,
    confirmation="never",
    runs_on="backend",
    execute=_complete,
)
