"""Generation tools retired from Adept UI v1.1.

These IDs must not appear in the live catalog, Co-Director tool list,
or workspace registry. Callers that still post them receive HTTP 410.
"""

from __future__ import annotations

from typing import Any

RETIRED_GENERATION_TOOL_IDS = frozenset({"brand.studio"})
RETIRED_CODIRECTOR_TOOL_IDS = frozenset({"propose_brand_generate"})

BRAND_STUDIO_RETIREMENT_MESSAGE = (
    "Brand Studio was retired from Adept UI v1.1. "
    "Reconsider for v1.2 as a separately scoped product rather than "
    "restoring the legacy implementation automatically."
)


def is_retired_generation_tool(tool_id: str) -> bool:
    return str(tool_id or "").strip() in RETIRED_GENERATION_TOOL_IDS


def retired_http_detail(tool_id: str) -> dict[str, Any]:
    return {
        "status": "RETIRED",
        "toolId": tool_id,
        "product": "Adept UI v1.1",
        "message": BRAND_STUDIO_RETIREMENT_MESSAGE,
    }
