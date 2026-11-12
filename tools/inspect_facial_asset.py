"""Read-only glTF/GLB inventory. No geometry or facial controls are generated.

Usage: python tools/inspect_facial_asset.py frontend/assets/scene.gltf --output docs/facial-asset-inventory.json
Supports uncompressed, non-sparse core glTF accessors; fails explicitly otherwise.
"""
import argparse
import base64
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
from urllib.parse import unquote


def inspect(path):
    path = Path(path)
    raw = path.read_bytes()
    binary = None
    if raw[:4] == b"glTF":
        magic, version, length = struct.unpack_from("<4sII", raw)
        if version != 2 or length != len(raw):
            raise ValueError("Invalid GLB header")
        offset = 12
        model = None
        while offset < length:
            size, kind = struct.unpack_from("<II", raw, offset)
            chunk = raw[offset + 8:offset + 8 + size]
            if len(chunk) != size:
                raise ValueError("Truncated GLB chunk")
            if kind == 0x4E4F534A:
                model = json.loads(chunk)
            elif kind == 0x004E4942:
                binary = chunk
            offset += 8 + size
        if model is None:
            raise ValueError("Missing GLB JSON")
    else:
        model = json.loads(raw)
    files = {path.name: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}}

    def resource(uri):
        if uri.startswith("data:"):
            header, payload = uri.split(",", 1)
            if ";base64" not in header:
                raise ValueError("Only base64 data URIs are supported")
            return base64.b64decode(payload, validate=True)
        target = (path.parent / unquote(uri)).resolve()
        if not target.is_relative_to(path.parent.resolve()):
            raise ValueError("Resource outside model directory")
        data = target.read_bytes()
        files[uri] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        return data

    buffers = [resource(b["uri"]) if "uri" in b else binary for b in model.get("buffers", [])]
    for definition, data in zip(model.get("buffers", []), buffers):
        if data is None or len(data) < definition["byteLength"]:
            raise ValueError("Missing or truncated buffer")
    for image in model.get("images", []):
        if "uri" in image:
            resource(image["uri"])

    def accessor(index):
        a = model["accessors"][index]
        if "sparse" in a or "bufferView" not in a:
            raise ValueError("Sparse/implicit accessors require a glTF decoder")
        view = model["bufferViews"][a["bufferView"]]
        if view.get("extensions"):
            raise ValueError("Compressed buffer views require a glTF decoder")
        fmt = {5120: "b", 5121: "B", 5122: "h", 5123: "H", 5125: "I", 5126: "f"}[a["componentType"]]
        width = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}[a["type"]]
        item = struct.Struct("<" + fmt * width)
        stride = view.get("byteStride", item.size)
        offset = view.get("byteOffset", 0) + a.get("byteOffset", 0)
        return [item.unpack_from(buffers[view["buffer"]], offset + n * stride) for n in range(a["count"])]

    meshes = []
    validation_errors = []
    for mi, mesh in enumerate(model.get("meshes", [])):
        primitives = []
        for primitive in mesh["primitives"]:
            if "KHR_draco_mesh_compression" in primitive.get("extensions", {}):
                raise ValueError("Draco primitives require a glTF decoder")
            positions = accessor(primitive["attributes"]["POSITION"])
            for ti, target in enumerate(primitive.get("targets", [])):
                for semantic, ai in target.items():
                    count = model["accessors"][ai]["count"]
                    if count != len(positions):
                        validation_errors.append({"mesh": mi, "target": ti, "semantic": semantic,
                                                  "expected_count": len(positions), "actual_count": count})
            indices = [i[0] for i in accessor(primitive["indices"])] if "indices" in primitive else list(range(len(positions)))
            if any(i >= len(positions) or i < 0 for i in indices):
                raise ValueError("Index outside vertex array")
            topology = {}
            if primitive.get("mode", 4) == 4:
                if len(indices) % 3:
                    raise ValueError("Incomplete triangle")
                # Exact positional welding is diagnostic only, never an asset mutation.
                unique = {p: i for i, p in enumerate(dict.fromkeys(positions))}
                welded = [unique[p] for p in positions]
                edges = Counter()
                parent = list(range(len(unique)))
                def find(x):
                    while parent[x] != x:
                        parent[x] = parent[parent[x]]
                        x = parent[x]
                    return x
                for at in range(0, len(indices), 3):
                    a, b, c = [welded[i] for i in indices[at:at + 3]]
                    for x, y in ((a, b), (b, c), (c, a)):
                        edges[tuple(sorted((x, y)))] += 1
                        parent[find(x)] = find(y)
                topology = {"triangles": len(indices) // 3, "exact_unique_positions": len(unique),
                            "position_welded_components": len({find(x) for x in welded}),
                            "position_welded_boundary_edges": sum(n == 1 for n in edges.values()),
                            "position_welded_nonmanifold_edges": sum(n > 2 for n in edges.values())}
            primitives.append({"vertices": len(positions), "indices": len(indices),
                               "attributes": primitive["attributes"], "material": primitive.get("material"),
                               "morph_target_count": len(primitive.get("targets", [])),
                               "targets": primitive.get("targets", []), "topology": topology})
        meshes.append({"index": mi, "name": mesh.get("name"),
                       "node_names": [n.get("name") for n in model.get("nodes", []) if n.get("mesh") == mi],
                       "target_names": mesh.get("extras", {}).get("targetNames", []),
                       "default_weights": mesh.get("weights", []), "primitives": primitives})
    return {"source": path.as_posix(), "files": files, "meshes": meshes,
            "validation_errors": validation_errors,
            "nodes": model.get("nodes", []), "skins": model.get("skins", []),
            "animations": model.get("animations", []), "materials": model.get("materials", []),
            "textures": model.get("textures", []), "images": model.get("images", []),
            "accessors": model.get("accessors", []), "buffer_views": model.get("bufferViews", []),
            "note": "Topology is global, not anatomical proof of lips, eyelids, teeth or a mouth cavity."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = json.dumps(inspect(args.model), indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result, encoding="utf-8")
    else:
        print(result)
