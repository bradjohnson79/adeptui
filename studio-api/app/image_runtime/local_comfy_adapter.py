"""Local Comfy adapter façade — same submit / poll / download verbs as kie/fal.

Not a product and not a parallel orchestrator. QueueWorker local _imagegen
calls these verbs; leaf-graph build and Comfy HTTP live here.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

PROVIDER_ID = "local"
ADAPTER_ID = "comfy"


def _legacy_key(contract: Any, workflow_key: str = "") -> str:
    key = str(workflow_key or "").strip()
    if key:
        return key
    raw = getattr(contract, "workflow_key", None) if contract is not None else None
    if raw is None and isinstance(contract, dict):
        raw = contract.get("workflowKey") or contract.get("workflow_key")
    try:
        from .workflow_execute import legacy_comfy_workflow_key

        return legacy_comfy_workflow_key(str(raw or ""))
    except Exception:
        return str(raw or "")


async def submit(
    graph: dict[str, Any] | None = None,
    *,
    workflow_key: str = "",
    contract: Any = None,
    settings: Any = None,
    expected_graph_hash: str | None = None,
    enforce_certified_fingerprint: bool = False,
    prompt: str = "",
    negative: str = "",
    width: int = 1024,
    height: int = 1024,
    seed: int = 0,
    steps: int = 8,
    cfg: float = 1.0,
    filename_prefix: str = "studio/image",
    reference_image: Any = None,
    source_image: Any = None,
    mask_image: Any = None,
    checkpoint: Any = None,
    denoise: float = 0.45,
    grow_mask_by: int = 6,
    outpaint_left: int = 0,
    outpaint_top: int = 0,
    outpaint_right: int = 256,
    outpaint_bottom: int = 256,
    **_extra: Any,
) -> dict[str, Any]:
    """Queue a local Comfy graph. Same verb as kie/fal submit.

    If ``graph`` is omitted, builds it via build_leaf_graph / prepare_executable_graph.
    """
    from ..comfy_client import comfy
    from .workflow_execute import build_leaf_graph, prepare_executable_graph

    wf = graph
    if wf is None:
        if contract is None:
            return {
                "ok": False,
                "error": "NO_GRAPH",
                "message": "LocalComfy submit requires graph or contract.",
                "providerId": PROVIDER_ID,
                "adapter": ADAPTER_ID,
                "mock": False,
            }
        wf = build_leaf_graph(
            contract,
            settings=settings,
            prompt=prompt,
            negative=negative or "blurry, low quality, watermark",
            width=width,
            height=height,
            seed=seed,
            steps=steps,
            cfg=cfg,
            filename_prefix=filename_prefix,
            reference_image=reference_image,
            source_image=source_image,
            mask_image=mask_image,
            checkpoint=checkpoint,
            denoise=denoise,
            grow_mask_by=grow_mask_by,
            outpaint_left=outpaint_left,
            outpaint_top=outpaint_top,
            outpaint_right=outpaint_right,
            outpaint_bottom=outpaint_bottom,
        )
        wf = prepare_executable_graph(
            contract,
            wf,
            expected_graph_hash=expected_graph_hash,
            enforce_certified_fingerprint=enforce_certified_fingerprint,
        )
    key = _legacy_key(contract, workflow_key)
    prompt_id = await comfy.queue_prompt(wf, workflow_key=key or None)
    return {
        "ok": bool(prompt_id),
        "providerId": PROVIDER_ID,
        "adapter": ADAPTER_ID,
        "taskId": prompt_id,
        "promptId": prompt_id,
        "workflowKey": key,
        "graph": wf,
        "mock": False,
    }


async def poll(
    submitted: dict[str, Any] | None = None,
    *args: Any,
    wait_fn: Any = None,
    on_progress: Any = None,
    cancel_check: Any = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Wait for the queued Comfy prompt. Same verb as kie/fal poll."""
    from ..comfy_client import comfy

    payload = submitted if isinstance(submitted, dict) else {}
    prompt_id = str(payload.get("taskId") or payload.get("promptId") or "").strip()
    if not prompt_id and args:
        prompt_id = str(args[0] or "").strip()
    if not prompt_id:
        return {
            "ok": False,
            "error": "NO_TASK",
            "state": "failed",
            "files": [],
            "imagePath": None,
            "imageUrl": "",
            "providerId": PROVIDER_ID,
            "mock": False,
        }
    if wait_fn is not None:
        history = await wait_fn(prompt_id)
    else:
        history = await comfy.wait_for_prompt(
            prompt_id, on_progress=on_progress, cancel_check=cancel_check
        )
    files = list(comfy.find_output_files(history) or [])
    image_path = files[0] if files else None
    return {
        "ok": bool(files),
        "state": "completed" if files else "failed",
        "history": history,
        "files": files,
        "imagePath": image_path,
        "imageUrl": str(image_path) if image_path else "",
        "taskId": prompt_id,
        "providerId": PROVIDER_ID,
        "adapter": ADAPTER_ID,
        "mock": False,
    }


async def download(source: Any, dest: Any) -> Any:
    """Copy local Comfy output to dest. Same verb as hosted URL download."""
    src = Path(source)
    dst = Path(dest)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst
