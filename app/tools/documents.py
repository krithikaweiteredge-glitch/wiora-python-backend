"""Document search tool (backend). Uses semantic (pgvector) search over document
chunks when embeddings are enabled; otherwise falls back to keyword matching
(blueprint §13)."""
import re

from pydantic import BaseModel, Field
from sqlalchemy import select

from ..ai.service import embedding_service
from ..models import Document, DocumentChunk
from .base import Tool, ToolContext


class SearchDocsArgs(BaseModel):
    query: str = Field(min_length=1, max_length=200)


def _semantic(query: str, ctx: ToolContext) -> str | None:
    q_emb = embedding_service.embed(query)
    if q_emb is None:
        return None
    rows = ctx.db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.user_id == ctx.user_id)
        .order_by(DocumentChunk.embedding.cosine_distance(q_emb))
        .limit(3)
    ).scalars().all()
    if not rows:
        return None
    return "\n---\n".join(r.text[:300] for r in rows)


def _keyword(query: str, ctx: ToolContext) -> str:
    docs = ctx.db.execute(
        select(Document).where(Document.user_id == ctx.user_id).order_by(Document.id.desc())
    ).scalars().all()
    if not docs:
        return "The user has not uploaded any documents."
    words = {w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) > 2}
    hits = []
    for d in docs:
        low = (d.text or "").lower()
        score = sum(1 for w in words if w in low) if words else 0
        if score > 0:
            idx = next((low.find(w) for w in words if low.find(w) >= 0), 0)
            snippet = (d.text or "")[max(0, idx - 60) : idx + 200].replace("\n", " ").strip()
            hits.append((score, f'"{d.filename}": …{snippet}…'))
    if not hits:
        return "No uploaded document matched that."
    hits.sort(key=lambda x: x[0], reverse=True)
    return "\n".join(h for _, h in hits[:3])


def _search(args: SearchDocsArgs, ctx: ToolContext) -> str:
    if embedding_service.enabled:
        result = _semantic(args.query, ctx)
        if result:
            return result
    return _keyword(args.query, ctx)


search_documents_tool = Tool(
    name="search_documents",
    description="Search the user's uploaded documents/files and return relevant passages.",
    parameters={
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
        "additionalProperties": False,
    },
    args_model=SearchDocsArgs,
    confirmation="never",
    runs_on="backend",
    execute=_search,
)
