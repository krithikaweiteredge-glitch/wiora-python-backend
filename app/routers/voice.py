"""Voice endpoints (blueprint §14). Audio passed as base64 JSON (no multipart).
503 when a provider isn't configured so the phone falls back to on-device voice."""
import base64
import binascii

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..voice.service import speech_service, tts_service

router = APIRouter()


class TranscribeBody(BaseModel):
    audioBase64: str = Field(min_length=1)
    mimeType: str = "audio/m4a"


class SpeakBody(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


@router.post("/api/voice/transcribe")
def transcribe(body: TranscribeBody) -> dict:
    if not speech_service.enabled:
        raise HTTPException(status_code=503, detail="Cloud STT not configured.")
    try:
        audio = base64.b64decode(body.audioBase64)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="Invalid audio encoding.")
    try:
        text = speech_service.transcribe(audio, body.mimeType)
    except Exception:
        raise HTTPException(status_code=500, detail="Transcription failed.")
    return {"text": text, "provider": speech_service.name}


@router.post("/api/voice/speak")
def speak(body: SpeakBody) -> dict:
    if not tts_service.enabled:
        raise HTTPException(status_code=503, detail="Cloud TTS not configured.")
    try:
        audio, content_type = tts_service.synthesize(body.text)
    except Exception:
        raise HTTPException(status_code=500, detail="Speech synthesis failed.")
    return {
        "audioBase64": base64.b64encode(audio).decode("ascii"),
        "contentType": content_type,
        "provider": tts_service.name,
    }
