"""M3.1a — Templates/Presets foundation + Project Types certification."""

from __future__ import annotations

import json

import pytest

from app.feature_flags import FeatureFlags
from app.migrations import DEFAULT_REGISTRY
from app.project_library import LIBRARY_SCHEMA_VERSION, all_system_keys
from app.templates_presets.catalog.project_types import get_builtin_project_type, list_builtin_project_types
from app.templates_presets.compatibility import compatibility_report
from app.templates_presets.import_export import export_creative_item, import_creative_item
from app.templates_presets.resolve import merge_profile, resolve_creative_plan
from app.templates_presets.schema import CreativeBinding, CreativeItem
from app.templates_presets.catalog.seed_placeholders import system_items_by_slug


@pytest.fixture()
def flag_on(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "app.feature_flags.feature_flags",
        FeatureFlags(templates_presets_v1=True),
    )
    monkeypatch.setattr(
        "app.templates_presets.api.feature_flags",
        FeatureFlags(templates_presets_v1=True),
    )


def _create(client, *, name: str, primary: str, traits: list[str] | None = None, overrides: dict | None = None):
    res = client.post(
        "/api/projects",
        json={
            "name": name,
            "primary_project_type": primary,
            "project_traits": traits or [],
            "profile_overrides": overrides or {},
        },
    )
    assert res.status_code == 200, res.text
    return res.json()


def test_m020_registered() -> None:
    revs = [m.revision for m in DEFAULT_REGISTRY.all()]
    assert "0020" in revs


def test_library_taxonomy_includes_templates_presets() -> None:
    keys = all_system_keys()
    assert LIBRARY_SCHEMA_VERSION >= 2
    assert "templates_presets" in keys
    assert "templates_presets.generation_templates.video" in keys
    assert "templates_presets.camera_presets.grammar_packs" in keys
    assert "templates_presets.look_presets" in keys


def test_system_stubs_and_import_export_roundtrip() -> None:
    item = system_items_by_slug()["dialogue_close_up"]
    report = compatibility_report(item)
    assert report["ok"] is True
    package = export_creative_item(item)
    imported, import_report = import_creative_item(package)
    assert imported.slug == item.slug
    assert imported.intent == item.intent
    assert "providerMappings" in package["item"]
    assert import_report["ok"] is True


def test_resolve_shot_override_does_not_require_parent_mutation() -> None:
    system = system_items_by_slug()
    cam = system["lens_85mm_emotional"]
    bindings = [
        CreativeBinding(
            id="b1",
            project_id="p1",
            scope_level="project",
            slot="default_camera",
            item_id=cam.id,
            mode="override",
        ),
        CreativeBinding(
            id="b2",
            project_id="p1",
            scope_level="shot",
            slot="default_camera",
            item_id=system["framing_close_up"].id,
            shot_ref="shot-4",
            mode="override",
        ),
    ]
    plan_all = resolve_creative_plan(project_id="p1", shot_ref="shot-4", bindings=bindings)
    plan_other = resolve_creative_plan(project_id="p1", shot_ref="shot-1", bindings=bindings)
    assert plan_all.slots["default_camera"].item is not None
    assert plan_all.slots["default_camera"].item.slug == "framing_close_up"
    assert plan_other.slots["default_camera"].item is not None
    assert plan_other.slots["default_camera"].item.slug == "lens_85mm_emotional"


def test_project_type_01_defaults_primary_type(client, flag_on):
    p = _create(client, name="PT01", primary="short_film")
    assert p["primary_project_type"] == "short_film"
    assert p.get("resolved_profile_json")


def test_project_type_02_short_film_defaults(client, flag_on):
    p = _create(client, name="PT02", primary="short_film")
    profile = json.loads(p["resolved_profile_json"])
    assert profile["defaults"]["aspectRatio"] in ("16:9", "2.39:1")
    assert "Scenes" in profile["libraryEmphasis"] or "Characters" in profile["libraryEmphasis"]
    assert "dialogue_close_up" in profile["recommendedTemplates"] or "establishing_shot" in profile["recommendedTemplates"]


