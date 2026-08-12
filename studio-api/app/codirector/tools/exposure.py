"""Capability-scoped tool exposure (c2-routing architectural repair).

Today ``_tool_instructions()`` injects all ~485 tools into every system prompt.
This module performs deterministic, metadata-derived filtering so the model is
shown only the tools relevant to the current workspace surface + intent, while
always preserving a safe baseline of core project-state read tools.

Design constraints (from the c2-routing plan):

* Derive each tool's domain from existing metadata ONLY — tool_id namespace
  prefix, the ``capability`` field, and ``kind``. We never edit
  ``definitions.py`` (owned by another agent).
* Inputs: current workspace surface, capability readiness (capability -> bool),
  and intent text as a secondary expansion signal.
* ALWAYS include a safe baseline: core project-state read tools
  (project/scene/timeline/asset/job reads) so cross-system workflows never lose
  required context tools.
* When intent is ambiguous or spans systems, EXPAND deliberately (union of
  relevant domains) — never filter below the safe baseline.
* Unsupported systems expose nothing; any system moved into
  ``UNSUPPORTED_SYSTEMS`` is asserted to have no registered tools. MAGI is
  currently OPERATIONAL read-only (see ``handlers/magi.py``): its read tools are
  exposed only when the workspace surface is ``magi``/``magieditor`` or intent
  explicitly references MAGI.
* Deterministic: same inputs -> same exposed set. No lexical-only filtering.

The filtering is metadata-driven and conservative: when in doubt we include
rather than exclude, and the baseline is always present.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

from .registry import all_definitions


# --------------------------------------------------------------------------
# Domain derivation — tool_id namespace prefix -> domain.
# Ordered longest-prefix-first so e.g. "voice_performance.*" wins over "voice.*".
# --------------------------------------------------------------------------

_DOMAIN_BY_PREFIX: tuple[tuple[str, str], ...] = (
    ("voice_performance", "voice"),
    ("voice_environment", "voice"),
    ("voice", "voice"),
    ("character_creator", "character"),
    ("character", "character"),
    ("production_bible", "bible"),
    ("production_plan", "plan"),
    ("image_pipeline", "image_pipeline"),
    ("minimax_h3", "minimax"),
    ("posecraft", "posecraft"),
    ("spatial", "spatial"),
    ("script", "script"),
    ("setup", "setup"),
    ("runtime", "setup"),
    ("ers", "environment"),
    ("audio", "audio"),
    ("prompt", "prompt"),
    ("references", "references"),
    ("continuity", "continuity"),
    ("avatar", "avatar"),
    ("timeline", "timeline"),
    ("workspace", "workspace"),
    ("editor", "editor"),
    ("magi", "magi"),
    ("job", "generation"),
    ("asset", "asset"),
    ("scene", "scene"),
    ("project", "project"),
    ("system", "system"),
    ("hosted_providers", "system"),
    ("vision", "vision"),
)

# Tools whose tool_id does not use a dotted namespace (legacy snake_case). Map
# them by keyword so the baseline + bible + generation domains stay complete.
_LEGACY_DOMAIN_BY_KEYWORD: tuple[tuple[tuple[str, ...], str], ...] = (
    (("bible", "canon", "continuity_update", "reference_link", "visual_language",
      "production_decision", "director_decision"), "bible"),
    (("create_scene", "update_scene", "set_scene", "scene"), "scene"),
    (("create_draft_character_profile", "propose_character_update", "character"), "character"),
    (("generate", "render", "upscale", "background_remove", "chroma_key",
      "portrait_skin", "video_extend", "lipsync", "subtitle", "shot", "brand",
      "music", "sfx", "timeline_render", "batch_timeline", "voice_generate"), "generation"),
    (("vision_correction", "asset_bible_link", "vision_review"), "vision"),
    (("reference_set", "reference_binding", "reference_preset", "asset_library_assignment"), "references"),
    (("record_production_decision", "record_director_decision"), "bible"),
)


def derive_domain(tool_id: str, *, capability: str = "project", kind: str = "read") -> str:
    """Return the domain string for a tool, derived from metadata only.

    Deterministic and total: every registered tool maps to exactly one domain.
    """

    tid = tool_id.lower()
    for prefix, domain in _DOMAIN_BY_PREFIX:
        if tid == prefix or tid.startswith(prefix + ".") or tid.startswith(prefix + "_"):
            return domain
    for keywords, domain in _LEGACY_DOMAIN_BY_KEYWORD:
        if any(kw in tid for kw in keywords):
            return domain
    # Fallback by capability (coarse): bible -> bible, references -> references,
    # vision -> vision, comfyui/preview_engine -> generation, library -> library,
    # provider -> system, project -> project.
    cap = (capability or "").lower()
    if cap == "bible":
        return "bible"
    if cap == "references":
        return "references"
    if cap == "vision":
        return "vision"
    if cap in ("comfyui", "preview_engine"):
        return "generation"
    if cap == "library":
        return "library"
    if cap == "provider":
        return "system"
    if cap == "source_manager":
        return "setup"
    return "project"


# --------------------------------------------------------------------------
# Safe baseline — core project-state read tools always exposed.
# These are the read tools a cross-system workflow needs regardless of the
# active surface, so context lookups never break.
# --------------------------------------------------------------------------

_BASELINE_READ_TOOL_IDS: frozenset[str] = frozenset(
    {
        "get_project_profile",
        "get_project_status",
        "list_scenes",
        "get_scene",
        "get_active_scene",
        "scene.list",
        "scene.get",
        "project.get_summary",
        "project.list_blockers",
        "asset.list",
        "asset.get",
        "asset.search",
        "job.list",
        "job.get",
        "workspace.get_active_context",
        "system.list_capabilities",
        "get_provider_health",
        "get_selected_model",
    }
)


# --------------------------------------------------------------------------
# Intent -> domain expansion signals (secondary). Keyword-based but only ever
# EXPANDS the selected set; the baseline + workspace surface drive the core.
# --------------------------------------------------------------------------

_INTENT_DOMAIN_SIGNALS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("timeline", "batch", "clip", "playhead", "track", "lipsync", "inpaint"), "timeline"),
    (("voice", "dialogue", "speech", "performance", "take", "voiceover"), "voice"),
    (("bible", "canon", "continuity", "character update", "reference link", "lore"), "bible"),
    (("character", "profile", "wardrobe", "voice profile", "visual identity"), "character"),
    (("scene", "shot", "storyboard", "setup"), "scene"),
    (("image", "render", "generate", "upscale", "txt2vid", "ltx", "wan", "generation"), "generation"),
    (("audio", "music", "sfx", "ambience", "sound"), "audio"),
    (("spatial", "map", "360", "panorama"), "spatial"),
    (("script", "outline", "beat", "dialogue line"), "script"),
    (("setup", "install", "runtime", "docker", "component", "comfy"), "setup"),
    (("pose", "posecraft", "figure"), "posecraft"),
    (("vision", "review", "validation"), "vision"),
    (("reference", "binding"), "references"),
    (("plan", "production plan", "draft plan"), "plan"),
    (("prompt", "enhance", "benchmark"), "prompt"),
    (("environment", "ers", "sheet"), "environment"),
    (("minimax", "h3", "ltx fallback"), "minimax"),
    (("library", "folder", "storage"), "library"),
    (("avatar", "lip-sync"), "avatar"),
    (("magi", "magieditor", "magi sequence"), "magi"),
)


def _domains_from_intent(intent: Optional[str]) -> set[str]:
    if not intent:
        return set()
    lowered = intent.lower()
    out: set[str] = set()
    for keywords, domain in _INTENT_DOMAIN_SIGNALS:
        if any(kw in lowered for kw in keywords):
            out.add(domain)
    return out


# Workspace surface -> primary domain. The surface is the UI tab the creator is
# on; it is the strongest signal for which tools are relevant.
_SURFACE_DOMAIN: dict[str, str] = {
    "timeline": "timeline",
    "voice": "voice",
    "bible": "bible",
    "character": "character",
    "scene": "scene",
    "library": "library",
    "setup": "setup",
    "posecraft": "posecraft",
    "image": "image_pipeline",
    "minimax": "minimax",
    "environment": "environment",
    "audio": "audio",
    "script": "script",
    "vision": "vision",
    "references": "references",
    "plan": "plan",
    "prompt": "prompt",
    "avatar": "avatar",
    "generation": "generation",
    "director": "timeline",
    "storyboard": "scene",
    "magi": "magi",
    "magieditor": "magi",
    "chat": "project",
    "default": "project",
}


def _domains_from_surface(surface: Optional[str]) -> set[str]:
    if not surface:
        return set()
    key = surface.strip().lower()
    primary = _SURFACE_DOMAIN.get(key)
    return {primary} if primary else set()


# --------------------------------------------------------------------------
# Unsupported systems must never expose tools. When a system's tools are
# ready they are removed from this set; the assertion then guarantees every
# registered tool derives to a supported domain.
# --------------------------------------------------------------------------

UNSUPPORTED_SYSTEMS: frozenset[str] = frozenset()


def assert_unsupported_systems_have_no_tools() -> None:
    """Assert no registered tool belongs to an unsupported system.

    Deterministic invariant: any system listed in ``UNSUPPORTED_SYSTEMS`` has no
    tools in the registry. If a tool were ever registered whose derived domain
    matches an unsupported system, this raises at import/call time so the
    exposure layer can never silently surface unsupported tools. MAGI is
    Operational (read-only) — it is NOT listed here, and its read tools are
    capability-scoped (see ``expose``).
    """

    for definition in all_definitions():
        domain = derive_domain(
            definition.tool_id, capability=definition.capability, kind=definition.kind
        )
        if domain in UNSUPPORTED_SYSTEMS:
            raise RuntimeError(
                f"Tool '{definition.tool_id}' derived to unsupported system domain "
                f"'{domain}'; unsupported systems must never expose tools."
            )


def _is_baseline(tool_id: str) -> bool:
    return tool_id in _BASELINE_READ_TOOL_IDS


def expose(
    *,
    workspace_surface: Optional[str] = None,
    capability_readiness: Optional[dict[str, bool]] = None,
    intent: Optional[str] = None,
    definitions: Optional[Iterable] = None,
) -> set[str]:
    """Return the deterministic set of tool_ids to expose to the model.

    Inputs:
        workspace_surface: current UI surface (e.g. "timeline", "voice",
            "bible", "scene"). Strongest signal.
        capability_readiness: capability key -> ready bool. Used to keep a
            domain's tools only when its capability is ready; missing/unknown
            capabilities default to ready=True (conservative: include).
        intent: free-text intent (secondary expansion signal). When it spans
            multiple domains, the union is included.

    Guarantees:
        * The safe baseline is ALWAYS present.
        * The set never drops below the baseline.
        * Ambiguous / multi-system intent EXPANDS (union), never restricts.
        * Deterministic: same inputs -> same set.
    """

    assert_unsupported_systems_have_no_tools()

    defs = list(definitions) if definitions is not None else list(all_definitions())

    surface_domains = _domains_from_surface(workspace_surface)
    intent_domains = _domains_from_intent(intent)
    # Union: when intent spans systems or surface + intent differ, expand.
    selected_domains = surface_domains | intent_domains
    if not selected_domains:
        # No signal at all: expose the baseline + project/scene/system reads
        # (the safe default for a generic chat turn).
        selected_domains = {"project", "scene", "system"}

    readiness = capability_readiness or {}

    def _domain_ready(domain: str) -> bool:
        # Map a few domains to their capability key for readiness gating. Unknown
        # / unmapped domains default to ready (conservative: include).
        cap_map = {
            "bible": "bible",
            "references": "references",
            "vision": "vision",
            "generation": "comfyui",
            "image_pipeline": "comfyui",
            "setup": "source_manager",
            "library": "library",
            "system": "provider",
        }
        cap = cap_map.get(domain)
        if cap is None:
            return True
        return bool(readiness.get(cap, True))

    exposed: set[str] = set(_BASELINE_READ_TOOL_IDS)
    for definition in defs:
        domain = derive_domain(
            definition.tool_id, capability=definition.capability, kind=definition.kind
        )
        if domain in selected_domains and _domain_ready(domain):
            exposed.add(definition.tool_id)
    # Baseline tools are included even if their domain was not selected / not
    # ready — they are the never-remove floor.
    exposed |= _BASELINE_READ_TOOL_IDS
    return exposed


def expose_ordered(
    *,
    workspace_surface: Optional[str] = None,
    capability_readiness: Optional[dict[str, bool]] = None,
    intent: Optional[str] = None,
    definitions: Optional[Iterable] = None,
) -> list[str]:
    """Return exposed tool_ids in stable registry order (deterministic)."""

    selected = expose(
        workspace_surface=workspace_surface,
        capability_readiness=capability_readiness,
        intent=intent,
        definitions=definitions,
    )
    defs = list(definitions) if definitions is not None else list(all_definitions())
    return [d.tool_id for d in defs if d.tool_id in selected]
