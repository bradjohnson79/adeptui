"""MAGI post-production authority stamps (CONTRACT_FREEZE).

Sole MAGI editorial and final_render mix authority is sequence.json plus finishing.
Legacy /api/projects/{id}/editor and Audio Studio mix.json are adjacent/compat only.
"""

from __future__ import annotations

from typing import Any

MAGI_SEQUENCE_AUTHORITY = "magi-sequence"
MAGI_SEQUENCE_STORE = "sequence.json"
MAGI_FINISHING_AUDIO_AUTHORITY = "magi-finishing.audio"
AUDIO_STUDIO_MIX_AUTHORITY = "audio-studio"
AUDIO_STUDIO_MIX_STORE = "audio_studio/{projectId}/mix.json"

LEGACY_EDITOR_WRITES_DEPRECATED = "LEGACY_EDITOR_WRITES_DEPRECATED"
EDITOR_MIX_DEPRECATED = "EDITOR_MIX_DEPRECATED"


def magi_sequence_path(project_id: str) -> str:
    return f"/api/magi/projects/{project_id}/sequence"


def magi_renders_path(project_id: str) -> str:
    return f"/api/magi/projects/{project_id}/renders"


def editorial_deprecation_detail(project_id: str) -> dict[str, Any]:
    return {
        "ok": False,
        "code": LEGACY_EDITOR_WRITES_DEPRECATED,
        "authority": MAGI_SEQUENCE_AUTHORITY,
        "authorityStore": MAGI_SEQUENCE_STORE,
        "magiSequencePath": magi_sequence_path(project_id),
        "message": (
            "Legacy /api/projects/{id}/editor writes are deprecated. "
            "MAGI sequence.json is the sole editorial authority. "
            f"Use PUT {magi_sequence_path(project_id)}."
        ),
    }


def editor_mix_deprecation_detail(project_id: str) -> dict[str, Any]:
    return {
        "ok": False,
        "code": EDITOR_MIX_DEPRECATED,
        "authority": MAGI_FINISHING_AUDIO_AUTHORITY,
        "magiRendersPath": magi_renders_path(project_id),
        "message": (
            "Legacy editor_mix is deprecated. MAGI Final Render mix authority is "
            "sequence finishing.audio (musicAssetId/sfxAssetId), not legacy Editor tracks "
            "or Audio Studio mix.json. "
            f"Use POST {magi_renders_path(project_id)}."
        ),
        "adjacentNotUsed": ["audio-studio-mix", "legacy-editor-tracks"],
    }


def audio_studio_mix_labels(project_id: str) -> dict[str, Any]:
    return {
        "authority": AUDIO_STUDIO_MIX_AUTHORITY,
        "authorityStore": AUDIO_STUDIO_MIX_STORE.replace("{projectId}", project_id),
        "notMagiAuthority": True,
        "finalRenderMixAuthority": MAGI_FINISHING_AUDIO_AUTHORITY,
        "message": (
            "Audio Studio mix is an adjacent domain for Timeline/Audio Studio workflows. "
            "MAGI Final Render uses sequence finishing.audio only - not this mix document."
        ),
    }


def finishing_audio_labels() -> dict[str, Any]:
    return {
        "authority": MAGI_FINISHING_AUDIO_AUTHORITY,
        "authorityStore": "sequence.json#finishing.audio",
        "adjacentNotUsed": ["audio-studio-mix", "legacy-editor-tracks"],
    }
