"""Reusable SDK clients and content-free request accounting."""
import asyncio
import contextvars
import json
import logging
import time
from contextlib import contextmanager
from functools import lru_cache
import openai
import config

request_id = contextvars.ContextVar("request_id", default="indexing")
log = logging.getLogger("panman.usage")

class ConfigurationError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def client():
    if not config.OPENAI_API_KEY:
        raise ConfigurationError("OpenAI credentials are not configured on the server.")
    return openai.OpenAI(api_key=config.OPENAI_API_KEY, timeout=config.OPENAI_TIMEOUT_SECONDS,
                         max_retries=config.OPENAI_MAX_RETRIES)

@lru_cache(maxsize=1)
def async_client():
    if not config.OPENAI_API_KEY:
        raise ConfigurationError("OpenAI credentials are not configured on the server.")
    return openai.AsyncOpenAI(api_key=config.OPENAI_API_KEY, timeout=config.OPENAI_TIMEOUT_SECONDS,
                              max_retries=config.OPENAI_MAX_RETRIES)

@contextmanager
def usage(service, model):
    started = time.monotonic()
    record = dict(request_id=request_id.get(), service=service, model=model,
                  request_count=1, retry_count=0, error=None, usage=None)
    try:
        yield record
    except BaseException as exc:
        record["error"] = type(exc).__name__
        raise
    finally:
        record["latency_ms"] = round((time.monotonic()-started)*1000, 1)
        prices = config.API_PRICING.get(model)
        actual = record.get("usage") or {}
        inputs = actual.get("input_tokens", actual.get("prompt_tokens"))
        outputs = actual.get("output_tokens", actual.get("completion_tokens"))
        if service == "embeddings":
            inputs = actual.get("total_tokens", inputs)
            outputs = 0
        if prices and inputs is not None and outputs is not None:
            record["estimated_usd"] = (inputs*prices["input_per_million"] + outputs*prices["output_per_million"])/1_000_000
        if config.DIAGNOSTICS_ENABLED:
            log.info(json.dumps(record))

def record_usage(record, response):
    value = getattr(response, "usage", None)
    record["usage"] = value.model_dump() if hasattr(value, "model_dump") else value

def public_error(exc):
    if isinstance(exc, ConfigurationError):
        return "OpenAI credentials are missing on the server. Please contact the operator."
    if isinstance(exc, openai.AuthenticationError):
        return "The server's OpenAI credentials were rejected. Please contact the operator."
    if isinstance(exc, openai.RateLimitError):
        return "The voice service is busy or its credit limit was reached. Please try again later."
    if isinstance(exc, (openai.APITimeoutError, TimeoutError)):
        return "The connection timed out. Please try speaking again."
    if isinstance(exc, openai.APIConnectionError):
        return "Cannot connect to OpenAI. Please check the server's internet connection."
    if isinstance(exc, openai.APIError):
        return "The voice service is temporarily unavailable. Please try again."
    return "This conversation could not continue. Please try again or contact the operator."

async def transcribe(data, mime):
    suffix = {"audio/webm":"webm", "audio/ogg":"ogg", "audio/mp4":"m4a", "audio/wav":"wav"}.get(mime.split(";")[0])
    if not suffix or not data or len(data) > config.MAX_AUDIO_BYTES:
        raise ValueError("Invalid recording")
    with usage("transcription", config.OPENAI_STT_MODEL) as record:
        record["audio_input_bytes"] = len(data)
        response = await async_client().audio.transcriptions.create(
            model=config.OPENAI_STT_MODEL, file=("utterance."+suffix, data, mime), language="en")
        record_usage(record, response)
        return " ".join(response.text.split())

async def generate(messages, instructions):
    with usage("responses", config.OPENAI_CHAT_MODEL) as record:
        stream = await async_client().responses.create(model=config.OPENAI_CHAT_MODEL,
            instructions=instructions, input=messages, stream=True, store=False,
            max_output_tokens=config.CHAT_MAX_OUTPUT_TOKENS)
        async with stream:
            async for event in stream:
                if event.type == "response.output_text.delta":
                    yield event.delta
                elif event.type == "response.completed":
                    record_usage(record, event.response)
                elif event.type in {"response.failed", "response.incomplete", "error"}:
                    raise RuntimeError("Generation did not complete")

async def synthesize(text):
    with usage("speech", config.OPENAI_TTS_MODEL) as record:
        # One request per complete group; binary chunks are assembled into one playable WAV.
        voice = ({"id": config.OPENAI_TTS_CUSTOM_VOICE_ID}
                 if config.OPENAI_TTS_CUSTOM_VOICE_ID else config.OPENAI_TTS_VOICE)
        async with async_client().audio.speech.with_streaming_response.create(
            model=config.OPENAI_TTS_MODEL, voice=voice, input=text,
            instructions=config.OPENAI_TTS_INSTRUCTIONS, speed=config.OPENAI_TTS_SPEED, response_format="wav") as response:
            chunks = []
            async for chunk in response.iter_bytes():
                chunks.append(chunk)
            data = b"".join(chunks)
            record["audio_output_bytes"] = len(data)
            return data