def test_project_type_03_web_series_hierarchy(client, flag_on):
    p = _create(client, name="PT03", primary="web_series")
    profile = client.get(f"/api/projects/{p['id']}/project-profile").json()
    units = profile["productionUnits"]
    kinds = {u["kind"] for u in units}
    assert "season" in kinds
    assert "episode" in kinds


def test_project_type_04_animation_emphasis(client, flag_on):
    p = _create(client, name="PT04", primary="animation")
    profile = json.loads(p["resolved_profile_json"])
    assert "Characters" in profile["libraryEmphasis"]
    assert "character_turnaround" in profile["recommendedTemplates"] or "expression_sheet" in profile["recommendedTemplates"]


def test_project_type_05_talking_avatar_context(client, flag_on):
    p = _create(client, name="PT05", primary="talking_avatar")
    profile = json.loads(p["resolved_profile_json"])
    ctx = profile["coDirectorContext"]
    assert ctx.get("planningMode") == "talking_avatar"
    assert "lipsync" in ctx.get("priority", [])


def test_project_type_06_commercial_defaults(client, flag_on):
    p = _create(client, name="PT06", primary="commercial")
    profile = json.loads(p["resolved_profile_json"])
    assert profile["defaults"].get("typicalDurationsSec") == [15, 30]
    assert "product_hero_shot" in profile["recommendedTemplates"]


def test_project_type_07_music_video(client, flag_on):
    p = _create(client, name="PT07", primary="music_video")
    profile = json.loads(p["resolved_profile_json"])
    assert "song_master" in profile["coDirectorContext"].get("priority", [])
    assert "music" in profile["audioTrackDefaults"]


def test_project_type_08_social_vertical(client, flag_on):
    p = _create(client, name="PT08", primary="social_media")
    profile = json.loads(p["resolved_profile_json"])
    assert profile["defaults"]["aspectRatio"] == "9:16"
    assert profile["defaults"].get("captionsDefault") is True
    assert p["width"] < p["height"]


def test_project_type_09_recommended_presets(client, flag_on):
    p = _create(client, name="PT09", primary="short_film")
    profile = json.loads(p["resolved_profile_json"])
    assert profile["recommendedCameraPresets"]
    assert profile["recommendedLightingPresets"]
    assert profile["recommendedColorPresets"]


def test_project_type_10_codirector_profile(client, flag_on):
    p = _create(client, name="PT10", primary="music_video", traits=["animation"])
    # Co-Director identity profile via project_service fields on project-profile endpoint
    payload = client.get(f"/api/projects/{p['id']}/project-profile").json()
    assert payload["primaryProjectType"] == "music_video"
    assert "animation" in payload["projectTraits"]
    assert payload["identity"]["primaryProjectType"] == "music_video"
    assert payload["identity"]["resolvedProfile"]["recommendedTemplates"]


def test_project_type_11_persist_reload(client, flag_on):
    p = _create(client, name="PT11", primary="documentary", traits=["educational"])
    again = client.get(f"/api/projects/{p['id']}").json()
    assert again["primary_project_type"] == "documentary"
    traits = json.loads(again["project_traits_json"])
    assert "educational" in traits


def test_project_type_12_non_destructive_type_change(client, flag_on):
    p = _create(client, name="PT12", primary="short_film")
    scene_ids = [s["id"] for s in p["scenes"]]
    preview = client.post(
        f"/api/projects/{p['id']}/project-type/preview",
        json={"primaryProjectType": "commercial"},
    ).json()
    assert preview["allowed"] is True
    assert preview["assetDelete"] is False
    assert preview["assetRelocate"] is False
    applied = client.post(
        f"/api/projects/{p['id']}/project-type",
        json={"primaryProjectType": "commercial"},
    ).json()
    assert applied["ok"] is True
    after = client.get(f"/api/projects/{p['id']}").json()
    assert after["primary_project_type"] == "commercial"
    assert [s["id"] for s in after["scenes"]] == scene_ids


def test_project_type_13_custom_type_reuse(client, flag_on):
    p = _create(client, name="PT13 Source", primary="short_film")
    saved = client.post(
        "/api/templates-presets/project-types/custom",
        json={"projectId": p["id"], "slug": "adept_chronicles_episode", "displayName": "Adept Chronicles Episode"},
    ).json()
    assert saved["slug"] == "adept_chronicles_episode"
    reused = _create(client, name="PT13 Reuse", primary="adept_chronicles_episode")
    assert reused["primary_project_type"] == "adept_chronicles_episode"


