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

    # --- Production hardening ---
    # Comma-separated allowed CORS origins ("*" = any; fine for a mobile client).
    allowed_origins: str = "*"
    log_level: str = "INFO"
    # Sentry error tracking — no-op until a DSN is set (sentry-sdk stays optional).
    sentry_dsn: str = ""
    environment: str = "production"
    # Logical service name reported to tracing backends (Langfuse/OTel).
    service_name: str = "wiora-backend"

    # --- LLM observability (Langfuse) ---
    # Traces every model call (prompt, output, latency, token cost) to Langfuse.
    # No-op until BOTH keys are set — the app never depends on it. Get free keys at
    # https://cloud.langfuse.com (or self-host and set LANGFUSE_HOST).
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
    # Generic OpenTelemetry export. Langfuse v3 emits OTel spans; set this to ALSO
    # ship them to your own OTLP collector (Grafana Tempo, Honeycomb, etc.). Empty
    # = only Langfuse (when configured) receives traces.
    otel_exporter_otlp_endpoint: str = ""

    # --- Web search tool ---
    # Provider: "tavily" | "brave" | "serper". Empty key = tool reports "not
    # configured" instead of failing. Get a free Tavily key at tavily.com.
    search_provider: str = "tavily"
    search_api_key: str = ""

    # --- Celery + push (blueprint workflow engine) ---
    # Broker defaults to REDIS_URL when unset. FCM needs a Firebase service-account
    # to send push; empty = push disabled (scheduling still logs). Provide it as
    # JSON pasted into an env var (recommended on Render) OR a file path.
    celery_broker_url: str = ""
    fcm_credentials_path: str = ""
    fcm_credentials_json: str = ""

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()] or ["*"]

    @property
    def broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

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
    def has_langfuse(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)

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
