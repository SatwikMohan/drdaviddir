# Model inspection and A-pose — 10 November 2026

> Update: the app now uses the [recovered original VRM/GLB](vrm-recovery/README.md). The malformed morph findings below apply to the preserved converted `scene.gltf`, not the newly active GLB.

The new model contains a usable body skeleton. The application now lowers its arms to an A-pose at load time. The source glTF, binary buffer, textures and bind matrices remain unchanged.

## Model findings

- One mesh attached to `output_unwrapped`, 91,863 vertex records, 30,621 triangles.
- POSITION, NORMAL, TEXCOORD_0, JOINTS_0 and WEIGHTS_0 each have matching vertex counts.
- One skin with 22 bones, including LeftArm/LeftForeArm/LeftHand and their right-side equivalents. No animation clips are present.
- Eleven morph targets exist, named `0` through `10`, with zero default weights. **None is usable as exported.** Each POSITION target accessor has 28,436 entries, while the base POSITION accessor has 91,863. Morph deltas must correspond to the base mesh's vertices.
- All eleven target data blocks are byte-for-byte identical (SHA-256 `9fc6467c3fcf3ab0fc9a10561d33a9d489610424481b2f92a4d0991dc53ad4aa`). They do not supply eleven distinct facial expressions. This is separate from the count mismatch.
- No jaw or eyelid bones exist. Head and neck bones provide body articulation, not facial expression controls.
- The neutral face still has visible faceting/irregular contours. Mouth interior, teeth, tongue and blink suitability remain unverified.

The updated `facial-asset-inventory.json` includes structural validation errors. The November 3 replacement inventory is retained in `facial-asset-inventory-nov03.json`. Older assessments are historical.

## A-pose implementation

`frontend/assets/avatar_pose.js` applies an explicit profile for this skeleton. It computes each upper arm's world direction, rotates it toward 45 degrees below horizontal, converts the rotation into the bone parent's coordinate system and refreshes skinned bounds. Shoulder, forearm and hand local rotations are preserved. The returned controller can restore the original rotations. Missing arm bones cause a graceful no-op.

`frontend/avatar_renderer.py` loads the module through the existing offline import map and applies the pose before camera fitting. No per-frame scene traversal was introduced. The current model has no animation clips that could overwrite the arm pose; if a future model adds such clips, their arm tracks will need explicit blending with this rest pose.

Configuration in `backend/config.py`:

```python
AVATAR_A_POSE = True
AVATAR_ARM_LOWERING_DEGREES = 45
```

Set `AVATAR_A_POSE = False` to display the original pose. The angle is the desired upper-arm slope below horizontal, allowed from 0 to 60 degrees. Restart the application and reload the browser after changes because renderer output is cached. This is a display pose, not a rewritten skeletal bind pose or a new exported asset.

Malformed morph attributes are disabled in memory with a console warning before rendering. The source remains available for correction. Valid, count-matching target sets are left untouched; matching counts alone still would not certify deformation quality.

## Verification

- Two Python inventory/container tests passed, including malformed morph count detection and unchanged source/resource hashes.
- Offline Edge/WebGL test loaded the actual model; verified both arm slopes at 45 degrees, hands below elbows, and exact restoration of original bone positions within 1e-6.
- Both the pose test and actual application renderer produced no WebGL/page errors.
- Full-body visual inspection showed arms clear of the torso without an obvious detached shoulder at the tested angle. This is not a certification of all clothing skin weights or arbitrary poses.
- No live OpenAI calls were made; speech behavior was not changed.

Evidence: [original T-pose](avatar-t-pose.png), [A-pose](avatar-a-pose.png), [application framing](avatar-a-pose-app.png), [face close-up](avatar-latest-face.png), [bone measurements](avatar-pose-validation.json).

Reproduce:

```powershell
python -m unittest discover -s tests -p test_facial_asset.py -v
.\.venv\Scripts\python.exe tests/avatar_pose_browser.py
```

## Facial export correction required

Return to the authoring project and ensure distinct facial shape keys exist on the final mesh. Export all morph targets using the same final vertex ordering/count as the base mesh, accounting for any triangulation or UV/normal seam splitting. Do not pad/truncate target arrays or rename these identical blocks as visemes. Use meaningful names such as jawOpen and eyeBlinkLeft only for genuinely authored movements, then reimport and test the exported file. No facial speech or blinking controls have been enabled by this change.

Changed code: `backend/config.py`, `frontend/avatar_renderer.py`, `tools/inspect_facial_asset.py`, `tests/test_facial_asset.py`. New code: `frontend/assets/avatar_pose.js`, `tests/avatar_pose_browser.py`. Documentation/evidence: this report, updated inventory, archived November 3 inventory, five screenshots/measurement files linked above, and historical-report notices.