def test_project_type_14_scene_binding_override(client, flag_on):
    p = _create(client, name="PT14", primary="short_film")
    scene_id = p["scenes"][0]["id"]
    item = client.post(
        "/api/templates-presets/items",
        json={
            "kind": "camera_preset",
            "name": "Low Angle Override",
            "slug": "low_angle_override",
            "scope": "project",
            "projectId": p["id"],
            "intent": {"angle": "low"},
            "providerMappings": {},
        },
    ).json()
    client.post(
        "/api/templates-presets/bindings",
        json={
            "projectId": p["id"],
            "slot": "default_camera",
            "itemId": item["id"],
            "scopeLevel": "scene",
            "sceneId": scene_id,
            "mode": "override",
        },
    )
    plan = client.post(
        "/api/templates-presets/resolve",
        json={"projectId": p["id"], "sceneId": scene_id},
    ).json()
    assert plan["slots"]["default_camera"]["item"]["slug"] == "low_angle_override"
    # Project primary type unchanged
    again = client.get(f"/api/projects/{p['id']}").json()
    assert again["primary_project_type"] == "short_film"


def test_trailer_hierarchy_and_beats(client, flag_on):
    p = _create(client, name="Trailer", primary="video_cinematic_trailer")
    profile = json.loads(p["resolved_profile_json"])
    assert profile["structure"]["trailerEnabled"] is True
    assert "Cold Open" in profile["beatSkeleton"] or len(profile["beatSkeleton"]) >= 3
    units = client.get(f"/api/projects/{p['id']}/project-profile").json()["productionUnits"]
    kinds = {u["kind"] for u in units}
    assert "trailer" in kinds
    assert "beat" in kinds
    assert any(d for d in profile["delivery"] if "trailer" in d or "teaser" in d or "social" in d)


def test_catalog_and_fork_does_not_mutate_system(client, flag_on):
    catalog = client.get("/api/templates-presets/catalog?scope=system").json()
    assert any(i["slug"] == "dialogue_close_up" for i in catalog["items"])
    p = _create(client, name="Fork", primary="custom")
    forked = client.post(
        "/api/templates-presets/items/sys:dialogue_close_up/fork",
        json={"name": "My Dialogue CU", "projectId": p["id"], "scope": "project"},
    ).json()
    assert forked["parentItemId"] == "sys:dialogue_close_up"
    assert forked["scope"] == "project"
    system = system_items_by_slug()["dialogue_close_up"]
    assert system.name == "Dialogue Close-Up"


def test_adapter_m213_light_preset(client, flag_on):
    res = client.get("/api/templates-presets/adapters/m213/preview?preset=three_point")
    assert res.status_code == 200
    body = res.json()
    assert body["source"]["system"] == "m213"
    assert body["intent"]["lighting"]["preset"] == "three_point"
    assert body["providerMappings"] == {}


def test_adapter_empty_profile_item_needs_clarification(client, flag_on):
    from app.db import SessionLocal
    from app.profiles import ProfileItem, ensure_profile_tables
    import uuid
    from datetime import datetime

    ensure_profile_tables()
    db = SessionLocal()
    pid = str(uuid.uuid4())
    try:
        db.add(
            ProfileItem(
                id=pid,
                kind="camera_preset",
                name="Empty Cam",
                data_json="{}",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )
        db.commit()
    finally:
        db.close()
    res = client.get(f"/api/templates-presets/adapters/profiles/preview?profileId={pid}")
    assert res.status_code == 200
    body = res.json()
    assert body["needsClarification"] is True
    assert "empty_data_json" in body["gaps"]


def test_primary_selector_includes_trailer():
    primaries = list_builtin_project_types(primary_only=True)
    slugs = [p.slug for p in primaries]
    assert "video_cinematic_trailer" in slugs
    assert "short_film" in slugs
    assert get_builtin_project_type("web_series") is not None


def test_merge_profile_series_trait_to_web_series():
    profile = merge_profile("series", traits=["web_series"])
    assert profile.project_type == "web_series"
    assert profile.structure.season_enabled is True
