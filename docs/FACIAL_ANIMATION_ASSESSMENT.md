# Facial animation assessment — 3 November 2026

> **Replacement model inspected later on 3 November:** see [updated assessment](FACIAL_ANIMATION_REASSESSMENT.md). The counts and screenshot below describe the previous asset. Its inventory is retained as `facial-asset-inventory-original.json`; `facial-asset-inventory.json` now describes the replacement. The replacement also has zero morph targets and no skeleton.

**Implementation gate: external geometry preparation is required.** The active character has zero morph targets and no skeleton. No facial animation engine, synthetic mouth, substitute face, or generated deformations have been introduced. This follows the task's explicit instruction to stop when the geometry cannot support the requested result. The original model and application code are unchanged.

## Existing application

| Area | Finding |
|---|---|
| Frontend | Plain HTML/CSS and ES modules, served by FastAPI; no React or Streamlit in the active path |
| Rendering | `frontend/avatar_renderer.py` embeds Three.js r160 and GLTFLoader through data-URI import maps |
| Active asset | `backend/config.py`: `AVATAR_MODEL_FILE = "assets/scene.gltf"`; this is glTF with external resources, not GLB |
| Packaging | `avatar_asset_manifest` checks files/case/LFS pointers; `model_uri` embeds buffer and texture resources; GLB loading is already supported |
| View | Perspective camera, 35° FOV, bounds-based head framing, hemisphere light, white key, green rim; model normalized to 2.4 units |
| Loop | One requestAnimationFrame loop, optional first animation clip, procedural whole-model rotation and breathing |
| Existing facial code | Searches for jaw/head/eyelid bones by name. None exist in the active model; jaw and blink updates have no effect |
| Microphone | getUserMedia, ScriptProcessor PCM capture, RMS/VAD, pre-roll, WAV encoding; one existing microphone button |
| Conversation | WebSocket `/voice`, request IDs, transcription → retrieval → streamed Responses generation → sentence grouping → WAV speech queue |
| Speech service | `backend/services/openai_service.py` uses configured `gpt-4o-mini-tts`, `cedar`, British voice instructions; returned WAV bytes are assembled before playback |
| Playback | One HTMLAudioElement, blob URL per segment, sequential playback, acknowledgement on end |
| Analysis | Existing MediaElementAudioSource → AnalyserNode → destination; 1024-sample time-domain RMS. Frame-dependent smoothing drives the nonexistent jaw bone |
| Timing | Audio messages contain sequence, MIME and bytes; no word, phoneme or viseme timestamps are transported |
| Cancellation | Epoch and request-ID checks; microphone/barge-in cancels the backend task, pauses/clears audio and queue, revokes URL; errors also stop playback |
| Cleanup gaps | Interaction disposes on pagehide; renderer currently does not cancel its RAF/disconnect ResizeObserver/close its analysis context. No explicit facial visibility handling |

Existing workspace changes were already extensive when this task began. They were preserved. In particular, the historical `tests/artifacts/desktop.png` depicts a different model and is not acceptance evidence for today's asset.

## Actual asset inventory

Reproduce using:

```powershell
python tools/inspect_facial_asset.py frontend/assets/scene.gltf --output docs/facial-asset-inventory.json
python -m unittest discover -s tests -p test_facial_asset.py -v
```

The read-only tool supports uncompressed core glTF and GLB. It explicitly rejects sparse/compressed geometry requiring a decoder. It records source/resource SHA-256 hashes, nodes, skins, material and texture assignments, accessor layouts for positions/normals/UVs, morph metadata and topology statistics. It is an offline inventory utility, not the requested future loaded-scene FacialRigInspector.

| Property | Observed value |
|---|---|
| Mesh name | glTF mesh unnamed; attached to node `output_unwrapped` |
| Other node | `FBX_Root` |
| Meshes / primitives | 1 / 1; face, hair and clothing share the mesh |
| Vertex records / indices | 76,620 / 76,620 |
| Triangles | 25,540 |
| Exact distinct positions | 12,767; exported vertex records are not equivalent to distinct anatomical vertices |
| Exact-position welded connected components | 1 |
| Exact-position welded boundary / nonmanifold edges | 39 / 27 |
| Attributes | POSITION, NORMAL, TEXCOORD_0; no JOINTS or WEIGHTS |
| Material | `Material_001`; baseColor and metallicRoughness textures |
| Textures | `baseColor_1.png`, `metallicRoughness_1.png` |
| Skeleton / facial bones / animation clips | 0 / 0 / 0 |
| Morph targets / names / default weights | 0 / `[]` / `[]`; no functional morph influence array is supplied |

