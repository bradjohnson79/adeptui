"""Deterministic video-generator R2V knowledge. No RAG. No embeddings.

Each ``video-generators/*.md`` is the semantic authority. YAML front matter
is the compile contract Timeline and Co-Director both read.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

VIDEO_KB_DIR = Path(__file__).resolve().parent / "video-generators"

PROFILE_FILES = {
    "minimax-h3": "minimax-h3.md",
    "minimax-h3-local": "minimax-h3.md",
    "minimax-h3-t2v-local": "minimax-h3.md",
    "minimax-h3-i2v-local": "minimax-h3.md",
    "minimax-h3-i2v": "minimax-h3.md",
    "ltx-2.5": "ltx-2.5.md",
    "ltx-2.5-full": "ltx-2.5.md",
    "ltx-2.5-distilled": "ltx-2.5.md",
    "ltx-2.5-comfy": "ltx-2.5.md",
    "ltx_2_5_full": "ltx-2.5.md",
    "ltx_2_5_distilled": "ltx-2.5.md",
    "ltx_2_5_comfy": "ltx-2.5.md",
    "seedance-2.0": "seedance-2.0.md",
    "seedance-api": "seedance-2.0.md",
    "seedance-fal": "seedance-2.0.md",
    "fal_seedance": "seedance-2.0.md",
    "seedance-2.5": "seedance-2.5.md",
    "fal_seedance_25": "seedance-2.5.md",
    "seedance-kie": "seedance-kie.md",
    "kling-api": "kling.md",
    "kling-fal": "kling.md",
    "kling-kie": "kling.md",
    "veo-api": "veo-3.1.md",
    "veo-kie": "veo-3.1.md",
    "veo-fal": "veo-fal.md",
}


@dataclass(frozen=True)
class R2VCompileContract:
    dialect: str = ""
    mechanism: str = ""
    emit_image: str | None = None
    emit_video: str | None = None
    emit_audio: str | None = None
    max_images: int = 0
    max_videos: int = 0
    max_audio: int = 0
    tensor_slots: str = "none"
    never_emit: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "dialect": self.dialect,
            "mechanism": self.mechanism,
            "emitImage": self.emit_image,
            "emitVideo": self.emit_video,
            "emitAudio": self.emit_audio,
            "maxImages": self.max_images,
            "maxVideos": self.max_videos,
            "maxAudio": self.max_audio,
            "tensorSlots": self.tensor_slots,
            "neverEmit": list(self.never_emit),
        }


@dataclass(frozen=True)
class VideoGeneratorKnowledge:
    generator_id: str
    spec_path: Path
    spec_text: str
    compile: R2VCompileContract = field(default_factory=R2VCompileContract)
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def loaded(self) -> bool:
        return bool(self.spec_text.strip()) and self.spec_path.is_file()


def resolve_video_generator_spec_name(generator_id: str | None) -> str | None:
    token = str(generator_id or "").strip()
    if not token:
        return None
    return PROFILE_FILES.get(token) or PROFILE_FILES.get(token.lower())


def _as_token(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "~"}:
        return None
    return text


def _parse_contract(raw: dict[str, Any] | None) -> R2VCompileContract:
    data = raw if isinstance(raw, dict) else {}
    never = tuple(str(item) for item in (data.get("never_emit") or []) if item)
    return R2VCompileContract(
        dialect=str(data.get("dialect") or "").strip(),
        mechanism=str(data.get("mechanism") or "").strip(),
        emit_image=_as_token(data.get("emit_image")),
        emit_video=_as_token(data.get("emit_video")),
        emit_audio=_as_token(data.get("emit_audio")),
        max_images=int(data.get("max_images") or 0),
        max_videos=int(data.get("max_videos") or 0),
        max_audio=int(data.get("max_audio") or 0),
        tensor_slots=str(data.get("tensor_slots") or "none").strip() or "none",
        never_emit=never,
    )


def _split_front_matter(text: str) -> tuple[dict[str, Any], str]:
    raw = text or ""
    if not raw.startswith("---"):
        return {}, raw
    rest = raw[3:]
    if rest.startswith("\n"):
        rest = rest[1:]
    marker = "\n---\n"
    idx = rest.find(marker)
    if idx < 0:
        alt = rest.find("\n---\r\n")
        if alt >= 0:
            idx = alt
            end = alt + len("\n---\r\n")
        else:
            return {}, raw
        payload = rest[:idx]
        body = rest[end:]
    else:
        payload = rest[:idx]
        body = rest[idx + len(marker) :]
    try:
        parsed = yaml.safe_load(payload)
    except yaml.YAMLError:
        return {}, raw
    if not isinstance(parsed, dict):
        return {}, raw
    return parsed, body


def load_video_generator_knowledge(
    generator_id: str | None,
    *,
    root: Path | None = None,
) -> VideoGeneratorKnowledge:
    kb_dir = Path(root) if root is not None else VIDEO_KB_DIR
    name = resolve_video_generator_spec_name(generator_id) or ""
    path = kb_dir / name if name else kb_dir / "_missing.md"
    raw = path.read_text(encoding="utf-8") if path.is_file() else ""
    meta, body = _split_front_matter(raw)
    compile_raw = meta.get("compile") if isinstance(meta.get("compile"), dict) else {}
    return VideoGeneratorKnowledge(
        generator_id=str(generator_id or ""),
        spec_path=path,
        spec_text=body.strip() or raw,
        compile=_parse_contract(compile_raw),
        meta=meta,
    )
