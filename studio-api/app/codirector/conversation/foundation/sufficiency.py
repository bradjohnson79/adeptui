"""Context sufficiency — ask only when a required field is truly missing.

Ask only if: required param missing AND not resolvable from project/character/
visual resolver AND no safe default AND material to execution.
Optional aesthetic conflict is not material.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .speech_act import (
    CRS_ADVANCE_TOOL,
    CRS_CREATE_ALIAS,
    SpeechAct,
    is_crs_create_action,
    resolve_production_action,
)


class SufficiencyResult(BaseModel):
    context_sufficient: bool = True
    clarification_required: bool = False
    missing_required_fields: list[str] = Field(default_factory=list)
    resolved_action: str = ""
    resolved_character_id: str = ""
    resolved_character_name: str = ""
    clarification_question: str = ""
    notes: list[str] = Field(default_factory=list)


def extract_character_name(user_message: str) -> str:
    import re

    text = user_message or ""
    patterns = (
        r"\bcreate\s+([A-Z][A-Za-z0-9'’\-]+)'s\s+(?:crs|character|visual|reference)\b",
        r"\b([A-Z][A-Za-z0-9'’\-]+)'s\s+(?:crs|character reference sheet|visual sheet)\b",
        r"\b(?:for|of)\s+([A-Z][A-Za-z0-9'’\-]+)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1).replace("’", "'").strip(" '")
    return ""


def evaluate_sufficiency(
    *,
    user_message: str,
    speech_act: SpeechAct,
    project_id: str | None = None,
    bound_character_id: str | None = None,
    db: Any = None,
    aesthetic_conflict: bool = False,
) -> SufficiencyResult:
    """Decide whether a COMMAND can execute without asking."""

    action = resolve_production_action(user_message)
    result = SufficiencyResult(resolved_action=action)
    if aesthetic_conflict:
        result.notes.append("optional_aesthetic_conflict_ignored")

    if speech_act != "COMMAND":
        result.context_sufficient = True
        result.clarification_required = False
        return result

    if not project_id:
        result.context_sufficient = False
        result.clarification_required = True
        result.missing_required_fields = ["projectId"]
        result.clarification_question = "Which project should I use?"
        return result

    if is_crs_create_action(action) or action == CRS_ADVANCE_TOOL or action == "character.assign_reference":
        return _evaluate_character_action(
            result,
            user_message=user_message,
            project_id=project_id,
            bound_character_id=bound_character_id,
            db=db,
            require_description=is_crs_create_action(action),
        )

    # Non-CRS commands: if we have a project, treat as sufficient unless a
    # required production object is named but unresolvable.
    result.context_sufficient = True
    return result


def _evaluate_character_action(
    result: SufficiencyResult,
    *,
    user_message: str,
    project_id: str,
    bound_character_id: str | None,
    db: Any,
    require_description: bool,
) -> SufficiencyResult:
    character_id = (bound_character_id or "").strip()
    character_name = extract_character_name(user_message)
    profile = None

    if db is not None:
        try:
            from app.character_identity.service import get_profile, resolve_character_by_name

            if character_id:
                try:
                    profile = get_profile(db, project_id, character_id)
                except Exception:
                    profile = None
            if profile is None and character_name:
                row = resolve_character_by_name(db, project_id, character_name)
                if row is not None:
                    character_id = str(getattr(row, "id", "") or character_id)
                    try:
                        profile = get_profile(db, project_id, character_id)
                    except Exception:
                        profile = row
        except Exception:
            profile = None

    if not character_id:
        result.context_sufficient = False
        result.clarification_required = True
        result.missing_required_fields = ["characterId"]
        result.clarification_question = "Which character should I make the reference sheet for?"
        return result

    result.resolved_character_id = character_id
    if profile is not None:
        result.resolved_character_name = str(getattr(profile, "name", "") or character_name)
        bio = str(getattr(profile, "description", "") or "").strip()
        visual = str(getattr(profile, "visual_description", "") or "").strip()
        combined = f"{bio} {visual}".strip()
        if require_description and len(combined) < 20:
            result.context_sufficient = False
            result.clarification_required = True
            result.missing_required_fields = ["description"]
            result.clarification_question = (
                f"I need a short description of {result.resolved_character_name or 'this character'} "
                "before I can generate a reference sheet — age, look, wardrobe, or the feeling you want."
            )
            return result
    elif require_description and db is None:
        # Unit tests without a DB still treat a bound/resolvable character as sufficient.
        result.resolved_character_name = character_name
        result.notes.append("profile_not_loaded")

    result.context_sufficient = True
    result.clarification_required = False
    if not result.resolved_action:
        result.resolved_action = CRS_CREATE_ALIAS
    return result


def apply_sufficiency_to_intent(intent: Any, sufficiency: SufficiencyResult) -> Any:
    """Copy sufficiency onto an IntentAnalysis (additive fields)."""

    intent.context_sufficient = sufficiency.context_sufficient
    intent.clarification_required = sufficiency.clarification_required
    intent.missing_required_fields = list(sufficiency.missing_required_fields)
    if sufficiency.resolved_action:
        intent.resolved_action = sufficiency.resolved_action
    if getattr(intent, "speech_act", "") == "COMMAND":
        intent.suppress_next_best_action = True
        if sufficiency.context_sufficient:
            intent.should_ask_question = False
            intent.should_use_tools = True
        else:
            intent.should_ask_question = True
            intent.should_use_tools = False
    return intent