Positional welding is used for diagnostics only. It does not repair the asset, and can merge coincident surfaces. These global counts do not localize defects to the face or prove anatomical connectivity. Normals and UV data remain in the original buffer; the inventory preserves their layouts and hashes rather than duplicating every float.

No model edit was attempted, so no modification backup was necessary at this stage. Before any external work, archive **all four files** (`scene.gltf`, `buffer.bin`, both PNGs) together and verify against the recorded hashes. Copying only the glTF loses its geometry and textures.

## Geometry suitability

**Category 2, provisional: suitable only after geometry preparation and artist verification.** This is not a certification that automatic blendshape generation will work. If facial topology cannot be repaired while retaining the surface, localized facial remodeling (category 3) will be necessary.

The fresh Edge/WebGL screenshot, [facial-current-model.png](facial-current-model.png), shows the original male character with a closed mouth and visibly faceted facial surfaces. This confirms rendering and appearance, not facial deformability.

| Region | Evidence and limitation |
|---|---|
| Lips | Visible closed lip contour; insufficient evidence of independent upper/lower lip rims or usable articulation loops. Textured detail must not be mistaken for deformation topology |
| Jaw | No bone, skin weights or shape keys; no independent jaw control |
| Mouth cavity | No separately identifiable interior; depth and sealed inner lip surfaces unverified |
| Teeth / tongue | No named or separate objects; usable teeth and tongue geometry **not established**. Their complete absence cannot be proved from mesh names alone; artist must inspect internally and add them if absent |
| Eyes | No separate eyeball objects. Surface eye appearance exists, but eyeball/lid separation and eyelid thickness are unverified |
| Eyelids | No blink controls; no demonstrated lid loops capable of closing over the eyes |
| Face | Combined triangulated mesh with global topology defects; facial edge flow and intersections need inspection in a modeling tool |

There are **no supported facial controls**. All 27 requested controls are missing: JawOpen, MouthClose, MouthFunnel, MouthPucker, MouthSmileLeft/Right, MouthStretchLeft/Right, MouthPressLeft/Right, UpperLipRaise, LowerLipDepress, MouthRollUpper/Lower, EyeBlinkLeft/Right, EyeSquintLeft/Right, BrowInnerUp, BrowOuterUpLeft/Right, BrowDownLeft/Right, CheekRaiseLeft/Right, NoseSneerLeft/Right. No AA/E/I/O/U/PP/FF/TH/DD/KK/SS/RR/SIL viseme targets exist. SIL can mean neutral conceptually, but is not a morph in this asset.

## Verified external preparation options

