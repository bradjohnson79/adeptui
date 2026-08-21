"""PoseCraft v4 low-poly human mannequins.

Rebuild aid only. Writes GLBs into assets/posecraft/v4/.
Does not touch PoseCraft application code.

Convention: meters, +Y up, +Z forward, character left = -X, feet on Y=0, T-pose.
TRANSFORM LAW: each region mesh is local to its PoseCraft pivot; node translation
assembles the T-pose; rotation = 0; scale = 1,1,1.
"""

from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
PREVIEWS = ROOT / "previews"

BODY_REGIONS = [
    "head",
    "neck",
    "chest",
    "spine",
    "pelvis",
    "leftUpperArm",
    "leftLowerArm",
    "leftHand",
    "rightUpperArm",
    "rightLowerArm",
    "rightHand",
    "leftUpperLeg",
    "leftLowerLeg",
    "leftFoot",
    "rightUpperLeg",
    "rightLowerLeg",
    "rightFoot",
]

GRAY = (0.55, 0.55, 0.58, 1.0)


@dataclass
class FigureSpec:
    model_id: str
    display_name: str
    age_class: str
    sex_class: str
    height: float
    shoulder_width: float
    hip_width: float
    upper_arm: float
    lower_arm: float
    upper_leg: float
    lower_leg: float
    # Anatomical (not a uniform scale of another figure).
    head_frac: float
    neck_frac: float
    jaw: float  # 0 round .. 1 square
    waist_pinch: float
    pec: float
    breast: float  # modest mannequin shelf only
    deltoid: float
    thigh: float
    calf: float
    arm_r: float
    hand_len: float
    foot_len: float
    child_soft: float


SPECS = [
    FigureSpec(
        model_id="adult-male-lowpoly-v4",
        display_name="Adult Male",
        age_class="adult",
        sex_class="male",
        height=1.84,
        shoulder_width=0.48,
        hip_width=0.26,
        upper_arm=0.31,
        lower_arm=0.29,
        upper_leg=0.46,
        lower_leg=0.45,
        head_frac=0.132,
        neck_frac=0.048,
        jaw=0.78,
        waist_pinch=0.18,
        pec=1.0,
        breast=0.0,
        deltoid=1.0,
        thigh=1.0,
        calf=1.0,
        arm_r=0.048,
        hand_len=0.175,
        foot_len=0.255,
        child_soft=0.0,
    ),
    FigureSpec(
        model_id="adult-female-lowpoly-v4",
        display_name="Adult Female",
        age_class="adult",
        sex_class="female",
        height=1.70,
        shoulder_width=0.34,
        hip_width=0.32,
        upper_arm=0.27,
        lower_arm=0.25,
        upper_leg=0.43,
        lower_leg=0.42,
        head_frac=0.128,
        neck_frac=0.046,
        jaw=0.42,
        waist_pinch=0.42,
        pec=0.35,
        breast=0.55,
        deltoid=0.62,
        thigh=0.88,
        calf=0.78,
        arm_r=0.036,
        hand_len=0.155,
        foot_len=0.225,
        child_soft=0.0,
    ),
    FigureSpec(
        model_id="child-boy-lowpoly-v4",
        display_name="Child Boy",
        age_class="child",
        sex_class="male",
        height=1.32,
        shoulder_width=0.29,
        hip_width=0.20,
        upper_arm=0.21,
        lower_arm=0.20,
        upper_leg=0.30,
        lower_leg=0.29,
        head_frac=0.205,
        neck_frac=0.052,
        jaw=0.55,
        waist_pinch=0.08,
        pec=0.45,
        breast=0.0,
        deltoid=0.55,
        thigh=0.72,
        calf=0.62,
        arm_r=0.032,
        hand_len=0.115,
        foot_len=0.175,
        child_soft=0.7,
    ),
    FigureSpec(
        model_id="child-girl-lowpoly-v4",
        display_name="Child Girl",
        age_class="child",
        sex_class="female",
        height=1.28,
        shoulder_width=0.27,
        hip_width=0.20,
        upper_arm=0.20,
        lower_arm=0.19,
        upper_leg=0.29,
        lower_leg=0.28,
        head_frac=0.210,
        neck_frac=0.050,
        jaw=0.32,
        waist_pinch=0.16,
        pec=0.22,
        breast=0.12,
        deltoid=0.48,
        thigh=0.70,
        calf=0.58,
        arm_r=0.030,
        hand_len=0.108,
        foot_len=0.165,
        child_soft=0.82,
    ),
]


class Mesh:
    def __init__(self) -> None:
        self.v: list[np.ndarray] = []
        self.f: list[tuple[int, int, int]] = []

    def add(self, p) -> int:
        self.v.append(np.asarray(p, dtype=np.float64))
        return len(self.v) - 1

    def face(self, a: int, b: int, c: int) -> None:
        self.f.append((a, b, c))

    def merge(self, other: "Mesh") -> None:
        off = len(self.v)
        self.v.extend(other.v)
        self.f.extend((a + off, b + off, c + off) for a, b, c in other.f)

    def numpy(self) -> tuple[np.ndarray, np.ndarray]:
        if not self.v:
            return np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int32)
        return np.vstack(self.v), np.array(self.f, dtype=np.int32)

    def triangle_count(self) -> int:
        return len(self.f)

    def fix_outward(self) -> None:
        if not self.v or not self.f:
            return
        verts = np.vstack(self.v)
        c = verts.mean(axis=0)
        fixed: list[tuple[int, int, int]] = []
        for a, b, d in self.f:
            n = np.cross(verts[b] - verts[a], verts[d] - verts[a])
            mid = (verts[a] + verts[b] + verts[d]) / 3.0
            if np.dot(n, mid - c) < 0:
                fixed.append((a, d, b))
            else:
                fixed.append((a, b, d))
        self.f = fixed


def _copysign_pow(val: float, exp: float) -> float:
    return math.copysign(abs(val) ** exp, val)


def ring_xz(y: float, radii: list[float], power: float = 3.35) -> list[tuple[float, float, float]]:
    n = len(radii)
    pts = []
    exp = 2.0 / power
    for i, r in enumerate(radii):
        a = (2.0 * math.pi * i) / n
        s, c = math.sin(a), math.cos(a)
        x = r * _copysign_pow(s, exp)
        z = r * _copysign_pow(c, exp)
        pts.append((x, y, z))
    return pts


