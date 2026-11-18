# Conversational behaviour

The browser replaces the generic “Just a moment...” message with the stage it is actually waiting for: transcription, current-scene analysis, retrieval, answer generation, or spoken-reply preparation. The avatar makes a small thinking movement while processing; its mouth remains driven by audio playback.

After transcription, `backend/services/behaviour.py` classifies the question with local rules and selects a short, non-repeating cue for slower turns. Simple questions and greetings receive no extra cue. The main retrieval and generation path starts immediately. If its first answer segment arrives before the cue is ready, the cue is cancelled. If processing continues, one progress line may be spoken after eight seconds. Its wording comes from the current stage, so it does not claim to be checking documents after retrieval has finished. Cues are temporary session state and are not written to user memory or the substantive answer history.

`TurnSpeechCoordinator` in `backend/services/conversation.py` assigns one sequence of audio events to cues and answer segments. The browser plays that sequence using its existing queue and lip-sync path. A new utterance cancels outstanding cue synthesis and the previous answer; events for old request IDs are ignored. Delivery hints accompany cue audio and adjust the existing TTS instructions slightly without changing the configured voice or speed.

Environment settings and defaults:

| Setting | Default | Effect |
| --- | ---: | --- |
| `CONVERSATIONAL_BEHAVIOUR_ENABLED` | `1` | Enable conversational cues. |
| `ACKNOWLEDGEMENT_ENABLED` | `1` | Enable short acknowledgements. |
| `PROGRESS_UPDATES_ENABLED` | `1` | Enable one stage-based update on long waits. |
| `ACKNOWLEDGEMENT_DELAY_MS` | `900` | Wait after transcription before considering a cue. |
| `PROGRESS_UPDATE_DELAY_MS` | `8000` | Wait after transcription before a progress cue. |
| `PHRASE_REPETITION_WINDOW` | `5` | Avoid recent cues within a session. |

Run `.\.venv\Scripts\python.exe -m pytest tests/test_behaviour.py tests/test_latency_pipeline.py tests/test_openai_integration.py -q` from the repository root. With the backend running at `http://127.0.0.1:8000`, run `.\.venv\Scripts\python.exe tests/behaviour_browser_smoke.py` to check browser states and ordered playback in Edge. For a live check, ask one simple question and one question that requires retrieval, then interrupt a long answer. Spoken cues require an extra TTS request when they are actually used. Their first-audio latency depends on the speech provider; the immediate on-screen stage text requires no provider call.
