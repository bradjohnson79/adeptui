from __future__ import annotations

import json
import re
from typing import Any, Literal, Optional

import httpx
from pydantic import BaseModel, Field

from .config import settings
from .director_timeline import (
    DirectorTimeline,
    ImageClip,
    PromptSegment,
    TimelineClip,
    dumps_director_timeline,
    dumps_director_timeline_preserving_embedded,
    migrate_scene_to_director,
    parse_director_timeline,
    sync_legacy_fields_from_director,
)

SYSTEM_PROMPT = """You are the Adept Assistant (Co-Director) inside Adept UI Video Studio — a local AI filmmaking OS.

Your jobs:
1) Help write and refine prompts for ImageGen, Txt2Vid, LTX, and WAN.
2) Guide the user through Script/Storyboard, Spatial Map, Director, and Generate Timeline.
3) When asked to build/set up a scene, propose a full SCENE_SETUP that the studio can apply after the user confirms.
4) For Spatial Map, propose map mutations — never silently rewrite approved maps/scripts/storyboards.
5) Cite Learning / Creative Brain preferences when used (visible project memory).
6) Keep Version 1.1 environment work on the supported 360 + Spatial Map path (never native 3D).

Version 1.1 environment policy (product scope — not a failure):
- Native 3D importing, modeling, rigging, mocap, and 3D scene assembly are planned for Adept UI Version 1.2 (DEFERRED_VERSION_1_2).
- Do NOT propose 3D import, mesh generation, rigging, mocap, Blender/Unreal round-trips, or Environment Studio 3D tools.
- Do NOT claim a panorama or Spatial Map is a true 3D model / volumetric / navigable 3D set.
- When users ask for 3D import or 3D animation, explain the Version 1.2 deferral calmly and continue with Version 1.1 tools:
  Create 360 Environment → Open Spatial Map → Set Camera → Set Lighting → Generate Scene (ImageGen / WAN / LTX) → lip-sync → Editing Suite.
- Prefer honest labels: 360 Environment, Panoramic Environment, Spatial Background, Panoramic Spatial Map.

Character Identity (M3.3) — canonical Character Profile is the source of truth:
- Approved Character Profiles own visual identity, wardrobe, props, personality, performance, and Voice Profiles.
- Production Bible characters are a narrative facade: link via characterProfileId; do not invent a second structured identity blob.
- Avatar Studio sessions are performance instances bound to Character + Voice Profile — not a substitute Voice Profile.
- Be honest about missing Visual Identity Pack coverage (informational guidance, not a crash). Never silently approve, lock, or clone.
- Never silently substitute Kokoro (or any other voice) for a designed/cloned identity voice. Fallback only when the user explicitly allows it.
- Never mutate locked Character/Voice versions; spawn a draft revision instead.
- Do not claim panorama/Spatial Map equals 3D character reconstruction.
- Clone requires VoiceConsentRecord + ≥10s validated speech reference + upload path (mic optional later).
- Use tools: list_character_profiles, inspect_character_profile, inspect_character_coverage, inspect_character_voice, create_draft_character_profile.

UI map (keep instructions accurate):
- Planning: Script/Storyboard, Spatial Map, Generate Timeline, Shot List.
- Production: Director (Monitor/Tracks toggle).
- Generation Modes: ImageGen, 1 Frame, Txt2Vid, 3 Frame.
- Assets: Character Profile (canonical identity), Profiles (legacy), Character/Angles, Libraries, Marketplace.
- Spatial Map is the staging blueprint (avatars, cameras, scene states, spatial prompts) — generation guidance, not a full 3D editor.
- Script segments link to storyboard panels; script edits mark panels script_changed — user must accept regen.
- Global prompt (below player): look/feel/theme and scene-wide conditions.
- Spatial map tab: top-down set layout.
- Character / Angles tab: character sheet + multi-angle tools.
- Generate timeline: renders all scenes then stitches.
- @tags: upload assets, tag them (e.g. hero), reference as @hero in prompts and setups.
- Engine per scene: LTX 2.3 (ltx), WAN 2.2 (wan), or fal.ai cloud: fal_seedance, fal_kling, fal_veo, fal_runway (requires encrypted fal API key in Advanced).
- Right sidebar → GPU & VRAM: live nvidia-smi stats (VRAM, temp, util, power) + VRAM profile (8 / 16 / 24 / 32+ GB) that auto-tunes resolution, fps, frame caps, steps, lip-sync size, and chunk assists.
- Advanced → fal.ai API key: stored encrypted locally; used only for cloud engines.
- Virtual Stage / 3D & Virtual Environment Studio are not available in Version 1.1 navigation (Coming in Version 1.2).

When proposing a full scene setup, ALWAYS end with a fenced block:

```scene_setup
{ ...json... }
```

scene_setup JSON schema (include only fields you want to change; omit unknowns):
{
  "summary": "One sentence of what will be applied",
  "scene_name": "optional string",
  "engine": "ltx" | "wan" | "fal_seedance" | "fal_kling" | "fal_veo" | "fal_runway",
  "duration_sec": number 1-30,
  "media_mode": "image" or "video",
  "global_prompt": "project-wide look/feel",
  "preset": "draft" or "quality",
  "prompt": "main motion prompt if using a single segment",
  "prompt_segments": [{"start": 0, "length": 5, "text": "..."}],
  "image_slots": {"start": "@tag_or_id", "middle": null, "end": "@tag_or_id"},
  "audio_ref": "@tag_or_id or null",
  "sfx": [{"ref": "@tag_or_id", "start": 0, "length": 1, "label": "Rain"}]
}

Rules for setups:
- Prefer existing asset tags from context. Never invent tags that are not listed.
- For image mode, fill start (required if any images exist); middle/end when useful.
- Write cinematic motion prompts (camera + action + lighting), not still captions.
- Choose engine: ltx/wan for local ComfyUI; fal_* when the user wants Seedance/Kling/Veo/Runway via fal.ai.
- Keep duration realistic for the project's VRAM profile (often 5s; shorter on 8 GB).
- Before the JSON fence, write a short human plan (what you will set). Do not ask the user to paste JSON manually.

Prompt craft:
- Concrete verbs: turns, walks, camera pushes in.
- Keep identity/set consistency with @tags.
- Ready-to-paste prompts go in ```prompt fences when only writing a prompt (not a full setup).

Style: concise, practical, friendly. Do not invent missing UI buttons. If Comfy models/nodes are required, say so plainly.

Tool truthfulness (non-negotiable):
- A ```tool fence is a REQUEST, not a result. Until the server returns a `tool_completed` (for an audited write) or `tool_proposal_created` (for a change needing approval), nothing has been applied.
- NEVER claim a change is done ("I've added / created / updated / deleted / saved …") unless the server has returned a tool result proving it. A mutation proposal is a preview the user must approve — say "I've proposed …" or "I can add …", never "I added …".
- If a read tool failed or was blocked, say plainly what you could not check. Do not claim you verified something you did not.
- The studio surfaces a visible correction to the creator if you stream a success claim that no tool result backs. State only what the evidence supports.
"""


