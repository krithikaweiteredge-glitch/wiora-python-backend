"""Gmail tools (backend). Use the phone-sent Google token. Draft only — no send."""
from pydantic import BaseModel, Field

from ..services.gmail import create_draft, read_message, search_messages, send_message
from .base import Tool, ToolContext

NOT_CONNECTED = "Gmail is not connected. Ask the user to connect Gmail in Settings first."


class SearchArgs(BaseModel):
    query: str = Field(min_length=1, max_length=200)


def _search(args: SearchArgs, ctx: ToolContext) -> str:
    if not ctx.google_access_token:
        return NOT_CONNECTED
    rows = search_messages(ctx.google_access_token, args.query, 10)
    if not rows:
        return "No emails matched that search."
    return "\n".join(f"id:{r['id']} | {r['from']} | {r['subject']} | {r['snippet']}" for r in rows)


search_email_tool = Tool(
    name="search_email",
    description="Search the user's Gmail (up to 10). Use Gmail search syntax in `query`.",
    parameters={
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
        "additionalProperties": False,
    },
    args_model=SearchArgs,
    confirmation="never",
    runs_on="backend",
    execute=_search,
)


class ReadArgs(BaseModel):
    id: str = Field(min_length=1, max_length=128)


def _read(args: ReadArgs, ctx: ToolContext) -> str:
    if not ctx.google_access_token:
        return NOT_CONNECTED
    m = read_message(ctx.google_access_token, args.id)
    return f"From: {m['from']}\nSubject: {m['subject']}\nDate: {m['date']}\n\n{m['body']}"


read_email_tool = Tool(
    name="read_email",
    description="Read one email by id (from search_email) — returns sender, subject, body.",
    parameters={
        "type": "object",
        "properties": {"id": {"type": "string"}},
        "required": ["id"],
        "additionalProperties": False,
    },
    args_model=ReadArgs,
    confirmation="never",
    runs_on="backend",
    execute=_read,
)


class DraftArgs(BaseModel):
    to: str = Field(min_length=1, max_length=200)
    subject: str | None = None
    body: str = Field(min_length=1, max_length=8000)


def _draft(args: DraftArgs, ctx: ToolContext) -> str:
    if not ctx.google_access_token:
        return NOT_CONNECTED
    draft_id = create_draft(ctx.google_access_token, args.to, args.subject or "(no subject)", args.body)
    return f"Draft created (id:{draft_id}) to {args.to}. The user can review and send it in Gmail."


create_email_draft_tool = Tool(
    name="create_email_draft",
    description="Create a Gmail DRAFT for the user to review and send. Never sends.",
    parameters={
        "type": "object",
        "properties": {
            "to": {"type": "string"},
            "subject": {"type": "string"},
            "body": {"type": "string"},
        },
        "required": ["to", "body"],
        "additionalProperties": False,
    },
    args_model=DraftArgs,
    confirmation="sensitive",
    runs_on="backend",
    execute=_draft,
)


def _send(args: DraftArgs, ctx: ToolContext) -> str:
    if not ctx.google_access_token:
        return NOT_CONNECTED
    msg_id = send_message(ctx.google_access_token, args.to, args.subject or "(no subject)", args.body)
    return f"Email sent to {args.to} (id:{msg_id})."


send_email_tool = Tool(
    name="send_email",
    description=(
        "SEND an email immediately (not a draft). Use only when the user clearly wants to send. "
        "This requires the user's confirmation before it runs."
    ),
    parameters={
        "type": "object",
        "properties": {
            "to": {"type": "string"},
            "subject": {"type": "string"},
            "body": {"type": "string"},
        },
        "required": ["to", "body"],
        "additionalProperties": False,
    },
    args_model=DraftArgs,
    confirmation="always",  # Approval Engine gates this — never auto-sends
    runs_on="backend",
    execute=_send,
)
