"""Contacts tool (backend) — Google People API via the phone-sent token."""
from pydantic import BaseModel, Field

from ..services.people import search_contacts
from .base import Tool, ToolContext

NOT_CONNECTED = "Contacts aren't available. Ask the user to connect Google in Settings."


class SearchContactArgs(BaseModel):
    query: str = Field(min_length=1, max_length=100)


def _search(args: SearchContactArgs, ctx: ToolContext) -> str:
    if not ctx.google_access_token:
        return NOT_CONNECTED
    rows = search_contacts(ctx.google_access_token, args.query, 10)
    if not rows:
        return "No matching contacts found."
    return "\n".join(
        f"{r['name']} | {', '.join(r['emails']) or 'no email'} | {', '.join(r['phones']) or 'no phone'}"
        for r in rows
    )


search_contact_tool = Tool(
    name="search_contact",
    description="Look up a person in the user's Google Contacts by name — returns their email/phone.",
    parameters={
        "type": "object",
        "properties": {"query": {"type": "string", "description": "Name to search for."}},
        "required": ["query"],
        "additionalProperties": False,
    },
    args_model=SearchContactArgs,
    confirmation="never",
    runs_on="backend",
    execute=_search,
)