def ring_yz(x: float, radii: list[float], power: float = 3.35) -> list[tuple[float, float, float]]:
    n = len(radii)
    pts = []
    exp = 2.0 / power
    for i, r in enumerate(radii):
        a = (2.0 * math.pi * i) / n
        s, c = math.sin(a), math.cos(a)
        y = r * _copysign_pow(c, exp)
        z = r * _copysign_pow(s, exp)
        pts.append((x, y, z))
    return pts


def foot_section(z: float, rx: float, y_top: float, y_bot: float, x_off: float = 0.0) -> list[tuple[float, float, float]]:
    """Closed 8-point anatomical foot cross-section in XY at a given Z."""
    yt, yb, ymid = y_top, y_bot, lerp(y_bot, y_top, 0.45)
    return [
        (x_off + 0.0, yt, z),
        (x_off + rx * 0.62, lerp(ymid, yt, 0.7), z),
        (x_off + rx, ymid, z),
        (x_off + rx * 0.88, lerp(yb, ymid, 0.22), z),
        (x_off + 0.0, yb, z),
        (x_off - rx * 0.88, lerp(yb, ymid, 0.22), z),
        (x_off - rx, ymid, z),
        (x_off - rx * 0.62, lerp(ymid, yt, 0.7), z),
    ]


def loft(stations: list[list[tuple[float, float, float]]], cap_start: bool = False, cap_end: bool = False) -> Mesh:
    m = Mesh()
    rings: list[list[int]] = []
    n = len(stations[0])
    for st in stations:
        if len(st) != n:
            raise ValueError("station size mismatch")
        rings.append([m.add(p) for p in st])
    for s in range(len(rings) - 1):
        a, b = rings[s], rings[s + 1]
        for i in range(n):
            j = (i + 1) % n
            m.face(a[i], a[j], b[j])
            m.face(a[i], b[j], b[i])

    def cap(ring: list[int], flip: bool) -> None:
        c = np.mean([m.v[i] for i in ring], axis=0)
        ci = m.add(c)
        for i in range(n):
            j = (i + 1) % n
            if flip:
                m.face(ci, ring[j], ring[i])
            else:
                m.face(ci, ring[i], ring[j])

    if cap_start:
        cap(rings[0], flip=True)
    if cap_end:
        cap(rings[-1], flip=False)
    m.fix_outward()
    return m


def add_box(m: Mesh, ax, bx, ay, by, az, bz) -> None:
    x0, x1 = min(ax, bx), max(ax, bx)
    y0, y1 = min(ay, by), max(ay, by)
    z0, z1 = min(az, bz), max(az, bz)
    v = [
        m.add((x0, y0, z0)),
        m.add((x1, y0, z0)),
        m.add((x1, y1, z0)),
        m.add((x0, y1, z0)),
        m.add((x0, y0, z1)),
        m.add((x1, y0, z1)),
        m.add((x1, y1, z1)),
        m.add((x0, y1, z1)),
    ]
    faces = [
        (0, 1, 2, 3),
        (5, 4, 7, 6),
        (4, 0, 3, 7),
        (1, 5, 6, 2),
        (3, 2, 6, 7),
        (4, 5, 1, 0),
    ]
    for a, b, c, d in faces:
        m.face(v[a], v[b], v[c])
        m.face(v[a], v[c], v[d])


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def mix_radii(a: list[float], b: list[float], t: float) -> list[float]:
    return [lerp(x, y, t) for x, y in zip(a, b)]


def scale_radii(r: list[float], s: float) -> list[float]:
    return [x * s for x in r]


def skeleton(spec: FigureSpec) -> dict[str, np.ndarray]:
    h = spec.height
    head_len = h * spec.head_frac
    neck_len = h * spec.neck_frac
    foot_h = 0.052 * (h / 1.84) if spec.age_class == "adult" else 0.040 * (h / 1.30)
    ankle_y = foot_h
    hip_y = ankle_y + spec.lower_leg + spec.upper_leg
    head_y = h - head_len * 0.90
    neck_y = head_y - neck_len * 0.85
    torso_span = neck_y - hip_y
    pelvis_y = hip_y
    spine_y = hip_y + torso_span * 0.34
    chest_y = hip_y + torso_span * 0.68
    sh_y = chest_y + (neck_y - chest_y) * 0.62
    sh_x = spec.shoulder_width * 0.5
    hip_x = spec.hip_width * 0.5
    la = spec.upper_arm
    lb = spec.lower_arm

    sk = {
        "pelvis": np.array([0.0, pelvis_y, 0.0]),
        "spine": np.array([0.0, spine_y, 0.0]),
        "chest": np.array([0.0, chest_y, 0.0]),
        "neck": np.array([0.0, neck_y, 0.0]),
        "head": np.array([0.0, head_y, 0.0]),
        "leftUpperArm": np.array([-sh_x, sh_y, 0.0]),
        "leftLowerArm": np.array([-sh_x - la, sh_y, 0.0]),
        "leftHand": np.array([-sh_x - la - lb, sh_y, 0.0]),
        "rightUpperArm": np.array([sh_x, sh_y, 0.0]),
        "rightLowerArm": np.array([sh_x + la, sh_y, 0.0]),
        "rightHand": np.array([sh_x + la + lb, sh_y, 0.0]),
        "leftUpperLeg": np.array([-hip_x, hip_y, 0.0]),
        "leftLowerLeg": np.array([-hip_x, hip_y - spec.upper_leg, 0.0]),
        "leftFoot": np.array([-hip_x, ankle_y, 0.0]),
        "rightUpperLeg": np.array([hip_x, hip_y, 0.0]),
        "rightLowerLeg": np.array([hip_x, hip_y - spec.upper_leg, 0.0]),
        "rightFoot": np.array([hip_x, ankle_y, 0.0]),
        "_head_len": np.array([head_len]),
        "_neck_len": np.array([neck_len]),
        "_foot_h": np.array([foot_h]),
        "_sh_y": np.array([sh_y]),
        "_neck_y": np.array([neck_y]),
        "_hip_y": np.array([hip_y]),
        "_chest_y": np.array([chest_y]),
        "_spine_y": np.array([spine_y]),
        "_torso_span": np.array([torso_span]),
    }
    return sk


