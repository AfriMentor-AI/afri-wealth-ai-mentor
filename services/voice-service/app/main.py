"""Voice Service — AfriMentor AI microservice stub.

Generated for card O1.2. Real implementation lands in later sprints.
Health endpoint is live so docker-compose health checks pass.
"""
import os
import io
import speech_recognition as sr
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import StreamingResponse
from gtts import gTTS
from pydantic import BaseModel


from .observability import instrument

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

@app.post("/tts", tags=["voice"])
async def text_to_speech(req: TTSRequest):
    """Converts text to speech."""
    # The persona parameter can be used to select different voices.
    # For now, we'll use the default gTTS voice.
    # In a real implementation, this could map to different voice models.
    lang = "en"
    if req.persona == "chioma":
        # Example of persona-based voice selection
        lang = "en-gh"


    tts = gTTS(req.text, lang=lang)
    mp3_fp = io.BytesIO()
    tts.write_to_fp(mp3_fp)
    mp3_fp.seek(0)

    return StreamingResponse(mp3_fp, media_type="audio/mpeg")


@app.post("/stt", tags=["voice"])
async def speech_to_text(file: UploadFile = File(...)):
    """Converts speech to text."""
    r = sr.Recognizer()
    with sr.AudioFile(io.BytesIO(file.file.read())) as source:
        audio = r.record(source)
    try:
        text = r.recognize_google(audio)
        return {"text": text}
    except sr.UnknownValueError:
        return {"text": ""}
    except sr.RequestError as e:
        return {"error": f"Could not request results from Google Speech Recognition service; {e}"}
