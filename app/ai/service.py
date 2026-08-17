"""AIService abstraction (blueprint §5): the app talks to THIS, never directly to
a provider. Groq is the current implementation (OpenAI-compatible); OpenAI /
Anthropic / local models can be added without touching callers.

Also hosts an EmbeddingService seam for pgvector semantic memory."""
from __future__ import annotations

from openai import OpenAI

from ..config import get_settings

settings = get_settings()


class AIService:
    """Text generation. Extend with stream() / structured() as versions grow."""

    def __init__(self) -> None:
        self.provider = "mock"
        self._client: OpenAI | None = None
        if settings.has_groq:
            self.provider = "groq"
            self._client = OpenAI(
                api_key=settings.groq_api_key,
                base_url="https://api.groq.com/openai/v1",
            )

    def generate(self, system: str, messages: list[dict]) -> str:
        if self._client is None:
            # No key configured — return a deterministic stub so the app runs.
            last = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
            return f'(mock) You said: "{last}". Add GROQ_API_KEY for real answers.'
        completion = self._client.chat.completions.create(
            model=settings.groq_model,
            messages=[{"role": "system", "content": system}, *messages],
            temperature=0.6,
        )
        return (completion.choices[0].message.content or "").strip()

    def generate_vision(self, system: str, prompt: str, image_data_uri: str) -> str:
        """Answer about an image using a vision-capable model."""
        if self._client is None:
            return "(mock) Add GROQ_API_KEY to read images."
        completion = self._client.chat.completions.create(
            model=settings.vision_model,
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt or "Describe this image."},
                        {"type": "image_url", "image_url": {"url": image_data_uri}},
                    ],
                },
            ],
            temperature=0.4,
        )
        return (completion.choices[0].message.content or "").strip()

    def generate_with_tools(
        self, system: str, messages: list[dict], tools: list[dict] | None
    ) -> tuple[str, list[dict]]:
        """Return (reply_text, raw_tool_calls). tool_calls are {name, args}."""
        if self._client is None:
            return self.generate(system, messages), []
        kwargs: dict = {}
        if tools:
            kwargs = {"tools": tools, "tool_choice": "auto"}
        try:
            completion = self._client.chat.completions.create(
                model=settings.groq_model,
                messages=[{"role": "system", "content": system}, *messages],
                temperature=0.6,
                **kwargs,
            )
        except Exception:
            # llama on Groq occasionally emits a malformed tool call (400
            # tool_use_failed). Fall back to a plain reply so the user isn't 500'd.
            if tools:
                return self.generate(system, messages), []
            raise
        msg = completion.choices[0].message
        calls: list[dict] = []
        for tc in msg.tool_calls or []:
            if getattr(tc, "type", "function") != "function":
                continue
            import json
            try:
                args = json.loads(tc.function.arguments or "{}")
            except Exception:
                args = {}
            calls.append({"name": tc.function.name, "args": args})
        return (msg.content or "").strip(), calls


class EmbeddingService:
    """Pluggable embeddings for semantic memory (blueprint §8.2). Default 'none'
    disables vectors so V1 runs without extra deps/credits; 'fastembed' (local
    ONNX) or 'openai' can be enabled via EMBEDDINGS_PROVIDER."""

    def __init__(self) -> None:
        self.provider = settings.embeddings_provider
        self._fastembed = None
        self._openai: OpenAI | None = None
        if self.provider == "fastembed":
            try:
                from fastembed import TextEmbedding  # type: ignore
                self._fastembed = TextEmbedding()  # small local model
            except Exception:
                self.provider = "none"
        elif self.provider == "openai" and settings.openai_api_key:
            self._openai = OpenAI(api_key=settings.openai_api_key)

    @property
    def enabled(self) -> bool:
        return self.provider in ("fastembed", "openai")

    def embed(self, text: str) -> list[float] | None:
        if self.provider == "fastembed" and self._fastembed is not None:
            return list(next(iter(self._fastembed.embed([text]))))
        if self.provider == "openai" and self._openai is not None:
            r = self._openai.embeddings.create(model="text-embedding-3-small", input=text)
            return r.data[0].embedding
        return None


ai_service = AIService()
embedding_service = EmbeddingService()
