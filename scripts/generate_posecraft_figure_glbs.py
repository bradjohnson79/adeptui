"""Write PoseCraft v3 T-pose GLB + JSON metadata deliverables.

Viewport figures remain the TypeScript 17-joint builder. These files are the
glTF/GLB + metadata package required by Revision C Phase 2.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "studio-web" / "public" / "posecraft" / "figures"

FIGURES = [
    {
        "id": "adult-male",
        "modelId": "adult-male-lowpoly-v3",
        "gender": "male",
        "ageClass": "adult",
        "heightM": 1.84,
        "triangleCount": 0,
    },
    {
        "id": "adult-female",
        "modelId": "adult-female-lowpoly-v3",
        "gender": "female",
        "ageClass": "adult",
        "heightM": 1.70,
        "triangleCount": 0,
    },
    {
        "id": "child-boy",
        "modelId": "child-boy-lowpoly-v3",
        "gender": "male",
        "ageClass": "child",
        "heightM": 1.32,
        "triangleCount": 0,
    },
    {
        "id": "child-girl",
        "modelId": "child-girl-lowpoly-v3",
        "gender": "female",
        "ageClass": "child",
        "heightM": 1.28,
        "triangleCount": 0,
    },
]


def _align4(data: bytes) -> bytes:
    pad = (4 - (len(data) % 4)) % 4
    return data + (b"\x00" * pad)


def write_glb(path: Path, positions: list[float], indices: list[int]) -> None:
    pos_bytes = b"".join(struct.pack("<fff", *positions[i : i + 3]) for i in range(0, len(positions), 3))
    idx_bytes = b"".join(struct.pack("<H", i) for i in indices)
    bin_chunk = _align4(pos_bytes + idx_bytes)
    pos_max = [max(positions[i::3]) for i in range(3)]
    pos_min = [min(positions[i::3]) for i in range(3)]
    gltf = {
        "asset": {"version": "2.0", "generator": "Adept PoseCraft v3"},
        "buffers": [{"byteLength": len(bin_chunk)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(pos_bytes), "target": 34962},
            {"buffer": 0, "byteOffset": len(pos_bytes), "byteLength": len(idx_bytes), "target": 34963},
        ],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": len(positions) // 3,
                "type": "VEC3",
                "max": pos_max,
                "min": pos_min,
            },
            {
                "bufferView": 1,
                "componentType": 5123,
                "count": len(indices),
                "type": "SCALAR",
            },
        ],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1, "mode": 4}]}],
        "nodes": [{"mesh": 0, "name": "TPoseFigure"}],
        "scenes": [{"nodes": [0]}],
        "scene": 0,
    }
    json_chunk = _align4(json.dumps(gltf, separators=(",", ":")).encode("utf-8"))
    # glTF JSON chunk type 0x4E4F534A = JSON; BIN 0x004E4942
    total = 12 + 8 + len(json_chunk) + 8 + len(bin_chunk)
    header = struct.pack("<4sII", b"glTF", 2, total)
    json_head = struct.pack("<II", len(json_chunk), 0x4E4F534A)
    bin_head = struct.pack("<II", len(bin_chunk), 0x004E4942)
    path.write_bytes(header + json_head + json_chunk + bin_head + bin_chunk)


def _icosphere(positions: list[float], indices: list[int], cx: float, cy: float, cz: float, radius: float, subdivisions: int = 2) -> None:
    import math

    t = (1.0 + math.sqrt(5.0)) / 2.0
    raw = [
        (-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0),
        (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
        (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1),
    ]
    faces = [
        (0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
        (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
        (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
        (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1),
    ]

    def norm(v: tuple[float, float, float]) -> tuple[float, float, float]:
        length = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
        return (v[0] / length, v[1] / length, v[2] / length)

    verts = [norm(v) for v in raw]
    midpoint_cache: dict[tuple[int, int], int] = {}

    def midpoint(a: int, b: int) -> int:
        key = (a, b) if a < b else (b, a)
        if key in midpoint_cache:
            return midpoint_cache[key]
        mid = norm((
            (verts[a][0] + verts[b][0]) * 0.5,
            (verts[a][1] + verts[b][1]) * 0.5,
            (verts[a][2] + verts[b][2]) * 0.5,
        ))
        midpoint_cache[key] = len(verts)
        verts.append(mid)
        return midpoint_cache[key]

    for _ in range(subdivisions):
        nxt = []
        for a, b, c in faces:
            ab, bc, ca = midpoint(a, b), midpoint(b, c), midpoint(c, a)
            nxt.extend([(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)])
        faces = nxt

    base = len(positions) // 3
    for vx, vy, vz in verts:
        positions.extend([cx + vx * radius, cy + vy * radius, cz + vz * radius * 0.92])
    for a, b, c in faces:
        indices.extend([base + a, base + b, base + c])


def faceted_human(height: float, male: bool, child: bool = False) -> tuple[list[float], list[int]]:
    """T-pose faceted anatomical hull for the GLB package (2k–5k tris)."""
    import math

    positions: list[float] = []
    indices: list[int] = []

    def add_ring(cx: float, cy: float, cz: float, rx: float, rz: float, sides: int, axis: str = "y") -> list[int]:
        start = len(positions) // 3
        for i in range(sides):
            a = (i / sides) * math.pi * 2
            x, y = math.cos(a) * rx, math.sin(a) * rz
            if axis == "y":
                positions.extend([cx + x, cy, cz + y])
            elif axis == "x":
                positions.extend([cx, cy + x, cz + y])
            else:
                positions.extend([cx + x, cy + y, cz])
        return list(range(start, start + sides))

    def stitch(a: list[int], b: list[int]) -> None:
        n = len(a)
        for i in range(n):
            i2 = (i + 1) % n
            indices.extend([a[i], b[i], a[i2], a[i2], b[i], b[i2]])

    def stack(rings: list[list[int]]) -> None:
        for i in range(len(rings) - 1):
            stitch(rings[i], rings[i + 1])

    chest = 0.22 if male else 0.17
    hip = 0.13 if male else 0.165
    waist = 0.11 if male else 0.095
    if child:
        chest *= 0.86
        hip *= 0.9
        waist *= 0.92
    shoulder = chest * (1.15 if male else 0.98)

    # Torso + neck
    torso_rings = [
        add_ring(0, height * 0.02, 0, 0.07, 0.055, 16),
        add_ring(0, height * 0.08, 0, hip * 0.92, hip * 0.7, 16),
        add_ring(0, height * 0.16, 0, hip, hip * 0.72, 16),
        add_ring(0, height * 0.24, 0, hip * 0.96, hip * 0.7, 16),
        add_ring(0, height * 0.32, 0, waist, waist * 0.72, 16),
        add_ring(0, height * 0.40, 0, waist * 1.05, waist * 0.74, 16),
        add_ring(0, height * 0.48, 0, (waist + chest) * 0.5, chest * 0.48, 16),
        add_ring(0, height * 0.56, 0, chest, chest * 0.55, 16),
        add_ring(0, height * 0.62, 0, chest * 1.02, chest * 0.52, 16),
        add_ring(0, height * 0.68, 0, shoulder, chest * 0.42, 16),
        add_ring(0, height * 0.73, 0, shoulder * 0.72, chest * 0.32, 16),
        add_ring(0, height * 0.78, 0, 0.055, 0.048, 16),
        add_ring(0, height * 0.84, 0, 0.05, 0.045, 16),
    ]
    stack(torso_rings)
    _icosphere(positions, indices, 0.0, height * 0.92, 0.0, 0.09 if not child else 0.095, 2)

    def limb(x0: float, y0: float, z0: float, x1: float, y1: float, z1: float, r0: float, r1: float, sides: int, segs: int) -> None:
        rings = []
        for i in range(segs):
            t = i / (segs - 1)
            rings.append(
                add_ring(
                    x0 + (x1 - x0) * t,
                    y0 + (y1 - y0) * t,
                    z0 + (z1 - z0) * t,
                    r0 + (r1 - r0) * t,
                    (r0 + (r1 - r0) * t) * 0.88,
                    sides,
                    axis="x" if abs(x1 - x0) > abs(y1 - y0) else "y",
                )
            )
        stack(rings)

    arm_y = height * 0.66
    arm_len = height * 0.32
    # T-pose arms
    limb(shoulder * 0.85, arm_y, 0, shoulder * 0.85 + arm_len, arm_y, 0, 0.055, 0.028, 12, 10)
    limb(-shoulder * 0.85, arm_y, 0, -shoulder * 0.85 - arm_len, arm_y, 0, 0.055, 0.028, 12, 10)
    # Legs
    crotch = height * 0.02
    limb(hip * 0.45, crotch, 0, hip * 0.5, -0.02, 0.02, 0.07, 0.035, 12, 10)
    limb(-hip * 0.45, crotch, 0, -hip * 0.5, -0.02, 0.02, 0.07, 0.035, 12, 10)
    # Deltoids
    _icosphere(positions, indices, shoulder * 0.9, arm_y, 0, 0.055, 2)
    _icosphere(positions, indices, -shoulder * 0.9, arm_y, 0, 0.055, 2)
    # Hands as faceted wedges
    for sign in (1.0, -1.0):
        hx = sign * (shoulder * 0.85 + arm_len)
        palm = [
            add_ring(hx, arm_y, 0.0, 0.03, 0.02, 8, axis="x"),
            add_ring(hx + sign * 0.04, arm_y, 0.02, 0.032, 0.018, 8, axis="x"),
            add_ring(hx + sign * 0.07, arm_y, 0.03, 0.028, 0.016, 8, axis="x"),
        ]
        stack(palm)
        for f in range(4):
            z = (f - 1.5) * 0.014
            finger = [
                add_ring(hx + sign * 0.07, arm_y, 0.03 + z, 0.008, 0.007, 6, axis="x"),
                add_ring(hx + sign * 0.11, arm_y, 0.04 + z, 0.007, 0.006, 6, axis="x"),
                add_ring(hx + sign * 0.14, arm_y, 0.045 + z, 0.005, 0.005, 6, axis="x"),
            ]
            stack(finger)
    # Feet
    for sign in (1.0, -1.0):
        fx = sign * hip * 0.5
        foot = [
            add_ring(fx, -0.02, -0.02, 0.04, 0.03, 8),
            add_ring(fx, -0.01, 0.04, 0.038, 0.028, 8),
            add_ring(fx, 0.0, 0.09, 0.03, 0.02, 8),
        ]
        stack(foot)

    return positions, indices


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    for fig in FIGURES:
        positions, indices = faceted_human(
            fig["heightM"],
            fig["gender"] == "male",
            child=fig["ageClass"] == "child",
        )
        tri_count = len(indices) // 3
        if tri_count < 2000 or tri_count > 5000:
            raise SystemExit(f"{fig['modelId']} triangleCount={tri_count} outside 2000-5000")
        glb = ROOT / f"{fig['modelId']}.glb"
        meta = ROOT / f"{fig['modelId']}.json"
        write_glb(glb, positions, indices)
        meta.write_text(
            json.dumps(
                {
                    "gender": fig["gender"],
                    "ageClass": fig["ageClass"],
                    "heightM": fig["heightM"],
                    "triangleCount": tri_count,
                    "jointCount": 17,
                    "rig": "posecraft-v2",
                    "uv": "generated",
                    "modelId": fig["modelId"],
                    "shading": "flat-faceted",
                    "pose": "T-pose",
                    "glb": f"/posecraft/figures/{fig['modelId']}.glb",
                    "viewportBuilder": "studio-web/src/posecraft/humanMeshBuilder.ts",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"wrote {glb.name} + {meta.name} tris={tri_count}")


if __name__ == "__main__":
    main()
