"""Central configuration — secrets come ONLY from the environment."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 4000

    database_url: str = ""

    # Which LLM provider the AIService uses: groq | gemini | mock.
    ai_provider: str = "groq"

    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    # Multimodal model for image attachments (Groq vision-capable).
    vision_model: str = "meta-llama/llama-4-scout-17b-16e-instruct"

    # Google Gemini (via its OpenAI-compatible endpoint). Get a key at
    # https://aistudio.google.com/apikey — it starts with "AIzaSy".
    gemini_api_key: str = ""
    # Current multimodal flash model (verified available + good at vision on the
    # OpenAI-compatible endpoint). Change GEMINI_MODEL if Google updates the lineup.
    gemini_model: str = "gemini-3.6-flash"

    firebase_project_id: str = "wiora-1a833"

    # Redis (caching, rate limiting, agent state). Empty = disabled; the app still
    # runs. e.g. redis://localhost:6379/0
    redis_url: str = ""
    rate_limit_per_min: int = 60

    embeddings_provider: str = "none"  # none | fastembed | openai
    openai_api_key: str = ""

    # Voice (blueprint §14). STT (Whisper) reuses the Groq key. TTS = ElevenLabs.
    whisper_model: str = "whisper-large-v3-turbo"
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"

    @property
    def has_whisper(self) -> bool:
        return bool(self.groq_api_key)

    @property
    def has_elevenlabs(self) -> bool:
        return bool(self.elevenlabs_api_key)

    @property
    def has_groq(self) -> bool:
        return bool(self.groq_api_key)

    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def has_db(self) -> bool:
        return bool(self.database_url)

    @property
    def sqlalchemy_url(self) -> str:
        """Normalise a Neon/Postgres URL for SQLAlchemy + psycopg v3."""
        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
