"""Asset inspection tests; no provider requests or rendering dependencies."""
import json
from pathlib import Path
import struct
import tempfile
import unittest

from tools.inspect_facial_asset import inspect


ROOT = Path(__file__).resolve().parents[1]


class FacialAssetTests(unittest.TestCase):
    def test_current_asset_matches_recorded_inventory(self):
        result = inspect(ROOT / "frontend/assets/scene.gltf")
        recorded = json.loads((ROOT / "docs/facial-asset-inventory.json").read_text())
        self.assertEqual(result["files"], recorded["files"])
        self.assertEqual(result["meshes"], recorded["meshes"])
        self.assertEqual(result["skins"], [])
        self.assertEqual(result["meshes"][0]["primitives"][0]["morph_target_count"], 0)

    def test_glb_and_gltf_have_same_geometry_inventory(self):
        # Synthetic triangle checks container parsing, not facial deformation quality.
        binary = struct.pack("<9f", 0, 0, 0, 1, 0, 0, 0, 1, 0)
        model = {"asset": {"version": "2.0"}, "buffers": [{"byteLength": len(binary)}],
                 "bufferViews": [{"buffer": 0, "byteLength": len(binary)}],
                 "accessors": [{"bufferView": 0, "componentType": 5126, "type": "VEC3", "count": 3}],
                 "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}]}
        data = json.dumps(model).encode()
        data += b" " * (-len(data) % 4)
        glb = struct.pack("<4sII", b"glTF", 2, 28 + len(data) + len(binary))
        glb += struct.pack("<II", len(data), 0x4E4F534A) + data
        glb += struct.pack("<II", len(binary), 0x004E4942) + binary
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "model.glb").write_bytes(glb)
            result = inspect(folder / "model.glb")
            (folder / "buffer.bin").write_bytes(binary)
            model["buffers"][0]["uri"] = "buffer.bin"
            (folder / "model.gltf").write_text(json.dumps(model))
            self.assertEqual(result["meshes"], inspect(folder / "model.gltf")["meshes"])
            (folder / "model.glb").write_bytes(glb[:-4])
            with self.assertRaisesRegex(ValueError, "header"):
                inspect(folder / "model.glb")


if __name__ == "__main__":
    unittest.main()
