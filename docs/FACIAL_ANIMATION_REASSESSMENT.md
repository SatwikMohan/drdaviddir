# Replacement model inspection — 3 November 2026

The replacement glTF and its new buffer/texture were inspected successfully. It remains a static model: no facial shape keys, morph targets, skinning, skeleton, or animation clips were exported. The requested facial animation implementation is still gated on external facial preparation, per the original task's explicit stop condition.

| Property | Previous asset | Replacement |
|---|---:|---:|
| Mesh node | output_unwrapped | geometry_0 |
| Meshes / primitives | 1 / 1 | 1 / 1 |
| Vertex records | 76,620 | 11,103 |
| Triangles | 25,540 | 15,532 |
| Exact unique positions | 12,767 | 7,915 |
| Exact-position welded components | 1 | 31 |
| Exact-position welded boundary edges | 39 | 228 |
| Exact-position welded nonmanifold edges | 27 | 0 |
| Morph targets | 0 | 0 |
| Skins / skeletons | 0 | 0 |

Zero detected nonmanifold edges is an improvement in that metric. The additional boundaries/components are not automatically defects: they may represent separate surfaces, intentional openings or export seams. These global counts do not establish useful lip or eyelid edge loops. The model still requires anatomical inspection before it can be certified suitable for realistic facial deformation.

The single mesh includes POSITION, NORMAL and TEXCOORD_0 attributes. It uses one unnamed, double-sided material and `baseColor.png`. There are no JOINTS/WEIGHTS attributes, morph POSITION deltas, target names or default morph weights. No controls in the requested facial set are available, and no viseme targets exist.

## Visual result and suitability

[Fresh render of the replacement](facial-updated-model.png) was captured using the existing renderer in headless Edge. Rendering succeeded with zero page errors. The neutral mouth remains closed, and the face shows faceting and irregular contours around the cheeks and eyes. This image does not establish mouth interior depth, separate lip rims, eyelid closure, or usable teeth and tongue. Those structures remain unverified; mesh names alone cannot prove their absence.

Classification remains **category 2, provisional: requires geometry preparation and facial rigging**. If an artist cannot establish adequate facial loops without localized remodeling, category 3 applies. No claim is made that the new topology is automatically ready for blendshape generation.

## Required next export

Provide the same character with genuine authored facial shape keys exported as glTF/GLB morph targets. At minimum, validate jaw opening, mouth closure, lip rounding and independent left/right blinking before extending expressions. A remeshed model or body skeleton alone does not supply these deformations. If the authoring project already has shape keys, verify they were included in the export and survived reimport.

Use the remote artist/Blender workflow in the [original assessment](FACIAL_ANIMATION_ASSESSMENT.md). Preserve this replacement and its texture; work on a copy. No local Blender installation is required by that workflow. No model modifications, generated mouth geometry or application changes were made in this reinspection.

## Updated evidence

- `facial-asset-inventory.json` now contains the replacement's actual hashes and geometry inventory.
- `facial-asset-inventory-original.json` preserves the previous inventory for comparison; this is metadata, not a backup of the old model's bytes.
- `facial-updated-model.png` records the replacement's current rendering.
- The two inventory/container tests passed against the replacement. Individual deformation, combination and audio-to-face synchronization tests cannot run because no facial targets exist.

Reproduce with `python tools/inspect_facial_asset.py frontend/assets/scene.gltf --output docs/facial-asset-inventory.json`, then `python -m unittest discover -s tests -p test_facial_asset.py -v`.
