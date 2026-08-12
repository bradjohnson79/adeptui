"""Dual HunyuanVideo provider capability matrix — independent of LTX/WAN defaults."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

ROOT = Path(__file__).resolve().parents[3]

ProviderId = Literal["hunyuan-video-1.5-local", "hunyuan-video-13b-local"]
EngineId = Literal["hunyuan15", "hunyuan13b"]

HUNYUAN_15 = "hunyuan-video-1.5-local"
HUNYUAN_13B = "hunyuan-video-13b-local"

OFFICIAL_SOURCES: dict[str, dict[str, Any]] = {
    HUNYUAN_15: {
        "engine": "hunyuan15",
        "label": "HunyuanVideo 1.5",
        "role": "recommended",
        "hfRepo": "tencent/HunyuanVideo-1.5",
        "github": "https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5",
        "componentId": "hunyuan_video_15",
        "minVramGb": 16,
        "recommendedVramGb": 24,
        "diskGb": 45,
        "profiles": ("consumer", "quality"),
        "defaultProfile": "consumer",
        "supports": ("text_to_video", "image_to_video", "timeline"),
        "threeFrame": False,
        "fp8Official": False,
    },
    HUNYUAN_13B: {
        "engine": "hunyuan13b",
        "label": "HunyuanVideo 13B",
        "role": "advanced",
        "hfRepo": "tencent/HunyuanVideo",
        "github": "https://github.com/Tencent-Hunyuan/HunyuanVideo",
        "componentId": "hunyuan_video_13b",
        "minVramGb": 24,
        "recommendedVramGb": 32,
        "diskGb": 80,
        "profiles": ("fp8_production", "full"),
        "defaultProfile": "fp8_production",
        "supports": ("text_to_video", "image_to_video", "timeline"),
        "threeFrame": False,
        "fp8Official": True,
    },
}

ENGINE_BY_PROVIDER = {pid: meta["engine"] for pid, meta in OFFICIAL_SOURCES.items()}
PROVIDER_BY_ENGINE = {meta["engine"]: pid for pid, meta in OFFICIAL_SOURCES.items()}
COMPONENT_BY_PROVIDER = {pid: meta["componentId"] for pid, meta in OFFICIAL_SOURCES.items()}
PROVIDER_BY_COMPONENT = {meta["componentId"]: pid for pid, meta in OFFICIAL_SOURCES.items()}


def models_root() -> Path:
    """Prefer D:\\01_Models for new Hunyuan downloads; fall back to repo data tree."""
    preferred = Path(r"D:\01_Models") / "Video" / "Hunyuan"
    try:
        preferred.mkdir(parents=True, exist_ok=True)
        return preferred
    except Exception:
        return ROOT / "data" / "models" / "video"


def provider_dir(provider_id: str) -> Path:
    return models_root() / provider_id


def cert_stamp_path(provider_id: str, name: str) -> Path:
    return ROOT / "artifacts" / "m42" / "hunyuan" / provider_id / name


def true_local_t2v_certified(provider_id: str) -> bool:
    """T2V only after per-provider evidence stamp exists."""
    p = cert_stamp_path(provider_id, "t2v_certified.json")
    if not p.is_file():
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
        return bool(data.get("ok") or data.get("passed") or data.get("go"))
    except Exception:
        return False


def install_status_path(provider_id: str) -> Path:
    return provider_dir(provider_id) / "install_status.json"


def load_install_status(provider_id: str) -> dict[str, Any]:
    path = install_status_path(provider_id)
    if not path.is_file():
        return {"installed": False, "healthy": False, "version": None, "profile": None}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {"installed": False, "healthy": False, "version": None, "profile": None}


def save_install_status(provider_id: str, payload: dict[str, Any]) -> None:
    root = provider_dir(provider_id)
    root.mkdir(parents=True, exist_ok=True)
    install_status_path(provider_id).write_text(json.dumps(payload, indent=2), encoding="utf-8")


@dataclass
class HunyuanProviderCapabilities:
    providerId: str
    engine: str
    label: str
    role: str
    status: str  # Default | Installed… | Not Installed | Queued | Downloading | Install Failed | Coming Soon
    installed: bool
    healthy: bool
    version: str | None
    storagePath: str
    hfRepo: str
    profiles: list[str]
    recommendedProfile: str
    minVramGb: float
    recommendedVramGb: float
    diskGb: float
    supportsTextToVideo: bool
    supportsImageToVideo: bool
    supportsTimeline: bool
    supportsThreeFrame: bool
    trueLocalT2vCertified: bool
    fp8Official: bool
    executable: bool
    lastError: str | None = None
    downloadPhase: str | None = None
    downloadPercent: float | None = None
    downloadOperationId: str | None = None
    notes: list[str] = field(default_factory=list)

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


def _resolve_install_status_label(
    provider_id: str,
    *,
    installed: bool,
    healthy: bool,
    role: str,
    status_row: dict[str, Any],
) -> tuple[str, str | None, str | None, float | None, str | None]:
    """Return (status, lastError, downloadPhase, downloadPercent, operationId)."""
    last_error = status_row.get("lastError")
    download_phase = None
    download_percent = None
    op_id = None
    try:
        from .hunyuan_install import active_download_for

        op = active_download_for(str(OFFICIAL_SOURCES[provider_id]["componentId"]))
    except Exception:
        op = None
    if op:
        op_id = str(op.get("id") or "") or None
        download_phase = str(op.get("phase") or "")
        pct = (op.get("progress") or {}).get("percent")
        if isinstance(pct, (int, float)):
            download_percent = float(pct)
        fail = op.get("failure") or {}
        if isinstance(fail, dict) and fail.get("message"):
            last_error = str(fail.get("message"))
        if not op.get("terminal"):
            if download_phase in {"queued", "planning"}:
                return "Queued", last_error, download_phase, download_percent, op_id
            if download_phase in {"downloading", "verifying", "extracting", "running", "starting"}:
                label = f"Downloading ({download_percent:.0f}%)" if download_percent is not None else "Downloading"
                return label, last_error, download_phase, download_percent, op_id
            return download_phase.title() or "Installing", last_error, download_phase, download_percent, op_id
        if download_phase == "failed" or fail:
            return "Install Failed", last_error, download_phase, download_percent, op_id

    if installed and healthy:
        return (
            "Installed Optional" if role == "recommended" else "Installed Advanced",
            None,
            download_phase,
            download_percent,
            op_id,
        )
    if last_error:
        return "Install Failed", str(last_error), download_phase, download_percent, op_id
    # Partial on-disk files but not healthy yet
    root = provider_dir(provider_id)
    if root.is_dir():
        weightish = any(
            p.is_file() and p.suffix in {".safetensors", ".pt"} and p.stat().st_size > 1_000_000
            for p in root.rglob("*")
            if ".cache" not in p.parts and ".adept-staging" not in p.parts
        )
        if weightish:
            return "Incomplete", last_error, download_phase, download_percent, op_id
    return "Not Installed", last_error, download_phase, download_percent, op_id


def describe_provider(provider_id: str) -> HunyuanProviderCapabilities:
    meta = OFFICIAL_SOURCES[provider_id]
    status_row = load_install_status(provider_id)
    # Re-probe weights so status recovers after a completed download without stale JSON
    try:
        from .hunyuan_install import verify_weights

        verify = verify_weights(provider_id)
        if verify.get("ok") and not status_row.get("installed"):
            status_row = {
                **status_row,
                "installed": True,
                "healthy": True,
                "version": "1.5" if provider_id == HUNYUAN_15 else "13b",
                "lastError": None,
                "updatedAt": status_row.get("updatedAt"),
            }
            save_install_status(provider_id, status_row)
        elif status_row.get("installed") and not verify.get("ok"):
            status_row = {
                **status_row,
                "installed": False,
                "healthy": False,
                "lastError": verify.get("message"),
            }
            save_install_status(provider_id, status_row)
    except Exception:
        pass

    installed = bool(status_row.get("installed"))
    healthy = bool(status_row.get("healthy"))
    t2v = true_local_t2v_certified(provider_id)
    role = str(meta["role"])
    status, last_error, dl_phase, dl_pct, op_id = _resolve_install_status_label(
        provider_id,
        installed=installed,
        healthy=healthy,
        role=role,
        status_row=status_row,
    )
    supports = set(meta["supports"])
    notes: list[str] = []
    if "text_to_video" in supports and not t2v:
        notes.append("True local T2V reserved until this provider passes certification.")
    if meta.get("fp8Official"):
        notes.append("Official FP8 profile available when hardware recommends it.")
    if last_error and status in {"Install Failed", "Incomplete", "Not Installed"}:
        notes.append(f"Last error: {last_error}")
    return HunyuanProviderCapabilities(
        providerId=provider_id,
        engine=str(meta["engine"]),
        label=str(meta["label"]),
        role=role,
        status=status,
        installed=installed,
        healthy=healthy,
        version=status_row.get("version"),
        storagePath=str(provider_dir(provider_id)),
        hfRepo=str(meta["hfRepo"]),
        profiles=list(meta["profiles"]),
        recommendedProfile=str(meta["defaultProfile"]),
        minVramGb=float(meta["minVramGb"]),
        recommendedVramGb=float(meta["recommendedVramGb"]),
        diskGb=float(meta["diskGb"]),
        supportsTextToVideo="text_to_video" in supports and t2v,
        supportsImageToVideo="image_to_video" in supports,
        supportsTimeline="timeline" in supports,
        supportsThreeFrame=bool(meta.get("threeFrame")),
        trueLocalT2vCertified=t2v,
        fp8Official=bool(meta.get("fp8Official")),
        executable=installed and healthy,
        lastError=str(last_error) if last_error else None,
        downloadPhase=dl_phase,
        downloadPercent=dl_pct,
        downloadOperationId=op_id,
        notes=notes,
    )


def list_hunyuan_providers() -> list[dict[str, Any]]:
    return [describe_provider(pid).public_dict() for pid in (HUNYUAN_15, HUNYUAN_13B)]


def video_library_matrix() -> dict[str, Any]:
    """Creator-facing Video Model Library matrix (LTX default preserved)."""
    return {
        "ok": True,
        "defaultProviderId": "minimax-h3",
        "providers": [
            {
                "providerId": "ltx-local",
                "label": "LTX Video",
                "status": "Default",
                "engine": "ltx",
                "supportsTextToVideo": False,
                "supportsImageToVideo": True,
                "notes": ["Default production engine. Local path remains start-frame / I2V-oriented."],
            },
            *list_hunyuan_providers(),
            {
                "providerId": "wan-local",
                "label": "WAN 2.2",
                "status": "Optional",
                "engine": "wan",
                "supportsTextToVideo": False,
                "supportsImageToVideo": True,
                "supportsThreeFrame": True,
                "notes": ["Optional local provider; not removed or hidden."],
            },
            {
                "providerId": "minimax-h3",
                "label": "MiniMax H3",
                "status": "Requires Setup",
                "engine": "minimax-h3",
                "supportsTextToVideo": True,
                "supportsImageToVideo": True,
                "supportsStartEndFrame": True,
                "supportsThreeFrame": False,
                "supportsNativeAudio": True,
                "notes": [
                    "Three-frame requests use Adept segmented assembly rather than native three-keyframe support.",
                    "Local MiniMax H3 remains territory-gated and does not auto-switch to LTX.",
                ],
            },
        ],
        "mock": False,
    }


def allow_local_t2v(engine: str | None) -> bool:
    eng = (engine or "").lower().strip()
    provider_id = PROVIDER_BY_ENGINE.get(eng)
    if not provider_id:
        return False
    return true_local_t2v_certified(provider_id)
