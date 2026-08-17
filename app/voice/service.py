"""Voice services (blueprint §14): Whisper STT via Groq + ElevenLabs TTS. Both
behind small abstractions so providers can be swapped. Optional — return None
when unconfigured so the phone falls back to on-device voice."""
from __future__ import annotations

import httpx
from openai import OpenAI

from ..config import get_settings

settings = get_settings()


class SpeechService:
    """Whisper transcription via Groq's OpenAI-compatible audio API."""

    def __init__(self) -> None:
        self._client = (
            OpenAI(api_key=settings.groq_api_key, base_url="https://api.groq.com/openai/v1")
            if settings.has_whisper
            else None
        )
        self.name = "whisper-groq" if self._client else "none"

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def transcribe(self, audio: bytes, mime_type: str) -> str:
        ext = "wav" if "wav" in mime_type else "mp3" if "mp3" in mime_type else "m4a"
        result = self._client.audio.transcriptions.create(  # type: ignore[union-attr]
            file=(f"audio.{ext}", audio, mime_type),
            model=settings.whisper_model,
        )
        return result.text.strip()


class TTSService:
    """ElevenLabs text-to-speech. Key stays server-side."""

    name = "elevenlabs"

    @property
    def enabled(self) -> bool:
        return settings.has_elevenlabs

    def synthesize(self, text: str) -> tuple[bytes, str]:
        r = httpx.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs_voice_id}",
            headers={
                "xi-api-key": settings.elevenlabs_api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            json={
                "text": text,
                "model_id": "eleven_turbo_v2_5",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
            },
            timeout=60,
        )
        r.raise_for_status()
        return r.content, "audio/mpeg"


speech_service = SpeechService()
tts_service = TTSService()
