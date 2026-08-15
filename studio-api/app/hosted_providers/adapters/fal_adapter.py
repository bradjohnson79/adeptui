from __future__ import annotations

from typing import Any


async def probe_fal(api_key: str) -> dict[str, Any]:
    """Delegate to existing fal live probe — no mock path."""
    from ...fal_client import validate_fal_key

    probe = await validate_fal_key(api_key)
    return {
        "providerId": "fal",
        "valid": probe.get("valid"),
        "status": probe.get("status"),
        "httpStatus": probe.get("httpStatus"),
        "message": probe.get("message") or "",
        "probeEndpoint": probe.get("probeEndpoint"),
        "balance": None,
        "mock": False,
    }


async def enqueue_fal(api_key: str, model_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Submit to fal queue. Does not invent success — live POST only."""
    from ...fal_client import run_fal_model

    result = await run_fal_model(model_id, arguments, api_key)
    return {"ok": True, "providerId": "fal", "modelId": model_id, "result": result, "mock": False}


async def chat_fal(api_key: str, *, prompt: str, model: str = "google/gemini-2.5-flash-lite", system_prompt: str = "", temperature: float = 0.55) -> dict[str, Any]:
    """Synchronous Any LLM call (official fal-ai/any-llm)."""
    from ...fal_client import run_fal_model

    args: dict[str, Any] = {"prompt": prompt, "model": model, "temperature": temperature}
    if system_prompt:
        args["system_prompt"] = system_prompt
    result = await run_fal_model("fal-ai/any-llm", args, api_key)
    output = ""
    if isinstance(result, dict):
        output = str(result.get("output") or result.get("data") or "")
        if isinstance(result.get("data"), dict):
            output = str(result["data"].get("output") or output)
    return {"ok": True, "providerId": "fal", "modelId": "fal-ai/any-llm", "output": output, "raw": result, "mock": False}



def strengthen_fal_character_sheet_prompt(prompt: str, *, model: str | None = None) -> str:
    """fal still-image four-panel turnaround strengthen."""
    from ...character_identity.four_view_sheet import strengthen_four_view_prompt

    return strengthen_four_view_prompt(prompt)
