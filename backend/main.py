"""Same-origin voice application. Run one worker; session ownership is in-process."""
import asyncio
import json
import logging
import sys
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import config

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
sys.path.insert(0, str(FRONTEND))
from avatar_renderer import render_script, avatar_asset_manifest
from services.conversation import Conversation
from services.retrieval import active_store
from services import openai_service

@asynccontextmanager
async def lifespan(app):
    config.validate_config()
    logging.basicConfig(level=logging.INFO)
    app.state.capacity = asyncio.Semaphore(config.OPENAI_MAX_CONCURRENT)
    app.state.sessions = 0
    yield
    if openai_service.async_client.cache_info().currsize:
        await openai_service.async_client().close()
        openai_service.async_client.cache_clear()
    if openai_service.client.cache_info().currsize:
        openai_service.client().close()
        openai_service.client.cache_clear()

app = FastAPI(title=config.ASSISTANT_NAME, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=FRONTEND / "voice"), name="static")

@lru_cache(maxsize=1)
def page():
    modules, renderer = render_script()
    html = (FRONTEND / "voice" / "index.html").read_text(encoding="utf-8")
    return html.replace("__IMPORTMAP__", modules).replace("__RENDERER__", renderer)

@app.get("/", response_class=HTMLResponse)
def home():
    return page()

@app.get("/config")
def browser_config():
    # Explicit allowlist: never serialize the config module.
    return dict(name=config.ASSISTANT_NAME, silenceMs=config.RECORDING_SILENCE_MS,
        minSpeechMs=config.RECORDING_MIN_SPEECH_MS, maxRecordingMs=config.RECORDING_MAX_MS,
        rmsThreshold=config.RECORDING_RMS_THRESHOLD, bargeThreshold=config.BARGE_IN_RMS_THRESHOLD,
        preRollMs=config.RECORDING_PRE_ROLL_MS, bufferFrames=config.RECORDING_BUFFER_FRAMES,
        bargeMs=config.BARGE_IN_MIN_MS,
        queueLimit=config.AUDIO_QUEUE_LIMIT, turnTimeoutMs=config.TURN_TIMEOUT_SECONDS*1000,
        cameraIntervalMs=config.VISION_CAPTURE_INTERVAL_MS, cameraWidth=config.VISION_FRAME_WIDTH)


@app.get("/health")
def health():
    return {"status":"ok"}

@app.get("/ready")
def ready():
    try:
        if not config.OPENAI_API_KEY:
            raise RuntimeError("Missing credentials")
        active_store()
        avatar_asset_manifest(config.AVATAR_MODEL_PATH)
        return {"status":"ready", "provider_check":"not performed"}
    except Exception:
        return JSONResponse({"status":"not_ready", "message":"Configure credentials, assets and a compatible index."}, status_code=503)

@app.websocket("/voice")
async def voice(socket: WebSocket):
    # Reject cross-site sockets; reverse proxy must preserve Host and Origin.
    origin = socket.headers.get("origin", "")
    host = socket.headers.get("host", "")
    if origin not in config.BROWSER_ALLOWED_ORIGINS and origin not in {"http://"+host, "https://"+host}:
        await socket.close(code=1008)
        return
    if app.state.sessions >= config.MAX_SESSIONS:
        await socket.close(code=1013)
        return
    await socket.accept()
    app.state.sessions += 1
    session = Conversation(socket, app.state.capacity)
    try:
        while True:
            raw = await asyncio.wait_for(socket.receive_text(), config.SESSION_IDLE_SECONDS)
            if len(raw) > config.MAX_AUDIO_BYTES*1.4+1024:
                await socket.close(code=1009)
                break
            message = json.loads(raw)
            if not isinstance(message, dict):
                raise ValueError("Expected an event object")
            kind = message.get("type")
            if kind == "utterance":
                await session.start(message)
            elif kind == "camera_start":
                session.start_camera()
            elif kind == "camera_frame":
                session.vision.submit(message.get("image"))
                await session.send("camera_status", status=session.vision.status,
                                   ready=session.vision.context() is not None)
            elif kind == "camera_stop":
                await session.cancel_proactive()
                await session.vision.stop()
            elif kind == "client_state":
                await session.set_client_state(message.get("state"))
            elif kind == "cancel":
                await session.cancel()
            elif kind == "played":
                session.acknowledge(message)
            elif kind == "audible" and message.get("request_id") == session.current:
                elapsed = message.get("latency_ms")
                if isinstance(elapsed, (int, float)) and 0 <= elapsed <= config.TURN_TIMEOUT_SECONDS * 1000:
                    logging.getLogger("panman.turn").info("stage request_id=%s name=submit_to_first_audible latency_ms=%.1f", session.current, elapsed)
            elif kind == "recover" and message.get("request_id") == session.current:
                await session.recover()
    except (WebSocketDisconnect, TimeoutError):
        pass
    except (ValueError, TypeError, KeyError):
        await socket.close(code=1008)
    finally:
        await session.vision.stop()
        await session.cancel()
        app.state.sessions -= 1

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT, log_level=config.API_LOG_LEVEL,
                ws_max_size=int(config.MAX_AUDIO_BYTES*1.4+1024))
