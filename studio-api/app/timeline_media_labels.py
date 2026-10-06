"""Canonical Timeline media TITLE + DESCRIPTION + clip-face LABEL resolver.

Python mirror of studio-web/src/timelineMaster/mediaClipLabels.ts.
Shared contract field names: title, description, label (truncated face).
Fallback order STRICT: metadata → job → prompt → asset → filename.
Never fabricates creative detail (unknown → None / "").
"""

from __future__ import annotations

import re
from typing import Any, Literal, Mapping, MutableMapping, Sequence

MediaClipKind = Literal[
    "audio", "sfx", "music", "ambience", "performance_retake", "lipsync"
]
MediaLabelTierource = Literal[
    "metadata", "job", "prompt", "asset", "filename", "none"
]

DEFAULT_MAX_LABEL = 36

_GENERIC_LABELS = {
    "audio",
    "sfx",
    "music",
    "ambience",
    "lip sync clip",
    "lipsync clip",
    "timeline audio",
    "music cue",
    "ambience bed",
}

_SAY_RE = re.compile(
    r"([A-Za-z][A-Za-z0-9_ '\-]{0,40}?)\s+says?,?\s*[\u201c\u201d\"](.+?)[\u201c\u201d\"]",
    re.IGNORECASE | re.DOTALL,
)
_COLON_RE = re.compile(
    r"([A-Za-z][A-Za-z0-9_ '\-]{0,40}?)\s*:\s*[\u201c\u201d\"](.+?)[\u201c\u201d\"]",
    re.IGNORECASE | re.DOTALL,
)
_PLACEHOLDER_LINE_RE = re.compile(r"^.+\s+line$", re.IGNORECASE)


def _trim(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def is_generic_label(label: str) -> bool:
    t = (label or "").strip()
    if not t:
        return True
    if t.lower() in _GENERIC_LABELS:
        return True
    if _PLACEHOLDER_LINE_RE.match(t):
        return True
    return False


def truncate_clip_face_label(text: str, max_chars: int = DEFAULT_MAX_LABEL) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    if max_chars < 4:
        return t[: max(0, max_chars)]
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 1].rstrip() + "…"


def extract_quoted_dialogue_from_prompt(
    prompt: str, speaker_hint: str | None = None
) -> list[dict[str, str]]:
    text = _trim(prompt)
    if not text:
        return []
    out: list[dict[str, str]] = []
    for pattern in (_SAY_RE, _COLON_RE):
        for m in pattern.finditer(text):
            speaker = _trim(m.group(1))
            line = _trim(m.group(2))
            if not speaker or not line:
                continue
            if any(x["speaker"] == speaker and x["line"] == line for x in out):
                continue
            out.append({"speaker": speaker, "line": line})
    hint = _trim(speaker_hint)
    if hint:
        matched = [x for x in out if x["speaker"].lower() == hint.lower()]
        if matched:
            return matched
    return out


def _first_non_empty(*values: Any) -> str | None:
    for v in values:
        t = _trim(v)
        if t:
            return t
    return None


def _filename_stem(filename: str | None) -> str | None:
    f = _trim(filename)
    if not f:
        return None
    base = f.replace("\\", "/").split("/")[-1]
    if "." in base:
        base = base.rsplit(".", 1)[0]
    base = base.strip()
    return base or None


def _job_string(job: Mapping[str, Any] | None, keys: Sequence[str]) -> str | None:
    if not job:
        return None
    for key in keys:
        v = job.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, Mapping):
            for nk in ("title", "description", "label", "line", "prompt"):
                nv = v.get(nk)
                if isinstance(nv, str) and nv.strip():
                    return nv.strip()
    return None


def _is_retake(kind: str) -> bool:
    return kind in ("performance_retake", "lipsync")


