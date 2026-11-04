# Voice interface

Served by `backend/main.py`; no separate frontend server or build step.
`voice/interaction.js` owns capture, VAD, interruption and audio playback.
`avatar_renderer.py` packages the original GLTF and Three.js modules.
See the root README for startup and browser acceptance tests.
