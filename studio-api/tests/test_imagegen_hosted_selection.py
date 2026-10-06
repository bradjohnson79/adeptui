"""Hosted Image Generator selection must pin the named API model."""

from __future__ import annotations

from app.image_product.compile import compile_image_request


def test_hosted_kie_selection_does_not_resolve_local_qwen() -> None:
    compiled = compile_image_request(
        "proj-hosted-select",
        {
            "prompt": "a simple metallic cube",
            "purpose": "general",
            "source": "api",
            "provider": "kie",
            "requested_provider": "kie",
            "hostedModelId": "gpt-image-2-kie",
            "modelId": "gpt-image-2-kie",
            "kieImageModelId": "gpt-image-2-kie",
            "providerPreference": "cloud",
            "lockModelFamily": True,
        },
    )
    runtime = compiled["imageRuntime"]
    assert runtime["provider"] == "kie"
    assert "qwen" not in str(runtime.get("workflowKey") or "").lower()
    assert compiled["imageIntent"]["providerPreference"] == "cloud"
    assert compiled.get("hostedModelId") == "gpt-image-2-kie"
