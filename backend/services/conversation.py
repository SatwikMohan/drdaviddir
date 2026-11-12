"""One authoritative cancellable turn per WebSocket session."""
import asyncio
import base64
import contextlib
import logging
import re
from collections import deque
import config
from services import openai_service as api
from services.persona import persona_prompt, GROUNDING
from services.retrieval import retrieve
from services.speech_chunker import IncrementalSpeechSegments

log = logging.getLogger("panman.turn")
SOCIAL = re.compile(r"^(hello|hi|hey|good (morning|evening|afternoon)|thank you|thanks|who are you|what is your name|how are you)[.!? ]*$", re.I)
ABSTENTION = "I don't have enough information to answer that reliably. Could you tell me a little more about what you mean?"

class Conversation:
    def __init__(self, socket, capacity):
        self.socket = socket
        self.capacity = capacity
        self.history = []
        self.seen = set()
        self.current = None
        self.task = None
        self.acks = {}
        self.recovery = []
        self.closed = False

    async def send(self, kind, **data):
        await self.socket.send_json(dict(type=kind, request_id=self.current, **data))

    async def cancel(self):
        if self.task and not self.task.done():
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task
        self.acks.clear()
        self.recovery.clear()

    async def start(self, message):
        rid = message.get("request_id", "")
        if not re.fullmatch(r"[a-zA-Z0-9-]{8,80}", rid):
            raise ValueError("Invalid request ID")
        if rid in self.seen:
            await self.send("duplicate")
            return
        if len(self.seen) >= config.SESSION_MAX_REQUESTS:
            await self.send("error", message="Please reload to start a fresh conversation.")
            return
        data = base64.b64decode(message.get("audio", ""), validate=True)
        if not data or len(data) > config.MAX_AUDIO_BYTES:
            raise ValueError("Empty or oversized recording")
        await self.cancel()
        self.seen.add(rid)
        self.current = rid
        self.task = asyncio.create_task(self.turn(data, message.get("mime", "")))

    def acknowledge(self, message):
        if message.get("request_id") == self.current:
            event = self.acks.get(message.get("sequence"))
            if event:
                event.set()

    async def audio_worker(self, queue):
        sequence = 0
        pending = deque()
        failed = False
        while True:
            text = await queue.get()
            if text is None:
                break
            if failed:
                self.recovery.append(text)
                continue
            try:
                if len(pending) >= config.AUDIO_QUEUE_LIMIT:
                    old = pending.popleft()
                    await asyncio.wait_for(old.wait(), config.AUDIO_ACK_TIMEOUT_SECONDS)
                data = await api.synthesize(text)
                event = asyncio.Event()
                self.acks[sequence] = event
                pending.append(event)
                await self.send("audio", sequence=sequence, audio=base64.b64encode(data).decode(), mime="audio/wav")
                sequence += 1
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                failed = True
                self.recovery.append(text)
                log.warning("Speech failed request_id=%s category=%s", self.current, type(exc).__name__)
        for event in pending:
            await asyncio.wait_for(event.wait(), config.AUDIO_ACK_TIMEOUT_SECONDS)
        self.acks.clear()
        return failed

    async def turn(self, data, mime):
        token = api.request_id.set(self.current)
        worker = None
        try:
            async with asyncio.timeout(config.TURN_TIMEOUT_SECONDS):
                async with self.capacity:
                    await self.send("state", state="transcribing")
                    question = await api.transcribe(data, mime)
                    if not question:
                        await self.send("error", message="I didn't catch any speech. Please try again.")
                        return
                    await self.send("state", state="retrieving")
                    # Exactly one normalized transcript vector. No query rewriting calls.
                    try:
                        context = await asyncio.to_thread(retrieve, question, self.history)
                    except Exception as exc:
                        log.warning("Retrieval failed request_id=%s category=%s", self.current, type(exc).__name__)
                        await self.send("error", message="I'm having trouble finding the information I need right now. Please try again shortly.")
                        return
                    queue = asyncio.Queue(config.AUDIO_QUEUE_LIMIT)
                    worker = asyncio.create_task(self.audio_worker(queue))
                    answer = ""
                    await self.send("state", state="generating")
                    if not context and not SOCIAL.fullmatch(question):
                        answer = ABSTENTION
                        await queue.put(answer)
                    else:
                        messages = self.history + [{"role":"user", "content":question}]
                        instructions = persona_prompt()+"\n"+GROUNDING+"\nIndexed evidence:\n"+(context or "No factual evidence.")
                        splitter = IncrementalSpeechSegments()
                        async for delta in api.generate(messages, instructions):
                            answer += delta
                            for sentence in splitter.push(delta):
                                await queue.put(sentence)
                        for sentence in splitter.finish():
                            await queue.put(sentence)
                    # Preserve full text even if speech fails; never regenerate to recover speech.
                    self.history.extend([{"role":"user", "content":question}, {"role":"assistant", "content":answer}])
                    while len(self.history)>config.SESSION_MAX_TURNS*2 or (len(self.history)>2 and sum(len(x["content"]) for x in self.history)>config.SESSION_MAX_CHARS):
                        del self.history[:2]
                    await queue.put(None)
                    failed = await worker
                    if failed:
                        await self.send("error", recoverable=True, message="Speech was interrupted. Tap the microphone to retry the remaining speech.")
                    else:
                        await self.send("done")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("Turn failed request_id=%s category=%s", self.current, type(exc).__name__)
            await self.send("error", message=api.public_error(exc))
        finally:
            if worker and not worker.done():
                worker.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await worker
            api.request_id.reset(token)

    async def recover(self):
        if self.task and not self.task.done():
            return
        if not self.recovery:
            return
        texts, self.recovery = self.recovery, []
        async def run():
            token = api.request_id.set(self.current)
            try:
                async with asyncio.timeout(config.TURN_TIMEOUT_SECONDS), self.capacity:
                    queue = asyncio.Queue()
                    for text in texts:
                        queue.put_nowait(text)
                    queue.put_nowait(None)
                    failed = await self.audio_worker(queue)
                    await self.send("error" if failed else "done", recoverable=failed,
                                    message="Speech is unavailable. Tap to retry." if failed else "")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await self.send("error", message=api.public_error(exc))
            finally:
                api.request_id.reset(token)
        self.task = asyncio.create_task(run())
