"""Deterministic behaviour and shared audio ordering; no external API calls."""
import asyncio
import base64
from unittest.mock import AsyncMock, patch

import config
from services.behaviour import BehaviourEngine
from services.conversation import Conversation, TurnSpeechCoordinator


class Socket:
    def __init__(self):
        self.events = []
        self.session = None

    async def send_json(self, event):
        self.events.append(event)
        if event["type"] == "audio" and self.session:
            self.session.acknowledge(event)


def session():
    socket = Socket()
    conversation = Conversation(socket, asyncio.Semaphore(1))
    socket.session = conversation
    conversation.current = "behaviour-0001"
    conversation.speech = TurnSpeechCoordinator(conversation, conversation.current)
    return conversation, socket


def test_intent_and_phrase_rotation():
    engine = BehaviourEngine()
    assert engine.classify("Hello", "DIRECT_CONVERSATION") == "social"
    assert engine.classify("Tell me about yourself", "DIRECT_CONVERSATION") == "personal_intro"
    assert engine.classify("What was your thesis about?", "PERSONAL_MEMORY") == "personal"
    assert engine.classify("I'm worried about this", "DIRECT_CONVERSATION") == "emotional"
    assert engine.classify("What is your opinion?", "DIRECT_CONVERSATION") == "opinion"
    assert engine.classify("Explain the research methodology", "LOCAL_KNOWLEDGE") == "local"
    assert engine.classify("What is in the scene?", "DIRECT_CONVERSATION", True) == "visual"
    assert engine.classify("How does the circuit work?", "DIRECT_CONVERSATION") == "technical"
    assert engine.classify("And what happened next?", "DIRECT_CONVERSATION", has_history=True) == "followup"
    assert engine.classify("What time is it?", "DIRECT_CONVERSATION") == "simple"
    assert engine.acknowledgement("simple") is None
    assert engine.acknowledgement("social") is None
    first = engine.acknowledgement("academic")
    second = engine.acknowledgement("academic")
    assert first.text != second.text
    assert first.delivery == second.delivery == "curious"
    assert engine.progress("transcribing") is None
    assert engine.progress("retrieving").purpose == "progress"
    assert engine.progress("retrieving") is None


def test_fast_answer_cancels_cue_without_tts():
    async def run():
        conversation, socket = session()
        with patch.object(config, "ACKNOWLEDGEMENT_DELAY_MS", 30), \
             patch("services.conversation.api.synthesize", AsyncMock(return_value=b"RIFF")) as synthesize:
            conversation.speech.start_cues("academic")
            conversation.speech.mark_answer_started()
            await conversation.speech.stop()
        synthesize.assert_not_awaited()
        assert socket.events == []

    asyncio.run(run())


def test_disabled_behaviour_makes_no_tts_request():
    async def run():
        conversation, socket = session()
        with patch.object(config, "CONVERSATIONAL_BEHAVIOUR_ENABLED", False), \
             patch("services.conversation.api.synthesize", AsyncMock(return_value=b"RIFF")) as synthesize:
            conversation.speech.start_cues("academic")
            await asyncio.sleep(.02)
        assert conversation.speech.cue_task is None
        synthesize.assert_not_awaited()
        assert socket.events == []

    asyncio.run(run())


def test_slow_answer_plays_cue_before_final_with_one_sequence():
    async def run():
        conversation, socket = session()
        with patch.object(config, "ACKNOWLEDGEMENT_DELAY_MS", 0), \
             patch.object(config, "PROGRESS_UPDATE_DELAY_MS", 1000), \
             patch("services.conversation.api.synthesize", AsyncMock(return_value=b"RIFF")) as synthesize:
            conversation.speech.start_cues("personal")
            for _ in range(100):
                if any(e["type"] == "audio" for e in socket.events):
                    break
                await asyncio.sleep(.01)
            conversation.speech.mark_answer_started()
            await conversation.speech.stop()
            await conversation.speech.emit(b"ANSWER")
        audio = [e for e in socket.events if e["type"] == "audio"]
        assert [e["sequence"] for e in audio] == [0, 1]
        assert [e["purpose"] for e in audio] == ["acknowledgement", "answer"]
        synthesize.assert_awaited_once()
        assert synthesize.await_args.kwargs["delivery"] == "warm"

    asyncio.run(run())


