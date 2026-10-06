"""Text to Video local engine tokens. Timeline adapters stay I2V/R2V."""

from __future__ import annotations

from pathlib import Path

LTX25_T2V_ENGINES = frozenset(
    {
        "ltx-2.5",
        "ltx-2.5-distilled",
        "ltx-2.5-full",
        "ltx-2.5-comfy",
    }
)
MINIMAX_T2V_ENGINES = frozenset(
    {
        "minimax-h3",
        "minimax-h3-t2v-local",
        "minimax-h3-local",
    }
)

LOCAL_T2V_UNAVAILABLE = "LOCAL_T2V_UNAVAILABLE"
WRONG_SURFACE_FOR_ENGINE = "WRONG_SURFACE_FOR_ENGINE"


def is_local_ltx25_t2v_engine(engine: str | None) -> bool:
    return (engine or "").strip().lower() in LTX25_T2V_ENGINES


def is_local_minimax_t2v_engine(engine: str | None) -> bool:
    return (engine or "").strip().lower() in MINIMAX_T2V_ENGINES


def is_local_t2v_engine(engine: str | None) -> bool:
    return is_local_ltx25_t2v_engine(engine) or is_local_minimax_t2v_engine(engine)


def ltx25_t2v_files_present() -> bool:
    try:
        from ..config import settings
    except Exception:
        return False
    root = Path(getattr(settings, "comfy_models_dir", "") or "")
    if not root.is_dir():
        return False
    names = (
        (getattr(settings, "ltx_2_5_checkpoint", ""), ("diffusion_models", "checkpoints")),
        (getattr(settings, "ltx_2_5_text_encoder", ""), ("text_encoders",)),
        (getattr(settings, "ltx_2_5_video_vae", ""), ("vae",)),
    )
    for name, folders in names:
        if not name:
            return False
        found = any((root / folder / name).is_file() for folder in folders)
        if not found:
            return False
    return True


def minimax_t2v_files_present() -> bool:
    try:
        from ..minimax_h3.route_a_adapter import required_checkpoint_paths
    except Exception:
        return False
    try:
        return all(path.is_file() and path.stat().st_size > 0 for path in required_checkpoint_paths().values())
    except Exception:
        return False


def resolve_txt2vid_engine(
    engine: str | None,
    *,
    ltx25_ready: bool | None = None,
    minimax_ready: bool | None = None,
    paid_fal_approved: bool = False,
) -> str:
    """Pick the Text to Video runtime. Auto prefers local LTX 2.5, then MiniMax."""
    eng = (engine or "auto").strip().lower() or "auto"
    if ltx25_ready is None:
        ltx25_ready = ltx25_t2v_files_present()
    if minimax_ready is None:
        minimax_ready = minimax_t2v_files_present()
    if eng == "auto":
        if ltx25_ready:
            return "ltx-2.5"
        if minimax_ready:
            return "minimax-h3"
        return "auto"
    return eng


def i2v_only_blocker(*, engine: str) -> dict[str, object]:
    return {
        "code": WRONG_SURFACE_FOR_ENGINE,
        "message": (
            f"'{engine}' needs a picture. Use 1 Frame or Timeline. "
            "Text to Video is words-only — pick LTX 2.5 or MiniMax H3."
        ),
        "preferredAction": "use_one_frame_or_timeline",
    }


def local_t2v_unavailable_blocker() -> dict[str, object]:
    return {
        "code": LOCAL_T2V_UNAVAILABLE,
        "message": (
            "No local Text-to-Video engine is ready. Install LTX 2.5 or MiniMax H3 "
            "in Source Manager, or approve a hosted generator."
        ),
        "preferredAction": "open_source_manager",
    }
