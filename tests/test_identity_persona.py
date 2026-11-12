import asyncio
from unittest.mock import AsyncMock, patch

from services.conversation import Conversation, IDENTITY_ANSWER
from services.persona import persona_prompt


class Socket:
    def __init__(self):
        self.events = []
        self.session = None

    async def send_json(self, event):
        self.events.append(event)
        if event["type"] == "audio":
            self.session.acknowledge(event)


def test_persona_has_identity_and_conversational_character():
    prompt = persona_prompt()
    assert "You are Dr. David Penman" in prompt
    assert "patient, observant mining educator" in prompt
    assert "Speak directly as yourself in the first person" in prompt
    assert "Do not step" in prompt and "outside the role" in prompt
    assert "do not imply that you practised" in prompt


def test_identity_is_first_person_without_index_or_model():
    async def run():
        socket = Socket()
        session = Conversation(socket, asyncio.Semaphore(1))
        socket.session = session
        session.current = "identity-0001"
        with patch("services.conversation.api.transcribe", AsyncMock(return_value="Who are you?")), \
             patch("services.conversation.retrieve") as retrieve, \
             patch("services.conversation.api.generate") as generate, \
             patch("services.conversation.api.synthesize", AsyncMock(return_value=b"RIFF")) as synthesize:
            await session.turn(b"audio", "audio/wav")
        retrieve.assert_not_called()
        generate.assert_not_called()
        synthesize.assert_awaited_once_with(IDENTITY_ANSWER)
        assert session.history[-1]["content"] == IDENTITY_ANSWER
        assert IDENTITY_ANSWER.startswith("I am Dr. David Penman")
        assert "founder-principal" in IDENTITY_ANSWER
        assert socket.events[-1]["type"] == "done"

    asyncio.run(run())


def test_unrelated_factual_question_still_uses_retrieval():
    async def run():
        socket = Socket()
        session = Conversation(socket, asyncio.Semaphore(1))
        socket.session = session
        session.current = "identity-0002"
        with patch("services.conversation.api.transcribe", AsyncMock(return_value="What is a bucket wheel excavator?")), \
             patch("services.conversation.retrieve", return_value="") as retrieve, \
             patch("services.conversation.api.generate") as generate, \
             patch("services.conversation.api.synthesize", AsyncMock(return_value=b"RIFF")):
            await session.turn(b"audio", "audio/wav")
        retrieve.assert_called_once()
        generate.assert_not_called()
        assert "I don't have enough information" in session.history[-1]["content"]

    asyncio.run(run())


def test_biography_question_uses_verified_persona_facts():
    async def answer(*args):
        yield "I researched mine ventilation and mining education in India."

    async def run():
        socket = Socket()
        session = Conversation(socket, asyncio.Semaphore(1))
        socket.session = session
        session.current = "identity-0003"
        with patch("services.conversation.api.transcribe", AsyncMock(return_value="Tell me about your research")), \
             patch("services.conversation.retrieve") as retrieve, \
             patch("services.conversation.api.generate", side_effect=answer) as generate, \
             patch("services.conversation.api.synthesize", AsyncMock(return_value=b"RIFF")):
            await session.turn(b"audio", "audio/wav")
        retrieve.assert_not_called()
        assert "Norman Henderson Prize" in generate.call_args.args[1]
        assert session.history[-1]["content"].startswith("I researched")

    asyncio.run(run())
