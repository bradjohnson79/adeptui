"""Parse a ```proposal fenced JSON block out of a provider reply.

Mirrors `assistant.extract_scene_setup` / `strip_scene_setup_blocks` — the same
fence-then-parse pattern M1 already uses for `scene_setup`, applied to Bible proposals. A
fence that fails to parse or validate is never silently dropped: the caller gets a
`STRUCTURED_OUTPUT_INVALID` error while the rest of the reply is still shown to the user.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional

from pydantic import ValidationError

from .bible.schemas import BibleMutationSet

_FENCE_RE = re.compile(r"```proposal\s*([\s\S]*?)```", re.IGNORECASE)


@dataclass
class ProposalExtractionResult:
    proposal_type: str = "entity_update"
    title: str = ""
    summary: str = ""
    mutations: Optional[BibleMutationSet] = None
    error: Optional[str] = None


def has_proposal_fence(reply: str) -> bool:
    return bool(reply) and bool(_FENCE_RE.search(reply))


def extract_proposal_block(reply: str) -> Optional[ProposalExtractionResult]:
    """Return None when there is no ```proposal fence at all (nothing to report)."""

    if not reply:
        return None
    match = _FENCE_RE.search(reply)
    if not match:
        return None

    raw = match.group(1).strip()
    try:
        data = json.loads(raw)
    except Exception as exc:
        return ProposalExtractionResult(error=f"Proposal block was not valid JSON: {exc}")

    if not isinstance(data, dict):
        return ProposalExtractionResult(error="Proposal block must be a JSON object.")

    try:
        mutations = BibleMutationSet.model_validate(
            {
                "entityMutations": data.get("entityMutations", []),
                "factMutations": data.get("factMutations", []),
                "summary": data.get("summary", ""),
                "changeReason": data.get("changeReason", ""),
            }
        )
    except ValidationError as exc:
        return ProposalExtractionResult(error=f"Proposal block failed validation: {exc.errors()[:1]}")

    return ProposalExtractionResult(
        proposal_type=str(data.get("proposalType") or "entity_update"),
        title=str(data.get("title") or "Untitled proposal"),
        summary=str(data.get("summary") or mutations.summary or ""),
        mutations=mutations,
    )


def strip_proposal_blocks(reply: str) -> str:
    cleaned = _FENCE_RE.sub("", reply)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()