def _torso_radii(spec: FigureSpec, station: str) -> list[float]:
    """16-gon, index 0 = +Z front, 4 = +X right, 8 = -Z back, 12 = -X left."""
    sh = spec.shoulder_width * 0.5
    hip = spec.hip_width * 0.5
    soft = 1.0 - 0.22 * spec.child_soft
    front_chest = 0.095 * (0.85 + 0.35 * spec.pec) * (hscale := spec.height / 1.84)
    if spec.age_class == "child":
        hscale = spec.height / 1.30
        front_chest = 0.078 * hscale
    back = 0.072 * hscale
    if spec.age_class == "child":
        back = 0.068 * (spec.height / 1.30)

    waist_rx = lerp(sh * 0.72, hip * 0.92, 0.35) * (1.0 - spec.waist_pinch)
    waist_front = front_chest * (0.72 - 0.18 * spec.waist_pinch)
    hip_front = 0.080 * hscale + (0.018 if spec.sex_class == "female" else 0.004)
    breast = 0.028 * spec.breast * hscale

    def R(front, fr, r, br, back_r, bl, l, fl) -> list[float]:
        # 16 samples around, anatomically weighted, then softened for children.
        raw = [
            front,
            lerp(front, fr, 0.55),
            fr,
            lerp(fr, r, 0.55),
            r,
            lerp(r, br, 0.5),
            br,
            lerp(br, back_r, 0.55),
            back_r,
            lerp(back_r, bl, 0.55),
            bl,
            lerp(bl, l, 0.5),
            l,
            lerp(l, fl, 0.55),
            fl,
            lerp(fl, front, 0.55),
        ]
        if spec.child_soft > 0:
            mean = sum(raw) / len(raw)
            raw = [lerp(x, mean, 0.22 * spec.child_soft) for x in raw]
        return [x * soft for x in raw]

    if station == "pelvis_bot":
        return R(hip_front * 0.55, hip * 0.55, hip * 0.62, hip * 0.5, back * 0.7, hip * 0.5, hip * 0.62, hip * 0.55)
    if station == "pelvis":
        return R(hip_front, hip * 0.92, hip * 1.02, hip * 0.78, back * 0.95, hip * 0.78, hip * 1.02, hip * 0.92)
    if station == "pelvis_top":
        return R(hip_front * 0.9, hip * 0.82, hip * 0.88, hip * 0.7, back * 0.88, hip * 0.7, hip * 0.88, hip * 0.82)
    if station == "waist":
        return R(waist_front, waist_rx * 0.85, waist_rx, waist_rx * 0.78, back * 0.78, waist_rx * 0.78, waist_rx, waist_rx * 0.85)
    if station == "ribs":
        rx = lerp(waist_rx, sh * 0.86, 0.55)
        f = front_chest * 0.92 + breast * 0.35
        return R(f, rx * 0.9, rx, rx * 0.72, back, rx * 0.72, rx, rx * 0.9)
    if station == "chest":
        f = front_chest + breast
        return R(f, sh * 0.78, sh * 0.86, sh * 0.62, back * 1.05, sh * 0.62, sh * 0.86, sh * 0.78)
    if station == "pec":
        f = front_chest * 1.05 + breast * 1.15
        return R(f, sh * 0.82, sh * 0.94, sh * 0.58, back * 1.02, sh * 0.58, sh * 0.94, sh * 0.82)
    if station == "shoulder":
        # Stay inside the deltoid so the chest does not spike at the shoulder tip.
        return R(front_chest * 0.70, sh * 0.62, sh * 0.70, sh * 0.48, back * 0.92, sh * 0.48, sh * 0.70, sh * 0.62)
    if station == "clavicle":
        return R(front_chest * 0.48, sh * 0.48, sh * 0.52, sh * 0.38, back * 0.7, sh * 0.38, sh * 0.52, sh * 0.48)
    if station == "collar":
        n = 0.055 * (spec.height / 1.84)
        if spec.age_class == "child":
            n = 0.048 * (spec.height / 1.30)
        return R(n * 0.85, n * 0.9, n, n * 0.85, n * 0.8, n * 0.85, n, n * 0.9)
    raise KeyError(station)


def build_pelvis(spec: FigureSpec, sk: dict) -> Mesh:
    py = sk["pelvis"][1]
    y_bot = -spec.upper_leg * 0.18
    spine_y = sk["spine"][1] - py
    y_top = spine_y * 0.62
    stations = [
        ring_xz(y_bot, _torso_radii(spec, "pelvis_bot"), 3.5),
        ring_xz(-spec.upper_leg * 0.06, _torso_radii(spec, "pelvis"), 3.35),
        ring_xz(0.0, _torso_radii(spec, "pelvis"), 3.3),
        ring_xz(y_top * 0.55, _torso_radii(spec, "pelvis_top"), 3.3),
        ring_xz(y_top, mix_radii(_torso_radii(spec, "pelvis_top"), _torso_radii(spec, "waist"), 0.45), 3.25),
    ]
    return loft(stations, cap_start=True, cap_end=False)


def build_spine(spec: FigureSpec, sk: dict) -> Mesh:
    sy = sk["spine"][1]
    y_bot = sk["pelvis"][1] - sy + (sk["spine"][1] - sk["pelvis"][1]) * 0.38
    y_top = (sk["chest"][1] - sy) * 0.58
    stations = [
        ring_xz(y_bot, mix_radii(_torso_radii(spec, "pelvis_top"), _torso_radii(spec, "waist"), 0.5), 3.25),
        ring_xz(0.0, _torso_radii(spec, "waist"), 3.2),
        ring_xz(y_top * 0.55, mix_radii(_torso_radii(spec, "waist"), _torso_radii(spec, "ribs"), 0.6), 3.2),
        ring_xz(y_top, _torso_radii(spec, "ribs"), 3.15),
    ]
    return loft(stations)


