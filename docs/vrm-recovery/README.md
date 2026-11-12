# Original VRM recovery

> Update: mouth-only audio-reactive animation is now enabled at the user's request. Only the original `aa` target follows the existing audio analyser, with smoothing and reset on playback stop/interruption. Blink and expression targets remain neutral; automatic clips and procedural facial bone motions are disabled. This retains the source's limited mouth deformation; it is not phoneme recognition or improved mouth anatomy. `tests/mouth_browser.py` passed actual local audio playback, silence, end, pause and source removal checks. The assessment below records the earlier decision against full facial animation.

The active model is now `frontend/assets/dr-david-original.glb`, selected by `AVATAR_MODEL_FILE` in `backend/config.py`. It is a byte-identical copy of `Meshy_AI_Distinguished_Orator__1109152616_texture.vrm` from the supplied Downloads path. The source is already a GLB v2 container; no mesh conversion, vertex reordering or sparse target expansion was needed. Its embedded textures and VRMC_vrm metadata are preserved. SHA-256: `53424559c3efcd951aa9b3188616b68f2bf48bf49202fb5b4b415683e9e46602`.

The existing Three.js GLTFLoader reads its standard glTF geometry, skinning and morph targets. This does not add a VRM expression runtime: the VRM preset bindings are preserved as metadata, not automatically animated. The existing 45-degree A-pose continues to work.

The former `scene.gltf` and all its resources remain unchanged for rollback. Its inventory is `../converted-gltf-inventory.json`. The current canonical inventory, `../facial-asset-inventory.json`, and this directory's `asset-inventory.json` describe the recovered GLB.

## Recovered data and visual limits

- 28,456 base vertex records, one skinned mesh, 22 body bones.
- Eleven named morph targets with matching POSITION and NORMAL counts: `aa`, `ih`, `ee`, `oh`, `ou`, `blinkLeft`, `blinkRight`, `blink`, `happy`, `angry`, `surprised`.
- Sparse morph data loads correctly in the existing Three.js version. No targets are rejected by the structural guard.
- `surprised` duplicates the `aa` POSITION deformation in the source. The other POSITION target arrays are distinct.
- No lip or jaw bones are present; this is a morph-based facial asset.

All eleven targets were rendered at 0, .25, .5, .75 and 1, producing [mouth](mouth.jpg) and [expression](expressions.jpg) contact sheets. These prove that the recovered deformations load, not that they meet realistic facial-animation acceptance.

**Automatic facial animation remains inactive.** Mouth shapes produce small surface changes; a convincing jaw opening and mouth interior were not demonstrated. Blink targets noticeably pull the brow/eye region at full strength, failing the original requirement that blinking not distort eyebrows. Teeth, tongue, mouth cavity and anatomical lid closure remain unverified. Increasing weights beyond 1 or adding invented bone motions is not a valid repair. The original task explicitly prioritized visual quality over simply making the mouth move.

The next facial preparation step is to correct the authored shapes and anatomy on this original source, then repeat visual acceptance. The malformed conversion is no longer the blocker. No API-based alignment, new speech requests or lip-sync claims were added.

## Verification

- Three inventory/container tests passed, including verification that the old conversion is unchanged.
- Four application tests passed, including the mocked conversation/TTS flow. No live OpenAI requests were made.
- Edge/WebGL loaded all 11 original named targets at five influence levels without page or WebGL errors.
- A-pose arm directions and restoration of the original T-pose passed.
- The actual application renderer loaded the configured recovered GLB: [application preview](application.png), [neutral](neutral.png), [A-pose](a-pose.png), [browser report](browser-report.json).

Restart the application and reload the browser to clear the cached model/page. To roll back, select `assets/scene.gltf` in config and restart; that older conversion still has invalid facial targets.

Changed files: `backend/config.py`, `tests/test_facial_asset.py`, `tests/test_application.py`, `tests/avatar_pose_browser.py`, and the canonical inventory. Added: `frontend/assets/dr-david-original.glb`, `tests/vrm_recovery_browser.py`, the archived conversion inventory and this recovery evidence directory. Existing historical pose screenshots/measurements were refreshed by the pose test.
