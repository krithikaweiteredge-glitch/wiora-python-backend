from fastapi import APIRouter

from .. import cache
from ..ai.service import ai_service, embedding_service
from ..config import get_settings
from ..schemas import HealthResponse

router = APIRouter()
settings = get_settings()


@router.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        ok=True,
        provider=ai_service.provider,
        database=settings.has_db,
        auth=bool(settings.firebase_project_id),
        embeddings=embedding_service.provider,
        redis=cache.status(),
    )
