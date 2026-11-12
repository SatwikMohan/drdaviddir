import asyncio
from unittest.mock import AsyncMock, patch

from services.conversation import Conversation
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


async def identity(*args):
    yield "I am Dr David Penman, the first founder-principal of the Indian School of Mines at Dhanbad."


def test_identity_uses_model_and_facts_without_retrieval():
    async def run():
        socket = Socket()
        session = Conversation(socket, asyncio.Semaphore(1))
        socket.session = session
        session.current = "identity-0001"
        with patch("services.conversation.api.transcribe", AsyncMock(return_value="Who are you?")), \
             patch("services.conversation.retrieve") as retrieve, \
             patch("services.conversation.api.generate", side_effect=identity) as generate, \
             patch("services.conversation.api.synthesize", AsyncMock(return_value=b"RIFF")) as synthesize:
            await session.turn(b"audio", "audio/wav")
        retrieve.assert_not_called()
        generate.assert_called_once()
        assert "first founder-principal" in generate.call_args.args[1]
        assert session.history[-1]["content"].startswith("I am Dr David Penman")
        synthesize.assert_awaited_once()
        assert socket.events[-1]["type"] == "done"

    asyncio.run(run())


def test_greeting_uses_model_without_retrieval():
    async def greeting(*args):
        yield "Good morning. How may I help you?"

    async def run():
        socket = Socket()
        session = Conversation(socket, asyncio.Semaphore(1))
        socket.session = session
        session.current = "identity-0002"
        with patch("services.conversation.api.transcribe", AsyncMock(return_value="Good morning!")), \
             patch("services.conversation.retrieve") as retrieve, \
             patch("services.conversation.api.generate", side_effect=greeting) as generate, \
             patch("services.conversation.api.synthesize", AsyncMock(return_value=b"RIFF")):
            await session.turn(b"audio", "audio/wav")
        retrieve.assert_not_called()
        generate.assert_called_once()
        assert session.history[-1]["content"].startswith("Good morning")
        assert socket.events[-1]["type"] == "done"

    asyncio.run(run())


def test_general_question_with_empty_index_still_uses_model():
    async def answer(*args):
        yield "Coal is a sedimentary rock formed from ancient plant material."

    async def run():
        socket = Socket()
        session = Conversation(socket, asyncio.Semaphore(1))
        socket.session = session
        session.current = "identity-0003"
        with patch("services.conversation.api.transcribe", AsyncMock(return_value="What is coal?")), \
             patch("services.conversation.retrieve", return_value="") as retrieve, \
             patch("services.conversation.api.generate", side_effect=answer) as generate, \
             patch("services.conversation.api.synthesize", AsyncMock(return_value=b"RIFF")):
            await session.turn(b"audio", "audio/wav")
        retrieve.assert_called_once()
        generate.assert_called_once()
        assert "general knowledge" in generate.call_args.args[1]
        assert session.history[-1]["content"].startswith("Coal is")

    asyncio.run(run())