def build_chest(spec: FigureSpec, sk: dict) -> Mesh:
    cy = sk["chest"][1]
    y_bot = sk["spine"][1] - cy + (sk["chest"][1] - sk["spine"][1]) * 0.42
    y_neck = sk["neck"][1] - cy
    stations = [
        ring_xz(y_bot, _torso_radii(spec, "ribs"), 3.15),
        ring_xz(0.0, _torso_radii(spec, "chest"), 3.2),
        ring_xz(y_neck * 0.28, _torso_radii(spec, "pec"), 3.25),
        ring_xz(y_neck * 0.58, _torso_radii(spec, "shoulder"), 3.3),
        ring_xz(y_neck * 0.82, _torso_radii(spec, "clavicle"), 3.2),
        ring_xz(y_neck * 1.02, _torso_radii(spec, "collar"), 3.1),
    ]
    return loft(stations)


def build_neck(spec: FigureSpec, sk: dict) -> Mesh:
    ny = sk["neck"][1]
    y_bot = -0.028
    y_top = sk["head"][1] - ny + 0.018
    n = 16
    hs = spec.height / (1.84 if spec.age_class == "adult" else 1.30)
    rx = 0.052 * hs
    rz = 0.040 * hs
    if spec.sex_class == "female":
        rx *= 0.88
        rz *= 0.90
    if spec.child_soft:
        rx *= 1.10
        rz *= 1.12
    adam = 0.007 * hs if spec.sex_class == "male" and spec.age_class == "adult" else 0.0

    def neck_r(s: float) -> list[float]:
        sx = lerp(rx * 1.18, rx * 0.86, s)
        sz = lerp(rz * 1.05, rz * 0.92, s)
        radii = []
        for i in range(n):
            a = 2 * math.pi * i / n
            c, si = math.cos(a), math.sin(a)
            r = 1.0 / math.sqrt((si / max(sx, 1e-6)) ** 2 + (c / max(sz, 1e-6)) ** 2)
            if c > 0:
                r += adam * c * (0.35 + 0.65 * s)
            radii.append(r)
        return radii

    stations = [
        ring_xz(y_bot, neck_r(0.0), 3.2),
        ring_xz(y_top * 0.40, neck_r(0.40), 3.05),
        ring_xz(y_top * 0.75, neck_r(0.75), 2.95),
        ring_xz(y_top, neck_r(1.0), 2.9),
    ]
    return loft(stations)


def build_head(spec: FigureSpec, sk: dict) -> Mesh:
    hl = float(sk["_head_len"][0])
    jaw = spec.jaw
    soft = spec.child_soft
    chin_y = -0.16 * hl
    crown_y = 0.92 * hl
    n = 16
    scale = hl / 0.243
    if spec.age_class == "child":
        scale *= 1.08

    # Explicit skull stations: t, half_width, front_z, back_z (meters at adult-male scale).
    raw = [
        (0.00, 0.018, 0.046, 0.010),  # chin tip
        (0.06, 0.028, 0.032, 0.018),  # under jaw
        (0.14, 0.058 + 0.016 * jaw, 0.040, 0.042),  # jaw corners
        (0.24, 0.066 + 0.008 * (1 - jaw), 0.044, 0.055),  # mouth
        (0.34, 0.074, 0.050, 0.062),  # cheeks
        (0.42, 0.070, 0.078, 0.064),  # nose
        (0.50, 0.076, 0.038, 0.068),  # eye inset
        (0.58, 0.080, 0.056 + 0.010 * jaw, 0.070),  # brow
        (0.70, 0.074, 0.050, 0.074),  # forehead
        (0.82, 0.062, 0.038, 0.070),  # upper cranium
        (0.92, 0.042, 0.022, 0.048),
        (1.00, 0.016, 0.008, 0.022),  # crown
    ]
    if spec.sex_class == "female" and spec.age_class == "adult":
        raw = [(t, w * 0.90, f * 0.94, b * 0.96) if t < 0.3 else (t, w * 0.96, f * 0.96, b) for t, w, f, b in raw]
        raw[5] = (0.42, 0.068, 0.070, 0.062)
    if spec.age_class == "child":
        raw = [(t, w * 1.08, f * 1.04, b * 1.10) for t, w, f, b in raw]
        # Rounder chin, smaller nose, fuller cheeks.
        raw[0] = (0.00, 0.026, 0.038, 0.016)
        raw[5] = (0.42, 0.078, 0.058, 0.072)
        raw[6] = (0.50, 0.082, 0.048, 0.074)
    if spec.sex_class == "female" and spec.age_class == "child":
        raw[2] = (0.14, raw[2][1] * 0.90, raw[2][2], raw[2][3])

    def head_radii(w: float, f: float, b: float, t: float) -> list[float]:
        w, f, b = w * scale, f * scale, b * scale
        if soft:
            mean = (w + f + b) / 3.0
            w, f, b = lerp(w, mean, 0.18 * soft), lerp(f, mean, 0.12 * soft), lerp(b, mean, 0.16 * soft)
        radii = []
        for i in range(n):
            a = 2 * math.pi * i / n
            c, s = math.cos(a), math.sin(a)
            depth = f if c >= 0 else b
            r = 1.0 / math.sqrt((s / max(w, 1e-6)) ** 2 + (c / max(depth, 1e-6)) ** 2)
            radii.append(r)
        return radii

    stations = []
    for t, w, f, b in raw:
        y = lerp(chin_y, crown_y, t)
        stations.append(ring_xz(y, head_radii(w, f, b, t), power=4.0))
    m = loft(stations, cap_start=True, cap_end=True)

    nose_y = lerp(chin_y, crown_y, 0.42)
    nose_len = 0.034 * scale * (0.55 if spec.age_class == "child" else 1.0)
    nose_w = 0.013 * scale
    nose_h = 0.028 * scale
    face_z = 0.050 * scale
    a = m.add((0.0, nose_y + nose_h * 0.55, face_z))
    b = m.add((-nose_w, nose_y, face_z * 0.92))
    c = m.add((nose_w, nose_y, face_z * 0.92))
    d = m.add((0.0, nose_y - nose_h * 0.45, face_z * 0.88))
    tip = m.add((0.0, nose_y - nose_h * 0.08, face_z + nose_len))
    m.face(tip, a, c)
    m.face(tip, c, d)
    m.face(tip, d, b)
    m.face(tip, b, a)

    ear_y = lerp(chin_y, crown_y, 0.56)
    ear_z = -0.008 * scale
    ear_x = 0.074 * scale * (1.06 if spec.age_class == "child" else 1.0)
    ear_h = 0.030 * scale
    ear_out = 0.016 * scale
    for sign in (-1.0, 1.0):
        e0 = m.add((sign * ear_x, ear_y + ear_h, ear_z))
        e1 = m.add((sign * ear_x, ear_y - ear_h * 0.75, ear_z))
        e2 = m.add((sign * ear_x, ear_y, ear_z - 0.012 * scale))
        e3 = m.add((sign * (ear_x + ear_out), ear_y - ear_h * 0.12, ear_z - 0.004 * scale))
        m.face(e0, e1, e3)
        m.face(e1, e2, e3)
        m.face(e2, e0, e3)
    m.fix_outward()
    return m


