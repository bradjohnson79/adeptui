"""Parse the structured blocks Co-Director may emit inside a plain-text reply.

Mirrors `assistant.extract_scene_setup` / `strip_scene_setup_blocks` — the same fence-then-parse
pattern M1 already uses for `scene_setup`. Two fences exist:

- ```` ```proposal ```` (M2.1) — a Production Bible mutation set. Unchanged.
- ```` ```tool ```` (M2.2) — a registry tool request, carrying an explicit `responseType`.

A fence that fails to parse or validate is never silently dropped: the caller gets a
`STRUCTURED_OUTPUT_INVALID`-shaped error while the rest of the reply is still shown to the user.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal, Optional

from pydantic import ValidationError

from .bible.schemas import BibleMutationSet

# A reply's kind is explicit rather than inferred:
#   message           — ordinary prose, nothing to execute.
#   read_tool_call    — the model wants one read tool run, then a follow-up turn.
#   mutation_proposal — the model wants a change; it becomes a proposal awaiting approval.
ResponseType = Literal["message", "read_tool_call", "mutation_proposal"]
RESPONSE_TYPES: tuple[str, ...] = ("message", "read_tool_call", "mutation_proposal")

_FENCE_RE = re.compile(r"```proposal\s*([\s\S]*?)```", re.IGNORECASE)
_TOOL_FENCE_RE = re.compile(r"```tool\s*([\s\S]*?)```", re.IGNORECASE)


@dataclass
class ProposalExtractionResult:
    proposal_type: str = "entity_update"
    title: str = ""
    summary: str = ""
    mutations: Optional[BibleMutationSet] = None
    error: Optional[str] = None


@dataclass
class ToolCallRequest:
    """A tool the model asked for. `arguments` is raw — the registry sanitizes it later."""

    response_type: ResponseType
    tool_id: str
    arguments: dict[str, Any]


@dataclass
class StructuredReply:
    """The classified result of one provider reply."""

    response_type: ResponseType = "message"
    display: str = ""
    tool_call: Optional[ToolCallRequest] = None
    bible_proposal: Optional[ProposalExtractionResult] = None
    error: Optional[str] = None


def has_proposal_fence(reply: str) -> bool:
    return bool(reply) and bool(_FENCE_RE.search(reply))


def has_tool_fence(reply: str) -> bool:
    return bool(reply) and bool(_TOOL_FENCE_RE.search(reply))


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


def strip_tool_blocks(reply: str) -> str:
    cleaned = _TOOL_FENCE_RE.sub("", reply)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def extract_tool_block(reply: str) -> Optional[StructuredReply]:
    """Parse a ```tool fence. Returns None when there isn't one.

    The fence body is `{"responseType": ..., "toolId": ..., "arguments": {...}}`. Arguments are
    passed through untouched — validating them here would duplicate the registry's schema, so
    the registry stays the single authority on what a tool accepts.
    """

    if not reply:
        return None
    match = _TOOL_FENCE_RE.search(reply)
    if not match:
        return None

    display = strip_tool_blocks(reply)
    raw = match.group(1).strip()
    try:
        data = json.loads(raw)
    except Exception as exc:
        return StructuredReply(display=display, error=f"Tool block was not valid JSON: {exc}")
    if not isinstance(data, dict):
        return StructuredReply(display=display, error="Tool block must be a JSON object.")

    claimed = str(data.get("responseType") or "").strip()
    if claimed and claimed not in RESPONSE_TYPES:
        return StructuredReply(
            display=display,
            error=f"Tool block has an unknown responseType '{claimed}'.",
        )
    if claimed == "message":
        return StructuredReply(response_type="message", display=display)

    tool_id = str(data.get("toolId") or "").strip()
    if not tool_id:
        return StructuredReply(display=display, error="Tool block is missing 'toolId'.")
    arguments = data.get("arguments")
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        return StructuredReply(display=display, error="Tool block 'arguments' must be a JSON object.")

    # The registry decides whether this executes now or needs approval. A reply claiming
    # `read_tool_call` for a mutating tool is not a reason to run it — the declared kind is the
    # only input to that decision, so `responseType` is advisory and unforgeable.
    from .tools import registry as tool_registry

    definition = tool_registry.find(tool_id)
    if definition is None:
        return StructuredReply(display=display, error=f"'{tool_id}' isn't a Co-Director tool.")
    response_type: ResponseType = "read_tool_call" if definition.kind == "read" else "mutation_proposal"

    return StructuredReply(
        response_type=response_type,
        display=display,
        tool_call=ToolCallRequest(response_type=response_type, tool_id=tool_id, arguments=arguments),
    )


def parse_structured_reply(reply: str) -> StructuredReply:
    """Classify one provider reply into `message | read_tool_call | mutation_proposal`.

    A ```tool fence wins over a ```proposal fence when both appear: the tool fence is explicit
    about its intent, and running both in one turn would mean two different approval artifacts
    from a single reply.
    """

    text = reply or ""
    tool_result = extract_tool_block(text)
    if tool_result is not None:
        tool_result.display = strip_proposal_blocks(tool_result.display)
        return tool_result

    proposal = extract_proposal_block(text)
    if proposal is None:
        return StructuredReply(response_type="message", display=text)

    display = strip_proposal_blocks(text)
    if proposal.error or proposal.mutations is None:
        return StructuredReply(
            response_type="mutation_proposal",
            display=display,
            error=proposal.error or "Co-Director's proposal could not be understood.",
        )
    return StructuredReply(response_type="mutation_proposal", display=display, bible_proposal=proposal)
