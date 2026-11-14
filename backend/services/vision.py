"""Session-owned, latest-frame-wins visual perception. No image leaves local Ollama."""
import asyncio
import base64
import io
import json
import logging
import threading
import time
import urllib.request
from collections import deque
from datetime import datetime, timezone

from PIL import Image, UnidentifiedImageError
import config

log = logging.getLogger("panman.vision")
_inference_limit = asyncio.Semaphore(1)
_ollama_lock = threading.Lock()


def preprocess(data):
    if len(data) > config.VISION_MAX_FRAME_BYTES:
        raise ValueError("Camera frame too large")
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in ("JPEG", "PNG") or image.width < 32 or image.height < 32 or image.width * image.height > 4_000_000:
                raise ValueError("Invalid camera frame")
            image = image.convert("RGB")
            image.thumbnail((config.VISION_FRAME_WIDTH, config.VISION_FRAME_WIDTH))
            thumb = image.convert("L").resize((32, 32))
            pixels = thumb.tobytes()
            out = io.BytesIO()
            image.save(out, "JPEG", quality=68)
            return out.getvalue(), pixels
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Invalid camera frame") from exc


def difference(left, right):
    return sum(abs(a - b) for a, b in zip(left, right)) / (255 * len(left))


def ollama_analyse(frame, detailed=False):
    with _ollama_lock:
        return _ollama_analyse_locked(frame, detailed)


def _ollama_analyse_locked(frame, detailed=False):
    prompt = ("Describe only what is clearly visible. Reply as compact JSON with keys scene_summary (string), "
              "objects (array of names), visible_text (array of exact readable strings), confidence (number 0 to 1). "
              "Say uncertain when unsure. " + ("Pay special attention to any object being shown and visible writing." if detailed else ""))
    body = json.dumps({"model": config.VISION_MODEL, "stream": False, "keep_alive": config.VISION_KEEP_ALIVE,
                       "messages": [{"role": "user", "content": prompt, "images": [base64.b64encode(frame).decode("ascii")]}],
                       "format": "json", "options": {"num_ctx": 2048, "num_predict": 180, "num_thread": 2}}).encode()
    request = urllib.request.Request(config.VISION_OLLAMA_URL.rstrip("/") + "/api/chat", body,
                                     {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=config.VISION_TIMEOUT_SECONDS) as response:
        result = json.load(response)
    return json.loads(result["message"]["content"])


class VisualPerception:
    def __init__(self):
        self.pending = None
        self.event = asyncio.Event()
        self.worker = None
        self.enabled = False
        self.closed = False
        self.sequence = 0
        self.latest = None
        self.history = deque(maxlen=config.VISION_HISTORY_LIMIT)
        self.last_pixels = None
        self.last_inference = 0.0
        self.retry_after = 0.0
        self.dropped = 0
        self.detailed = False
        self.status = "off"

    def start(self):
        self.closed = False
        self.enabled = True
        self.status = "starting"
        if self.worker is None or self.worker.done():
            self.worker = asyncio.create_task(self._run())

    def submit(self, encoded):
        if not self.enabled or self.closed or not isinstance(encoded, str) or len(encoded) > config.VISION_MAX_FRAME_BYTES * 1.4:
            return
        try:
            frame = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError):
            return
        if not frame or len(frame) > config.VISION_MAX_FRAME_BYTES:
            return
        self.sequence += 1
        if self.pending is not None:
            self.dropped += 1
        self.pending = (self.sequence, frame)
        self.event.set()

    def request_detail(self):
        self.detailed = True
        if self.pending:
            self.event.set()

    def context(self):
        item = self.latest
        if not self.enabled or not item or time.monotonic() - item["received_at"] > config.VISION_CONTEXT_TTL_SECONDS:
            return None
        return {key: value for key, value in item.items() if key != "received_at"}

    async def stop(self):
        self.enabled = False
        self.closed = True
        self.pending = None
        self.latest = None
        self.history.clear()
        self.event.set()
        if self.worker:
            self.worker.cancel()
            try:
                await self.worker
            except asyncio.CancelledError:
                pass
            self.worker = None
        self.status = "off"

    async def _run(self):
        while self.enabled and not self.closed:
            await self.event.wait()
            self.event.clear()
            if not self.pending:
                continue
            sequence, raw = self.pending
            self.pending = None
            started = time.monotonic()
            try:
                frame, pixels = await asyncio.to_thread(preprocess, raw)
                preprocess_ms = (time.monotonic() - started) * 1000
                change = difference(pixels, self.last_pixels) if self.last_pixels else 1.0
                self.last_pixels = pixels
                now = time.monotonic()
                if now < self.retry_after:
                    continue
                if change < config.VISION_CHANGE_THRESHOLD and not self.detailed and now - self.last_inference < config.VISION_CONTEXT_TTL_SECONDS / 2:
                    continue
                if now - self.last_inference < config.VISION_COOLDOWN_SECONDS and not self.detailed:
                    continue
                self.last_inference = now
                self.status = "analysing"
                inference_started = time.monotonic()
                detailed = self.detailed
                self.detailed = False
                async with _inference_limit:
                    result = await asyncio.to_thread(ollama_analyse, frame, detailed)
                inference_ms = (time.monotonic() - inference_started) * 1000
                if not self.enabled or self.closed or (self.latest and self.latest["sequence_id"] > sequence):
                    continue
                summary = str(result.get("scene_summary", ""))[:400]
                confidence = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
                item = {"scene_summary": summary, "objects": [str(x)[:60] for x in result.get("objects", [])[:12]],
                        "visible_text": [str(x)[:120] for x in result.get("visible_text", [])[:8]],
                        "confidence": confidence, "timestamp": datetime.now(timezone.utc).isoformat(),
                        "sequence_id": sequence, "status": "available", "received_at": time.monotonic()}
                self.latest = item
                self.history.append(item)
                self.status = "available"
                self.retry_after = 0.0
                log.info("scene sequence=%s preprocess_ms=%.1f inference_ms=%.1f total_ms=%.1f changed=%.3f dropped=%s", sequence,
                         preprocess_ms, inference_ms, (time.monotonic()-started)*1000, change, self.dropped)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.status = "unavailable"
                self.retry_after = time.monotonic() + config.VISION_FAILURE_BACKOFF_SECONDS
                log.warning("vision failure sequence=%s category=%s elapsed_ms=%.1f retry_after_s=%.1f dropped=%s",
                            sequence, type(exc).__name__, (time.monotonic()-started)*1000,
                            config.VISION_FAILURE_BACKOFF_SECONDS, self.dropped)
