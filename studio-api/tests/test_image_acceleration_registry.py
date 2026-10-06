"""Acceleration keep/reject is tuple-specific. CC/Prop stay regression boundaries."""

from __future__ import annotations

from app.image_runtime.acceleration_registry import (
    is_accepted,
    lookup,
    should_keep_models_resident,
)
from app.image_runtime.residency import (
    clear_residency,
    note_still_loaded,
    should_unload_before,
    vram_pressure,
)


def test_cd_still_residency_accepted_same_family() -> None:
    assert is_accepted(kind="residency", family="zimage", workflow_class="codirector_still") is True
    assert should_keep_models_resident(family="zimage", workflow_class="codirector_still") is True


def test_cc_does_not_unload_when_nothing_is_resident() -> None:
    clear_residency()
    assert (
        should_unload_before(
            next_family="qwen_edit_2509",
            next_workflow="character_creator_multiview",
        )
        is False
    )
    note_still_loaded("zimage", "codirector_still")
    assert (
        should_unload_before(
            next_family="qwen_edit_2509",
            next_workflow="character_creator_multiview",
        )
        is True
    )
    clear_residency()


def test_unload_after_render_and_video_handoff_evict() -> None:
    assert (
        should_keep_models_resident(
            family="zimage",
            workflow_class="codirector_still",
            unload_after_render=True,
        )
        is False
    )
    assert (
        should_keep_models_resident(
            family="zimage",
            workflow_class="codirector_still",
            next_needs_vram=True,
        )
        is False
    )
    assert should_unload_before(next_family="wan", next_needs_vram=True) is True


def test_qwen_edit_family_does_not_keep_cd_residency() -> None:
    assert (
        should_keep_models_resident(
            family="qwen_edit_2509",
            workflow_class="character_creator_multiview",
        )
        is False
    )


def test_character_creator_residency_not_accepted() -> None:
    record = lookup(
        kind="residency",
        family="qwen_image_edit_2509",
        workflow_class="character_creator_multiview",
    )
    assert record is not None
    assert record.state != "accepted"
    assert (
        should_keep_models_resident(
            family="qwen_image_edit_2509",
            workflow_class="character_creator_multiview",
        )
        is False
    )


def test_same_family_reuses_and_incompatible_evicts() -> None:
    clear_residency()
    note_still_loaded("qwen2512", "codirector_still")
    assert (
        should_unload_before(next_family="qwen2512", next_workflow="codirector_still")
        is False
    )
    assert should_unload_before(next_family="flux", next_workflow="codirector_still") is True
    note_still_loaded("flux", "codirector_still")
    assert should_unload_before(next_family="qwen2512", next_workflow="codirector_still") is True
    clear_residency()


def test_cc_and_prop_do_not_unload_without_resident_or_vram() -> None:
    clear_residency()
    assert (
        should_unload_before(
            next_family="qwen_edit_2509",
            next_workflow="character_creator_multiview",
        )
        is False
    )
    assert (
        should_unload_before(next_family="flux", next_workflow="prop_creator")
        is False
    )
    assert (
        should_unload_before(
            next_family="qwen_edit_2509",
            next_workflow="character_creator_multiview",
            vram_free_mib=512,
        )
        is True
    )
    clear_residency()


def test_cc_prop_same_family_does_not_evict_without_vram() -> None:
    """CC/Prop evict only for family incompatibility or VRAM — not because they are protected."""

    clear_residency()
    note_still_loaded("flux", "codirector_still")
    assert should_unload_before(next_family="flux", next_workflow="prop_creator") is False
    note_still_loaded("qwen_edit_2509", "character_creator_multiview")
    assert (
        should_unload_before(
            next_family="qwen_edit_2509",
            next_workflow="character_creator_multiview",
        )
        is False
    )
    assert (
        should_unload_before(
            next_family="qwen_edit_2509",
            next_workflow="character_creator_multiview",
            vram_free_mib=512,
        )
        is True
    )
    clear_residency()


def test_vram_pressure_helper() -> None:
    assert vram_pressure(None) is False
    assert vram_pressure(4096) is False
    assert vram_pressure(512) is True


def test_teacache_and_compile_rejected_as_cd_default() -> None:
    assert is_accepted(kind="approximate_cache", family="flux", workflow_class="t2i") is False
    assert is_accepted(kind="compile", family="flux", workflow_class="t2i") is False
    assert is_accepted(kind="attention", family="flux", workflow_class="t2i") is False


def test_flux_attention_does_not_authorize_qwen_edit() -> None:
    flux = lookup(kind="attention", family="flux", workflow_class="t2i")
    qwen = lookup(kind="attention", family="qwen_image_edit_2509", workflow_class="edit")
    assert flux is None or flux.state != "accepted"
    assert qwen is None or qwen.state != "accepted"
