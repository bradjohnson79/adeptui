"""Minimal system creative-item stubs so resolve/import/export have real shapes.

Full generation/camera/lighting/color catalogs land in M3.1b–f.
"""

from __future__ import annotations

from typing import Any

from ..kinds import LIBRARY_KEY_BY_KIND
from ..schema import CreativeItem


def _item(
    *,
    slug: str,
    kind: str,
    name: str,
    category: str,
    subcategory: str = "",
    intent: dict[str, Any] | None = None,
    library_key: str = "",
) -> CreativeItem:
    key = library_key or LIBRARY_KEY_BY_KIND.get(kind, "templates_presets")
    return CreativeItem(
        id=f"sys:{slug}",
        kind=kind,
        name=name,
        slug=slug,
        scope="system",
        category=category,
        subcategory=subcategory,
        description=f"System stub: {name}",
        intent=intent or {"stub": True},
        provider_mappings={},
        compatibility={"providers": ["ltx", "wan"], "status": "stub"},
        lifecycle="approved",
        approval_state="approved",
        version=1,
        origin="builtin",
        visibility="shared",
        library_system_key=key,
        tags=["system", "stub"],
    )


SYSTEM_CREATIVE_ITEMS: tuple[CreativeItem, ...] = (
    _item(
        slug="dialogue_close_up",
        kind="generation_template",
        name="Dialogue Close-Up",
        category="video",
        intent={
            "productionType": "video",
            "promptStructure": "dialogue close-up coverage",
            "aspectRatio": "16:9",
            "durationSec": 5,
            "referenceSlots": ["character_identity", "wardrobe"],
            "continuity": ["identity", "wardrobe", "lighting"],
            "outputFolder": "video.generated",
        },
        library_key="templates_presets.generation_templates.video",
    ),
    _item(
        slug="establishing_shot",
        kind="generation_template",
        name="Establishing Shot",
        category="video",
        intent={"productionType": "video", "promptStructure": "wide establishing"},
        library_key="templates_presets.generation_templates.video",
    ),
    _item(
        slug="character_identity_sheet",
        kind="generation_template",
        name="Character Identity Sheet",
        category="image",
        intent={"productionType": "image", "promptStructure": "character identity sheet"},
        library_key="templates_presets.generation_templates.image",
    ),
    _item(
        slug="character_turnaround",
        kind="generation_template",
        name="Character Turnaround",
        category="image",
        intent={"productionType": "image", "promptStructure": "character turnaround"},
        library_key="templates_presets.generation_templates.image",
    ),
    _item(
        slug="music_cue",
        kind="generation_template",
        name="Music Cue",
        category="audio",
        intent={"productionType": "audio", "role": "music"},
        library_key="templates_presets.generation_templates.audio",
    ),
    _item(
        slug="lipsync_dialogue_shot",
        kind="generation_template",
        name="Lip-Sync Dialogue Shot",
        category="lipsync",
        intent={"productionType": "lipsync"},
        library_key="templates_presets.generation_templates.lipsync",
    ),
    _item(
        slug="lens_85mm_emotional",
        kind="camera_preset",
        name="85mm Emotional Close-Up",
        category="lens",
        intent={
            "focalLength": 85,
            "aperture": 2.0,
            "depthOfField": "shallow",
            "subjectDistance": "close",
            "compression": "high",
            "intendedUse": ["emotional close-up", "reaction shot"],
        },
        library_key="templates_presets.camera_presets.lens",
    ),
    _item(
        slug="framing_close_up",
        kind="camera_preset",
        name="Close-Up",
        category="framing",
        intent={"shotSize": "close_up"},
        library_key="templates_presets.camera_presets.framing",
    ),
    _item(
        slug="motion_slow_push_in",
        kind="camera_preset",
        name="Slow Push-In",
        category="movement",
        intent={
            "movement": "push_in",
            "speed": "slow",
            "stabilization": "high",
            "subjectTracking": True,
        },
        library_key="templates_presets.camera_presets.movement",
    ),
    _item(
        slug="grammar_1990s_tv_drama",
        kind="camera_preset",
        name="1990s Television Drama",
        category="grammar_packs",
        intent={
            "movement": "restrained",
            "coverage": ["medium", "wide", "close_up", "reaction"],
            "handheld": "minimal",
            "continuityFirst": True,
        },
        library_key="templates_presets.camera_presets.grammar_packs",
    ),
    _item(
        slug="grammar_episodic_drama",
        kind="camera_preset",
        name="Episodic Drama Grammar",
        category="grammar_packs",
        intent={"movement": "restrained", "coverage": ["medium", "wide", "close_up"]},
        library_key="templates_presets.camera_presets.grammar_packs",
    ),
    _item(
        slug="lighting_soft_low_key_interior",
        kind="lighting_preset",
        name="Soft Low-Key Interior",
        category="interior",
        intent={
            "keyDirection": "camera-left",
            "keyTemperature": 4800,
            "fillRatio": "4:1",
            "shadowSoftness": "medium",
            "contrast": "high",
            "mood": "controlled tension",
        },
        library_key="templates_presets.lighting_presets.interior",
    ),
    _item(
        slug="lighting_fluorescent_facility",
        kind="lighting_preset",
        name="Fluorescent Facility",
        category="interior",
        intent={"mood": "clinical", "keyTemperature": 4200, "contrast": "moderate"},
        library_key="templates_presets.lighting_presets.interior",
    ),
    _item(
        slug="color_muted_1990s_tv",
        kind="color_preset",
        name="Muted 1990s Television Drama",
        category="generation_looks",
        intent={"look": "muted_drama", "era": "1990s_tv", "skinProtection": True},
        library_key="templates_presets.color_presets.generation_looks",
    ),
    _item(
        slug="color_web_sdr",
        kind="color_preset",
        name="Web SDR",
        category="delivery",
        intent={"delivery": "web_sdr", "colorSpace": "rec709"},
        library_key="templates_presets.color_presets.delivery",
    ),
    _item(
        slug="look_dreamweaver_research",
        kind="look_preset",
        name="Dreamweaver — 1990s Research Facility",
        category="combined",
        intent={
            "cameraRefs": ["grammar_1990s_tv_drama", "lens_85mm_emotional"],
            "lightingRefs": ["lighting_fluorescent_facility"],
            "colorRefs": ["color_muted_1990s_tv"],
        },
        library_key="templates_presets.look_presets",
    ),
    _item(
        slug="episode_package",
        kind="generation_template",
        name="Episode Package",
        category="production_workflows",
        intent={"workflow": "episode_package"},
        library_key="templates_presets.generation_templates.production_workflows",
    ),
    _item(
        slug="opening_titles",
        kind="generation_template",
        name="Opening Titles",
        category="production_workflows",
        intent={"workflow": "opening_titles"},
        library_key="templates_presets.generation_templates.production_workflows",
    ),
    _item(
        slug="product_hero_shot",
        kind="generation_template",
        name="Product Hero Shot",
        category="video",
        intent={"productionType": "video", "promptStructure": "product hero"},
        library_key="templates_presets.generation_templates.video",
    ),
    _item(
        slug="performance_shot",
        kind="generation_template",
        name="Performance Shot",
        category="video",
        intent={"productionType": "video", "promptStructure": "performance"},
        library_key="templates_presets.generation_templates.video",
    ),
    _item(
        slug="cinematic_establishing",
        kind="generation_template",
        name="Cinematic Establishing Shot",
        category="video",
        intent={"productionType": "video", "promptStructure": "cinematic establishing"},
        library_key="templates_presets.generation_templates.video",
    ),
    _item(
        slug="logo_reveal",
        kind="generation_template",
        name="Logo Reveal",
        category="video",
        intent={"productionType": "video", "promptStructure": "logo reveal"},
        library_key="templates_presets.generation_templates.video",
    ),
    _item(
        slug="title_card",
        kind="generation_template",
        name="Title Card",
        category="video",
        intent={"productionType": "video", "promptStructure": "title card"},
        library_key="templates_presets.generation_templates.video",
    ),
    _item(
        slug="storyboard_panel",
        kind="generation_template",
        name="Storyboard Panel",
        category="image",
        intent={"productionType": "image", "promptStructure": "storyboard panel"},
        library_key="templates_presets.generation_templates.image",
    ),
    _item(
        slug="expression_sheet",
        kind="generation_template",
        name="Expression Sheet",
        category="image",
        intent={"productionType": "image", "promptStructure": "expression sheet"},
        library_key="templates_presets.generation_templates.image",
    ),
    _item(
        slug="vertical_avatar",
        kind="generation_template",
        name="Vertical Avatar",
        category="lipsync",
        intent={"productionType": "lipsync", "aspectRatio": "9:16"},
        library_key="templates_presets.generation_templates.lipsync",
    ),
)


def system_items_by_slug() -> dict[str, CreativeItem]:
    return {item.slug: item for item in SYSTEM_CREATIVE_ITEMS}


def list_system_items(
    *,
    kind: str | None = None,
    category: str | None = None,
) -> list[CreativeItem]:
    items = list(SYSTEM_CREATIVE_ITEMS)
    if kind:
        items = [i for i in items if i.kind == kind]
    if category:
        items = [i for i in items if i.category == category]
    return items
