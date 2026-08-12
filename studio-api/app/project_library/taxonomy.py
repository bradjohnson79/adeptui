"""Canonical Studio Project Library taxonomy — virtual system folders + entity templates.

System folders are derived from this module at runtime. They are NOT persisted as empty DB
rows per project. Only custom / entity folders are stored in project settings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


SYSTEM_FOLDER_PREFIX = "sys:"


@dataclass(frozen=True)
class TaxonomyNode:
    system_key: str
    display_name: str
    children: tuple["TaxonomyNode", ...] = ()
    entity_container: bool = False
    entity_subfolder: bool = False
    renamable: bool = False
    deletable: bool = False


def system_folder_id(system_key: str) -> str:
    return f"{SYSTEM_FOLDER_PREFIX}{system_key}"


def is_system_folder_id(folder_id: str) -> bool:
    return folder_id.startswith(SYSTEM_FOLDER_PREFIX)


def system_key_from_folder_id(folder_id: str) -> Optional[str]:
    if is_system_folder_id(folder_id):
        return folder_id[len(SYSTEM_FOLDER_PREFIX) :]
    return None


# ---------------------------------------------------------------------------
# Canonical tree (matches M3.0j Co-Director library map)
# ---------------------------------------------------------------------------

TAXONOMY_ROOT = TaxonomyNode(
    system_key="root",
    display_name="Project",
    children=(
        TaxonomyNode(
            system_key="video",
            display_name="Video",
            children=(
                TaxonomyNode("video.generated", "Generated"),
                TaxonomyNode("video.imported", "Imported"),
                TaxonomyNode("video.lipsync", "Lip Sync"),
                TaxonomyNode("video.renders", "Renders"),
            ),
        ),
        TaxonomyNode(
            system_key="audio",
            display_name="Audio",
            children=(
                TaxonomyNode("audio.music", "Music"),
                TaxonomyNode("audio.music_track", "Music Track"),
                TaxonomyNode("audio.music_loop", "Music Loop"),
                TaxonomyNode("audio.music_stem", "Music Stem"),
                TaxonomyNode("audio.sfx", "SFX"),
                TaxonomyNode("audio.foley", "Foley"),
                TaxonomyNode("audio.reaction", "Reaction"),
                TaxonomyNode("audio.sound_effect", "Sound Effect"),
                TaxonomyNode("audio.transition", "Transition"),
                TaxonomyNode("audio.dialogue", "Dialogue"),
                TaxonomyNode("audio.ambience", "Ambience"),
                TaxonomyNode("audio.room_tone", "Room Tone"),
                TaxonomyNode("audio.voice_references", "Voice References"),
            ),
        ),
        TaxonomyNode("storyboards", "Storyboards"),
        TaxonomyNode(
            system_key="characters",
            display_name="Characters",
            entity_container=True,
            children=(
                TaxonomyNode("characters.references", "References", entity_subfolder=True),
                TaxonomyNode("characters.identity_references", "Identity References", entity_subfolder=True),
                TaxonomyNode("characters.turnarounds", "Turnarounds", entity_subfolder=True),
                TaxonomyNode("characters.closeups", "Close-Ups", entity_subfolder=True),
                TaxonomyNode("characters.poses", "Poses", entity_subfolder=True),
                TaxonomyNode("characters.expressions", "Expressions", entity_subfolder=True),
                TaxonomyNode("characters.skin", "Skin", entity_subfolder=True),
                TaxonomyNode("characters.hair", "Hair", entity_subfolder=True),
                TaxonomyNode("characters.wardrobe", "Wardrobe", entity_subfolder=True),
                TaxonomyNode("characters.props", "Props", entity_subfolder=True),
                TaxonomyNode("characters.voice_references", "Voice References", entity_subfolder=True),
                TaxonomyNode("characters.voice_previews", "Voice Previews", entity_subfolder=True),
                TaxonomyNode("characters.dialogue", "Dialogue", entity_subfolder=True),
                TaxonomyNode("characters.lipsync", "Lipsync", entity_subfolder=True),
                TaxonomyNode(
                    "characters.three_d",
                    "3D (Coming in Version 1.2)",
                    entity_subfolder=True,
                ),
                TaxonomyNode("characters.voice", "Voice", entity_subfolder=True),
            ),
        ),
        TaxonomyNode(
            system_key="props",
            display_name="Props",
            entity_container=True,
            children=(
                TaxonomyNode("props.generated", "Generated", entity_subfolder=True),
                TaxonomyNode("props.references", "References", entity_subfolder=True),
                TaxonomyNode("props.variations", "Variations", entity_subfolder=True),
                TaxonomyNode(
                    "props.three_d",
                    "3D (Coming in Version 1.2)",
                    entity_subfolder=True,
                ),
            ),
        ),
        TaxonomyNode(
            system_key="scenes",
            display_name="Scenes",
            entity_container=True,
            children=(
                TaxonomyNode("scenes.backgrounds", "Backgrounds", entity_subfolder=True),
                TaxonomyNode(
                    "scenes.panoramas_360",
                    "360 Environments",
                    entity_subfolder=True,
                ),
                TaxonomyNode("scenes.locations", "Locations", entity_subfolder=True),
                TaxonomyNode("scenes.sets", "Sets", entity_subfolder=True),
                TaxonomyNode("scenes.lighting", "Lighting", entity_subfolder=True),
                TaxonomyNode(
                    "scenes.three_d",
                    "3D (Coming in Version 1.2)",
                    entity_subfolder=True,
                ),
            ),
        ),
        TaxonomyNode(
            system_key="three_d",
            display_name="3D (Coming in Version 1.2)",
            children=(
                TaxonomyNode("three_d.characters", "Characters"),
                TaxonomyNode("three_d.props", "Props"),
                TaxonomyNode("three_d.environments", "Environments"),
                TaxonomyNode("three_d.hdri", "HDRI"),
                TaxonomyNode("three_d.textures", "Textures"),
            ),
        ),
        TaxonomyNode("scripts", "Scripts"),
        TaxonomyNode("production_bible", "Production Bible"),
        TaxonomyNode(
            system_key="templates_presets",
            display_name="Templates and Presets",
            children=(
                TaxonomyNode(
                    system_key="templates_presets.generation_templates",
                    display_name="Generation Templates",
                    children=(
                        TaxonomyNode("templates_presets.generation_templates.image", "Image"),
                        TaxonomyNode("templates_presets.generation_templates.video", "Video"),
                        TaxonomyNode("templates_presets.generation_templates.audio", "Audio"),
                        TaxonomyNode("templates_presets.generation_templates.lipsync", "Lip Sync"),
                        TaxonomyNode(
                            "templates_presets.generation_templates.three_d",
                            "3D (Coming in Version 1.2)",
                        ),
                        TaxonomyNode(
                            "templates_presets.generation_templates.production_workflows",
                            "Production Workflows",
                        ),
                    ),
                ),
                TaxonomyNode(
                    system_key="templates_presets.camera_presets",
                    display_name="Camera Presets",
                    children=(
                        TaxonomyNode("templates_presets.camera_presets.framing", "Framing"),
                        TaxonomyNode("templates_presets.camera_presets.lens", "Lens"),
                        TaxonomyNode("templates_presets.camera_presets.movement", "Movement"),
                        TaxonomyNode(
                            "templates_presets.camera_presets.grammar_packs",
                            "Grammar Packs",
                        ),
                    ),
                ),
                TaxonomyNode(
                    system_key="templates_presets.lighting_presets",
                    display_name="Lighting Presets",
                    children=(
                        TaxonomyNode("templates_presets.lighting_presets.interior", "Interior"),
                        TaxonomyNode("templates_presets.lighting_presets.exterior", "Exterior"),
                        TaxonomyNode("templates_presets.lighting_presets.character", "Character"),
                        TaxonomyNode(
                            "templates_presets.lighting_presets.environment",
                            "Environment",
                        ),
                    ),
                ),
                TaxonomyNode(
                    system_key="templates_presets.color_presets",
                    display_name="Color Presets",
                    children=(
                        TaxonomyNode(
                            "templates_presets.color_presets.generation_looks",
                            "Generation Looks",
                        ),
                        TaxonomyNode("templates_presets.color_presets.correction", "Correction"),
                        TaxonomyNode(
                            "templates_presets.color_presets.creative_grades",
                            "Creative Grades",
                        ),
                        TaxonomyNode("templates_presets.color_presets.delivery", "Delivery"),
                    ),
                ),
                TaxonomyNode("templates_presets.look_presets", "Look Presets"),
            ),
        ),
        TaxonomyNode(
            system_key="exports",
            display_name="Exports",
            children=(
                TaxonomyNode("exports.drafts", "Drafts"),
                TaxonomyNode("exports.final", "Final"),
            ),
        ),
        TaxonomyNode("miscellaneous", "Miscellaneous", renamable=False, deletable=False),
    ),
)


@dataclass
class _IndexEntry:
    node: TaxonomyNode
    display_path: str
    parent_system_key: Optional[str]


def _build_index(
    node: TaxonomyNode,
    parent_path: str = "",
    parent_key: Optional[str] = None,
    index: Optional[dict[str, _IndexEntry]] = None,
) -> dict[str, _IndexEntry]:
    out = index if index is not None else {}
    path = f"{parent_path}/{node.display_name}" if parent_path else node.display_name
    out[node.system_key] = _IndexEntry(node=node, display_path=path, parent_system_key=parent_key)
    for child in node.children:
        _build_index(child, path, node.system_key, out)
    return out


SYSTEM_INDEX: dict[str, _IndexEntry] = _build_index(TAXONOMY_ROOT)


def all_system_keys() -> tuple[str, ...]:
    return tuple(k for k in SYSTEM_INDEX if k != "root")


def get_system_node(system_key: str) -> Optional[TaxonomyNode]:
    entry = SYSTEM_INDEX.get(system_key)
    return entry.node if entry else None


def display_path_for_system_key(system_key: str) -> str:
    entry = SYSTEM_INDEX.get(system_key)
    return entry.display_path if entry else system_key


def parent_system_key(system_key: str) -> Optional[str]:
    entry = SYSTEM_INDEX.get(system_key)
    return entry.parent_system_key if entry else None


def entity_subfolder_keys(entity_root: str) -> tuple[str, ...]:
    node = get_system_node(entity_root)
    if not node:
        return ()
    return tuple(c.system_key for c in node.children if c.entity_subfolder)


ENTITY_ROOTS: dict[str, str] = {
    "character": "characters",
    "prop": "props",
    "scene": "scenes",
}

ENTITY_ID_FIELDS: dict[str, str] = {
    "character": "characterId",
    "prop": "propId",
    "scene": "sceneId",
}

# 3D import extensions — USD is explicitly unsupported in M3.0j scope.
SUPPORTED_3D_EXTENSIONS: frozenset[str] = frozenset({".fbx", ".obj", ".glb", ".gltf"})
UNSUPPORTED_3D_EXTENSIONS: frozenset[str] = frozenset({".usd", ".usda", ".usdc", ".usdz"})
