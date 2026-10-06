"""Co-Director image.generate uses CIS Strategy A adapter selection.

Decision table
--------------
typed refs                         family        adapter
exactly 1 (real asset id)          qwen2512      qwen2512.ref
char+env OR 2+ typed (real ids)    any CD        qwen_edit_2509.edit
                                 (IDENTITY=image1, SCENE=image2)
typed refs + locked incapable      illustrious   FAIL-CLOSED (never *.txt2img)
names/prose only (no asset ids)    qwen2512      no invented identity / no force
exactly 1                          flux (CD)     flux.img2img (existing CD binder)
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.image_product.cis_ref_binding import apply_cis_reference_binding
from app.image_product.compile import compile_image_request
from app.image_product.prompt_tokens import compile_typed_image_authority


def _char_env_refs() -> list[dict]:
    return [
        {
            "key": "character:cami-id",
            "kind": "character",
            "assetId": "cami-id",
            "name": "Cami",
            "chip": "@Cami",
        },
        {
            "key": "environment:corridor-id",
            "kind": "environment",
            "assetId": "corridor-id",
            "name": "Corridor",
            "chip": "#Corridor",
        },
    ]


def test_cd_one_typed_ref_selects_qwen2512_ref() -> None:
    body = {
        "prompt": "make it more like this",
        "purpose": "codirector_image_generate",
        "modelFamilyPreference": "qwen2512",
        "lockModelFamily": True,
        "authorityRefs": [
            {"kind": "character", "assetId": "lib-keep", "name": "Cami", "chip": "@Cami"}
        ],
        "referenceAssetIds": ["lib-keep"],
        "creativeContext": {},
    }
    apply_cis_reference_binding(body)
    assert body["forceWorkflowKey"] == "qwen2512.ref"
    assert body["forceWorkflowKey"] != "qwen2512.txt2img"
    assert not str(body.get("forceWorkflowKey")).endswith(".txt2img")
    bind = (body.get("creativeContext") or {}).get("referenceBinding") or {}
    assert bind.get("strategy") == "qwen2512.ref"
    assert bind.get("identityAssetId") == "lib-keep"


def test_cd_char_plus_env_selects_qwen_edit_2509() -> None:
    body = {
        "prompt": "@Cami walking the #Corridor",
        "purpose": "codirector_image_generate",
        "modelFamilyPreference": "qwen2512",
        "lockModelFamily": True,
        "authorityRefs": _char_env_refs(),
        "selectedCharacters": [_char_env_refs()[0]],
        "selectedEnvironment": _char_env_refs()[1],
        "referenceAssetIds": ["cami-id", "corridor-id"],
        "creativeContext": {},
    }
    apply_cis_reference_binding(body)
    assert body["forceWorkflowKey"] == "qwen_edit_2509.edit"
    assert body["forceWorkflowKey"] != "qwen2512.ref"
    assert body["forceWorkflowKey"] != "qwen2512.txt2img"
    assert body["modelFamilyPreference"] == "qwen_edit_2509"
    assert body["sourceAssetId"] == "cami-id"
    assert body["sceneReferenceAssetId"] == "corridor-id"
    bind = (body.get("creativeContext") or {}).get("referenceBinding") or {}
    assert bind.get("strategy") == "qwen_edit_2509.multi_ref"
    assert bind.get("identityAssetId") == "cami-id"
    assert bind.get("sceneAssetId") == "corridor-id"
    assert bind.get("identitySlot") == "IDENTITY_REFERENCE"
    assert bind.get("sceneSlot") == "SCENE_REFERENCE"


def test_cd_two_typed_refs_from_selected_star_selects_edit() -> None:
    """selectedCharacters + selectedEnvironment after normalize is enough."""
    body = {
        "prompt": "still",
        "purpose": "codirector_image_generate",
        "modelFamilyPreference": "qwen2512",
        "lockModelFamily": True,
        "selectedCharacters": [{"assetId": "char-a", "name": "A"}],
        "selectedEnvironment": {"assetId": "env-b", "name": "B"},
        "creativeContext": {},
    }
    apply_cis_reference_binding(body)
    assert body["forceWorkflowKey"] == "qwen_edit_2509.edit"
    assert body["sourceAssetId"] == "char-a"
    assert body["sceneReferenceAssetId"] == "env-b"


def test_cd_refs_plus_incapable_family_fail_closed() -> None:
    body = {
        "prompt": "locked text-only family with refs",
        "purpose": "codirector_image_generate",
        "modelFamilyPreference": "illustrious",
        "lockModelFamily": True,
        "referenceAssetIds": ["lib-x"],
        "authorityRefs": [{"kind": "character", "assetId": "lib-x", "name": "X"}],
        "creativeContext": {},
    }
    with pytest.raises(RuntimeError, match="cannot use an attached picture"):
        apply_cis_reference_binding(body)
    assert str(body.get("forceWorkflowKey") or "") != "illustrious.txt2img"
    assert not str(body.get("forceWorkflowKey") or "").endswith(".txt2img")


def test_cd_prose_names_do_not_invent_identity_or_force() -> None:
    pack = compile_typed_image_authority(
        planning={"prompt": "Cami in Venture Corridor", "authorityRefs": []}
    )
    assert pack["authorityRefs"] == []
    body = {
        "prompt": "Cami in Venture Corridor",
        "purpose": "codirector_image_generate",
        "modelFamilyPreference": "qwen2512",
        "lockModelFamily": True,
        "creativeContext": {},
    }
    apply_cis_reference_binding(body)
    assert "forceWorkflowKey" not in body or not body.get("forceWorkflowKey")


def test_cd_compile_one_ref_pins_qwen_ref() -> None:
    compiled = compile_image_request(
        "test-cd-one-ref",
        {
            "prompt": "make it more like this",
            "purpose": "codirector_image_generate",
            "referenceAssetIds": ["lib-keep"],
            "referenceImage": "lib-keep",
            "lockModelFamily": True,
            "modelFamilyPreference": "qwen2512",
            "source": "local",
            "allow_force_workflow_key": True,
        },
    )
    key = compiled["imageRuntime"].get("workflowKey")
    assert key == "qwen2512.ref"
    assert not str(key).endswith(".txt2img")


def test_cd_compile_char_env_pins_edit_2509() -> None:
    compiled = compile_image_request(
        "test-cd-char-env",
        {
            "prompt": "@Cami walking the #Corridor",
            "purpose": "codirector_image_generate",
            "referenceAssetIds": ["cami-id", "corridor-id"],
            "authorityRefs": _char_env_refs(),
            "lockModelFamily": True,
            "modelFamilyPreference": "qwen2512",
            "source": "local",
            "allowDraft": True,
            "allow_draft": True,
        },
    )
    key = compiled["imageRuntime"].get("workflowKey")
    assert key == "qwen_edit_2509.edit"
    assert key != "qwen2512.txt2img"
    assert key != "qwen2512.ref"
    intent = compiled["imageIntent"]
    assert intent.get("sourceAssetId") == "cami-id"
    meta = intent.get("metadata") or {}
    assert meta.get("sceneReferenceAssetId") == "corridor-id"
    bind = meta.get("referenceBinding") or {}
    assert bind.get("strategy") == "qwen_edit_2509.multi_ref"


def test_cd_compile_incapable_family_fail_closed() -> None:
    with pytest.raises(RuntimeError, match="cannot use an attached picture"):
        compile_image_request(
            "test-cd-illustrious-ref",
            {
                "prompt": "locked text-only family with refs",
                "purpose": "codirector_image_generate",
                "referenceAssetIds": ["lib-x"],
                "lockModelFamily": True,
                "modelFamilyPreference": "illustrious",
                "source": "local",
            },
        )


def test_cd_binding_is_idempotent_for_edit() -> None:
    body = {
        "prompt": "@Cami in #Corridor",
        "purpose": "codirector_image_generate",
        "modelFamilyPreference": "qwen2512",
        "lockModelFamily": True,
        "authorityRefs": _char_env_refs(),
        "referenceAssetIds": ["cami-id", "corridor-id"],
        "creativeContext": {},
    }
    apply_cis_reference_binding(body)
    apply_cis_reference_binding(body)
    assert body["forceWorkflowKey"] == "qwen_edit_2509.edit"
    assert body["modelFamilyPreference"] == "qwen_edit_2509"


def _qwen_candidate():
    from app.production_control.image_generator_query import ImageGeneratorCandidate

    return ImageGeneratorCandidate(
        model_id="qwen-image-2512-local",
        family="qwen2512",
        locality="local",
        executable=True,
        installed=True,
        runtime_ready=True,
        supports=("text_to_image", "reference_conditioning"),
        supports_reference=True,
        supports_edit=True,
        provider="comfy",
        model_family="qwen2512",
        capability_label="Certified",
        default_eligible=True,
        label="Qwen",
    )


def _illustrious_candidate():
    from app.production_control.image_generator_query import ImageGeneratorCandidate

    return ImageGeneratorCandidate(
        model_id="illustrious-local",
        family="illustrious",
        locality="local",
        executable=True,
        installed=True,
        runtime_ready=True,
        supports=("text_to_image",),
        supports_reference=False,
        supports_edit=False,
        provider="comfy",
        model_family="illustrious",
        capability_label="Available",
        default_eligible=True,
        label="Illustrious",
    )


def _patch_handler_common(monkeypatch, handler, chosen, captured):
    from app.codirector.preferences.resolver import PreferenceResolution
    from app.production_control.image_generator_query import AutoImageSelection

    monkeypatch.setattr(
        "app.image_product.prompt_tokens.resolve_image_prompt_tokens",
        lambda *args, **kwargs: {"tokens": [], "reference_asset_ids": []},
    )
    monkeypatch.setattr(
        handler,
        "resolve_generator_preference",
        lambda *args, **kwargs: PreferenceResolution(
            provider=chosen.family, source="default", modality="image"
        ),
    )
    monkeypatch.setattr("runtime_supervisor.health.comfy_healthy", lambda: True)
    monkeypatch.setattr(handler, "_check_runtime_admission", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        handler,
        "select_auto_image_generator",
        lambda *args, **kwargs: AutoImageSelection(
            selected=chosen,
            task="reference",
            why="test-strategy-a",
            local_candidates=[chosen],
        ),
    )
    monkeypatch.setattr(
        "app.storyboard_jobs.enqueue_imagegen_job",
        lambda db, project_id, body=None, **kwargs: captured.append(dict(body or {}))
        or SimpleNamespace(id="job-strategy-a"),
    )


def test_handler_one_ref_pins_qwen_ref(monkeypatch) -> None:
    from app.codirector.capabilities.handlers import image_generate as handler

    captured: list[dict] = []
    chosen = _qwen_candidate()
    monkeypatch.setattr(
        handler,
        "collect_character_references",
        lambda *args, **kwargs: ([], ["lib-keep"], ""),
    )
    _patch_handler_common(monkeypatch, handler, chosen, captured)
    result = handler.handle(
        db=MagicMock(),
        project_id="proj",
        execution_id="exec-one-ref",
        prompt="Make it more like this.",
        user_instructions="Make it more like this.",
        original_user_instructions="Make it more like this.",
        attachment_asset_ids=["lib-keep"],
        authority_refs=[{"kind": "character", "assetId": "lib-keep", "name": "Cami"}],
    )
    assert captured
    body = captured[0]
    assert body["forceWorkflowKey"] == "qwen2512.ref"
    assert not str(body.get("forceWorkflowKey")).endswith(".txt2img")
    assert body["referenceImage"] == "lib-keep"
    assert result["child_jobs"]


def test_handler_char_env_pins_edit_2509(monkeypatch) -> None:
    from app.codirector.capabilities.handlers import image_generate as handler

    captured: list[dict] = []
    chosen = _qwen_candidate()
    monkeypatch.setattr(
        handler,
        "collect_character_references",
        lambda *args, **kwargs: ([], ["cami-id", "corridor-id"], ""),
    )
    _patch_handler_common(monkeypatch, handler, chosen, captured)
    result = handler.handle(
        db=MagicMock(),
        project_id="proj",
        execution_id="exec-char-env",
        prompt="@Cami walking the #Corridor",
        user_instructions="@Cami walking the #Corridor",
        original_user_instructions="@Cami walking the #Corridor",
        attachment_asset_ids=["cami-id", "corridor-id"],
        authority_refs=_char_env_refs(),
        selected_characters=[_char_env_refs()[0]],
        selected_environment=_char_env_refs()[1],
    )
    assert captured
    body = captured[0]
    assert body["forceWorkflowKey"] == "qwen_edit_2509.edit"
    assert body["forceWorkflowKey"] != "qwen2512.txt2img"
    assert body["forceWorkflowKey"] != "qwen2512.ref"
    assert body["modelFamilyPreference"] == "qwen_edit_2509"
    assert body["sourceAssetId"] == "cami-id"
    assert body["sceneReferenceAssetId"] == "corridor-id"
    assert body["creativeContext"]["workflowKey"] == "qwen_edit_2509.edit"
    bind = body["creativeContext"].get("referenceBinding") or {}
    assert bind.get("identitySlot") == "IDENTITY_REFERENCE"
    assert bind.get("sceneSlot") == "SCENE_REFERENCE"
    assert result["child_jobs"]


def test_handler_refs_plus_incapable_fail_closed_not_txt2img(monkeypatch) -> None:
    from app.codirector.capabilities.handlers import image_generate as handler

    captured: list[dict] = []
    chosen = _illustrious_candidate()
    monkeypatch.setattr(
        handler,
        "collect_character_references",
        lambda *args, **kwargs: ([], ["lib-x"], ""),
    )
    _patch_handler_common(monkeypatch, handler, chosen, captured)
    monkeypatch.setattr(handler, "match_explicit_image_generator", lambda *args, **kwargs: chosen)
    result = handler.handle(
        db=MagicMock(),
        project_id="proj",
        execution_id="exec-fail-closed",
        prompt="Use Illustrious with this reference.",
        user_instructions="Use Illustrious with this reference.",
        original_user_instructions="Use Illustrious with this reference.",
        attachment_asset_ids=["lib-x"],
        authority_refs=[{"kind": "character", "assetId": "lib-x", "name": "X"}],
        requested_model_id="illustrious",
        lock_level="PREFERRED",
    )
    assert captured == []
    assert result["child_jobs"] == []
    err = (result.get("error") or "").lower()
    assert "cannot use an attached picture" in err or "txt2img" in err
    assert "illustrious.txt2img" not in err
