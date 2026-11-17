import asyncio
import json
from types import SimpleNamespace as NS
from unittest.mock import Mock, AsyncMock, patch
import httpx
import openai
import pytest
import config
from services import openai_service as api
from services.embedding_service import OpenAIEmbeddings, embedding_profile

@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "EMBED_CACHE_FILE", str(tmp_path / "cache.sqlite"))
    monkeypatch.setattr(config, "OPENAI_EMBED_DIMENSIONS", 3)
    api.client.cache_clear()
    api.async_client.cache_clear()
    yield
    api.client.cache_clear()
    api.async_client.cache_clear()

def response(texts):
    return NS(data=[NS(index=i, embedding=[1.,float(i+1),1.]) for i,_ in enumerate(texts)], usage=NS(model_dump=lambda:{"total_tokens":len(texts)}))

def test_missing_key(monkeypatch):
    monkeypatch.setattr(config, "OPENAI_API_KEY", "")
    with pytest.raises(RuntimeError, match="credentials"):
        api.client()

def test_reuses_client(monkeypatch):
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-key")
    with patch.object(openai, "OpenAI") as factory:
        assert api.client() is api.client()
        factory.assert_called_once_with(api_key="test-key", timeout=config.OPENAI_TIMEOUT_SECONDS,max_retries=0)

def test_embeddings_persist_cache_and_deduplicate():
    create=Mock(side_effect=lambda **kw: response(kw["input"]))
    with patch("services.embedding_service.client",return_value=NS(embeddings=NS(create=create))):
        embed=OpenAIEmbeddings()
        vectors=embed.embed_documents(["same", "different", "same"])
        assert len(vectors)==3 and vectors[0]==vectors[2]
        assert create.call_count==1
        assert len(create.call_args.kwargs["input"])==2
        assert OpenAIEmbeddings().embed_query("same")==vectors[0]
        assert create.call_count==1
        embed.embed_documents(["same", "changed"])
        assert create.call_count==2
        assert create.call_args.kwargs["input"]==["changed"]

def test_dimensions_and_model_isolate_cache(monkeypatch):
    first=embedding_profile().fingerprint
    monkeypatch.setattr(config,"OPENAI_EMBED_MODEL","different-model")
    assert embedding_profile().fingerprint!=first
    monkeypatch.setattr(config,"OPENAI_EMBED_DIMENSIONS",7)
    create=Mock(return_value=response(["x"]))
    with patch("services.embedding_service.client",return_value=NS(embeddings=NS(create=create))):
        with pytest.raises(ValueError,match="dimension"):
            OpenAIEmbeddings().embed_query("x")

def test_usage_content_free(caplog):
    caplog.set_level("INFO",logger="panman.usage")
    with api.usage("embeddings","model") as record:
        api.record_usage(record,response(["private text"]))
    payload=json.loads(caplog.records[-1].message)
    assert payload["request_count"]==1 and payload["usage"]["total_tokens"]==1
    assert "private text" not in caplog.text
    assert payload["retry_count"]==0

@pytest.mark.parametrize("error",[openai.AuthenticationError("secret",response=httpx.Response(401,request=httpx.Request("POST","https://api.openai.com")),body=None),openai.APITimeoutError(request=httpx.Request("POST","https://api.openai.com")),openai.APIConnectionError(request=httpx.Request("POST","https://api.openai.com")),openai.RateLimitError("secret",response=httpx.Response(429,request=httpx.Request("POST","https://api.openai.com")),body=None)])
def test_errors_never_expose_provider_body(error):
    assert "secret" not in api.public_error(error)

class Stream:
    def __init__(self, events): self.events=events; self.closed=False
    async def __aenter__(self): return self
    async def __aexit__(self,*args): self.closed=True
    def __aiter__(self): return self.iterate()
    async def iterate(self):
        for e in self.events: yield e

def test_stream_and_transcription():
    async def run():
        stream=Stream([NS(type="response.output_text.delta",delta="Good morning."),NS(type="response.completed",response=NS(usage=None))])
        create=AsyncMock(return_value=stream)
        stt=AsyncMock(return_value=NS(text="  Hello   there ",usage=None))
        with patch.object(api,"async_client",return_value=NS(responses=NS(create=create),audio=NS(transcriptions=NS(create=stt)))):
            assert await api.transcribe(b"audio","audio/wav")=="Hello there"
            assert "".join([t async for t in api.generate([],"persona")])=="Good morning."
            assert stream.closed
            assert create.call_count==stt.call_count==1
            assert create.call_args.kwargs["store"] is False
    asyncio.run(run())

def test_tts_voice_and_cancellation():
    class AudioStream(Stream):
        async def iter_bytes(self):
            yield b"RIFF"
            yield b"audio"
    async def run():
        stream=AudioStream([])
        create=Mock(return_value=stream)
        with patch.object(api,"async_client",return_value=NS(audio=NS(speech=NS(with_streaming_response=NS(create=create))))):
            assert await api.synthesize("Good morning.")==b"RIFFaudio"
            assert stream.closed
            assert create.call_args.kwargs["voice"]==config.OPENAI_TTS_VOICE
            assert "British" in create.call_args.kwargs["instructions"]
            assert create.call_args.kwargs["speed"]==config.OPENAI_TTS_SPEED
            with patch.object(config,"OPENAI_TTS_CUSTOM_VOICE_ID","voice_approved"):
                assert await api.synthesize("Hello again.")==b"RIFFaudio"
                assert create.call_args.kwargs["voice"]=={"id":"voice_approved"}
    asyncio.run(run())