def _prompts_for_clip(ctx: Mapping[str, Any] | None) -> list[str]:
    if not ctx:
        return []
    collected: list[str] = []
    for p in ctx.get("prompts") or []:
        t = _trim(p)
        if t:
            collected.append(t)
    segs = ctx.get("promptSegments") or ctx.get("prompt_segments") or []
    clip_start = ctx.get("clipStart", ctx.get("clip_start"))
    clip_length = ctx.get("clipLength", ctx.get("clip_length"))
    has_window = isinstance(clip_start, (int, float)) and isinstance(
        clip_length, (int, float)
    )
    for seg in segs:
        if not isinstance(seg, Mapping):
            continue
        text = _trim(seg.get("text"))
        if not text:
            continue
        if has_window:
            s = float(seg.get("start") or 0)
            l = float(seg.get("length") or 0)
            clip_end = float(clip_start) + float(clip_length)
            seg_end = s + l
            if l > 0 and not (s < clip_end and seg_end > float(clip_start)):
                continue
        collected.append(text)
    return collected


def _build_retake_description(line: str | None, ids: Mapping[str, Any]) -> str | None:
    parts: list[str] = []
    if line:
        parts.append(line)
    id_bits: list[str] = []
    if ids.get("retakeId"):
        id_bits.append(f"retakeId={ids['retakeId']}")
    if ids.get("voiceAssetId"):
        id_bits.append(f"voiceAssetId={ids['voiceAssetId']}")
    if ids.get("audioAssetId"):
        id_bits.append(f"audio_asset_id={ids['audioAssetId']}")
    asset_id = ids.get("assetId")
    if asset_id and asset_id != ids.get("audioAssetId"):
        id_bits.append(f"assetId={asset_id}")
    if id_bits:
        parts.append("; ".join(id_bits))
    return "\n".join(parts) if parts else None


