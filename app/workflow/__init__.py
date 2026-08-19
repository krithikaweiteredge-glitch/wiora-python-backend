"""Workflow Engine (blueprint §9): Celery-backed scheduled/background jobs —
reminder delivery + daily-briefing push. Optional: runs only when a broker
(Redis) and a worker/beat process are configured. The FastAPI app itself does
not import Celery, so the API runs with or without workers."""
