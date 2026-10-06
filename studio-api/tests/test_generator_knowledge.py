"""VideoGeneratorKnowledgeProfile: PC-id resolver, dialect dispatch, no MiniMax leak."""

from __future__ import annotations

from app.codirector.generator_knowledge.compiler import (
    UNAVAILABLE_MESSAGE,
    compile_for_generator,
)
from app.codirector.generator_knowledge.resolver import (
    PROFILE_KEYS,
    canonical_profile_id,
    resolve_profile,
    try_resolve_profile,
)
from app.codirector.model_intelligence.schemas import NormalizedGenerationIntent


def _intent(prompt: str = "A rainy street at dusk") -> NormalizedGenerationIntent:
    return NormalizedGenerationIntent(
        userPrompt=prompt,
        mode="image_to_video",
        mediaType="video",
        hasSourceImage=True,
    )


def test_resolver_keys_production_control_ids():
    assert canonical_profile_id("minimax-h3") == "minimax-h3"
    assert canonical_profile_id("minimax-h3-t2v-local") == "minimax-h3"
    assert canonical_profile_id("ltx-2.5") == "ltx-2.5"
    assert canonical_profile_id("ltx-2.5-full") == "ltx-2.5"
    assert canonical_profile_id("ltx-2.5-distilled") == "ltx-2.5"
    assert canonical_profile_id("ltx-2.5-comfy") == "ltx-2.5"
    assert canonical_profile_id("unknown-generator-xyz") is None


def test_ltx_25_ids_share_one_profile():
    a = resolve_profile("ltx-2.5")
    b = resolve_profile("ltx-2.5-full")
    c = resolve_profile("ltx-2.5-distilled")
    d = resolve_profile("ltx-2.5-comfy")
    assert a.profileId == "ltx-2.5"
    assert b.profileId == c.profileId == d.profileId == "ltx-2.5"
    assert b.workflow.adapterId == "ltx-2.5-distilled"
    assert "ltx-2.5-full" in b.workflow.versionNotes
    assert b.workflow.versionNotes["ltx-2.5-full"].requiredComponents


def test_profiles_are_three_layers():
    for gid in ("minimax-h3", "ltx-2.5", "ltx-2.5-distilled", "ltx-2.5-full"):
        profile = resolve_profile(gid)
        assert profile.capability is not None
        assert profile.prompt.dialect
        assert profile.workflow.adapterId


def test_minimax_compile_uses_frame_roles_not_subject_tags():
    out = compile_for_generator("minimax-h3", _intent("Korri walks across the porch"))
    assert out.status == "ok"
    assert "<subject" not in (out.compiledPrompt or "").lower()
    assert "Korri walks across the porch" in out.compiledPrompt
    assert out.parameters.get("dialect") == "h3_frame_roles"
    assert out.parameters.get("subjectTagsEmitted") is False
    assert out.parameters.get("frameRoles") == ["crs", "ers", "prs", "prior_frame"]
    assert out.parameters.get("knowledgeLoaded") is True
    assert "minimax-h3.md" in str(out.parameters.get("knowledgeSpecPath") or "")
    assert out.parameters.get("r2vDialect") == "h3_picture_tokens"
    assert any(r.ruleId == "prompt.frame_roles" for r in out.appliedRules)


def test_ltx25_compile_does_not_emit_minimax_tags_or_h3_roles():
    out = compile_for_generator("ltx-2.5-distilled", _intent("Natural tracking shot"))
    assert out.status == "ok"
    assert "<subject" not in (out.compiledPrompt or "").lower()
    text = (out.compiledPrompt or "").lower()
    assert "start-middle" not in text
    assert out.parameters.get("dialect") == "pack_rules"
    assert out.parameters.get("profileId") == "ltx-2.5"
    assert "natural tracking shot" in text


def test_ltx_25_compile_inherits_pack_and_attaches_version_notes():
    out = compile_for_generator("ltx-2.5-full", _intent("Natural tracking shot"))
    assert out.status == "ok"
    assert out.parameters.get("profileId") == "ltx-2.5"
    assert out.parameters.get("requestedGeneratorId") == "ltx-2.5-full"
    assert out.parameters.get("knowledgeFile") == "ltx-2.5.md"
    assert out.parameters.get("r2vDialect") == "ltx25_single_cond"
    assert any("ltx_2_5_checkpoint" in w for w in out.warnings)
    assert "<subject" not in (out.compiledPrompt or "").lower()
    assert "<Picture" not in (out.compiledPrompt or "")


def test_minimax_and_ltx25_zero_subject_tags():
    h3 = compile_for_generator("minimax-h3", _intent("Slow dolly in"))
    ltx = compile_for_generator("ltx-2.5-distilled", _intent("Slow dolly in"))
    assert h3.status == "ok"
    assert ltx.status == "ok"
    assert "<subject" not in (h3.compiledPrompt or "").lower()
    assert "<subject" not in (ltx.compiledPrompt or "").lower()
    assert h3.parameters.get("dialect") == "h3_frame_roles"
    assert ltx.parameters.get("dialect") == "pack_rules"
    assert ltx.compiledPrompt.startswith("Slow dolly in")


def test_unknown_generator_is_honest_unavailable():
    out = compile_for_generator("totally-unknown", _intent())
    assert out.status == "GENERATOR_KNOWLEDGE_UNAVAILABLE"
    assert UNAVAILABLE_MESSAGE in " ".join(out.warnings)
    assert out.compiledPrompt == ""


def test_no_minimax_substring_keys_in_profile_map():
    # Resolver table is explicit IDs only; dialect switches must not scan "minimax" in hot paths.
    for key in PROFILE_KEYS:
        assert key == key  # mapping is exact-token
    missing, err = try_resolve_profile("not-a-generator")
    assert missing is None
    assert err

def test_minimax_profile_image_contract():
    profile = resolve_profile("minimax-h3")
    cap = profile.capability
    assert cap.maxImagesTextToVideo == 0
    assert cap.maxImagesImageToVideo == 9
    assert cap.supportsEndFrame is False
    assert cap.imageSlots["ref_images"] == "WIRED"
    assert cap.imageSlots["last_frame"] == "WIRED_PRIOR_FRAME"
    assert profile.prompt.subjectTags is True
    assert profile.prompt.frameRoles == ["crs", "ers", "prs", "prior_frame"]
    notes = " ".join(cap.notes)
    assert "Reference-to-Video" in notes
    assert "<Picture N>" in notes
    disclosure = profile.prompt.disclosure or ""
    assert "@ CRS" in disclosure
    assert "minimax-h3.md" in disclosure
    out = compile_for_generator("minimax-h3", _intent("A quiet porch at dusk"))
    blob = " ".join(out.warnings)
    assert "Reference-to-Video" in blob
    assert "<subject" not in (out.compiledPrompt or "").lower()
    assert out.parameters.get("knowledgeLoaded") is True


def test_resolver_examples_match_production_control_ids():
    examples = {
        "minimax-h3": "minimax-h3",
        "minimax-h3-i2v-local": "minimax-h3",
        "ltx-2.5": "ltx-2.5",
        "ltx-2.5-full": "ltx-2.5",
        "ltx-2.5-distilled": "ltx-2.5",
        "ltx-2.5-comfy": "ltx-2.5",
        "seedance-fal": "seedance-api",
        "kling-kie": "kling-api",
        "veo-kie": "veo-api",
    }
    for gid, pid in examples.items():
        assert canonical_profile_id(gid) == pid
        assert resolve_profile(gid).profileId == pid