class SetupPromptSegment(BaseModel):
    start: float = 0.0
    length: float = 5.0
    text: str = ""


class SetupSfxClip(BaseModel):
    ref: str
    start: float = 0.0
    length: float = 1.0
    label: str = "SFX"


class SceneSetupProposal(BaseModel):
    """Assistant-proposed scene configuration (user must confirm before apply)."""

    summary: str = ""
    scene_name: Optional[str] = None
    engine: Optional[Literal["ltx", "wan", "fal_seedance", "fal_kling", "fal_veo", "fal_runway"]] = None
    duration_sec: Optional[float] = None
    media_mode: Optional[Literal["image", "video"]] = None
    global_prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    preset: Optional[Literal["draft", "quality"]] = None
    prompt: Optional[str] = None
    prompt_segments: Optional[list[SetupPromptSegment]] = None
    image_slots: Optional[dict[str, Optional[str]]] = None
    audio_ref: Optional[str] = None
    sfx: Optional[list[SetupSfxClip]] = None


class ApplySetupResult(BaseModel):
    ok: bool = True
    applied: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    scene_id: str
    project_id: str


def build_context_block(
    project: dict[str, Any] | None,
    scene_id: str | None = None,
    director: dict[str, Any] | None = None,
) -> str:
    if not project:
        return "No project is open."
    lines = [
        f"Product: Adept UI Video Studio",
        f"Project: {project.get('name')}",
        f"Default engine: {project.get('engine_default')}",
        f"Resolution: {project.get('width')}x{project.get('height')} @ {project.get('fps')}fps",
        f"Preset: {project.get('preset')}",
        f"VRAM profile: {project.get('vram_gb', 32)} GB",
        f"Global prompt: {project.get('global_prompt') or '(empty)'}",
    ]
    assets = project.get("assets") or []
    if assets:
        lines.append("Assets (use these refs in SCENE_SETUP):")
        for a in assets:
            tag = a.get("tag") or ""
            tag_s = f"@{tag}" if tag else "(untagged)"
            lines.append(
                f"  - id={a.get('id')} tag={tag_s} kind={a.get('kind')} file={a.get('filename')}"
            )
    else:
        lines.append("Assets: (none yet — do not invent image/audio refs)")

    scenes = project.get("scenes") or []
    lines.append(f"Scenes: {len(scenes)}")
    selected = None
    for s in scenes:
        marker = ""
        if scene_id and s.get("id") == scene_id:
            selected = s
            marker = " [SELECTED — setup applies here]"
        lines.append(
            f"- Scene {s.get('index', 0) + 1}{marker}: {s.get('name')} | engine={s.get('engine')} | "
            f"{s.get('duration_sec')}s | prompt={s.get('prompt') or '(empty)'}"
        )
    if selected:
        lines.append(
            "Selected scene keyframes: "
            f"start={'yes' if selected.get('start_asset_id') else 'no'}, "
            f"middle={'yes' if selected.get('middle_asset_id') else 'no'}, "
            f"end={'yes' if selected.get('end_asset_id') else 'no'}, "
            f"lipsync={'on' if selected.get('lipsync_enabled') else 'off'}"
        )
    if director:
        lines.append(
            "Selected director: "
            f"media_mode={director.get('media_mode')}, "
            f"duration={director.get('duration_sec')}s, "
            f"prompt_segments={len(director.get('prompt_segments') or [])}, "
            f"audio_clips={len(director.get('audio_clips') or [])}, "
            f"sfx_clips={len(director.get('sfx_clips') or [])}"
        )
    return "\n".join(lines)


