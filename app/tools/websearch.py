"""search_web — look up current information on the internet (backend tool)."""
from pydantic import BaseModel, Field

from ..services.search import search
from .base import Tool, ToolContext


class SearchWebArgs(BaseModel):
    query: str = Field(min_length=1, max_length=300)


def _execute(args: SearchWebArgs, ctx: ToolContext) -> str:
    return search(args.query)


search_web_tool = Tool(
    name="search_web",
    description=(
        "Search the public internet for current or factual information the user "
        "asks about (news, prices, facts, how-tos) that isn't in the conversation "
        "or the user's own data. Returns a digest of top results with sources."
    ),
    parameters={
        "type": "object",
        "properties": {"query": {"type": "string", "description": "The search query."}},
        "required": ["query"],
        "additionalProperties": False,
    },
    args_model=SearchWebArgs,
    confirmation="never",
    runs_on="backend",
    execute=_execute,
)