Meshy accepts uploaded glTF/GLB/FBX/OBJ/STL characters, supports body rigging, and exports rigged characters as FBX or GLB. Its documentation explicitly directs custom facial skeleton work to Blender or Maya. **Meshy Pro is not a verified solution for generating this facial blendshape set.** Body auto-rigging or remeshing alone does not solve this task. [Meshy rigging documentation](https://docs.meshy.ai/en/webapp/guides/3d-model/rigging)

Recommended workflow: a facial character artist using Blender remotely, optionally assisted by Faceit. Faceit supports an existing face mesh, including multiple objects, but requires a connected face and appropriate topology; it can generate shape keys and export them. It does not remove the need to prepare this character's anatomy. [Faceit geometry requirements](https://faceit-doc.readthedocs.io/en/latest/geometry/), [Faceit export](https://faceit-doc.readthedocs.io/en/beta/export/)

For browser access without local Blender, Vagon documents running Blender on a cloud computer through a browser. This is a remote workstation, not an automatic rigging service; an artist or operator still performs the work. No account, paid session, upload or subscription was created. [Vagon Blender workflow](https://vagon.io/blog/using-blender-on-a-cloud-computer)

Reallusion offers custom humanoid characterization/facial workflows, but free AccuRIG is not a facial-blendshape generator. An artist using its tools must explicitly supply and validate the facial setup for this original mesh; it should not be treated as a one-click substitute. [AccuRIG comparison](https://www.reallusion.com/auto-rig/accurig/default.html), [custom character workflow](https://cdn-www.reallusion.com/character-creator/animate-any-character.html)

### Artist handoff

1. Work from the archived original on a remote workstation. Preserve identity, silhouette, face proportions, skin texture, hair, clothes and neutral expression. No donor face or attached mouth.
2. Inspect the face internally and in wireframe. Repair duplicated/disconnected vertices and nonmanifold edges carefully; preserve UV seams and normals. Establish lip and eyelid edge flow. Document any topology changes rather than claiming identical topology.
3. Separate upper/lower lip articulation on the original face. Prepare a continuous inner mouth, appropriate teeth/gums and tongue if absent. Prepare eyelids that close over eyes without scaling eyeballs. These are integrated anatomical modeling tasks.
4. Author genuine named shape keys on the prepared original surface. Begin with jaw opening, lip closure/rounding and left/right blinks; validate before expanding to the 27 controls. Supply a name mapping and safe per-control ranges. Faceit is optional assistance.
5. Test every shape at 0, .25, .5, .75 and 1; inspect front, profile and three-quarter views. Test jaw+funnel, jaw+pucker, jaw+upper-lip-raise, smile+jaw, paired blink, brow-inner-up+squint and jaw+stretch. Supply corrective shapes or reduced safe limits where needed.
6. Export `dr-david-panman-facial.glb` with embedded textures, normals, UVs and shape keys. Blender's glTF exporter supports morph targets. Reimport the GLB and verify the actual exported shapes. [Blender glTF manual](https://docs.blender.org/manual/en/5.1/addons/import_export/scene_gltf2.html)
7. Deliver the GLB, editable source, neutral reference renders, shape-name mapping, safe ranges, individual/combination validation captures, and a list of anatomy/topology edits.

## Integration after the asset passes inspection

Place the prepared copy under `frontend/assets/` and set `AVATAR_MODEL_FILE` in `backend/config.py` to its relative path. Restart the server to clear the cached page/model/import map. Keep the current asset for rollback. Run the inventory on the new GLB first. Loading a new GLB alone will **not** activate speech morphs: the current renderer only animates selected bone names.

The deferred engine should use one loaded-scene inspector and a configurable normalized mapping across every morph mesh; a single manager should own influence writes. Layer safe base pose, speech, subtle expressions and blink envelopes, clamp to validated limits, and cache bindings outside the frame loop. Add manual sliders only for actual targets behind a server-controlled development flag; no debug panel was added, so there is currently no flag to enable.

Reuse the existing audio element and analysis graph. Select timed visemes from `audio.currentTime` when alignment metadata exists; otherwise label RMS/frequency-driven movement as audio-reactive approximation. The current backend provides no alignment data. Do not infer phonemes from amplitude or add animation-only API requests. Integrate start/playing, pause, waiting, end, error, source replacement, interruption and visibility handling; reset speech weights immediately on stop. Dispose RAF, observers, handlers and owned audio resources. These are design requirements for the next stage, **not implemented features**.

## Verification and deliverables

| Check | Result |
|---|---|
| Current glTF and external buffers/textures | Parsed; index bounds valid; resource hashes recorded |
| Current model browser rendering | Fresh headless Edge/Three.js render succeeded, zero page errors; screenshot attached |
| Inventory regression | 2 unittest tests passed: original hashes/geometry; glTF/GLB parity and truncated GLB rejection |
| Individual target levels | Not executable: zero targets; no deformation pass claimed |
| Combination tests | Not executable: zero targets |
| Mouth interior, teeth, tongue, eyelid acceptance | Unverified; external modeling gate remains |
| Audio-synchronized facial movement | Not executable with this asset; existing pipeline inspected, no new audio behavior implemented or tested |
| Production UI | Unchanged; no debug panel, extra buttons or text input added |

An existing test, `tests/test_application.py::test_assets_exact_case_and_rig`, asserts a jaw node exists. That assertion conflicts with today's configured asset. It was not weakened or used as evidence that a rig exists. The full existing suite was not run for this inspection-only change.

Files created in this task (no existing application files modified):

- `tools/inspect_facial_asset.py`: reusable read-only asset inventory CLI.
- `tests/test_facial_asset.py`: inventory/container checks.
- `docs/facial-asset-inventory.json`: actual geometry, rig and preservation inventory.
- `docs/facial-current-model.png`: current rendered character evidence.
- `docs/FACIAL_ANIMATION_ASSESSMENT.md`: assessment, limitations and external handoff.

Inspection and preparation documentation are complete. Facial blendshape authoring, runtime morph animation, viseme mapping, expressions, blinking and their visual/audio acceptance remain blocked by the unprepared character asset; none are reported as successfully implemented.
