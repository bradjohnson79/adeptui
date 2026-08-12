"""Built-in Project Type definitions and primary selector catalog (M3.1a)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..schema import ProjectProfile, ProjectStructure, ProjectTypeDefinition


def _struct(**kwargs: bool) -> ProjectStructure:
    return ProjectStructure(**kwargs)


def _profile(
    slug: str,
    display: str,
    *,
    structure: ProjectStructure | None = None,
    defaults: dict[str, Any] | None = None,
    library: list[str] | None = None,
    templates: list[str] | None = None,
    camera: list[str] | None = None,
    lighting: list[str] | None = None,
    color: list[str] | None = None,
    looks: list[str] | None = None,
    bible: list[str] | None = None,
    cd: dict[str, Any] | None = None,
    audio: list[str] | None = None,
    delivery: list[str] | None = None,
    beats: list[str] | None = None,
    group: str = "",
    parent: str | None = None,
) -> ProjectProfile:
    return ProjectProfile(
        project_type=slug,
        display_name=display,
        structure=structure or _struct(),
        defaults=defaults
        or {
            "aspectRatio": "16:9",
            "frameRate": 24,
            "resolution": "1080p",
            "delivery": "web_sdr",
        },
        library_emphasis=library or ["Scenes", "Characters", "Scripts"],
        recommended_templates=templates or ["establishing_shot", "dialogue_close_up"],
        recommended_camera_presets=camera or ["grammar_episodic_drama", "framing_close_up"],
        recommended_lighting_presets=lighting or ["lighting_soft_low_key_interior"],
        recommended_color_presets=color or ["color_muted_1990s_tv", "color_web_sdr"],
        recommended_look_presets=looks or [],
        bible_sections=bible or ["project_profile", "character", "location", "visual_language"],
        co_director_context=cd or {"planningMode": "narrative"},
        audio_track_defaults=audio or ["dialogue", "music", "ambience"],
        delivery=delivery or ["web_sdr"],
        version=1,
        parent_selector=parent,
        group=group,
        beat_skeleton=beats or [],
    )


def _def(
    slug: str,
    display: str,
    profile: ProjectProfile,
    *,
    group: str = "",
    primary: bool = False,
    parent: str | None = None,
    subtypes: list[str] | None = None,
    traits: list[str] | None = None,
) -> ProjectTypeDefinition:
    return ProjectTypeDefinition(
        id=f"builtin:{slug}",
        slug=slug,
        display_name=display,
        group=group,
        is_builtin=True,
        parent_selector=parent,
        profile=profile,
        version=1,
        lifecycle="approved",
        origin="builtin",
        primary_selector=primary,
        subtypes=subtypes or [],
        trait_options=traits or [],
    )


_TRAILER_BEATS = [
    "Cold Open",
    "Hook",
    "World or premise reveal",
    "Character introduction",
    "Escalation",
    "Montage",
    "Music rise",
    "Climax",
    "Title reveal",
    "Release information",
    "Logo/end card",
]


def _build_catalog() -> dict[str, ProjectTypeDefinition]:
    items: list[ProjectTypeDefinition] = [
        _def(
            "feature_film",
            "Feature Film",
            _profile(
                "feature_film",
                "Feature Film",
                defaults={
                    "aspectRatio": "2.39:1",
                    "frameRate": 24,
                    "resolution": "1080p",
                    "delivery": "web_sdr",
                    "typicalDurationMin": 90,
                },
                library=["Scenes", "Characters", "Scripts", "Production Bible", "Storyboards"],
                templates=["establishing_shot", "dialogue_close_up", "character_identity_sheet"],
                group="film_narrative",
            ),
            group="film_narrative",
            primary=True,
        ),
        _def(
            "short_film",
            "Short Film",
            _profile(
                "short_film",
                "Short Film",
                defaults={
                    "aspectRatio": "16:9",
                    "frameRate": 24,
                    "resolution": "1080p",
                    "delivery": "web_sdr",
                    "cameraGrammar": "episodic_drama",
                    "productionEmphasis": ["scenes", "characters", "scripts", "storyboards", "continuity"],
                },
                library=["Scenes", "Characters", "Scripts", "Production Bible", "Storyboards"],
                templates=["establishing_shot", "dialogue_close_up", "storyboard_panel"],
                camera=["grammar_episodic_drama", "framing_close_up", "motion_slow_push_in"],
                group="film_narrative",
            ),
            group="film_narrative",
            primary=True,
        ),
        _def(
            "series",
            "Series",
            _profile(
                "series",
                "Series",
                structure=_struct(season_enabled=True, episode_enabled=True),
                defaults={
                    "aspectRatio": "16:9",
                    "frameRate": 24,
                    "resolution": "1080p",
                    "delivery": "web_sdr",
                    "cameraGrammar": "episodic_drama",
                },
                library=["Characters", "Scenes", "Scripts", "Production Bible"],
                templates=["episode_package", "dialogue_close_up", "opening_titles"],
                group="film_narrative",
            ),
            group="film_narrative",
            primary=True,
            subtypes=[
                "web_series",
                "television_episodic",
                "animated_series",
                "docuseries",
                "limited_series",
            ],
            traits=["animation", "educational", "vertical_derivatives"],
        ),
        _def(
            "web_series",
            "Web Series",
            _profile(
                "web_series",
                "Web Series",
                structure=_struct(season_enabled=True, episode_enabled=True),
                defaults={
                    "aspectRatio": "16:9",
                    "frameRate": 24,
                    "resolution": "1080p",
                    "delivery": "web_sdr",
                    "cameraGrammar": "episodic_drama",
                },
                library=["Characters", "Scenes", "Scripts", "Production Bible"],
                templates=["episode_package", "dialogue_close_up", "opening_titles"],
                camera=["grammar_episodic_drama"],
                group="film_narrative",
                parent="series",
            ),
            group="film_narrative",
            parent="series",
        ),
        _def(
            "television_episodic",
            "Television / Episodic Series",
            _profile(
                "television_episodic",
                "Television / Episodic Series",
                structure=_struct(season_enabled=True, episode_enabled=True),
                defaults={"aspectRatio": "16:9", "frameRate": 24, "resolution": "1080p"},
                library=["Characters", "Scenes", "Scripts", "Production Bible"],
                templates=["episode_package", "dialogue_close_up", "opening_titles"],
                parent="series",
                group="film_narrative",
            ),
            group="film_narrative",
            parent="series",
        ),
        _def(
            "animated_series",
            "Animated Series",
            _profile(
                "animated_series",
                "Animated Series",
                structure=_struct(season_enabled=True, episode_enabled=True),
                defaults={"aspectRatio": "16:9", "frameRate": 24},
                library=["Characters", "Storyboards", "Scripts"],
                templates=["character_turnaround", "expression_sheet", "storyboard_panel", "lipsync_dialogue_shot"],
                parent="series",
                group="film_narrative",
            ),
            group="film_narrative",
            parent="series",
        ),
        _def(
            "docuseries",
            "Docuseries",
            _profile(
                "docuseries",
                "Docuseries",
                structure=_struct(season_enabled=True, episode_enabled=True),
                defaults={"aspectRatio": "16:9", "frameRate": 24},
                library=["Scenes", "Scripts", "Production Bible"],
                templates=["establishing_shot", "dialogue_close_up"],
                parent="series",
                group="film_narrative",
            ),
            group="film_narrative",
            parent="series",
        ),
        _def(
            "limited_series",
            "Limited Series",
            _profile(
                "limited_series",
                "Limited Series",
                structure=_struct(season_enabled=True, episode_enabled=True),
                defaults={"aspectRatio": "16:9", "frameRate": 24},
                parent="series",
                group="film_narrative",
            ),
            group="film_narrative",
            parent="series",
        ),
        _def(
            "documentary",
            "Documentary",
            _profile(
                "documentary",
                "Documentary",
                defaults={"aspectRatio": "16:9", "frameRate": 24, "resolution": "1080p"},
                library=["Scenes", "Scripts", "Production Bible", "Exports"],
                templates=["establishing_shot", "dialogue_close_up"],
                camera=["grammar_episodic_drama"],
                cd={"planningMode": "documentary", "priority": ["interview", "broll", "archive"]},
                group="film_narrative",
            ),
            group="film_narrative",
            primary=True,
        ),
        _def(
            "animation",
            "Animation",
            _profile(
                "animation",
                "Animation / Cartoon",
                defaults={
                    "aspectRatio": "16:9",
                    "frameRate": 24,
                    "resolution": "1080p",
                    "productionEmphasis": ["character_sheets", "poses", "expressions", "backgrounds", "style"],
                },
                library=["Characters", "Storyboards", "Scenes", "Audio"],
                templates=[
                    "character_turnaround",
                    "expression_sheet",
                    "storyboard_panel",
                    "lipsync_dialogue_shot",
                    "music_cue",
                ],
                cd={"planningMode": "animation", "priority": ["character", "storyboard", "voice", "lipsync"]},
                group="film_narrative",
            ),
            group="film_narrative",
            primary=True,
            traits=["anime", "educational"],
        ),
        _def(
            "anime",
            "Anime",
            _profile(
                "anime",
                "Anime",
                defaults={"aspectRatio": "16:9", "frameRate": 24},
                library=["Characters", "Storyboards", "Scenes"],
                templates=["character_turnaround", "expression_sheet", "storyboard_panel"],
                parent="animation",
                group="film_narrative",
            ),
            group="film_narrative",
            parent="animation",
        ),
        _def(
            "talking_avatar",
            "Talking Avatar",
            _profile(
                "talking_avatar",
                "Talking Avatar",
                defaults={
                    "aspectRatio": "16:9",
                    "frameRate": 24,
                    "resolution": "1080p",
                    "productionEmphasis": ["script", "voice", "avatar", "lipsync", "background"],
                },
                library=["Characters", "Audio", "Scripts", "Video"],
                templates=["vertical_avatar", "lipsync_dialogue_shot", "music_cue"],
                cd={
                    "planningMode": "talking_avatar",
                    "priority": ["script", "avatar", "voice", "lipsync", "background", "captions"],
                },
                audio=["dialogue", "voiceover", "music"],
                group="creator_digital",
            ),
            group="creator_digital",
            primary=True,
            traits=["vertical_derivatives", "educational"],
        ),
        _def(
            "commercial",
            "Commercial",
            _profile(
                "commercial",
                "Commercial",
                defaults={
                    "aspectRatio": "16:9",
                    "frameRate": 24,
                    "resolution": "1080p",
                    "typicalDurationsSec": [15, 30],
                    "productionEmphasis": ["product", "brand", "cta", "duration", "delivery"],
                },
                library=["Props", "Scenes", "Exports", "Audio"],
                templates=["product_hero_shot", "logo_reveal", "title_card"],
                delivery=["web_sdr", "social_vertical", "15s", "30s"],
                cd={"planningMode": "commercial", "priority": ["product", "brand_rules", "cta", "duration"]},
                group="advertising",
            ),
            group="advertising",
            primary=True,
            subtypes=["brand_ad"],
            traits=["vertical_derivatives", "social_media"],
        ),
        _def(
            "brand_ad",
            "Brand Ad",
            _profile(
                "brand_ad",
                "Brand Ad",
                defaults={
                    "aspectRatio": "16:9",
                    "frameRate": 24,
                    "resolution": "1080p",
                    "typicalDurationsSec": [15, 30, 60],
                    "productionEmphasis": ["brand", "identity", "cta", "duration", "delivery"],
                },
                library=["Props", "Scenes", "Exports", "Audio"],
                templates=["product_hero_shot", "logo_reveal", "title_card"],
                delivery=["web_sdr", "social_vertical", "15s", "30s", "60s"],
                cd={"planningMode": "commercial", "priority": ["brand", "identity", "cta", "duration"]},
                group="advertising",
            ),
            group="advertising",
            parent="commercial",
        ),
        _def(
            "product_video",
            "Product Video",
            _profile(
                "product_video",
                "Product Video",
                defaults={"aspectRatio": "16:9", "frameRate": 24},
                templates=["product_hero_shot", "logo_reveal"],
                group="advertising",
            ),
            group="advertising",
        ),
        _def(
            "brand_promotional",
            "Brand / Promotional Video",
            _profile(
                "brand_promotional",
                "Brand / Promotional Video",
                defaults={"aspectRatio": "16:9", "frameRate": 24},
                templates=["product_hero_shot", "logo_reveal", "title_card"],
                group="advertising",
            ),
            group="advertising",
        ),
        _def(
            "music_video",
            "Music Video",
            _profile(
                "music_video",
                "Music Video",
                defaults={
                    "aspectRatio": "16:9",
                    "frameRate": 24,
                    "resolution": "1080p",
                    "productionEmphasis": ["song", "performance", "rhythm", "motifs", "edit_timing"],
                },
                library=["Audio", "Video", "Scenes", "Characters"],
                templates=["performance_shot", "music_cue", "establishing_shot"],
                audio=["music", "dialogue", "sfx", "ambience"],
                cd={
                    "planningMode": "music_video",
                    "priority": [
                        "song_master",
                        "song_duration",
                        "performance_refs",
                        "visual_concept",
                        "beat_structure",
                        "delivery",
                    ],
                },
                group="music_performance",
            ),
            group="music_performance",
            primary=True,
            traits=["animation", "social_media", "vertical_derivatives"],
        ),
        _def(
            "lyric_visualizer",
            "Lyric Video / Visualizer",
            _profile(
                "lyric_visualizer",
                "Lyric Video / Visualizer",
                defaults={"aspectRatio": "16:9", "frameRate": 24},
                templates=["performance_shot", "music_cue", "title_card"],
                group="music_performance",
            ),
            group="music_performance",
        ),
        _def(
            "social_media",
            "Social Media",
            _profile(
                "social_media",
                "Social Media",
                defaults={
                    "aspectRatio": "9:16",
                    "frameRate": 30,
                    "resolution": "1080p",
                    "captionsDefault": True,
                    "productionEmphasis": ["short_duration", "vertical", "captions", "hook", "cta"],
                },
                library=["Video", "Audio", "Exports"],
                templates=["vertical_avatar", "product_hero_shot", "title_card"],
                delivery=["social_vertical", "square_promo", "web_sdr"],
                cd={"planningMode": "social", "priority": ["hook", "captions", "cta", "duration"]},
                group="creator_digital",
            ),
            group="creator_digital",
            primary=True,
            subtypes=[
                "youtube_short",
                "tiktok",
                "instagram_reel",
                "facebook_video",
                "vertical_advertisement",
                "multi_platform_campaign",
            ],
            traits=["commercial", "educational"],
        ),
        _def(
            "youtube_creator",
            "YouTube / Creator Video",
            _profile(
                "youtube_creator",
                "YouTube / Creator Video",
                defaults={"aspectRatio": "16:9", "frameRate": 30, "resolution": "1080p", "captionsDefault": True},
                library=["Video", "Audio", "Scripts", "Exports"],
                templates=["dialogue_close_up", "title_card", "music_cue"],
                delivery=["youtube_sdr", "web_sdr"],
                group="creator_digital",
            ),
            group="creator_digital",
            primary=True,
        ),
        _def(
            "video_podcast",
            "Video Podcast",
            _profile(
                "video_podcast",
                "Video Podcast",
                defaults={"aspectRatio": "16:9", "frameRate": 30},
                templates=["dialogue_close_up", "lipsync_dialogue_shot"],
                audio=["dialogue", "music", "ambience"],
                group="creator_digital",
            ),
            group="creator_digital",
        ),
        _def(
            "educational_explainer",
            "Educational / Explainer",
            _profile(
                "educational_explainer",
                "Educational / Explainer",
                defaults={"aspectRatio": "16:9", "frameRate": 24, "captionsDefault": True},
                library=["Scripts", "Scenes", "Audio", "Exports"],
                templates=["dialogue_close_up", "title_card", "storyboard_panel"],
                cd={"planningMode": "educational", "priority": ["script", "clarity", "captions"]},
                group="creator_digital",
            ),
            group="creator_digital",
            primary=True,
        ),
        _def(
            "explainer_video",
            "Explainer Video",
            _profile(
                "explainer_video",
                "Explainer Video",
                defaults={"aspectRatio": "16:9", "frameRate": 24},
                parent="educational_explainer",
                group="creator_digital",
            ),
            group="creator_digital",
            parent="educational_explainer",
        ),
        _def(
            "storyboard_previs",
            "Storyboard / Previsualization",
            _profile(
                "storyboard_previs",
                "Storyboard / Previsualization",
                defaults={"aspectRatio": "16:9", "frameRate": 24, "resolution": "1080p"},
                library=["Storyboards", "Scenes", "Characters", "Scripts"],
                templates=["storyboard_panel", "character_identity_sheet", "establishing_shot"],
                cd={"planningMode": "previs", "priority": ["storyboard", "animatic", "blocking"]},
                group="specialized",
            ),
            group="specialized",
            primary=True,
        ),
        _def(
            "game_cinematic",
            "Game Cinematic",
            _profile(
                "game_cinematic",
                "Game Cinematic",
                defaults={"aspectRatio": "21:9", "frameRate": 24, "resolution": "1080p"},
                # V1.1: panoramic 360 + Spatial Map — native 3D import is Version 1.2.
                library=["Characters", "Scenes", "Audio"],
                templates=["cinematic_establishing", "character_identity_sheet", "performance_shot"],
                camera=["motion_slow_push_in", "lens_85mm_emotional"],
                group="specialized",
                cd={
                    "planningMode": "cinematic",
                    "environmentMethod": "360_panoramic_spatial_map",
                    "native3d": "DEFERRED_VERSION_1_2",
                    "version11Note": (
                        "Version 1.1 uses 360 panoramic environments and Spatial Map "
                        "camera/lighting direction. Native 3D importing is planned for Version 1.2."
                    ),
                },
            ),
            group="specialized",
            primary=True,
        ),
        _def(
            "previsualization",
            "Previsualization",
            _profile(
                "previsualization",
                "Previsualization",
                defaults={"aspectRatio": "16:9", "frameRate": 24},
                templates=["storyboard_panel", "establishing_shot"],
                group="specialized",
            ),
            group="specialized",
        ),
        _def(
            "video_cinematic_trailer",
            "Video / Cinematic Trailer",
            _profile(
                "video_cinematic_trailer",
                "Video / Cinematic Trailer",
                structure=_struct(
                    trailer_enabled=True,
                    sequence_enabled=True,
                    beat_enabled=True,
                    scene_enabled=True,
                    shot_enabled=True,
                ),
                defaults={
                    "aspectRatio": "16:9",
                    "frameRate": 24,
                    "resolution": "1080p",
                    "typicalDurationsSec": [30, 60, 90, 150],
                    "productionEmphasis": [
                        "hero_shots",
                        "montage",
                        "voiceover",
                        "music_sync",
                        "impacts",
                        "title_cards",
                        "pacing",
                        "end_cards",
                        "multi_delivery",
                    ],
                    "spoilerRestrictions": True,
                },
                library=["Video", "Audio", "Scenes", "Exports", "Production Bible"],
                templates=[
                    "cinematic_establishing",
                    "dialogue_close_up",
                    "logo_reveal",
                    "title_card",
                    "performance_shot",
                ],
                camera=[
                    "motion_slow_push_in",
                    "lens_85mm_emotional",
                    "framing_close_up",
                    "grammar_episodic_drama",
                ],
                lighting=["lighting_soft_low_key_interior"],
                color=["color_muted_1990s_tv", "color_web_sdr"],
                audio=[
                    "dialogue",
                    "voiceover",
                    "music",
                    "ambience",
                    "risers",
                    "braams",
                    "impacts",
                    "whooshes",
                    "stingers",
                    "logo_sound",
                ],
                delivery=[
                    "full_trailer",
                    "short_trailer",
                    "teaser",
                    "youtube_trailer",
                    "social_trailer",
                    "square_promo",
                ],
                beats=_TRAILER_BEATS,
                cd={
                    "planningMode": "cinematic_trailer",
                    "priority": [
                        "trailer_beats",
                        "hero_shots",
                        "spoiler_constraints",
                        "music_escalation",
                        "title_cards",
                        "derivative_cuts",
                    ],
                },
                group="advertising",
            ),
            group="advertising",
            primary=True,
            subtypes=[
                "film_trailer",
                "series_trailer",
                "cinematic_game_trailer",
                "book_trailer",
                "product_cinematic",
                "concept_trailer",
                "proof_of_concept_trailer",
                "announcement_trailer",
                "launch_trailer",
                "character_trailer",
                "world_environment_trailer",
                "teaser_trailer",
                "social_trailer_cut",
            ],
            traits=["social_media", "vertical_derivatives", "animation"],
        ),
        _def(
            "custom",
            "Custom Project",
            _profile(
                "custom",
                "Custom Project",
                defaults={"aspectRatio": "16:9", "frameRate": 24, "resolution": "1080p"},
                library=["Scenes", "Characters", "Scripts", "Exports"],
                templates=["establishing_shot", "dialogue_close_up"],
                cd={"planningMode": "custom"},
                group="specialized",
            ),
            group="specialized",
            primary=True,
            traits=["animation", "educational", "vertical_derivatives", "social_media"],
        ),
    ]

    # Trailer subtypes share trailer profile with subtype-specific display names.
    trailer_parent = next(i for i in items if i.slug == "video_cinematic_trailer")
    for sub in trailer_parent.subtypes:
        display = sub.replace("_", " ").title()
        prof = deepcopy(trailer_parent.profile)
        prof.project_type = sub
        prof.display_name = display
        prof.parent_selector = "video_cinematic_trailer"
        items.append(
            _def(
                sub,
                display,
                prof,
                group="advertising",
                parent="video_cinematic_trailer",
            )
        )

    # Social subtypes
    social = next(i for i in items if i.slug == "social_media")
    for sub in social.subtypes:
        display = sub.replace("_", " ").title()
        prof = deepcopy(social.profile)
        prof.project_type = sub
        prof.display_name = display
        prof.parent_selector = "social_media"
        items.append(_def(sub, display, prof, group="creator_digital", parent="social_media"))

    # Commercial subtypes (e.g. brand_ad)
    commercial = next(i for i in items if i.slug == "commercial")
    for sub in commercial.subtypes:
        if any(i.slug == sub for i in items):
            continue
        display = sub.replace("_", " ").title()
        prof = deepcopy(commercial.profile)
        prof.project_type = sub
        prof.display_name = display
        prof.parent_selector = "commercial"
        items.append(_def(sub, display, prof, group="advertising", parent="commercial"))

    return {item.slug: item for item in items}


BUILTIN_PROJECT_TYPES: dict[str, ProjectTypeDefinition] = _build_catalog()


def get_builtin_project_type(slug: str) -> ProjectTypeDefinition | None:
    return BUILTIN_PROJECT_TYPES.get(slug)


def list_builtin_project_types(*, primary_only: bool = False) -> list[ProjectTypeDefinition]:
    items = list(BUILTIN_PROJECT_TYPES.values())
    if primary_only:
        items = [i for i in items if i.primary_selector]
    # Stable UX order for primary selector
    order = [
        "feature_film",
        "short_film",
        "series",
        "documentary",
        "animation",
        "talking_avatar",
        "commercial",
        "music_video",
        "social_media",
        "youtube_creator",
        "educational_explainer",
        "storyboard_previs",
        "game_cinematic",
        "video_cinematic_trailer",
        "custom",
    ]
    rank = {s: i for i, s in enumerate(order)}
    items.sort(key=lambda x: (rank.get(x.slug, 1000), x.display_name))
    return items


def resolve_type_slug(primary: str, traits: list[str] | None = None) -> str:
    """Pick concrete type slug: prefer explicit subtype trait match, else primary."""
    primary = (primary or "custom").strip() or "custom"
    if primary in BUILTIN_PROJECT_TYPES:
        return primary
    # Allow legacy labels
    from ..kinds import LEGACY_PRODUCTION_TYPE_MAP

    mapped = LEGACY_PRODUCTION_TYPE_MAP.get(primary)
    if mapped:
        return mapped
    return "custom"
