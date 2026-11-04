# Dr. David Panman delivery report

## Implemented and verified

The application now runs as one FastAPI server with a full-screen voice-only browser
interface, one floating microphone, the original locally packaged GLTF renderer,
OpenAI services, local persistent Chroma, and isolated session histories.
Ollama/local speech inference, model provisioning, Streamlit and old typed-chat UI
entry points have been removed. No existing document/vector/model data was deleted.

1. **Architecture:** see the Mermaid diagram and workflow in [README](README.md).
   [MIGRATION](MIGRATION.md) records the audit, dependency mapping and planned API lifecycle.
2. **Files:** complete source inventory appears below. The removed-file manifest is
   [tests/removed_files.json](tests/removed_files.json). Historical reports are retained.
3. **Model/API choices:** reusable official SDK clients; Responses streaming with
   gpt-5.4-mini; Embeddings with text-embedding-3-small at 1536 dimensions; file
   transcription with gpt-transcribe; Speech with gpt-4o-mini-tts and cedar. All
   selection, deadlines, justification and official source links are in README.
4. **Calls per turn:** 3+N on an embedding cache miss; 2+N on a hit, where N is the
   number of synthesized sentence groups. Abstention skips the generation request.
   No validation, classification, query-rewriting or web-retrieval model calls.
5. **Caching/indexing:** persistent SQLite content-hash vectors, batch misses only,
   unchanged-file skips and unchanged-chunk reuse, profile/model/dimension validation.
   Cache stores vectors, not answers or retrieval results. Indexing version is 9.
6. **Migration:** separate candidate collections, manifest promotion after labelled
   recall checks, and previous collection retention. The real legacy index has NOT
   been rebuilt or promoted: there is no configured API key. Incompatible collections
   are refused before embedding a query. Tests exercise real temporary Chroma storage.
7. **Voice:** configurable local VAD, pre-roll, min/max recording lengths, automatic
   submission, request IDs, async cancellation, bounded serial synthesis, ordered
   playback with acknowledgements, natural barge-in and stale-event rejection.
   Failed speech retains the answer and supports recovery without another generation.
8. **Voice validation:** cedar plus British delivery instructions is provisional.
   No live synthesis, accent or masculine-delivery listening test was possible.
   The explicit audition script produces three paid samples when credentials exist.
9. **Character:** original model retained, head-to-chest camera framing and responsive
   viewport. Listening/processing movement, small eyelid motion and amplitude-driven
   jaw movement track lifecycle/playback. No morph targets or phoneme lip sync.
   The bundled model is Debbie Grayson and does not visually match a male doctor.
10. **Tests:** 50 passed, 3 dependency deprecation warnings. Coverage includes SDK
    client reuse/missing credentials/authentication/timeouts, embeddings/cache/profile,
    streaming/STT/TTS, metadata-only usage, real Chroma incremental indexing and safe
    migration, evidence abstention, session isolation, bounded queue, cancellation,
    duplicate IDs, speech recovery, and a mocked-provider WebSocket end-to-end turn.
    Real Edge browser acceptance passed: WebGL, desktop/mobile, one microphone/no
    text input, silence submission, playback, speech-triggered interruption, stale
    event rejection and recovery to idle. Compile checks and normal git diff checks
    pass. HTTP /health returns 200; public config contains only allowlisted settings.
11. **Install/configuration:** [README](README.md) includes Python dependencies,
    process-secret injection, document ingestion, model settings, OCR and Docker.
12. **Exact startup:** from the repository root, run
    `.\.venv\Scripts\python.exe backend/main.py`; open http://127.0.0.1:8000.
13. **Remaining validation/deployment requirements:** no live OpenAI tests or real
    microphone/acoustic tests; no production Docker build (Docker is unavailable).
    Speech API TTS retirement is scheduled for January 6, 2027; the official successor
    requires a Realtime workflow migration, not a model-string substitution.
    Production needs HTTPS, access control, and one worker. Indexing is single-process;
    do not mutate the active production index concurrently. Cancellation closes async
    streams but cannot guarantee cancellation of work already billed by the provider;
    an in-progress synchronous embedding request may finish after interruption, with
    its downstream output discarded. Refreshing/reconnecting starts a fresh session.

No cost or latency benchmark is claimed. Usage logs retain actual reported usage;
missing usage remains unknown. Configured token prices may produce estimates;
no unconfigured price or conversion from audio bytes to billable tokens is invented.