def _limb_radii(n: int, r_up: float, r_side: float, r_down: float, r_front: float, r_back: float) -> list[float]:
    out = []
    for i in range(n):
        a = 2 * math.pi * i / n
        c, s = math.cos(a), math.sin(a)
        if c >= 0 and s >= 0:
            r = lerp(r_up, r_front, abs(s) / (abs(c) + abs(s) + 1e-9))
        elif c < 0 and s >= 0:
            r = lerp(r_down, r_front, abs(s) / (abs(c) + abs(s) + 1e-9))
        elif c < 0 and s < 0:
            r = lerp(r_down, r_back, abs(s) / (abs(c) + abs(s) + 1e-9))
        else:
            r = lerp(r_up, r_back, abs(s) / (abs(c) + abs(s) + 1e-9))
        r = lerp(r, r_side, abs(s) * 0.35)
        out.append(r)
    return out


def build_arm(spec: FigureSpec, side: int, segment: str) -> Mesh:
    n = 16
    length = spec.upper_arm if segment == "upper" else spec.lower_arm
    r0 = spec.arm_r * (1.35 if segment == "upper" else 0.95)
    r1 = spec.arm_r * (0.80 if segment == "upper" else 0.64)
    if spec.sex_class == "female":
        r0 *= 0.88
        r1 *= 0.90
    if spec.child_soft:
        r0 *= 1.10
        r1 *= 1.14
    # Overlap the neighboring region so the assembled T-pose has no gaps.
    x0 = (0.08 if segment == "upper" else 0.032) * -side
    x1 = length * side * (1.04 if segment == "upper" else 1.03)

    def rad_at(t: float) -> list[float]:
        r = lerp(r0, r1, t)
        up = r * 1.05
        down = r * 0.90
        front = r * 0.92
        back = r * 1.04
        side_r = r * 1.04
        if segment == "upper" and t < 0.34:
            cap = (1.0 - t / 0.34)
            up *= 1.0 + 0.85 * spec.deltoid * cap
            side_r *= 1.0 + 0.55 * spec.deltoid * cap
            back *= 1.0 + 0.25 * spec.deltoid * cap
        if segment == "upper" and t > 0.78:
            front *= 0.80
            back *= 0.80
            up *= 1.16
            down *= 1.16
        if segment == "lower" and t < 0.18:
            front *= 0.82
            up *= 1.12
        if segment == "lower" and t > 0.72:
            up *= 0.76
            down *= 0.76
            side_r *= 1.08
            front *= 0.82
        return _limb_radii(n, up, side_r, down, front, back)

    ts = [0.0, 0.10, 0.22, 0.38, 0.55, 0.72, 0.88, 1.0]
    stations = [ring_yz(lerp(x0, x1, t), rad_at(t), 3.5) for t in ts]
    return loft(stations, cap_start=segment == "upper", cap_end=False)


def _palm_radii(hy: float, hz: float, n: int = 12) -> list[float]:
    radii = []
    for i in range(n):
        a = 2 * math.pi * i / n
        c, s = math.cos(a), math.sin(a)
        radii.append(1.0 / math.sqrt((c / max(hy, 1e-6)) ** 2 + (s / max(hz, 1e-6)) ** 2))
    return radii


def build_hand(spec: FigureSpec, side: int) -> Mesh:
    """Palm-down flattened loft + tapered finger silhouettes. One mesh."""
    hl = spec.hand_len
    palm_len = hl * 0.40
    palm_w = hl * 0.48
    palm_t = hl * 0.22
    if spec.child_soft:
        palm_t *= 1.12
        palm_w *= 1.04
    x0 = 0.018 * -side
    x_knuckle = palm_len * side
    palm = loft(
        [
            ring_yz(x0, _palm_radii(palm_t * 0.95, palm_w * 0.38), 3.8),
            ring_yz(x_knuckle * 0.45, _palm_radii(palm_t, palm_w * 0.50), 3.7),
            ring_yz(x_knuckle, _palm_radii(palm_t * 0.82, palm_w * 0.52), 3.7),
        ],
        cap_start=True,
        cap_end=False,
    )
    finger_len = hl * 0.52
    zs = [-0.34, -0.12, 0.11, 0.33]
    lens = [0.88, 1.00, 0.96, 0.76]
    for zf, ln in zip(zs, lens):
        zc = zf * palm_w
        fx0 = x_knuckle * 0.90
        fx1 = x_knuckle + finger_len * ln * side
        mid = lerp(fx0, fx1, 0.55)
        fw, ft = palm_w * 0.11, palm_t * 0.62
        finger = loft(
            [
                [ (x, y, z + zc) for x, y, z in ring_yz(fx0, _palm_radii(ft, fw), 3.6) ],
                [ (x, y, z + zc) for x, y, z in ring_yz(mid, _palm_radii(ft * 0.9, fw * 0.9), 3.6) ],
                [ (x, y, z + zc) for x, y, z in ring_yz(fx1, _palm_radii(ft * 0.55, fw * 0.55), 3.6) ],
            ],
            cap_start=False,
            cap_end=True,
        )
        palm.merge(finger)
    # Thumb toward +Z, slightly palmar (-Y).
    tw, tt = palm_w * 0.13, palm_t * 0.70
    tx0 = palm_len * 0.08 * side
    tx1 = palm_len * 0.18 * side + hl * 0.28 * side
    thumb = loft(
        [
            [ (x, y - palm_t * 0.35, z + palm_w * 0.28) for x, y, z in ring_yz(tx0, _palm_radii(tt, tw), 3.6) ],
            [ (x, y - palm_t * 0.55, z + palm_w * 0.42) for x, y, z in ring_yz(lerp(tx0, tx1, 0.55), _palm_radii(tt * 0.85, tw * 0.85), 3.6) ],
            [ (x, y - palm_t * 0.62, z + palm_w * 0.50) for x, y, z in ring_yz(tx1, _palm_radii(tt * 0.5, tw * 0.5), 3.6) ],
        ],
        cap_start=False,
        cap_end=True,
    )
    palm.merge(thumb)
    palm.fix_outward()
    return palm


