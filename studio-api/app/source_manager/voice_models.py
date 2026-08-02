"""Character Voice Models surface for Source Manager (M3.3i)."""

from __future__ import annotations

from typing import Any

from ..codirector.m210b.qwen_voice_install import COMPONENT_SPECS, runtime_ready, uninstall_component
from ..setup.catalog import get_component
from ..setup.diagnostics import diagnose, verify_component
from ..voice_performance.runtime import get_index_tts2_runtime
from .downloads.models import create_install_plan
from .downloads.queue import get_queue_manager


def list_voice_models() -> dict[str, Any]:
    items = []
    for component_id, spec in COMPONENT_SPECS.items():
        component = get_component(component_id)
        ready, detail = runtime_ready(component_id)
        verification = verify_component(component_id)
        diagnostic = diagnose(component_id)
        items.append(
            {
                "componentId": component_id,
                "name": component.name,
                "description": component.description,
                "category": component.category,
                "registryId": spec["registryId"],
                "sourceKey": spec["sourceKey"],
                "modelRepository": f"https://huggingface.co/{spec['sourceKey']}",
                "downloadBytes": component.download_bytes,
                "ready": ready,
                "installed": ready,
                "status": "ready" if ready else "not_installed",
                "detail": detail,
                "verification": {
                    "healthy": verification.healthy,
                    "issue": verification.issue_code,
                    "summary": verification.summary,
                },
                "recommendation": diagnostic.get("recommendation"),
            }
        )
    index_component_id = "index_tts2"
    index_component = get_component(index_component_id)
    index_runtime = get_index_tts2_runtime()
    index_status = index_runtime.inspect_installation()
    index_verification = verify_component(index_component_id)
    index_diagnostic = diagnose(index_component_id)
    items.append(
        {
            "componentId": index_component_id,
            "name": index_component.name,
            "description": index_component.description,
            "category": index_component.category,
            "registryId": "index-tts2-local",
            "sourceKey": "IndexTeam/IndexTTS-2",
            "modelRepository": "https://huggingface.co/IndexTeam/IndexTTS-2",
            "downloadBytes": index_component.download_bytes,
            "ready": index_status.get("state") == "ready",
            "installed": index_status.get("state") in {"compatible", "installed", "ready"},
            "status": index_status.get("state"),
            "detail": index_status,
            "verification": {
                "healthy": index_verification.healthy,
                "issue": index_verification.issue_code,
                "summary": index_verification.summary,
            },
            "recommendation": index_diagnostic.get("recommendation"),
        }
    )
    return {"components": items, "count": len(items)}


def enqueue_voice_install(
    component_id: str,
    *,
    confirm: bool = True,
    confirm_download_models: bool = False,
) -> dict[str, Any]:
    if component_id == "index_tts2":
        if not confirm:
            raise ValueError("confirm=true is required to install IndexTTS2.")
        runtime = get_index_tts2_runtime()
        result = runtime.install(
            confirm=True,
            confirm_download_models=bool(confirm_download_models),
        )
        return {
            "componentId": component_id,
            "runtime": result,
            "confirm": True,
            "confirmDownloadModels": bool(confirm_download_models),
            "downloadDeferred": not bool(confirm_download_models),
        }
    if component_id not in COMPONENT_SPECS:
        raise KeyError(component_id)
    from ..codirector.m210b.qwen_voice_install import scaffold

    spec = COMPONENT_SPECS[component_id]
    sandbox = scaffold(component_id)
    plan = create_install_plan(
        component_id=component_id,
        source_id=spec["sourceKey"],
        provider_id="huggingface_snapshot",
        artifacts=[
            {
                "remotePath": spec["sourceKey"],
                "destinationRelativePath": "models",
                "downloadUrl": f"https://huggingface.co/{spec['sourceKey']}",
            }
        ],
        destination_root=str(sandbox),
        estimated_download_bytes=3_500_000_000,
        estimated_extracted_bytes=3_500_000_000,
        metadata={
            "componentId": component_id,
            "registryId": spec["registryId"],
            "sourceKey": spec["sourceKey"],
            "officialOnly": True,
        },
    )
    op = get_queue_manager().enqueue(plan, priority=50)
    return {"operation": op, "componentId": component_id}


def uninstall_voice_model(component_id: str) -> dict[str, Any]:
    if component_id == "index_tts2":
        return get_index_tts2_runtime().remove()
    if component_id not in COMPONENT_SPECS:
        raise KeyError(component_id)
    return uninstall_component(component_id)
