"""Observability: structured logging + optional Sentry error tracking + optional
Langfuse LLM tracing.

All three are safe no-ops when unconfigured — the app never depends on them.
Sentry initialises only when SENTRY_DSN is set; Langfuse only when BOTH Langfuse
keys are set. Missing packages are swallowed too, so a lean deploy still boots."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from functools import lru_cache
from typing import Any, Iterator

from .config import get_settings

settings = get_settings()


def setup_logging() -> None:
    """Configure root logging once, at the level from LOG_LEVEL."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def setup_sentry() -> bool:
    """Initialise Sentry if a DSN is set and the SDK is available. Returns whether
    it was enabled. Never raises — monitoring must not crash the app."""
    if not settings.sentry_dsn:
        return False
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            traces_sample_rate=0.1,
            send_default_pii=False,
        )
        logging.getLogger("wiora").info("Sentry error tracking enabled")
        return True
    except Exception as e:  # noqa: BLE001 — never let monitoring break startup
        logging.getLogger("wiora").warning("Sentry not enabled: %s", e)
        return False


# ---------------------------------------------------------------------------
# Langfuse — LLM tracing (prompts, outputs, latency, token cost per model call).
# Built on OpenTelemetry: set OTEL_EXPORTER_OTLP_ENDPOINT to ALSO ship the same
# spans to a generic OTLP collector. Everything below no-ops when unconfigured.
# ---------------------------------------------------------------------------
@lru_cache
def get_langfuse():
    """Return a cached Langfuse client, or None if disabled/unavailable. Cached so
    the client (and its background exporter thread) is created at most once."""
    if not settings.has_langfuse:
        return None
    try:
        import os

        from langfuse import Langfuse

        # Langfuse v3 is OTel-based; forward its OTLP endpoint via env if set so the
        # same traces reach a self-hosted collector alongside Langfuse.
        if settings.otel_exporter_otlp_endpoint:
            os.environ.setdefault(
                "OTEL_EXPORTER_OTLP_ENDPOINT", settings.otel_exporter_otlp_endpoint
            )
        client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
            environment=settings.environment,
        )
        logging.getLogger("wiora").info("Langfuse LLM tracing enabled")
        return client
    except Exception as e:  # noqa: BLE001 — tracing must never break the app
        logging.getLogger("wiora").warning("Langfuse not enabled: %s", e)
        return None


def setup_langfuse() -> bool:
    """Eagerly initialise Langfuse at startup. Returns whether it is enabled."""
    return get_langfuse() is not None


def flush_langfuse() -> None:
    """Flush buffered traces (call on shutdown so nothing is lost)."""
    client = get_langfuse()
    if client is not None:
        try:
            client.flush()
        except Exception:  # noqa: BLE001
            pass


class _Generation:
    """Handle the caller uses to record an LLM call's output. No-op when tracing
    is off, so call sites stay identical whether or not Langfuse is configured."""

    def __init__(self, gen: Any = None) -> None:
        self._gen = gen

    def output(self, text: Any, usage: Any = None) -> None:
        if self._gen is None:
            return
        try:
            details = None
            if usage is not None:
                # OpenAI-shaped usage (Groq/Gemini via the OpenAI client).
                details = {
                    "input": getattr(usage, "prompt_tokens", None),
                    "output": getattr(usage, "completion_tokens", None),
                    "total": getattr(usage, "total_tokens", None),
                }
                details = {k: v for k, v in details.items() if v is not None} or None
            self._gen.update(output=text, usage_details=details)
        except Exception:  # noqa: BLE001
            pass


@contextmanager
def llm_trace(
    name: str, *, model: str, provider: str, messages: Any
) -> Iterator[_Generation]:
    """Trace one LLM call. Yields a handle whose .output(text, usage) records the
    result. A no-op context when Langfuse is disabled, and a failure to START the
    trace never breaks generation — the caller's body always runs regardless."""
    client = get_langfuse()
    cm = gen = None
    if client is not None:
        try:
            cm = client.start_as_current_generation(
                name=name, model=model, input=messages, metadata={"provider": provider}
            )
            gen = cm.__enter__()
        except Exception:  # noqa: BLE001 — tracing must never break generation
            logging.getLogger("wiora").debug("llm_trace start failed", exc_info=True)
            cm = gen = None
    try:
        yield _Generation(gen)
    finally:
        if cm is not None:
            try:
                cm.__exit__(None, None, None)
            except Exception:  # noqa: BLE001
                pass
