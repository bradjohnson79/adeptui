"""Layer B — Co-Director reasons over verified facts. Code still owns wiring."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from .readiness import build_scene_creator_readiness

_CACHE: dict[str, dict[str, Any]] = {}
_CACHE_LIMIT = 24

_SYSTEM = (
    "You are Co-Director, a production supervisor. Evaluate only the supplied "
    "verified production facts. Do not invent missing character, prop, environment, "
    "camera, spatial, or provider information. If something is unknown, return unknown. "
    "Do not rewrite canon. Reply with JSON only: "
    '{"status":"pass"|"advisory"|"blocked","issues":[{"type":"advisory"|"blocking","message":"..."}],'
    '"summary":"..."}'
)


def _parse_json_reply(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if fence:
        raw = fence.group(1).strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(raw[start : end + 1])
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def compact_integrity_facts(readiness: dict[str, Any], packet: dict[str, Any] | None = None) -> dict[str, Any]:
    pkt = packet if isinstance(packet, dict) else {}
    chars = list(pkt.get("characters") or [])
    props = list(pkt.get("props") or [])
    env = pkt.get("environment") if isinstance(pkt.get("environment"), dict) else {}
    cine = pkt.get("cinematography") if isinstance(pkt.get("cinematography"), dict) else {}
    shot = pkt.get("shot") if isinstance(pkt.get("shot"), dict) else {}
    spatial = pkt.get("spatial") if isinstance(pkt.get("spatial"), dict) else {}
    char0 = chars[0] if chars else {}
    prop0 = props[0] if props else {}
    return {
        "shot": {
            "prompt": str(shot.get("prompt") or ""),
            "camera": str(cine.get("framing") or cine.get("angle") or ""),
        },
        "character": {
            "name": str(char0.get("name") or ""),
            "referenceAvailable": bool(char0.get("assetId")),
            "consumption": str(char0.get("consumption") or ""),
        },
        "prop": {
            "name": str(prop0.get("name") or ""),
            "referenceAvailable": bool(prop0.get("assetId")),
            "relationship": str(prop0.get("relationship") or ""),
            "consumption": str(prop0.get("consumption") or ""),
        },
        "environment": {
            "ersAvailable": bool(env.get("assetId")),
            "consumption": str(env.get("consumption") or ""),
        },
        "spatial": {"lines": list(spatial.get("lines") or [])[:8]},
        "provider": {
            "family": str(pkt.get("family") or ""),
            "pixelSlots": pkt.get("pixelSlots"),
            "consumedAssetIds": list(pkt.get("consumedAssetIds") or []),
        },
        "deterministic": {
            "status": readiness.get("status"),
            "checks": readiness.get("checks"),
            "issues": readiness.get("issues"),
        },
    }


def _call_cd_llm(facts: dict[str, Any]) -> dict[str, Any]:
    from ..codirector.providers.base import ChatRequest
    from ..codirector.service import get_provider

    provider = get_provider("ollama")
    request = ChatRequest(
        request_id=str(uuid.uuid4()),
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": json.dumps(facts, ensure_ascii=True)},
        ],
        model_id=None,
        temperature=0.1,
        mode="chat",
    )
    import asyncio
    import concurrent.futures

    async def _go():
        return await asyncio.wait_for(provider.generate(request), timeout=8)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        result = asyncio.run(_go())
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(asyncio.run, _go()).result(timeout=12)
    parsed = _parse_json_reply(getattr(result, "reply", "") or "")
    if not parsed:
        raise ValueError("empty_or_invalid")
    status = str(parsed.get("status") or "advisory").strip().lower()
    if status not in {"pass", "advisory", "blocked"}:
        status = "advisory"
    issues = parsed.get("issues") if isinstance(parsed.get("issues"), list) else []
    clean_issues = []
    for item in issues:
        if not isinstance(item, dict):
            continue
        msg = str(item.get("message") or "").strip()
        if not msg:
            continue
        kind = str(item.get("type") or "advisory").strip().lower()
        if kind not in {"advisory", "blocking"}:
            kind = "advisory"
        clean_issues.append({"type": kind, "message": msg})
    return {
        "status": status,
        "issues": clean_issues,
        "summary": str(parsed.get("summary") or "").strip(),
        "available": True,
    }


def assess_production_integrity(
    readiness: dict[str, Any],
    packet: dict[str, Any] | None = None,
    *,
    invoke_llm: bool = True,
) -> dict[str, Any]:
    """Attach Layer B. Deterministic checks remain authoritative."""
    out = dict(readiness or {})
    fingerprint = str(out.get("fingerprint") or "")
    if fingerprint and fingerprint in _CACHE:
        cached = dict(_CACHE[fingerprint])
        out["llm"] = cached.get("llm")
        if cached.get("status") in {"pass", "advisory", "blocked"} and out.get("status") != "blocked":
            if cached.get("llm", {}).get("status") == "blocked":
                out["status"] = "blocked"
                out["ready"] = False
            elif cached.get("llm", {}).get("status") == "advisory" and out.get("status") == "pass":
                out["status"] = "advisory"
        return out

    if not invoke_llm or out.get("status") in {"idle", "blocked"}:
        out["llm"] = None
        return out

    try:
        facts = compact_integrity_facts(out, packet)
        llm = _call_cd_llm(facts)
    except Exception:
        llm = {
            "status": "unavailable",
            "issues": [],
            "summary": "",
            "available": False,
        }
        if out.get("status") == "pass":
            out["status"] = "llm_unavailable"

    out["llm"] = llm
    if llm.get("available") and llm.get("status") == "blocked" and out.get("status") != "blocked":
        # CD may not invent wiring. Only honor blocked if it cites supplied deterministic issues
        # or a prompt/spatial conflict (advisory-class unless code already blocked).
        # Prompt/blocking conflicts stay advisory per product law.
        if any(i.get("type") == "blocking" for i in (llm.get("issues") or [])):
            # Do not let LLM invent a missing asset. Keep code status unless already blocked.
            pass
        if out.get("status") == "pass":
            out["status"] = "advisory"
            out["issues"] = list(out.get("issues") or []) + [
                i for i in (llm.get("issues") or []) if i.get("type") == "advisory"
            ]
    elif llm.get("available") and llm.get("status") == "advisory" and out.get("status") == "pass":
        out["status"] = "advisory"
        out["issues"] = list(out.get("issues") or []) + list(llm.get("issues") or [])

    if fingerprint:
        if len(_CACHE) >= _CACHE_LIMIT:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[fingerprint] = {"status": out.get("status"), "llm": out.get("llm")}
    return out


def parse_assessment_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    """Unit-test helper for the CD JSON contract."""
    status = str(payload.get("status") or "").strip().lower()
    if status not in {"pass", "advisory", "blocked"}:
        raise ValueError("invalid status")
    issues = payload.get("issues") if isinstance(payload.get("issues"), list) else []
    return {
        "status": status,
        "issues": issues,
        "summary": str(payload.get("summary") or ""),
    }


def merge_readiness_with_packet(
    production_context: dict[str, Any] | None,
    selected_profile: Any,
    packet: dict[str, Any],
    *,
    family: str,
    camera_hash: str = "",
    scene_id: str = "",
    invoke_llm: bool = False,
) -> dict[str, Any]:
    ready = build_scene_creator_readiness(
        production_context=production_context,
        selected_profile=selected_profile,
        packet=packet,
        family=family,
        camera_hash=camera_hash,
        scene_id=scene_id,
    )
    return assess_production_integrity(ready, packet, invoke_llm=invoke_llm)
