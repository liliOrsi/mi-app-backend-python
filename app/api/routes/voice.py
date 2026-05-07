import asyncio
import io

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openai import OpenAI

from app.core.config import settings

router = APIRouter()

_openai: OpenAI | None = None


def get_openai() -> OpenAI:
    global _openai
    if _openai is None:
        _openai = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai


# ── TTS ──────────────────────────────────────────────────────────────────────

class TTSRequest(BaseModel):
    text: str
    voice: str = "nova"   # alloy | echo | fable | onyx | nova | shimmer


@router.post("/tts")
async def text_to_speech(req: TTSRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text is empty")

    def _synthesize():
        client = get_openai()
        return client.audio.speech.create(
            model="tts-1",
            voice=req.voice,
            input=req.text[:4096],
            response_format="mp3",
        )

    response = await asyncio.to_thread(_synthesize)
    audio_bytes = response.read()

    return StreamingResponse(
        io.BytesIO(audio_bytes),
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-cache"},
    )


# ── STT ──────────────────────────────────────────────────────────────────────

@router.post("/stt")
async def speech_to_text(audio: UploadFile = File(...)):
    content = await audio.read()
    if not content:
        raise HTTPException(status_code=400, detail="audio file is empty")

    filename = audio.filename or "recording.webm"

    def _transcribe():
        client = get_openai()
        return client.audio.transcriptions.create(
            model="whisper-1",
            file=(filename, content, audio.content_type or "audio/webm"),
            language="es",
        )

    result = await asyncio.to_thread(_transcribe)
    return {"text": result.text}
