# Dr. David Panman migration

## Audit and implementation plan (before implementation)

The existing product uses Streamlit (`frontend/app.py`) with an embedded browser
voice component and a Three.js renderer. FastAPI exposes separate QA, STT and TTS
routes; Streamlit also imports backend services directly. This creates multiple
owners of audio and request state. QA uses LangChain/Ollama, a second semantic
verification generation, local Chroma, lexical search, version selection and
bounded history. STT loads Whisper; TTS supports several local workers and model
downloads. Docker provisions Ollama and GPU speech models before starting UI.

Retain the document extraction/chunking code in `train_engine.py`, structured
parsers, source/page/version metadata, lexical index, staged Chroma promotion,
deterministic evidence checks, sentence buffering and the original GLTF assets.
The original character has a jaw/eye rig, no morph targets and no animation clips.
Amplitude-driven jaw movement is possible; phoneme-accurate lips are not.

Replace inference and speech with one reused official OpenAI client per process.
Replace Streamlit with a same-origin FastAPI-served browser interface, avoiding
rerun-induced requests. One WebSocket owns each session, its bounded history,
deduplication, cancellable turn task and ordered speech queue. Browser owns capture,
VAD and actual playback, with request IDs fencing every event. Keep Python config.

## Call lifecycle

An utterance causes one file transcription, one embedding (zero on cache hit),
one local retrieval, at most one streamed Responses generation, and one speech
request per sentence group. There are no rewriting/classification/validation LLM
calls and no web retrieval. Insufficient evidence uses a deterministic abstention.
SDK retries default to zero to avoid ambiguous duplicate charges. Failed TTS may
be explicitly recovered from stored text without a second LLM generation.

Indexing batches only cache misses. Cache keys include provider, model, dimensions,
normalization and input content hash. Existing ingestion skips unchanged files;
the cache also reuses unchanged chunks within changed files. New embedding spaces
build separate candidate collections. Old collections remain intact; active index
compatibility must be checked before any query. Promotion retains the existing
labelled retrieval gate. Query caches contain vectors, never retrieval results.

## Implementation sequence

1. Audit and document this plan and API lifecycle.
2. Central configuration, reusable SDK client and metadata-only usage logging.
3. OpenAI embedding cache and compatible staged ingestion.
4. Responses, file transcription and consistent instructed speech.
5. Session-owned voice lifecycle, cancellation and bounded pipelining.
6. Full-screen original character, single microphone, responsive framing.
7. State-driven rig animation and playback-driven jaw.
8. Remove obsolete runtime/startup dependencies and UI entry points.
9. Mocked API, real local Chroma and browser acceptance checks.
10. Document credentials, startup, migration and unverified live behavior.

## Documentation checked November 1, 2026

- https://developers.openai.com/api/docs/models/gpt-5.4-mini
- https://developers.openai.com/api/docs/guides/embeddings
- https://developers.openai.com/api/docs/guides/speech-to-text
- https://developers.openai.com/api/docs/guides/text-to-speech

Defaults: gpt-5.4-mini (small general Responses model), text-embedding-3-small
(1536 dimensions), gpt-transcribe (current file transcription), gpt-4o-mini-tts
(instructed Speech API), cedar (provisional listening-test candidate).
Speech API TTS is deprecated with January 6, 2027 shutdown; the documented successor
uses Realtime, which requires a workflow migration rather than changing a model ID.
No claim of accent quality or live API availability is made without live testing.