def test_long_wait_gets_one_progress_update():
    async def run():
        conversation, socket = session()
        with patch.object(config, "ACKNOWLEDGEMENT_DELAY_MS", 0), \
             patch.object(config, "PROGRESS_UPDATE_DELAY_MS", 40), \
             patch("services.conversation.api.synthesize", AsyncMock(return_value=b"RIFF")) as synthesize:
            conversation.speech.stage = "retrieving"
            conversation.speech.start_cues("local")
            await conversation.speech.cue_task
        audio = [e for e in socket.events if e["type"] == "audio"]
        assert [e["sequence"] for e in audio] == [0, 1]
        assert [e["purpose"] for e in audio] == ["acknowledgement", "progress"]
        assert synthesize.await_count == 2

    asyncio.run(run())


def test_interruption_during_cue_tts_sends_no_stale_audio():
    async def run():
        conversation, socket = session()
        started = asyncio.Event()

        async def slow_synthesis(*args, **kwargs):
            started.set()
            await asyncio.sleep(10)
            return b"RIFF"

        with patch.object(config, "ACKNOWLEDGEMENT_DELAY_MS", 0), \
             patch("services.conversation.api.synthesize", side_effect=slow_synthesis):
            conversation.speech.start_cues("academic")
            await asyncio.wait_for(started.wait(), 2)
            await conversation.cancel()
        assert not any(e["type"] == "audio" for e in socket.events)

    asyncio.run(run())


def test_full_turn_cue_then_answer_stays_ordered():
    async def slow_answer(*args):
        await asyncio.sleep(.08)
        yield "The method compares the available evidence carefully."

    async def run():
        conversation, socket = session()
        with patch.object(config, "ACKNOWLEDGEMENT_DELAY_MS", 5), \
             patch.object(config, "PROGRESS_UPDATE_DELAY_MS", 500), \
             patch("services.conversation.api.transcribe", AsyncMock(return_value="Explain the methodology")), \
             patch("services.conversation.api.generate", side_effect=slow_answer), \
             patch("services.conversation.api.synthesize", AsyncMock(return_value=b"RIFF")):
            await conversation.start({"request_id": "behaviour-0002", "audio": base64.b64encode(b"audio").decode(),
                                      "mime": "audio/wav"})
            await conversation.task
        audio = [event for event in socket.events if event["type"] == "audio"]
        assert [event["sequence"] for event in audio] == [0, 1]
        assert [event["purpose"] for event in audio] == ["acknowledgement", "answer"]
        assert socket.events[-1]["type"] == "done"

    asyncio.run(run())


def test_full_turn_fast_answer_skips_cue():
    async def quick_answer(*args):
        yield "The answer is straightforward."

    async def run():
        conversation, socket = session()
        with patch.object(config, "ACKNOWLEDGEMENT_DELAY_MS", 50), \
             patch("services.conversation.api.transcribe", AsyncMock(return_value="Explain the method")), \
             patch("services.conversation.api.generate", side_effect=quick_answer), \
             patch("services.conversation.api.synthesize", AsyncMock(return_value=b"RIFF")) as synthesize:
            await conversation.start({"request_id": "behaviour-0003", "audio": base64.b64encode(b"audio").decode(),
                                      "mime": "audio/wav"})
            await conversation.task
        audio = [event for event in socket.events if event["type"] == "audio"]
        assert [event["sequence"] for event in audio] == [0]
        assert [event["purpose"] for event in audio] == ["answer"]
        synthesize.assert_awaited_once()

    asyncio.run(run())