def extract_scene_setup(reply: str) -> SceneSetupProposal | None:
    if not reply:
        return None
    patterns = [
        r"```scene_setup\s*([\s\S]*?)```",
        r"```json\s*(\{\s*\"summary\"[\s\S]*?\})\s*```",
        r"SCENE_SETUP\s*```(?:json|scene_setup)?\s*([\s\S]*?)```",
    ]
    raw = None
    for pat in patterns:
        m = re.search(pat, reply, re.IGNORECASE)
        if m:
            raw = m.group(1).strip()
            break
    if not raw:
        # bare JSON object with summary + engine/prompt keys
        m = re.search(r"(\{\s*\"summary\"[\s\S]*\})", reply)
        if m:
            raw = m.group(1).strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return SceneSetupProposal.model_validate(data)
    except Exception:
        return None


def strip_scene_setup_blocks(reply: str) -> str:
    cleaned = re.sub(r"```scene_setup\s*[\s\S]*?```", "", reply, flags=re.IGNORECASE)
    cleaned = re.sub(r"SCENE_SETUP\s*", "", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def extract_suggested_prompt(reply: str) -> str | None:
    # Prefer prompt fences; skip scene_setup / JSON setup blobs
    for m in re.finditer(r"```(\w*)\s*([\s\S]*?)```", reply, re.IGNORECASE):
        lang = (m.group(1) or "").lower()
        text = m.group(2).strip()
        if lang in {"scene_setup", "json"} and text.startswith("{"):
            continue
        if lang in {"prompt", "text", ""} and text and not (text.startswith("{") and '"summary"' in text):
            return text
    labeled = re.search(r"(?im)^(?:prompt|suggested prompt)\s*:\s*(.+)$", reply)
    if labeled:
        return labeled.group(1).strip()
    return None


def resolve_asset_ref(ref: str | None, assets: list[dict[str, Any]], *, kind: str | None = None) -> str | None:
    if not ref or not str(ref).strip():
        return None
    key = str(ref).strip().lstrip("@").lower()
    candidates = assets
    if kind:
        candidates = [a for a in assets if a.get("kind") == kind] or assets
    for a in candidates:
        if str(a.get("id", "")).lower() == key:
            return a["id"]
    for a in candidates:
        tag = (a.get("tag") or "").lower()
        if tag and tag == key:
            return a["id"]
    for a in candidates:
        fn = (a.get("filename") or "").lower()
        if fn == key or fn.rsplit(".", 1)[0] == key:
            return a["id"]
    return None


def apply_scene_setup(
    *,
    project: Any,
    scene: Any,
    setup: SceneSetupProposal,
    assets: list[dict[str, Any]],
    director: DirectorTimeline | None = None,
) -> ApplySetupResult:
    """Mutate project/scene ORM objects and director; caller commits."""
    applied: list[str] = []
    warnings: list[str] = []

    if setup.global_prompt is not None:
        project.global_prompt = setup.global_prompt
        applied.append("global_prompt")
    if setup.negative_prompt is not None:
        project.negative_prompt = setup.negative_prompt
        applied.append("negative_prompt")
    if setup.preset is not None:
        project.preset = setup.preset
        applied.append(f"preset={setup.preset}")

    if setup.scene_name:
        scene.name = setup.scene_name.strip()
        applied.append(f"scene_name={scene.name}")
    if setup.engine:
        scene.engine = setup.engine
        applied.append(f"engine={setup.engine}")

    if director is None:
        if scene.director_json and str(scene.director_json).strip():
            director = parse_director_timeline(
                scene.director_json,
                fallback_duration=scene.duration_sec,
                fallback_prompt=scene.prompt or "",
            )
        else:
            director = migrate_scene_to_director(
                duration_sec=scene.duration_sec,
                prompt=scene.prompt or "",
                start_asset_id=scene.start_asset_id,
                middle_asset_id=scene.middle_asset_id,
                end_asset_id=scene.end_asset_id,
                audio_asset_id=scene.audio_asset_id,
                lipsync_tracks_json=scene.lipsync_tracks_json,
            )

    duration = float(setup.duration_sec) if setup.duration_sec is not None else float(director.duration_sec)
    duration = max(1.0, min(30.0, duration))
    if setup.duration_sec is not None:
        director.duration_sec = duration
        applied.append(f"duration={duration}s")

    if setup.media_mode:
        director.media_mode = setup.media_mode
        applied.append(f"media_mode={setup.media_mode}")
        if setup.media_mode == "video" and not director.video_clips:
            director.video_clips = [
                TimelineClip(start=0.0, length=duration, label="Video", asset_id=None)
            ]

    # Prompts
    if setup.prompt_segments:
        director.prompt_segments = [
            PromptSegment(start=s.start, length=s.length or duration, text=s.text)
            for s in setup.prompt_segments
        ]
        applied.append(f"prompt_segments={len(director.prompt_segments)}")
    elif setup.prompt is not None:
        director.prompt_segments = [PromptSegment(start=0.0, length=duration, text=setup.prompt)]
        applied.append("prompt")

    # Image slots
    if setup.image_slots:
        role_map = {"start": "start", "middle": "middle", "end": "end"}
        if not director.image_clips:
            director.image_clips = DirectorTimeline.default(duration).image_clips
        for role, ref in setup.image_slots.items():
            role_l = role_map.get(str(role).lower())
            if not role_l:
                continue
            clip = next((c for c in director.image_clips if c.role == role_l), None)
            if clip is None:
                clip = ImageClip(role=role_l, start=0.0, length=duration / 3, label=role_l.title())
                director.image_clips.append(clip)
            if ref is None or str(ref).strip().lower() in {"", "null", "none"}:
                clip.asset_id = None
                applied.append(f"image_{role_l}=cleared")
                continue
            aid = resolve_asset_ref(str(ref), assets, kind="image")
            if not aid:
                warnings.append(f"Could not resolve image slot {role_l} ref '{ref}'")
            else:
                clip.asset_id = aid
                applied.append(f"image_{role_l}={ref}")

    # Audio
    if setup.audio_ref is not None:
        if str(setup.audio_ref).strip().lower() in {"", "null", "none"}:
            director.audio_clips = []
            applied.append("audio=cleared")
        else:
            aid = resolve_asset_ref(setup.audio_ref, assets, kind="audio")
            if not aid:
                warnings.append(f"Could not resolve audio_ref '{setup.audio_ref}'")
            else:
                director.audio_clips = [
                    TimelineClip(asset_id=aid, start=0.0, length=duration, label="Audio")
                ]
                applied.append(f"audio={setup.audio_ref}")

    # SFX
    if setup.sfx is not None:
        clips: list[TimelineClip] = []
        for item in setup.sfx:
            aid = resolve_asset_ref(item.ref, assets, kind="audio")
            if not aid:
                warnings.append(f"Could not resolve SFX ref '{item.ref}'")
                continue
            clips.append(
                TimelineClip(
                    asset_id=aid,
                    start=max(0.0, item.start),
                    length=max(0.2, item.length),
                    label=item.label or "SFX",
                )
            )
        director.sfx_clips = clips
        applied.append(f"sfx={len(clips)}")

    legacy = sync_legacy_fields_from_director(director)
    for k, v in legacy.items():
        setattr(scene, k, v)
    scene.director_json = dumps_director_timeline_preserving_embedded(director, scene.director_json)

    if not applied:
        warnings.append("Nothing to apply — proposal had no actionable fields")

    return ApplySetupResult(
        ok=True,
        applied=applied,
        warnings=warnings,
        scene_id=scene.id,
        project_id=project.id,
    )


async def ollama_reachable() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{settings.ollama_url.rstrip('/')}/api/tags")
            return r.status_code == 200
    except Exception:
        return False


async def list_ollama_models() -> list[str]:
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.get(f"{settings.ollama_url.rstrip('/')}/api/tags")
        r.raise_for_status()
        data = r.json()
    return [m.get("name", "") for m in data.get("models", []) if m.get("name")]


async def chat_ollama(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    project_context: str = "",
) -> str:
    model_name = model or settings.ollama_model
    system = SYSTEM_PROMPT
    if project_context.strip():
        system += "\n\nCurrent studio context:\n" + project_context.strip()

    payload = {
        "model": model_name,
        "stream": False,
        "messages": [{"role": "system", "content": system}, *messages],
        "options": {"temperature": 0.55},
    }
    async with httpx.AsyncClient(timeout=settings.ollama_timeout_sec) as client:
        r = await client.post(f"{settings.ollama_url.rstrip('/')}/api/chat", json=payload)
        if r.status_code >= 400:
            raise RuntimeError(f"Ollama error ({r.status_code}): {r.text[:800]}")
        data = r.json()
    message = data.get("message") or {}
    content = message.get("content") or data.get("response") or ""
    if not content.strip():
        raise RuntimeError("Ollama returned an empty response")
    return content.strip()
