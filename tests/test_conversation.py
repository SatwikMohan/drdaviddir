import asyncio
import base64
from unittest.mock import AsyncMock, patch
import config
from services.conversation import Conversation

class Socket:
    def __init__(self): self.events=[];self.session=None
    async def send_json(self,event):
        self.events.append(event)
        if event["type"]=="audio": self.session.acknowledge(dict(event,type="played"))

def message(rid="request-0001"):
    return dict(request_id=rid,audio=base64.b64encode(b"test audio").decode(),mime="audio/wav")

async def generated(*args):
    yield "A bucket wheel excavator continuously removes material using buckets mounted on a rotating wheel. "
    yield "The indexed manual describes its operation."

def test_full_turn_and_deduplication():
    async def run():
        socket=Socket();session=Conversation(socket,asyncio.Semaphore(1));socket.session=session
        with patch("services.conversation.api.transcribe",AsyncMock(return_value="What does your indexed paper say about a bucket wheel excavator?")) as stt,patch("services.conversation.retrieve",return_value="Evidence") as retrieval,patch("services.conversation.api.generate",side_effect=generated) as generation,patch("services.conversation.api.synthesize",AsyncMock(return_value=b"RIFF")) as tts:
            await session.start(message());await session.task
            assert socket.events[-1]["type"]=="done"
            assert stt.call_count==retrieval.call_count==generation.call_count==1
            audio=[e for e in socket.events if e["type"]=="audio"]
            assert [e["sequence"] for e in audio]==list(range(len(audio)))
            assert tts.call_count==len(audio)==2
            assert len(session.history)==2
            await session.start(message())
            assert stt.call_count==1 and socket.events[-1]["type"]=="duplicate"
            other=Conversation(Socket(),asyncio.Semaphore(1));assert other.history==[]
    asyncio.run(run())

def test_missing_index_evidence_still_uses_model():
    async def run():
        socket=Socket();session=Conversation(socket,asyncio.Semaphore(1));socket.session=session
        with patch("services.conversation.api.transcribe",AsyncMock(return_value="What is coal?")),patch("services.conversation.retrieve",return_value="") as retrieval,patch("services.conversation.api.generate",side_effect=generated) as generation,patch("services.conversation.api.synthesize",AsyncMock(return_value=b"RIFF")):
            await session.start(message());await session.task
            retrieval.assert_not_called()
            generation.assert_called_once()
            assert socket.events[-1]["type"]=="done"
            assert session.history[-1]["content"]

    asyncio.run(run())

def test_interrupt_cancels_inflight_and_fences_old_turn():
    async def run():
        socket=Socket();session=Conversation(socket,asyncio.Semaphore(1));socket.session=session
        cancelled=asyncio.Event();started=asyncio.Event()
        async def blocked(*args):
            started.set()
            try: await asyncio.sleep(20)
            finally: cancelled.set()
        with patch("services.conversation.api.transcribe",side_effect=blocked):
            await session.start(message());await started.wait();old=session.task
            await session.start(message("request-0002"))
            assert old.cancelled() and cancelled.is_set()
            assert session.current=="request-0002"
            await session.cancel()
            assert not any(e["type"]=="audio" for e in socket.events)
    asyncio.run(run())

def test_tts_failure_recovers_without_regeneration():
    async def run():
        socket=Socket();session=Conversation(socket,asyncio.Semaphore(1));socket.session=session
        with patch("services.conversation.api.transcribe",AsyncMock(return_value="Hello")),patch("services.conversation.retrieve",return_value=""),patch("services.conversation.api.generate",side_effect=generated) as generation,patch("services.conversation.api.synthesize",AsyncMock(side_effect=RuntimeError("failed"))):
            await session.start(message());await session.task
            assert socket.events[-1]["recoverable"] and session.history[-1]["content"]
            assert len(session.recovery)==2
            with patch("services.conversation.api.synthesize",AsyncMock(return_value=b"RIFF")):
                await session.recover();await session.task
            assert socket.events[-1]["type"]=="done" and generation.call_count==1
    asyncio.run(run())

def test_retrieval_failure_still_allows_general_answer():
    async def run():
        socket=Socket();session=Conversation(socket,asyncio.Semaphore(1));socket.session=session
        with patch("services.conversation.api.transcribe",AsyncMock(return_value="What is coal?")),patch("services.conversation.retrieve",side_effect=RuntimeError("broken index")) as retrieval,patch("services.conversation.api.generate",side_effect=generated) as generation,patch("services.conversation.api.synthesize",AsyncMock(return_value=b"RIFF")):
            await session.start(message());await session.task
            retrieval.assert_not_called()
            generation.assert_called_once()
            assert socket.events[-1]["type"]=="done"

    asyncio.run(run())

def test_bounded_audio_lookahead():
    async def run():
        class SlowSocket(Socket):
            async def send_json(self,event): self.events.append(event)
        socket=SlowSocket();session=Conversation(socket,asyncio.Semaphore(1));session.current="bounded-0001"
        queue=asyncio.Queue()
        for i in range(config.AUDIO_QUEUE_LIMIT+2): queue.put_nowait(str(i))
        queue.put_nowait(None)
        with patch("services.conversation.api.synthesize",AsyncMock(return_value=b"audio")) as synth:
            worker=asyncio.create_task(session.audio_worker(queue))
            await asyncio.sleep(.02)
            assert synth.call_count==config.AUDIO_QUEUE_LIMIT
            session.acknowledge({"request_id":session.current,"sequence":0})
            await asyncio.sleep(.02)
            assert synth.call_count==config.AUDIO_QUEUE_LIMIT+1
            worker.cancel()
            try: await worker
            except asyncio.CancelledError: pass
    asyncio.run(run())


def test_timeout_returns_error_and_releases_capacity():
    async def run():
        socket=Socket();capacity=asyncio.Semaphore(1);session=Conversation(socket,capacity)
        async def blocked(*args): await asyncio.sleep(10)
        with patch.object(config,"TURN_TIMEOUT_SECONDS",.02),patch("services.conversation.api.transcribe",side_effect=blocked):
            await session.start(message());await session.task
        assert socket.events[-1]["type"]=="error"
        assert "timed out" in socket.events[-1]["message"]
        assert not capacity.locked()
    asyncio.run(run())
