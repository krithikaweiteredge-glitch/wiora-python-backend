"""Wiora backend — FastAPI (blueprint V1 core).

Five reusable components are wired here so later versions bolt on without a
rewrite: AI Orchestrator (orchestrator/), Memory Engine (memory/), Tool Engine
(tools/ — V4), Workflow Engine (workflow/ — V2, Celery), Approval & Audit
(audit.py)."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import init_db
from .routers import agent, briefing, chat, health, meeting, store, tool, voice

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.has_db:
        init_db()
    yield


app = FastAPI(title="Wiora API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(voice.router)
app.include_router(meeting.router)
app.include_router(tool.router)
app.include_router(agent.router)
app.include_router(store.router)
app.include_router(briefing.router)


def main() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.port, reload=False)


if __name__ == "__main__":
    main()
