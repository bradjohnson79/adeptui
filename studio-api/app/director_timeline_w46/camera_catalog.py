"""Shared camera motion and rig catalog for W46 timeline planning."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

CameraCapability = Literal[
    "Native",
    "Compiled Prompt Guidance",
    "Workflow-Mapped",
    "Approximate",
    "Unsupported",
]


@dataclass(frozen=True)
class CameraDefaults:
    speed: float
    intensity: float
    subjectLock: float


@dataclass(frozen=True)
class CameraCatalogEntry:
    id: str
    label: str
    category: str
    aliases: tuple[str, ...]
    description: str
    defaults: CameraDefaults
    capability: CameraCapability
    native_motion_type: str | None = None
    native_rig: str | None = None
    workflow_motion_type: str | None = None
    workflow_rig: str | None = None


@dataclass(frozen=True)
class CameraContradictionRule:
    id: str
    motion_ids: tuple[str, ...] = ()
    rig_ids: tuple[str, ...] = ()
    severity: Literal["warning", "error"] = "warning"
    message: str = ""
    fix_proposal: str = ""


def _defaults(speed: float, intensity: float, subject_lock: float) -> CameraDefaults:
    return CameraDefaults(speed=speed, intensity=intensity, subjectLock=subject_lock)


MOTION_CATALOG: tuple[CameraCatalogEntry, ...] = (
    CameraCatalogEntry(
        id="static",
        label="Static",
        category="Static and Locked",
        aliases=("still", "static frame"),
        description="No intentional camera move.",
        defaults=_defaults(0.0, 0.05, 0.85),
        capability="Native",
        native_motion_type="static",
    ),
    CameraCatalogEntry(
        id="locked_off",
        label="Locked Off",
        category="Static and Locked",
        aliases=("lockoff", "locked off", "fixed"),
        description="Completely fixed frame with no visible operator movement.",
        defaults=_defaults(0.0, 0.0, 0.95),
        capability="Workflow-Mapped",
        workflow_motion_type="static",
        workflow_rig="tripod",
    ),
    CameraCatalogEntry(
        id="micro_drift",
        label="Micro Drift",
        category="Static and Locked",
        aliases=("subtle drift", "float drift"),
        description="Almost static frame with a barely perceptible cinematic drift.",
        defaults=_defaults(0.12, 0.15, 0.8),
        capability="Compiled Prompt Guidance",
    ),
    CameraCatalogEntry(
        id="dolly_in",
        label="Dolly In",
        category="Push and Pull",
        aliases=("dolly forward", "move in"),
        description="Camera physically moves toward the subject.",
        defaults=_defaults(0.45, 0.35, 0.75),
        capability="Native",
        native_motion_type="dolly_in",
    ),
    CameraCatalogEntry(
        id="dolly_out",
        label="Dolly Out",
        category="Push and Pull",
        aliases=("dolly back", "move out"),
        description="Camera physically moves away from the subject.",
        defaults=_defaults(0.4, 0.3, 0.7),
        capability="Native",
        native_motion_type="dolly_out",
    ),
    CameraCatalogEntry(
        id="push",
        label="Push",
        category="Push and Pull",
        aliases=("push in", "creep in"),
        description="Forward camera energy without promising a specific support rig.",
        defaults=_defaults(0.42, 0.4, 0.75),
        capability="Native",
        native_motion_type="push",
    ),
    CameraCatalogEntry(
        id="pull",
        label="Pull",
        category="Push and Pull",
        aliases=("pull back", "pull out"),
        description="Backward camera energy without promising a specific support rig.",
        defaults=_defaults(0.38, 0.35, 0.7),
        capability="Native",
        native_motion_type="pull",
    ),
    CameraCatalogEntry(
        id="slow_zoom_in",
        label="Slow Zoom In",
        category="Push and Pull",
        aliases=("zoom in", "lens in"),
        description="Lens-driven push feel rather than a physical dolly move.",
        defaults=_defaults(0.28, 0.25, 0.8),
        capability="Compiled Prompt Guidance",
    ),
    CameraCatalogEntry(
        id="slow_zoom_out",
        label="Slow Zoom Out",
        category="Push and Pull",
        aliases=("zoom out", "lens out"),
        description="Lens-driven pull feel rather than a physical dolly move.",
        defaults=_defaults(0.24, 0.22, 0.8),
        capability="Compiled Prompt Guidance",
    ),
    CameraCatalogEntry(
        id="pan",
        label="Pan",
        category="Pan and Tilt",
        aliases=("pan sweep",),
        description="Horizontal pivot from a mostly fixed camera position.",
        defaults=_defaults(0.45, 0.35, 0.65),
        capability="Native",
        native_motion_type="pan",
    ),
    CameraCatalogEntry(
        id="tilt",
        label="Tilt",
        category="Pan and Tilt",
        aliases=("tilt sweep",),
        description="Vertical pivot from a mostly fixed camera position.",
        defaults=_defaults(0.4, 0.3, 0.65),
        capability="Native",
        native_motion_type="tilt",
    ),
    CameraCatalogEntry(
        id="whip_pan",
        label="Whip Pan",
        category="Pan and Tilt",
        aliases=("snap pan", "swish pan"),
        description="Fast directional pan used as an energetic transition or reveal.",
        defaults=_defaults(0.95, 0.9, 0.2),
        capability="Approximate",
        workflow_motion_type="pan",
    ),
    CameraCatalogEntry(
        id="orbit",
        label="Orbit",
        category="Arc and Reveal",
        aliases=("circle move", "wraparound"),
        description="Camera arcs around the subject.",
        defaults=_defaults(0.55, 0.5, 0.9),
        capability="Native",
        native_motion_type="orbit",
    ),
    CameraCatalogEntry(
        id="arc_left",
        label="Arc Left",
        category="Arc and Reveal",
        aliases=("orbit left", "circle left"),
        description="Leftward arc around the subject.",
        defaults=_defaults(0.5, 0.45, 0.9),
        capability="Workflow-Mapped",
        workflow_motion_type="orbit",
    ),
    CameraCatalogEntry(
        id="arc_right",
        label="Arc Right",
        category="Arc and Reveal",
        aliases=("orbit right", "circle right"),
        description="Rightward arc around the subject.",
        defaults=_defaults(0.5, 0.45, 0.9),
        capability="Workflow-Mapped",
        workflow_motion_type="orbit",
    ),
    CameraCatalogEntry(
        id="rail",
        label="Rail",
        category="Tracking",
        aliases=("track", "slider track"),
        description="Straight mechanical move along a track or rail.",
        defaults=_defaults(0.5, 0.35, 0.8),
        capability="Native",
        native_motion_type="rail",
    ),
    CameraCatalogEntry(
        id="tracking_left",
        label="Track Left",
        category="Tracking",
        aliases=("truck left", "slide left"),
        description="Lateral move toward camera left.",
        defaults=_defaults(0.48, 0.35, 0.78),
        capability="Workflow-Mapped",
        workflow_motion_type="rail",
    ),
    CameraCatalogEntry(
        id="tracking_right",
        label="Track Right",
        category="Tracking",
        aliases=("truck right", "slide right"),
        description="Lateral move toward camera right.",
        defaults=_defaults(0.48, 0.35, 0.78),
        capability="Workflow-Mapped",
        workflow_motion_type="rail",
    ),
    CameraCatalogEntry(
        id="follow",
        label="Follow",
        category="Tracking",
        aliases=("follow shot", "tracking follow"),
        description="Camera keeps pace with a moving subject.",
        defaults=_defaults(0.55, 0.45, 0.95),
        capability="Compiled Prompt Guidance",
    ),
    CameraCatalogEntry(
        id="crane",
        label="Crane",
        category="Vertical and Aerial",
        aliases=("boom",),
        description="Elevated sweeping move using a crane-like support.",
        defaults=_defaults(0.5, 0.45, 0.72),
        capability="Native",
        native_motion_type="crane",
    ),
    CameraCatalogEntry(
        id="crane_up",
        label="Crane Up",
        category="Vertical and Aerial",
        aliases=("boom up", "rise up"),
        description="Ascending crane move.",
        defaults=_defaults(0.45, 0.4, 0.72),
        capability="Workflow-Mapped",
        workflow_motion_type="crane",
    ),
    CameraCatalogEntry(
        id="crane_down",
        label="Crane Down",
        category="Vertical and Aerial",
        aliases=("boom down", "descend"),
        description="Descending crane move.",
        defaults=_defaults(0.42, 0.38, 0.72),
        capability="Workflow-Mapped",
        workflow_motion_type="crane",
    ),
    CameraCatalogEntry(
        id="handheld",
        label="Handheld",
        category="Organic and Kinetic",
        aliases=("shaky cam", "operator carried"),
        description="Organic operator-carried motion with natural instability.",
        defaults=_defaults(0.62, 0.75, 0.55),
        capability="Native",
        native_motion_type="handheld",
    ),
    CameraCatalogEntry(
        id="gimbal_float",
        label="Gimbal Float",
        category="Organic and Kinetic",
        aliases=("floating gimbal", "glide"),
        description="Smooth floating move with gentle body-follow energy.",
        defaults=_defaults(0.4, 0.22, 0.88),
        capability="Approximate",
    ),
    CameraCatalogEntry(
        id="drone",
        label="Drone",
        category="Vertical and Aerial",
        aliases=("aerial",),
        description="Aerial move from a drone perspective.",
        defaults=_defaults(0.58, 0.42, 0.6),
        capability="Native",
        native_motion_type="drone",
    ),
    CameraCatalogEntry(
        id="drone_rise",
        label="Drone Rise",
        category="Vertical and Aerial",
        aliases=("aerial rise",),
        description="Ascending aerial lift that reveals more environment.",
        defaults=_defaults(0.52, 0.4, 0.55),
        capability="Workflow-Mapped",
        workflow_motion_type="drone",
    ),
    CameraCatalogEntry(
        id="drone_descend",
        label="Drone Descend",
        category="Vertical and Aerial",
        aliases=("aerial descend",),
        description="Descending aerial approach toward the scene.",
        defaults=_defaults(0.48, 0.38, 0.55),
        capability="Workflow-Mapped",
        workflow_motion_type="drone",
    ),
    CameraCatalogEntry(
        id="custom",
        label="Custom",
        category="Custom",
        aliases=("other", "bespoke"),
        description="Creator-defined motion phrase preserved as a custom label.",
        defaults=_defaults(0.45, 0.5, 0.7),
        capability="Compiled Prompt Guidance",
    ),
)

RIG_CATALOG: tuple[CameraCatalogEntry, ...] = (
    CameraCatalogEntry(
        id="tripod",
        label="Tripod",
        category="Locked Support",
        aliases=("sticks",),
        description="Stable fixed support for static, pan, and tilt work.",
        defaults=_defaults(0.0, 0.0, 0.95),
        capability="Native",
        native_rig="tripod",
    ),
    CameraCatalogEntry(
        id="monopod",
        label="Monopod",
        category="Locked Support",
        aliases=("single leg",),
        description="Compact support with slight body influence.",
        defaults=_defaults(0.08, 0.12, 0.88),
        capability="Approximate",
    ),
    CameraCatalogEntry(
        id="dolly",
        label="Dolly",
        category="Ground Motion",
        aliases=("dolly cart",),
        description="Wheeled ground support for smooth push, pull, and track moves.",
        defaults=_defaults(0.45, 0.25, 0.85),
        capability="Native",
        native_rig="dolly",
    ),
    CameraCatalogEntry(
        id="rail",
        label="Rail",
        category="Ground Motion",
        aliases=("track", "slider rail"),
        description="Mechanical straight path support.",
        defaults=_defaults(0.45, 0.2, 0.88),
        capability="Native",
        native_rig="rail",
    ),
    CameraCatalogEntry(
        id="slider",
        label="Slider",
        category="Ground Motion",
        aliases=("mini slider",),
        description="Short controlled tracking support for subtle lateral moves.",
        defaults=_defaults(0.3, 0.18, 0.88),
        capability="Workflow-Mapped",
        workflow_rig="rail",
    ),
    CameraCatalogEntry(
        id="crane",
        label="Crane",
        category="Elevated Support",
        aliases=("boom arm",),
        description="Large elevated support for sweeping vertical movement.",
        defaults=_defaults(0.4, 0.28, 0.82),
        capability="Native",
        native_rig="crane",
    ),
    CameraCatalogEntry(
        id="jib",
        label="Jib",
        category="Elevated Support",
        aliases=("mini crane",),
        description="Compact boom support for vertical lift or descent.",
        defaults=_defaults(0.35, 0.22, 0.82),
        capability="Workflow-Mapped",
        workflow_rig="crane",
    ),
    CameraCatalogEntry(
        id="steadicam",
        label="Steadicam",
        category="Body-Mounted Support",
        aliases=("stabilized body rig",),
        description="Body-mounted stabilization with smooth human movement.",
        defaults=_defaults(0.45, 0.18, 0.9),
        capability="Native",
        native_rig="steadicam",
    ),
    CameraCatalogEntry(
        id="gimbal",
        label="Gimbal",
        category="Body-Mounted Support",
        aliases=("motorized stabilizer",),
        description="Motorized handheld stabilizer for smooth floating shots.",
        defaults=_defaults(0.38, 0.14, 0.92),
        capability="Native",
        native_rig="gimbal",
    ),
    CameraCatalogEntry(
        id="handheld",
        label="Handheld",
        category="Body-Mounted Support",
        aliases=("operator handheld",),
        description="Camera carried directly by the operator.",
        defaults=_defaults(0.6, 0.75, 0.55),
        capability="Native",
        native_rig="handheld",
    ),
    CameraCatalogEntry(
        id="shoulder_rig",
        label="Shoulder Rig",
        category="Body-Mounted Support",
        aliases=("shoulder mount",),
        description="Operator-carried support with reduced shake versus pure handheld.",
        defaults=_defaults(0.48, 0.45, 0.72),
        capability="Approximate",
    ),
    CameraCatalogEntry(
        id="drone",
        label="Drone",
        category="Aerial Support",
        aliases=("uav", "quad"),
        description="Aerial support for wide reveals and overhead movement.",
        defaults=_defaults(0.55, 0.3, 0.58),
        capability="Native",
        native_rig="drone",
    ),
    CameraCatalogEntry(
        id="cable_cam",
        label="Cable Cam",
        category="Aerial Support",
        aliases=("wire cam",),
        description="Suspended track system for precise travel over distance.",
        defaults=_defaults(0.52, 0.22, 0.86),
        capability="Approximate",
    ),
    CameraCatalogEntry(
        id="vehicle_mount",
        label="Vehicle Mount",
        category="Specialty Support",
        aliases=("car mount", "hood mount"),
        description="Mounted support attached to a moving vehicle.",
        defaults=_defaults(0.62, 0.35, 0.82),
        capability="Approximate",
    ),
    CameraCatalogEntry(
        id="virtual",
        label="Virtual",
        category="Specialty Support",
        aliases=("cg camera", "virtual camera"),
        description="Purely virtual camera path.",
        defaults=_defaults(0.5, 0.25, 0.95),
        capability="Native",
        native_rig="virtual",
    ),
    CameraCatalogEntry(
        id="custom",
        label="Custom",
        category="Custom",
        aliases=("other", "bespoke"),
        description="Creator-defined rig phrase preserved as a custom label.",
        defaults=_defaults(0.45, 0.4, 0.75),
        capability="Compiled Prompt Guidance",
    ),
)

CONTRADICTION_RULES: tuple[CameraContradictionRule, ...] = (
    CameraContradictionRule(
        id="locked_off_with_handheld_family",
        motion_ids=("locked_off",),
        rig_ids=("handheld", "shoulder_rig"),
        severity="error",
        message="Locked Off conflicts with handheld-style support.",
        fix_proposal="Use Tripod, Monopod, or Virtual for Locked Off framing, or change the motion to Handheld.",
    ),
    CameraContradictionRule(
        id="handheld_with_locked_support",
        motion_ids=("handheld",),
        rig_ids=("tripod", "dolly", "rail", "slider", "crane", "jib", "virtual"),
        severity="error",
        message="Handheld motion conflicts with locked or mechanically smooth support.",
        fix_proposal="Switch the rig to Handheld or Shoulder Rig, or change the motion to a supported move like Static, Rail, or Dolly In.",
    ),
    CameraContradictionRule(
        id="whip_pan_with_high_subject_lock",
        motion_ids=("whip_pan",),
        severity="warning",
        message="Whip Pan usually conflicts with a very strong subject lock.",
        fix_proposal="Reduce subject lock for a blurrier transition, or choose Pan for a steadier keep-on-subject move.",
    ),
    CameraContradictionRule(
        id="drone_with_grounded_rig",
        motion_ids=("drone", "drone_rise", "drone_descend"),
        rig_ids=("tripod", "dolly", "rail", "slider", "gimbal", "steadicam", "handheld", "shoulder_rig"),
        severity="error",
        message="Drone-style motion conflicts with a grounded rig selection.",
        fix_proposal="Use the Drone rig for aerial moves, or switch the motion to a ground-based move.",
    ),
)

_CAPABILITY_ORDER: dict[CameraCapability, int] = {
    "Native": 0,
    "Workflow-Mapped": 1,
    "Compiled Prompt Guidance": 2,
    "Approximate": 3,
    "Unsupported": 4,
}

_MOTION_BY_ID = {entry.id: entry for entry in MOTION_CATALOG}
_RIG_BY_ID = {entry.id: entry for entry in RIG_CATALOG}
_MOTION_BY_ALIAS = {
    alias.lower(): entry for entry in MOTION_CATALOG for alias in (entry.id, *entry.aliases)
}
_RIG_BY_ALIAS = {
    alias.lower(): entry for entry in RIG_CATALOG for alias in (entry.id, *entry.aliases)
}


def _entry_payload(entry: CameraCatalogEntry) -> dict[str, Any]:
    payload = asdict(entry)
    payload["defaults"] = asdict(entry.defaults)
    return payload


def _group_payload(entries: tuple[CameraCatalogEntry, ...]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        grouped.setdefault(entry.category, []).append(_entry_payload(entry))
    return [{"category": category, "items": items} for category, items in grouped.items()]


def _normalize_key(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    return text.replace("-", "_")


def get_motion_entry(motion_id: str | None) -> CameraCatalogEntry | None:
    key = _normalize_key(motion_id)
    if not key:
        return None
    return _MOTION_BY_ID.get(key) or _MOTION_BY_ALIAS.get(key)


def get_rig_entry(rig_id: str | None) -> CameraCatalogEntry | None:
    key = _normalize_key(rig_id)
    if not key:
        return None
    return _RIG_BY_ID.get(key) or _RIG_BY_ALIAS.get(key)


def resolve_motion_label(
    motion_id: str | None,
    *,
    custom_label: str | None = None,
    fallback: str | None = None,
) -> str | None:
    custom = (custom_label or "").strip()
    if custom:
        return custom
    entry = get_motion_entry(motion_id)
    if entry:
        return entry.label
    if fallback:
        return fallback.replace("_", " ").strip().title()
    return None


def resolve_rig_label(
    rig_id: str | None,
    *,
    custom_label: str | None = None,
    fallback: str | None = None,
) -> str | None:
    custom = (custom_label or "").strip()
    if custom:
        return custom
    entry = get_rig_entry(rig_id)
    if entry:
        return entry.label
    if fallback:
        return fallback.replace("_", " ").strip().title()
    return None


def classify_camera_capability(
    *,
    motion_id: str | None = None,
    rig_id: str | None = None,
    custom_motion_label: str | None = None,
    custom_rig_label: str | None = None,
) -> CameraCapability:
    custom_motion = bool((custom_motion_label or "").strip())
    custom_rig = bool((custom_rig_label or "").strip())
    motion_entry = get_motion_entry(motion_id)
    rig_entry = get_rig_entry(rig_id)
    motion_cap = (
        "Compiled Prompt Guidance"
        if custom_motion
        else (motion_entry.capability if motion_entry else "Unsupported")
    )
    rig_cap = (
        "Compiled Prompt Guidance"
        if custom_rig
        else (rig_entry.capability if rig_entry else "Unsupported")
    )
    return max((motion_cap, rig_cap), key=lambda item: _CAPABILITY_ORDER[item])


def describe_camera_clip(clip: Any) -> dict[str, Any]:
    motion_id = getattr(clip, "motion_id", None) or getattr(clip, "motion_type", None)
    rig_id = getattr(clip, "rig_id", None) or getattr(clip, "rig", None)
    custom_motion_label = getattr(clip, "custom_motion_label", None)
    custom_rig_label = getattr(clip, "custom_rig_label", None)
    motion_label = resolve_motion_label(
        motion_id,
        custom_label=custom_motion_label,
        fallback=getattr(clip, "motion_type", None),
    )
    rig_label = resolve_rig_label(
        rig_id,
        custom_label=custom_rig_label,
        fallback=getattr(clip, "rig", None),
    )
    capability = classify_camera_capability(
        motion_id=motion_id,
        rig_id=rig_id,
        custom_motion_label=custom_motion_label,
        custom_rig_label=custom_rig_label,
    )
    execution_strategy = (
        getattr(clip, "execution_strategy", None)
        or {
            "Native": "native",
            "Workflow-Mapped": "workflow_mapped",
            "Compiled Prompt Guidance": "compiled_prompt_guidance",
            "Approximate": "approximate",
            "Unsupported": "unsupported",
        }[capability]
    )
    return {
        "clipId": getattr(clip, "id", None),
        "motionId": _normalize_key(motion_id),
        "motionLabel": motion_label,
        "rigId": _normalize_key(rig_id),
        "rigLabel": rig_label,
        "customMotionLabel": custom_motion_label,
        "customRigLabel": custom_rig_label,
        "capability": capability,
        "executionStrategy": execution_strategy,
        "defaults": {
            "speed": getattr(clip, "speed", None),
            "intensity": getattr(clip, "intensity", None),
            "subjectLock": getattr(clip, "subject_lock", None),
        },
        "text": getattr(clip, "text", None) or "",
        "referenceBindingIds": list(getattr(clip, "reference_binding_ids", None) or []),
    }


def detect_camera_contradictions(clips: list[Any] | None) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for clip in clips or []:
        motion_id = _normalize_key(getattr(clip, "motion_id", None) or getattr(clip, "motion_type", None))
        rig_id = _normalize_key(getattr(clip, "rig_id", None) or getattr(clip, "rig", None))
        subject_lock = getattr(clip, "subject_lock", None)
        if motion_id == "custom" and not str(getattr(clip, "custom_motion_label", "") or "").strip():
            findings.append(
                {
                    "clipId": getattr(clip, "id", None),
                    "code": "camera_custom_motion_missing_label",
                    "severity": "error",
                    "message": "Custom camera motion requires a custom motion label.",
                    "fixProposal": "Name the custom motion so the system can preserve it honestly.",
                }
            )
        if rig_id == "custom" and not str(getattr(clip, "custom_rig_label", "") or "").strip():
            findings.append(
                {
                    "clipId": getattr(clip, "id", None),
                    "code": "camera_custom_rig_missing_label",
                    "severity": "error",
                    "message": "Custom camera rig requires a custom rig label.",
                    "fixProposal": "Name the custom rig so the system can preserve it honestly.",
                }
            )
        for rule in CONTRADICTION_RULES:
            if rule.motion_ids and motion_id not in rule.motion_ids:
                continue
            if rule.rig_ids and rig_id not in rule.rig_ids:
                continue
            if rule.id == "whip_pan_with_high_subject_lock" and (subject_lock is None or float(subject_lock) < 0.8):
                continue
            findings.append(
                {
                    "clipId": getattr(clip, "id", None),
                    "code": f"camera_contradiction:{rule.id}",
                    "severity": rule.severity,
                    "message": rule.message,
                    "fixProposal": rule.fix_proposal,
                }
            )
    return findings


def summarize_camera_strategy(clips: list[Any] | None) -> dict[str, Any]:
    clip_summaries = [describe_camera_clip(clip) for clip in (clips or [])]
    contradictions = detect_camera_contradictions(clips)
    overall = "Native"
    for summary in clip_summaries:
        if _CAPABILITY_ORDER[summary["capability"]] > _CAPABILITY_ORDER[overall]:
            overall = summary["capability"]
    return {
        "capability": overall,
        "clips": clip_summaries,
        "contradictions": contradictions,
        "hasContradictions": bool(contradictions),
    }


def camera_catalog_payload() -> dict[str, Any]:
    return {
        "version": "w46",
        "motions": [_entry_payload(entry) for entry in MOTION_CATALOG],
        "motionGroups": _group_payload(MOTION_CATALOG),
        "rigs": [_entry_payload(entry) for entry in RIG_CATALOG],
        "rigGroups": _group_payload(RIG_CATALOG),
        "contradictionRules": [asdict(rule) for rule in CONTRADICTION_RULES],
    }