def resolve_media_clip_labels(input_data: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve title/description/label. Input keys mirror the TS MediaClipLabelInput."""
    kind = str(input_data.get("kind") or "audio")
    clip = input_data.get("clip") or {}
    if not isinstance(clip, Mapping):
        clip = {}
    asset = input_data.get("asset")
    job = input_data.get("job")
    prompt_context = input_data.get("promptContext") or input_data.get("prompt_context")
    max_chars = int(input_data.get("maxLabelChars") or input_data.get("max_label_chars") or DEFAULT_MAX_LABEL)

    ids = {
        "retakeId": _first_non_empty(
            clip.get("retakeId"),
            clip.get("retake_id"),
            clip.get("id") if _is_retake(kind) else None,
        ),
        "voiceAssetId": _first_non_empty(clip.get("voiceAssetId"), clip.get("voice_asset_id")),
        "audioAssetId": _first_non_empty(clip.get("audio_asset_id")),
        "assetId": _first_non_empty(clip.get("asset_id")),
    }

    title: str | None = None
    description: str | None = None
    title_source: MediaLabelTierource = "none"
    description_source: MediaLabelTierource = "none"

    meta_title = _first_non_empty(clip.get("title"))
    meta_description = _first_non_empty(clip.get("description"))
    meta_line = _first_non_empty(clip.get("line"))
    meta_label = _first_non_empty(clip.get("label"))
    speaker = _first_non_empty(clip.get("character_name"))

    # 1. metadata
    if _is_retake(kind):
        if speaker and meta_line:
            title = f"{speaker}: {meta_line}"
            title_source = "metadata"
            description = _build_retake_description(meta_line, ids)
            description_source = "metadata"
        elif meta_title:
            title = meta_title
            title_source = "metadata"
            description = meta_description or _build_retake_description(meta_line, ids)
            description_source = "metadata" if description else "none"
        elif meta_label and not is_generic_label(meta_label) and meta_line:
            title = f"{speaker}: {meta_line}" if speaker else meta_label
            title_source = "metadata"
            description = _build_retake_description(meta_line, ids)
            description_source = "metadata"
    else:
        if meta_title:
            title = meta_title
            title_source = "metadata"
        elif meta_label and not is_generic_label(meta_label):
            title = meta_label
            title_source = "metadata"
        if meta_description:
            description = meta_description
            description_source = "metadata"

    # 2. job
    if not title:
        job_title = _job_string(job if isinstance(job, Mapping) else None, ("title", "label", "clipLabel", "name"))
        if job_title and not is_generic_label(job_title):
            title = job_title
            title_source = "job"
    if not description:
        job_desc = _job_string(
            job if isinstance(job, Mapping) else None, ("description", "line", "dialogue", "prompt")
        )
        if job_desc:
            description = job_desc
            description_source = "job"
    if _is_retake(kind) and not title:
        job_line = _job_string(job if isinstance(job, Mapping) else None, ("line", "dialogue"))
        job_speaker = (
            _job_string(
                job if isinstance(job, Mapping) else None,
                ("character_name", "speaker", "characterName"),
            )
            or speaker
        )
        if job_speaker and job_line:
            title = f"{job_speaker}: {job_line}"
            title_source = "job"
            if not description:
                description = _build_retake_description(job_line, ids)
                description_source = "job"

    # 3. prompt
    if _is_retake(kind) and (not title or not meta_line):
        prompt_texts = _prompts_for_clip(prompt_context if isinstance(prompt_context, Mapping) else None)
        found = None
        for p in prompt_texts:
            hits = extract_quoted_dialogue_from_prompt(p, speaker)
            if hits:
                found = hits[0]
                break
        if found:
            if not title or is_generic_label(meta_label or "") or not meta_line:
                title = f"{found['speaker']}: {found['line']}"
                title_source = "prompt"
            if not description or not meta_line:
                description = _build_retake_description(found["line"], ids)
                description_source = "prompt"

    # 4. asset
    if not title and isinstance(asset, Mapping):
        labels = asset.get("labels") or []
        label_hit = next((_trim(x) for x in labels if _trim(x)), None) if isinstance(labels, list) else None
        from_asset = _first_non_empty(asset.get("tag"), label_hit, asset.get("prompt_meta"))
        if from_asset and not is_generic_label(from_asset):
            title = from_asset
            title_source = "asset"
    if not description and isinstance(asset, Mapping):
        d = _first_non_empty(asset.get("prompt_meta"))
        if d and d != title:
            description = d
            description_source = "asset"

    # 5. filename
    if not title and isinstance(asset, Mapping):
        stem = _filename_stem(asset.get("filename") if isinstance(asset.get("filename"), str) else None)
        if stem:
            title = stem
            title_source = "filename"

    if _is_retake(kind) and not description:
        id_only = _build_retake_description(None, ids)
        if id_only:
            description = id_only
            if description_source == "none":
                description_source = "metadata"

    label = truncate_clip_face_label(title or "", max_chars)
    return {
        "title": title,
        "description": description,
        "label": label,
        "sources": {"title": title_source, "description": description_source},
        "ids": ids,
    }


def apply_resolved_media_clip_labels(
    clip: MutableMapping[str, Any],
    resolved: Mapping[str, Any],
    *,
    set_line_from_title: bool = False,
    speaker: str | None = None,
    persist_truncated_label: bool = False,
) -> MutableMapping[str, Any]:
    """Apply resolver output onto a clip dict.

    By default persists the FULL title into ``label`` (UI truncates at render time
    via resolve_media_clip_labels().label). Pass persist_truncated_label=True only
    when deliberately storing the clip-face string.
    """
    clip["title"] = resolved.get("title")
    clip["description"] = resolved.get("description")
    if persist_truncated_label:
        clip["label"] = resolved.get("label") or _trim(clip.get("label")) or ""
    else:
        clip["label"] = (
            _trim(resolved.get("title"))
            or _trim(clip.get("label"))
            or _trim(resolved.get("label"))
            or ""
        )
    if set_line_from_title and resolved.get("title") and not _trim(clip.get("line")):
        title = str(resolved["title"])
        sp = _trim(speaker) or _trim(clip.get("character_name"))
        line = ""
        if sp and title.startswith(f"{sp}:"):
            line = title[len(sp) + 1 :].strip()
        else:
            idx = title.find(":")
            if idx > 0:
                line = title[idx + 1 :].strip()
        if line:
            clip["line"] = line
    return clip