## Visual checks

- [Desktop screenshot](tests/artifacts/desktop.png)
- [Mobile screenshot](tests/artifacts/mobile.png)

## Source inventory

### Created

- `DELIVERY.md`
- `MIGRATION.md`
- `README.md`
- `backend/scripts/validate_voice.py`
- `backend/services/conversation.py`
- `backend/services/openai_service.py`
- `backend/services/persona.py`
- `backend/services/retrieval.py`
- `frontend/voice/index.html`
- `frontend/voice/interaction.js`
- `frontend/voice/style.css`
- `pytest.ini`
- `requirements-dev.txt`
- `tests/browser_smoke.py`
- `tests/removed_files.json`
- `tests/test_application.py`
- `tests/test_conversation.py`
- `tests/test_index_migration.py`
- `tests/test_openai_integration.py`

### Modified

- `Caddyfile`
- `DEPLOYMENT.md`
- `Dockerfile`
- `backend/config.py`
- `backend/evals/README.md`
- `backend/evaluate_retrieval.py`
- `backend/main.py`
- `backend/requirements.txt`
- `backend/services/embedding_service.py`
- `backend/services/language_service.py`
- `backend/train_engine.py`
- `docker-compose.yml`
- `frontend/README.md`
- `frontend/avatar_renderer.py`

### Removed

- `backend/Dockerfile`
- `backend/evals/benchmark_chat_runtime.py`
- `backend/evals/benchmark_ingestion.py`
- `backend/evals/benchmark_tts_only.py`
- `backend/evals/benchmark_voice.py`
- `backend/evals/evaluate_answer_quality.py`
- `backend/evals/evaluate_english_candidate.py`
- `backend/evals/evaluate_language_aware_tts.py`
- `backend/evals/evaluate_rag.py`
- `backend/evals/veena_smoke.py`
- `backend/routes/__init__.py`
- `backend/routes/qa_routes.py`
- `backend/routes/stt_routes.py`
- `backend/routes/tts_routes.py`
- `backend/scripts/configure_gateway.py`
- `backend/scripts/diagnose_voice.py`
- `backend/scripts/patch_f5_tts.py`
- `backend/scripts/provision_models.py`
- `backend/scripts/provision_ollama.py`
- `backend/scripts/transcribe_sample.py`
- `backend/services/audio_chunks.py`
- `backend/services/goonj_voice.py`
- `backend/services/hinglish_lexicon.py`
- `backend/services/hinglish_speech.py`
- `backend/services/indicf5_runtime.py`
- `backend/services/model_config.py`
- `backend/services/piper_worker.py`
- `backend/services/qa_service.py`
- `backend/services/request_lifecycle.py`
- `backend/services/reranker_service.py`
- `backend/services/response_stream.py`
- `backend/services/semantic_evidence.py`
- `backend/services/speech_language.py`
- `backend/services/stt_service.py`
- `backend/services/tts_service.py`
- `backend/services/veena_worker.py`
- `backend/services/voice_interaction.py`
- `backend/tests/test_custom_voice_provisioning.py`
- `backend/tests/test_direct_voice_interaction.py`
- `backend/tests/test_followup_grounding.py`
- `backend/tests/test_hinglish_speech.py`
- `backend/tests/test_language_aware_tts.py`
- `backend/tests/test_piper_worker_reuse.py`
- `backend/tests/test_production_workflow.py`
- `backend/tests/test_response_delivery.py`
- `backend/tests/test_retrieval_foundation.py`
- `backend/tests/test_semantic_evidence.py`
- `backend/tests/test_shared_config.py`
- `backend/tests/test_stream_stage_policy.py`
- `backend/tests/test_veena_voice.py`
- `backend/tests/test_versions_and_languages.py`
- `backend/tests/test_voice_lifecycle.py`
- `frontend/Dockerfile`
- `frontend/app.py`
- `frontend/assets/audio_manager.js`
- `frontend/audio_manager.py`
- `frontend/requirements.txt`
- `frontend/tests/audio_queue_smoke.html`
- `frontend/tests/test_interface.py`
- `frontend/tests/voice_browser_smoke.py`
- `frontend/theme.css`
- `frontend/visualization.py`
- `frontend/voice_query_component/index.html`