def build_leg(spec: FigureSpec, side: int, segment: str) -> Mesh:
    n = 16
    length = spec.upper_leg if segment == "upper" else spec.lower_leg
    hip_r = spec.thigh * 0.080 * (spec.height / 1.84)
    if spec.age_class == "child":
        hip_r = spec.thigh * 0.066 * (spec.height / 1.30)
    if segment == "upper":
        r0, r1 = hip_r * 1.12, hip_r * 0.62
    else:
        r0, r1 = hip_r * 0.60, hip_r * 0.42
        r0 *= 0.95 + 0.22 * spec.calf
    y0 = 0.055 if segment == "upper" else 0.028
    y1 = -length * 1.04

    def rad_at(t: float) -> list[float]:
        r = lerp(r0, r1, t)
        front = r * 0.95
        back = r * 1.06
        side_r = r * 1.04
        if segment == "upper":
            if t < 0.22:
                side_r *= 1.16
                front *= 1.08
            if t > 0.80:
                front *= 1.22
                side_r *= 0.86
                back *= 0.88
        else:
            if t < 0.16:
                front *= 1.14
                side_r *= 0.88
            if 0.28 < t < 0.62:
                back *= 1.0 + 0.50 * spec.calf
                side_r *= 1.06
            if t > 0.82:
                side_r *= 0.76
                front *= 0.84
                back *= 0.86
        radii = []
        for i in range(n):
            a = 2 * math.pi * i / n
            c, s = math.cos(a), math.sin(a)
            r_fb = lerp(side_r, front if c >= 0 else back, abs(c))
            radii.append(lerp(r_fb, side_r, abs(s) * 0.22))
        return radii

    ts = [0.0, 0.12, 0.28, 0.48, 0.68, 0.86, 1.0]
    stations = [ring_xz(lerp(y0, y1, t), rad_at(t), 3.45) for t in ts]
    return loft(stations, cap_start=segment == "upper", cap_end=False)


def build_foot(spec: FigureSpec, side: int, sk: dict) -> Mesh:
    fl = spec.foot_len
    fw = fl * 0.36
    fh = float(sk["_foot_h"][0])
    lat = 0.010 * side
    heel_z = -fl * 0.24
    ankle_z = -fl * 0.04
    arch_z = fl * 0.16
    ball_z = fl * 0.42
    toe_z = fl * 0.68
    yb = -fh
    stations = [
        foot_section(heel_z, fw * 0.72, fh * 0.55, yb, lat * 0.15),
        foot_section(ankle_z, fw * 0.82, fh * 0.70, yb, lat * 0.35),
        foot_section(arch_z, fw * 0.78, fh * 0.42, yb + fh * 0.04, lat * 0.55),
        foot_section(ball_z, fw * 0.92, fh * 0.32, yb, lat * 0.85),
        foot_section(toe_z, fw * 0.62, fh * 0.16, yb, lat * 1.15),
    ]
    m = loft(stations, cap_start=True, cap_end=True)
    cuff_r = spec.arm_r * 1.35 if spec.age_class == "adult" else spec.arm_r * 1.25
    cuff = loft(
        [
            ring_xz(0.03, [cuff_r * 0.95] * 12, 3.2),
            ring_xz(-fh * 0.20, [cuff_r * 1.12] * 12, 3.3),
        ],
        cap_start=False,
        cap_end=False,
    )
    m.merge(cuff)
    m.fix_outward()
    return m


def build_figure(spec: FigureSpec) -> dict[str, tuple[Mesh, list[float]]]:
    sk = skeleton(spec)
    parts: dict[str, tuple[Mesh, list[float]]] = {}

    def place(name: str, mesh: Mesh) -> None:
        mesh.fix_outward()
        t = sk[name]
        parts[name] = (mesh, [float(t[0]), float(t[1]), float(t[2])])

    place("pelvis", build_pelvis(spec, sk))
    place("spine", build_spine(spec, sk))
    place("chest", build_chest(spec, sk))
    place("neck", build_neck(spec, sk))
    place("head", build_head(spec, sk))
    place("leftUpperArm", build_arm(spec, -1, "upper"))
    place("leftLowerArm", build_arm(spec, -1, "lower"))
    place("leftHand", build_hand(spec, -1))
    place("rightUpperArm", build_arm(spec, 1, "upper"))
    place("rightLowerArm", build_arm(spec, 1, "lower"))
    place("rightHand", build_hand(spec, 1))
    place("leftUpperLeg", build_leg(spec, -1, "upper"))
    place("leftLowerLeg", build_leg(spec, -1, "lower"))
    place("leftFoot", build_foot(spec, -1, sk))
    place("rightUpperLeg", build_leg(spec, 1, "upper"))
    place("rightLowerLeg", build_leg(spec, 1, "lower"))
    place("rightFoot", build_foot(spec, 1, sk))
    return parts


def _align4(data: bytes) -> bytes:
    pad = (4 - (len(data) % 4)) % 4
    return data + (b"\x00" * pad)


def _align4_json(data: bytes) -> bytes:
    # glTF JSON chunks must be padded with 0x20, not NUL — Babylon JSON.parse
    # rejects trailing nulls ("Unexpected non-whitespace character after JSON").
    pad = (4 - (len(data) % 4)) % 4
    return data + (b" " * pad)


def mesh_flat_arrays(mesh: Mesh) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    verts, faces = mesh.numpy()
    if len(faces) == 0:
        return np.zeros((0, 3), np.float32), np.zeros((0, 3), np.float32), np.zeros((0,), np.uint16)
    pos = []
    nrm = []
    for a, b, c in faces:
        p0, p1, p2 = verts[a], verts[b], verts[c]
        n = np.cross(p1 - p0, p2 - p0)
        ln = np.linalg.norm(n)
        n = n / ln if ln > 1e-12 else np.array([0.0, 1.0, 0.0])
        pos.extend([p0, p1, p2])
        nrm.extend([n, n, n])
    pos_a = np.asarray(pos, dtype=np.float32)
    nrm_a = np.asarray(nrm, dtype=np.float32)
    idx = np.arange(len(pos_a), dtype=np.uint16)
    return pos_a, nrm_a, idx


