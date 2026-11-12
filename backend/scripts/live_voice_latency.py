"""Opt-in live voice smoke test. Uses configured credentials and incurs API charges."""
import asyncio
import base64
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.conversation import Conversation


class Socket:
    def __init__(self):
        self.session = None
        self.events = []
        self.first_audio_at = None

    async def send_json(self, event):
        self.events.append(event)
        if event["type"] == "audio":
            if self.first_audio_at is None:
                self.first_audio_at = time.monotonic()
            self.session.acknowledge({"request_id": event["request_id"], "sequence": event["sequence"]})


async def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sample = Path(__file__).resolve().parents[2] / "voice-audition" / "onyx-british-mature.wav"
    if not sample.exists():
        raise SystemExit("The prerecorded WAV test sample is missing")
    audio = base64.b64encode(sample.read_bytes()).decode("ascii")
    socket = Socket()
    session = Conversation(socket, asyncio.Semaphore(1))
    socket.session = session
    results = []
    for number in (1, 2):
        socket.events.clear()
        socket.first_audio_at = None
        start = time.monotonic()
        await session.start({"request_id": f"live-test-{number:04d}", "audio": audio, "mime": "audio/wav"})
        await session.task
        result = {
            "turn": number,
            "status": socket.events[-1]["type"],
            "first_audio_ms": round((socket.first_audio_at - start) * 1000) if socket.first_audio_at else None,
            "total_ms": round((time.monotonic() - start) * 1000),
            "audio_chunks": sum(event["type"] == "audio" for event in socket.events),
            "history_turns": len(session.history) // 2,
        }
        results.append(result)
        if result["status"] != "done":
            result["error"] = socket.events[-1].get("message", "")
            break
    print("LIVE_RESULTS=" + json.dumps(results))


if __name__ == "__main__":
    asyncio.run(main())
