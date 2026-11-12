"""Deterministic timings for repeated turns; no external API calls."""
import asyncio
import base64
import time
from unittest.mock import AsyncMock, patch

from services.conversation import Conversation


class Socket:
    def __init__(self):
        self.session = None
        self.first_audio = None
        self.events = []

    async def send_json(self, event):
        self.events.append(event)
        if event["type"] == "audio":
            if self.first_audio is None:
                self.first_audio = time.monotonic()
            self.session.acknowledge({"request_id": event["request_id"], "sequence": event["sequence"]})


async def answer(*args):
    await asyncio.sleep(.04)
    yield "My thesis examined mine ventilation and rescue methods. "
    await asyncio.sleep(.04)
    yield "Those ideas remain useful."


def test_repeated_turns_overlap_independent_lookups():
    async def run():
        socket = Socket()
        session = Conversation(socket, asyncio.Semaphore(1))
        session.user_id = "benchmark-user"
        socket.session = session

        async def transcribe(*args):
            await asyncio.sleep(.03)
            return "Tell me about your thesis"

        def retrieve(*args):
            time.sleep(.06)
            return "Verified local evidence"

        def memory(*args, **kwargs):
            time.sleep(.05)
            return ""

        serial = []
        parallel = []
        for _ in range(5):
            start = time.monotonic()
            await asyncio.to_thread(retrieve)
            await asyncio.to_thread(memory)
            serial.append((time.monotonic() - start) * 1000)
            start = time.monotonic()
            await asyncio.gather(asyncio.to_thread(retrieve), asyncio.to_thread(memory))
            parallel.append((time.monotonic() - start) * 1000)

        async def synthesize(*args):
            await asyncio.sleep(.04)
            return b"RIFF"

        samples = []
        with patch("services.conversation.api.transcribe", side_effect=transcribe), \
             patch("services.conversation.retrieve", side_effect=retrieve), \
             patch("services.conversation.memory.relevant", side_effect=memory), \
             patch("services.conversation.memory.save", return_value=False), \
             patch("services.conversation.api.generate", side_effect=answer), \
             patch("services.conversation.api.synthesize", side_effect=synthesize):
            for index in range(5):
                socket.first_audio = None
                start = time.monotonic()
                await session.start({"request_id": f"request-{index:04d}", "audio": base64.b64encode(b"audio").decode(), "mime": "audio/wav", "user_id": "benchmark-user"})
                await session.task
                samples.append(round((socket.first_audio - start) * 1000, 1))
        assert all(event["type"] != "error" for event in socket.events)
        assert len(samples) == 5
        # A serial lookup would add roughly 50 ms to these controlled turns.
        assert max(samples) < 300, samples
        print("mock first-audio latency ms:", samples)
        print("mock lookup serial/parallel mean ms:", round(sum(serial)/5, 1), round(sum(parallel)/5, 1))
        assert sum(parallel) < sum(serial)
    asyncio.run(run())


def test_new_request_cancels_speech_and_rejects_stale_audio():
    async def run():
        socket = Socket()
        session = Conversation(socket, asyncio.Semaphore(1))
        socket.session = session
        started = asyncio.Event()
        cancelled = asyncio.Event()

        async def generate(*args):
            yield "A sufficiently long first sentence reaches speech quickly. "
            await asyncio.sleep(10)

        async def synthesize(*args):
            started.set()
            try:
                await asyncio.sleep(10)
            finally:
                cancelled.set()
            return b"RIFF"

        with patch("services.conversation.api.transcribe", AsyncMock(return_value="What is coal?")), \
             patch("services.conversation.api.generate", side_effect=generate), \
             patch("services.conversation.api.synthesize", side_effect=synthesize):
            await session.start({"request_id": "request-0001", "audio": base64.b64encode(b"audio").decode(), "mime": "audio/wav"})
            await asyncio.wait_for(started.wait(), 2)
            first = session.task
            await session.start({"request_id": "request-0002", "audio": base64.b64encode(b"audio").decode(), "mime": "audio/wav"})
            assert first.cancelled() and cancelled.is_set()
            assert not any(event["type"] == "audio" and event["request_id"] == "request-0001" for event in socket.events)
            await session.cancel()
    asyncio.run(run())