def write_glb(path: Path, spec: FigureSpec, parts: dict[str, tuple[Mesh, list[float]]]) -> int:
    bin_parts: list[bytes] = []
    views = []
    accessors = []
    meshes_gltf = []
    nodes = []

    def push_view(data: bytes, target: int | None) -> int:
        data = data if len(data) % 4 == 0 else data + b"\x00" * ((4 - len(data) % 4) % 4)
        off = sum(len(x) for x in bin_parts)
        bin_parts.append(data)
        view = {"buffer": 0, "byteOffset": off, "byteLength": len(data)}
        if target is not None:
            view["target"] = target
        views.append(view)
        return len(views) - 1

    total_tris = 0
    region_nodes: list[int] = []
    for name in BODY_REGIONS:
        mesh, trans = parts[name]
        pos, nrm, idx = mesh_flat_arrays(mesh)
        tri = len(idx) // 3
        total_tris += tri
        pos_b = pos.tobytes()
        nrm_b = nrm.tobytes()
        # uint16 indices
        if pos.shape[0] >= 65535:
            raise SystemExit(f"{name} too many verts for uint16")
        idx_b = idx.astype(np.uint16).tobytes()
        pv = push_view(pos_b, 34962)
        nv = push_view(nrm_b, 34962)
        iv = push_view(idx_b, 34963)
        pmin = pos.min(axis=0).tolist()
        pmax = pos.max(axis=0).tolist()
        ap = len(accessors)
        accessors.append(
            {
                "bufferView": pv,
                "componentType": 5126,
                "count": int(pos.shape[0]),
                "type": "VEC3",
                "min": pmin,
                "max": pmax,
            }
        )
        accessors.append(
            {
                "bufferView": nv,
                "componentType": 5126,
                "count": int(nrm.shape[0]),
                "type": "VEC3",
            }
        )
        accessors.append(
            {
                "bufferView": iv,
                "componentType": 5123,
                "count": int(idx.shape[0]),
                "type": "SCALAR",
            }
        )
        meshes_gltf.append(
            {
                "name": name,
                "primitives": [
                    {
                        "attributes": {"POSITION": ap, "NORMAL": ap + 1},
                        "indices": ap + 2,
                        "material": 0,
                        "mode": 4,
                    }
                ],
            }
        )
        nodes.append(
            {
                "name": name,
                "mesh": len(meshes_gltf) - 1,
                "translation": trans,
            }
        )
        region_nodes.append(len(nodes) - 1)

    # Identity root, children = 17 region nodes. No extra geometry.
    root = {
        "name": "Figure",
        "children": region_nodes,
    }
    nodes.insert(0, root)
    # children indices shifted by +1 because root was inserted at 0
    nodes[0]["children"] = [i + 1 for i in region_nodes]

    blob = b"".join(bin_parts)
    blob = _align4(blob)
    gltf = {
        "asset": {
            "version": "2.0",
            "generator": "Adept PoseCraft v4 mannequin",
        },
        "scene": 0,
        "scenes": [{"nodes": [0], "name": spec.model_id}],
        "nodes": nodes,
        "meshes": meshes_gltf,
        "materials": [
            {
                "name": "mannequinGray",
                "pbrMetallicRoughness": {
                    "baseColorFactor": list(GRAY),
                    "metallicFactor": 0.0,
                    "roughnessFactor": 0.92,
                },
                "doubleSided": False,
            }
        ],
        "buffers": [{"byteLength": len(blob)}],
        "bufferViews": views,
        "accessors": accessors,
        "extras": {
            "displayName": spec.display_name,
            "ageClass": spec.age_class,
            "sexClass": spec.sex_class,
            "units": "meters",
            "upAxis": "+Y",
            "pose": "T-pose",
            "regionNaming": "PoseCraft 17-region",
        },
    }
    json_chunk = _align4_json(json.dumps(gltf, separators=(",", ":")).encode("utf-8"))
    total = 12 + 8 + len(json_chunk) + 8 + len(blob)
    header = struct.pack("<4sII", b"glTF", 2, total)
    json_head = struct.pack("<II", len(json_chunk), 0x4E4F534A)
    bin_head = struct.pack("<II", len(blob), 0x004E4942)
    path.write_bytes(header + json_head + json_chunk + bin_head + blob)
    return total_tris


def world_triangles(parts: dict[str, tuple[Mesh, list[float]]]) -> tuple[np.ndarray, np.ndarray]:
    tris = []
    nrms = []
    for name in BODY_REGIONS:
        mesh, trans = parts[name]
        t = np.asarray(trans)
        v, f = mesh.numpy()
        vw = v + t
        for a, b, c in f:
            p0, p1, p2 = vw[a], vw[b], vw[c]
            n = np.cross(p1 - p0, p2 - p0)
            ln = np.linalg.norm(n)
            n = n / ln if ln > 1e-12 else np.array([0.0, 1.0, 0.0])
            tris.append((p0, p1, p2))
            nrms.append(n)
    return np.array(tris), np.array(nrms)


def measure(parts: dict[str, tuple[Mesh, list[float]]]) -> dict:
    pts = []
    for name in BODY_REGIONS:
        mesh, trans = parts[name]
        v, _ = mesh.numpy()
        pts.append(v + np.asarray(trans))
    p = np.vstack(pts)
    return {
        "min": p.min(axis=0).tolist(),
        "max": p.max(axis=0).tolist(),
        "height": float(p.max(axis=0)[1] - p.min(axis=0)[1]),
        "y_min": float(p.min(axis=0)[1]),
        "y_max": float(p.max(axis=0)[1]),
        "x_mid": float((p.min(axis=0)[0] + p.max(axis=0)[0]) * 0.5),
        "z_mid": float((p.min(axis=0)[2] + p.max(axis=0)[2]) * 0.5),
    }


def parse_glb(path: Path) -> dict:
    data = path.read_bytes()
    assert data[:4] == b"glTF"
    json_len = struct.unpack_from("<I", data, 12)[0]
    json_bytes = data[20 : 20 + json_len]
    return json.loads(json_bytes.split(b"\x00")[0].decode("utf-8"))


