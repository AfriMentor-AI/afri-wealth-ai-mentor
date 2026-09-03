"""Voice Service — AfriMentor AI microservice stub.

Generated for card O1.2. Real implementation lands in later sprints.
Health endpoint is live so docker-compose health checks pass.
"""
import io
import logging
import os

import speech_recognition as sr
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import Response, StreamingResponse
from gtts import gTTS
from pydantic import BaseModel

from .observability import instrument

logger = logging.getLogger("voice-service")

SERVICE_NAME = "voice-service"
SERVICE_VERSION = "0.1.0"

app = FastAPI(
    title="AfriMentor AI — Voice Service",
    version=SERVICE_VERSION,
    description="Stub service. See docs/adr/0001-microservices-architecture.md",
)

instrument(app, SERVICE_NAME)

class TTSRequest(BaseModel):
    text: str
    persona: str = "default"

@app.get("/health", tags=["meta"])
def health() -> dict:
    """Liveness/readiness probe used by docker-compose and the gateway."""
    return {
        "status": "healthy",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "env": os.getenv("APP_ENV", "dev"),
    }


@app.get("/", tags=["meta"])
def root() -> dict:
    return {"service": SERVICE_NAME, "message": "Voice Service online", "docs": "/docs"}

VOICE_MAP = {
    "chioma": "en-NG-EzinneNeural",  # Warm, authentic Nigerian female mentor
    "kwame": "en-GH-KwameNeural",    # Authentic Ghanaian male mentor
    "abeo": "en-NG-AbeoNeural",      # Nigerian male
    "nana": "en-GH-NanaNeural",      # Ghanaian female
}

@app.post("/tts", tags=["voice"])
@app.post("/api/v1/voice/tts", tags=["voice"])
@app.post("/api/v1/voice/synthesize", tags=["voice"])
async def text_to_speech(req: TTSRequest):
    """Converts text to speech using African Microsoft Neural voices with gTTS fallback."""
    voice_name = VOICE_MAP.get((req.persona or "chioma").lower(), "en-NG-EzinneNeural")
    spoken_text = req.text.strip()

    # 1. Try Microsoft Neural African Voice (edge-tts)
    try:
        import edge_tts

        communicate = edge_tts.Communicate(spoken_text, voice_name)
        mp3_bytes = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                mp3_bytes.extend(chunk["data"])

        if mp3_bytes:
            return Response(content=bytes(mp3_bytes), media_type="audio/mpeg")
    except Exception as exc:
        logger.warning("edge-tts synthesis notice: %s. Using gTTS fallback.", exc)

    # 2. Fallback to gTTS if edge-tts is unavailable
    lang = "en"
    tld = "com.ng" if (req.persona or "").lower() == "chioma" else "com.gh"
    capped_text = spoken_text[:350] if len(spoken_text) > 350 else spoken_text

    tts = gTTS(capped_text, lang=lang, tld=tld)
    mp3_fp = io.BytesIO()
    tts.write_to_fp(mp3_fp)
    mp3_fp.seek(0)

    return StreamingResponse(mp3_fp, media_type="audio/mpeg")


@app.post("/stt", tags=["voice"])
@app.post("/api/v1/voice/stt", tags=["voice"])
@app.post("/api/v1/voice/transcribe", tags=["voice"])
async def speech_to_text(file: UploadFile = File(...)):
    """Converts speech to text."""
    r = sr.Recognizer()
    raw_data = await file.read()

    try:
        with sr.AudioFile(io.BytesIO(raw_data)) as source:
            audio = r.record(source)
    except Exception as exc:
        return {"text": "", "error": f"Audio processing error: {exc}"}

    try:
        text = r.recognize_google(audio)
        return {"text": text}
    except sr.UnknownValueError:
        return {"text": ""}
    except sr.RequestError as e:
        return {"error": f"Could not request results from Google Speech Recognition service; {e}"}