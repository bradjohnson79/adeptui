"""Deterministic gate between an agent decision and tool execution."""

from __future__ import annotations

import hashlib

from .models import AuthorityEnvelope, FailureState, ToolRequest, TurnMode


def mutation_identity(
    *,
    workflow_id: str,
    tool_call_id: str,
    project_id: str,
    scene_id: str | None,
    action: str,
) -> str:
    raw = "|".join([workflow_id, tool_call_id, project_id, scene_id or "", action])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def mode_allows_tool(mode: str, *, kind: str, tool_id: str) -> bool:
    """Which tools a validated mode may call. This does not decide what the user meant."""

    if mode == "CONVERSATION":
        return False
    if mode == "READ":
        return kind == "read" and "open" not in tool_id
    if mode == "NAVIGATE":
        return "open" in tool_id and kind != "mutating"
    if mode in {"PROPOSE", "MUTATE"}:
        return kind == "mutating"
    return False


def authorize_tool(
    envelope: AuthorityEnvelope,
    *,
    tool_id: str,
    arguments: dict,
    tool_call_id: str,
    kind: str,
    shelved: bool,
) -> ToolRequest | FailureState:
    if shelved or tool_id not in envelope.exposed_tool_ids:
        return FailureState(
            code="TOOL_NOT_ADMITTED",
            message=f"'{tool_id}' is not in the admitted toolset.",
            workflow_id=envelope.workflow_id,
            tool_id=tool_id,
        )
    mode: TurnMode = envelope.turn_mode
    if kind == "mutating" and mode not in ("MUTATE", "PROPOSE"):
        return FailureState(
            code="MUTATION_NOT_AUTHORIZED",
            message="This turn was not admitted as a change, so no project data was written.",
            workflow_id=envelope.workflow_id,
            tool_id=tool_id,
        )
    action = f"{kind}:{tool_id}"
    return ToolRequest(
        workflow_id=envelope.workflow_id,
        tool_call_id=tool_call_id,
        mutation_id=mutation_identity(
            workflow_id=envelope.workflow_id,
            tool_call_id=tool_call_id,
            project_id=envelope.project_id,
            scene_id=envelope.scene_id,
            action=action,
        ),
        project_id=envelope.project_id,
        scene_id=envelope.scene_id,
        tool_id=tool_id,
        arguments=arguments,
        action=action,
    )