def validate_glb(path: Path, spec: FigureSpec) -> list[str]:
    errors: list[str] = []
    g = parse_glb(path)
    if "skins" in g:
        errors.append("has skins")
    if "animations" in g:
        errors.append("has animations")
    nodes = g["nodes"]
    geom = []
    for n in nodes:
        if "mesh" in n:
            geom.append(n)
            rot = n.get("rotation")
            sc = n.get("scale")
            if rot and rot != [0, 0, 0, 1]:
                errors.append(f"{n.get('name')} has rotation {rot}")
            if sc and sc != [1, 1, 1]:
                errors.append(f"{n.get('name')} has scale {sc}")
            if "scale" in n and any(s < 0 for s in n["scale"]):
                errors.append(f"{n.get('name')} negative scale")
    names = [n["name"] for n in geom]
    if sorted(names) != sorted(BODY_REGIONS):
        errors.append(f"geometry node names {names}")
    if len(names) != 17:
        errors.append(f"expected 17 geometry nodes, got {len(names)}")
    if len(set(names)) != 17:
        errors.append("duplicate geometry names")
    extras_ok = any(n.get("name") == "Figure" and "mesh" not in n for n in nodes)
    if not extras_ok:
        errors.append("missing Figure root")
    # TRANSFORM LAW: each mesh AABB should sit near its local origin.
    for n in geom:
        mesh = g["meshes"][n["mesh"]]
        acc = g["accessors"][mesh["primitives"][0]["attributes"]["POSITION"]]
        mn, mx = np.array(acc["min"]), np.array(acc["max"])
        # origin should not be far from the AABB
        dist = 0.0
        for i in range(3):
            if mx[i] < 0:
                dist = max(dist, -mx[i])
            elif mn[i] > 0:
                dist = max(dist, mn[i])
        if dist > 0.12:
            errors.append(f"{n['name']} geometry far from pivot dist={dist:.3f}")
    return errors


def render_sheet(spec: FigureSpec, parts: dict, meas: dict, tri_count: int) -> None:
    tris, nrms = world_triangles(parts)
    light = np.array([0.32, 0.86, 0.40])
    light = light / np.linalg.norm(light)
    shade = np.clip(0.16 + 0.84 * np.clip(nrms @ light, 0.0, 1.0), 0.0, 1.0)
    size = 640
    views = []
    for mode in ("front", "side"):
        if mode == "front":
            uv = tris[:, :, [0, 1]]
            depth = tris[:, :, 2].mean(axis=1)
        else:
            uv = tris[:, :, [2, 1]]
            depth = -tris[:, :, 0].mean(axis=1)
        pts = uv.reshape(-1, 2)
        mn = pts.min(axis=0)
        mx = pts.max(axis=0)
        span = max(mx[0] - mn[0], mx[1] - mn[1], 1e-6)
        pad = span * 0.10
        mn = mn - pad
        span = span + pad * 2
        img = Image.new("RGB", (size, size), (232, 234, 236))
        draw = ImageDraw.Draw(img)
        order = np.argsort(depth)
        for i in order:
            p = (uv[i] - mn) / span
            xs = p[:, 0] * (size - 1)
            ys = (1.0 - p[:, 1]) * (size - 1)
            poly = [(float(xs[0]), float(ys[0])), (float(xs[1]), float(ys[1])), (float(xs[2]), float(ys[2]))]
            s = float(shade[i])
            fill = (int(140 * s), int(140 * s), int(148 * s))
            edge = (int(70 * s), int(70 * s), int(74 * s))
            draw.polygon(poly, fill=fill, outline=edge)
        views.append(img)
    sheet = Image.new("RGB", (size * 2 + 24, size + 70), (232, 234, 236))
    sheet.paste(views[0], (8, 54))
    sheet.paste(views[1], (size + 16, 54))
    draw = ImageDraw.Draw(sheet)
    draw.text(
        (16, 16),
        f"{spec.display_name}  h={meas['height']:.3f}m  tris={tri_count}  ymin={meas['y_min']:.3f}",
        fill=(40, 40, 44),
    )
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    sheet.save(PREVIEWS / f"{spec.model_id}-preview.png")


def write_json(spec: FigureSpec, tri_count: int, meas: dict) -> None:
    payload = {
        "displayName": spec.display_name,
        "ageClass": spec.age_class,
        "sexClass": spec.sex_class,
        "heightMeters": spec.height,
        "measuredHeightMeters": round(meas["height"], 4),
        "measuredYMin": round(meas["y_min"], 4),
        "measuredYMax": round(meas["y_max"], 4),
        "triangleCount": tri_count,
        "units": "meters",
        "upAxis": "+Y",
        "forwardAxis": "+Z",
        "pose": "T-pose",
        "regionNaming": "PoseCraft 17-region",
        "modelId": spec.model_id,
    }
    (ROOT / f"{spec.model_id}.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    report = []
    for spec in SPECS:
        parts = build_figure(spec)
        missing = [r for r in BODY_REGIONS if r not in parts]
        extra = [k for k in parts if k not in BODY_REGIONS]
        if missing or extra:
            raise SystemExit(f"{spec.model_id} regions missing={missing} extra={extra}")
        tri = sum(parts[n][0].triangle_count() for n in BODY_REGIONS)
        glb_path = ROOT / f"{spec.model_id}.glb"
        written_tris = write_glb(glb_path, spec, parts)
        meas = measure(parts)
        write_json(spec, written_tris, meas)
        errs = validate_glb(glb_path, spec)
        render_sheet(spec, parts, meas, written_tris)
        ok_tris = 2000 <= written_tris <= 5000
        height_err = abs(meas["y_max"] - spec.height)
        floor_err = abs(meas["y_min"])
        line = {
            "id": spec.model_id,
            "tris": written_tris,
            "height": round(meas["height"], 4),
            "y_max": round(meas["y_max"], 4),
            "y_min": round(meas["y_min"], 4),
            "height_err": round(height_err, 4),
            "floor_err": round(floor_err, 4),
            "tris_ok": ok_tris,
            "errors": errs,
        }
        report.append(line)
        print(json.dumps(line))
        if not ok_tris:
            print(f"WARNING tris {written_tris} outside 2000-5000")
    (ROOT / "build" / "last_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
