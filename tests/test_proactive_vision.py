import asyncio
import base64
import time
from unittest.mock import AsyncMock, patch

import config
from services.conversation import Conversation


class Socket:
    def __init__(self):
        self.events = []
        self.session = None

    async def send_json(self, event):
        self.events.append(event)
        if event["type"] == "audio" and self.session:
            self.session.acknowledge(event)


def scene(sequence=1):
    return {"scene_summary": "A person holds up a labelled diagram", "objects": ["diagram"],
            "visible_text": [], "confidence": .9, "sequence_id": sequence,
            "timestamp": "2026-11-16T00:00:00Z", "status": "available", "received_at": time.monotonic()}


async def brief_remark(*args):
    yield "Would you like a hand with that diagram?"


def test_notable_scene_can_trigger_echo_comment():
    async def run():
        socket = Socket()
        session = Conversation(socket, asyncio.Semaphore(1))
        session.vision.enabled = True
        session.vision.latest = scene()
        with patch.object(config, "VISION_PROACTIVE_CHANGE_IDLE_SECONDS", 0), \
             patch("services.conversation.api.generate", side_effect=brief_remark) as generate, \
             patch("services.conversation.api.synthesize", AsyncMock(return_value=b"RIFF")) as synthesize:
            session._visual_observation(session.vision.latest, 0.5)
            await session.proactive_task
        assert generate.call_count == 1
        synthesize.assert_awaited_once_with("Would you like a hand with that diagram?")
        assert [event["type"] for event in socket.events] == ["proactive_audio"]
        assert socket.events[0]["scene_sequence"] == 1

    asyncio.run(run())


def test_listening_cancels_pending_proactive_comment():
    async def blocked(*args):
        await asyncio.sleep(10)
        yield "This should never be spoken."

    async def run():
        socket = Socket()
        session = Conversation(socket, asyncio.Semaphore(1))
        session.vision.enabled = True
        session.vision.latest = scene()
        with patch.object(config, "VISION_PROACTIVE_CHANGE_IDLE_SECONDS", 0), \
             patch("services.conversation.api.generate", side_effect=blocked), \
             patch("services.conversation.api.synthesize", AsyncMock(return_value=b"RIFF")) as synthesize:
            session._visual_observation(session.vision.latest, 0.5)
            await session.set_client_state("listening")
            assert not socket.events
            synthesize.assert_not_awaited()

    asyncio.run(run())


def test_idle_scene_can_invite_interaction_once():
    async def run():
        socket = Socket()
        session = Conversation(socket, asyncio.Semaphore(1))
        session.vision.enabled = True
        session.vision.latest = scene()
        session.idle_since = time.monotonic() - 60
        with patch("services.conversation.api.generate", side_effect=brief_remark) as generate, \
             patch("services.conversation.api.synthesize", AsyncMock(return_value=b"RIFF")):
            session._visual_observation(session.vision.latest, 0.0)
            await session.proactive_task
            session.vision.latest = scene(2)
            session._visual_observation(session.vision.latest, 0.0)
        assert generate.call_count == 1
        assert [event["type"] for event in socket.events] == ["proactive_audio"]

    asyncio.run(run())


def test_scene_change_waits_for_idle_without_losing_change_reason():
    async def run():
        socket = Socket()
        session = Conversation(socket, asyncio.Semaphore(1))
        session.vision.enabled = True
        session.vision.latest = scene()
        with patch.object(config, "VISION_PROACTIVE_CHANGE_IDLE_SECONDS", .05), \
             patch.object(config, "VISION_PROACTIVE_IDLE_SECONDS", 45), \
             patch("services.conversation.api.generate", side_effect=brief_remark) as generate, \
             patch("services.conversation.api.synthesize", AsyncMock(return_value=b"RIFF")):
            session._visual_observation(session.vision.latest, .5)
            session.vision.latest = scene(2)
            session._visual_observation(session.vision.latest, 0)
            assert session.pending_proactive == (2, "change")
            await asyncio.sleep(.1)
            assert session.proactive_task is not None
            await session.proactive_task
        assert generate.call_count == 1
        assert socket.events[0]["scene_sequence"] == 2

    asyncio.run(run())


def test_scene_question_uses_frame_submitted_with_utterance():
    async def answer(messages, instructions):
        assert "New scene" in instructions
        assert "Previous scene" not in instructions
        yield "I can see the new scene."

    async def run():
        socket = Socket()
        session = Conversation(socket, asyncio.Semaphore(1))
        socket.session = session
        session.vision.enabled = True
        old = scene(1)
        old["scene_summary"] = "Previous scene"
        session.vision.latest = old
        session.vision.sequence = 2
        new = scene(2)
        new["scene_summary"] = "New scene"
        with patch("services.conversation.api.transcribe", AsyncMock(return_value="What is the scene update?")), \
             patch.object(session.vision, "wait_for_sequence", AsyncMock(return_value=new)) as wait, \
             patch("services.conversation.api.generate", side_effect=answer), \
             patch("services.conversation.api.synthesize", AsyncMock(return_value=b"RIFF")):
            await session.start({"request_id": "visual-0001", "audio": base64.b64encode(b"audio").decode(),
                                 "mime": "audio/wav", "visual_frame_sent": True})
            await session.task
        wait.assert_awaited_once_with(2, config.VISION_QUESTION_WAIT_SECONDS)
        assert any(event["type"] == "audio" for event in socket.events)

    asyncio.run(run())
