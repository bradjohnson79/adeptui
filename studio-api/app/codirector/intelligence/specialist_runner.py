"""Specialist runner: heuristic findings for E2E/mock, optional provider JSON path."""

from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any, Iterable, Optional

from pydantic import ValidationError

from ..errors import SPECIALIST_OUTPUT_INVALID, SPECIALIST_TIMEOUT, CoDirectorError
from ..providers.base import ChatRequest, CoDirectorProvider
from .context_compiler import ContextCompiler
from .schemas import ContextPackage, ProposedToolAction, SpecialistFinding
from .specialist_registry import SpecialistDefinition, SpecialistRegistry

_SPECIALIST_JSON_RE = re.compile(r"```json\s*([\s\S]*?)```", re.IGNORECASE)
DEFAULT_TIMEOUT_SEC = 25.0
_WRAPPER_KEYS = {
    "specialist-finding-v1",
    "specialist_finding_v1",
    "specialistfindingv1",
    "finding",
    "result",
    "output",
    "response",
    "payload",
    "data",
}
_FIELD_ALIASES = {
    "summary": (
        "summary",
        "synopsis",
        "overview",
        "assessment",
        "analysis",
        "finding",
        "findingSummary",
        "finding_summary",
        "sceneIntention",
        "scene_intention",
        "headline",
    ),
    "recommendation": (
        "recommendation",
        "recommendations",
        "advice",
        "guidance",
        "proposedAction",
        "proposed_action",
        "nextStep",
        "next_step",
        "conclusion",
        "strategy",
        "rationale",
    ),
    "requirements": (
        "requirements",
        "required",
        "needs",
        "dependencies",
        "prerequisites",
        "missingAssets",
        "missing_assets",
        "requiredAssets",
        "required_assets",
    ),
    "risks": (
        "risks",
        "risk",
        "concerns",
        "threats",
        "continuityRisks",
        "continuity_risks",
        "techRisks",
        "tech_risks",
        "capabilityGaps",
        "capability_gaps",
    ),
    "blockingIssues": (
        "blockingIssues",
        "blocking_issues",
        "blockers",
        "blocking",
        "conflicts",
        "issues",
    ),
    "optionalImprovements": (
        "optionalImprovements",
        "optional_improvements",
        "improvements",
        "enhancements",
    ),
    "assumptions": ("assumptions", "assumption", "caveats", "constraints"),
}

LIMITED_ANALYSIS_MODE = "limited-analysis"
PROVIDER_ANALYSIS_MODE = "provider"
LIMITED_ANALYSIS_ASSUMPTION = (
    "Limited-analysis / heuristic specialist output — no live model reasoning. "
    "Not deep story or emotional intelligence."
)


def _e2e_mode() -> bool:
    return os.environ.get("STUDIO_E2E", "").strip().lower() in ("1", "true", "yes", "on")


async def resolve_provider_for_specialists(
    provider: Optional[CoDirectorProvider] = None,
    *,
    prefer_provider: bool | None = None,
) -> tuple[Optional[CoDirectorProvider], bool, str]:
    """Decide whether specialists may call a live provider.

    Returns ``(provider_or_none, use_provider, analysis_mode)``.
    ``use_provider`` is True only when a provider is available, healthy enough to
    serve a model, and the process is not in ``STUDIO_E2E``. Otherwise analysis
    is explicitly ``limited-analysis`` (heuristic) — never presented as deep reasoning.
    """
    if _e2e_mode():
        return None, False, LIMITED_ANALYSIS_MODE

    candidate = provider
    if candidate is None and prefer_provider is not False:
        try:
            from ..service import get_provider

            candidate = get_provider()
        except Exception:  # noqa: BLE001
            return None, False, LIMITED_ANALYSIS_MODE

    if candidate is None:
        return None, False, LIMITED_ANALYSIS_MODE

    if prefer_provider is False:
        return None, False, LIMITED_ANALYSIS_MODE

    try:
        health = await candidate.health()
    except Exception:  # noqa: BLE001
        return None, False, LIMITED_ANALYSIS_MODE

    if not (getattr(health, "reachable", False) and getattr(health, "model_available", False)):
        return None, False, LIMITED_ANALYSIS_MODE

    return candidate, True, PROVIDER_ANALYSIS_MODE


class SpecialistRunner:
    def __init__(
        self,
        registry: SpecialistRegistry | None = None,
        *,
        timeout_sec: float = DEFAULT_TIMEOUT_SEC,
    ) -> None:
        self.registry = registry or SpecialistRegistry()
        self.timeout_sec = timeout_sec
        self.context_compiler = ContextCompiler()

    async def run_all(
        self,
        db,
        *,
        project_id: str,
        user_message: str,
        specialist_ids: Iterable[str],
        scene_id: Optional[str] = None,
        provider: Optional[CoDirectorProvider] = None,
        model_id: Optional[str] = None,
        request_id: Optional[str] = None,
        use_provider: bool = False,
    ) -> tuple[list[SpecialistFinding], list[CoDirectorError]]:
        definitions = [self.registry.require(sid) for sid in specialist_ids]
        package = await self.context_compiler.compile(
            db,
            project_id=project_id,
            user_message=user_message,
            scene_id=scene_id,
            specialists=definitions,
        )
        findings: list[SpecialistFinding] = []
        errors: list[CoDirectorError] = []
        for definition in definitions:
            scoped = self.context_compiler.filter_for_specialist(package, definition)
            try:
                finding = await self.run_one(
                    definition,
                    scoped,
                    user_message=user_message,
                    provider=provider,
                    model_id=model_id,
                    request_id=request_id,
                    use_provider=use_provider and provider is not None and not _e2e_mode(),
                )
                findings.append(finding)
            except CoDirectorError as err:
                errors.append(err)
        return findings, errors

    async def run_one(
        self,
        definition: SpecialistDefinition,
        package: ContextPackage,
        *,
        user_message: str,
        provider: Optional[CoDirectorProvider] = None,
        model_id: Optional[str] = None,
        request_id: Optional[str] = None,
        use_provider: bool = False,
    ) -> SpecialistFinding:
        if use_provider and provider is not None:
            try:
                raw = await asyncio.wait_for(
                    self._provider_structured(
                        provider,
                        definition,
                        package,
                        user_message=user_message,
                        model_id=model_id,
                        request_id=request_id or "specialist",
                    ),
                    timeout=min(self.timeout_sec, definition.timeout_ms / 1000.0),
                )
                finding = self._validate_or_repair(definition, raw)
                finding.status = "validated"
                finding.promptVersion = definition.prompt_version
                finding.modelId = model_id
                return finding
            except asyncio.TimeoutError as exc:
                raise CoDirectorError(
                    SPECIALIST_TIMEOUT,
                    f"Specialist '{definition.id}' timed out.",
                    details={"specialistId": definition.id},
                    recoverable=True,
                ) from exc
            except CoDirectorError:
                raise
            except Exception as exc:  # noqa: BLE001
                raise CoDirectorError(
                    SPECIALIST_OUTPUT_INVALID,
                    f"Specialist '{definition.id}' returned invalid output.",
                    details={"specialistId": definition.id, "reason": str(exc)[:200]},
                    recoverable=True,
                ) from exc

        finding = self._heuristic_finding(definition, package, user_message)
        finding.status = "validated"
        finding.promptVersion = definition.prompt_version
        return finding

    async def _provider_structured(
        self,
        provider: CoDirectorProvider,
        definition: SpecialistDefinition,
        package: ContextPackage,
        *,
        user_message: str,
        model_id: Optional[str],
        request_id: str,
    ) -> dict[str, Any]:
        system = (
            f"You are the {definition.display_name} specialist. "
            "Return ONLY JSON matching specialist-finding-v1 inside a ```json fence. "
            "Never execute tools."
        )
        user = (
            f"User request:\n{package.userMessageDelimited}\n\n"
            f"Context hash: {package.contextHash}\n"
            f"Facts: {json.dumps([f.model_dump(mode='json') for f in package.facts], default=str)[:6000]}"
        )
        result = await provider.generate(
            ChatRequest(request_id=request_id, messages=[{"role": "system", "content": system}, {"role": "user", "content": user}], model_id=model_id)
        )
        match = _SPECIALIST_JSON_RE.search(result.reply)
        payload = match.group(1) if match else result.reply
        return json.loads(payload)

    def _validate_or_repair(
        self, definition: SpecialistDefinition, raw: dict[str, Any]
    ) -> SpecialistFinding:
        normalized = self._normalize_provider_payload(raw)
        normalized.setdefault("specialistId", definition.id)
        try:
            return SpecialistFinding.model_validate(normalized)
        except ValidationError:
            repaired = dict(normalized)
            content_dropped = not self._has_substantive_content(normalized)
            repaired["summary"] = str(repaired.get("summary") or definition.display_name)
            repaired["recommendation"] = str(repaired.get("recommendation") or repaired["summary"])
            repaired["requirements"] = list(repaired.get("requirements") or [])
            repaired["risks"] = list(repaired.get("risks") or [])
            repaired["blockingIssues"] = list(repaired.get("blockingIssues") or [])
            repaired["optionalImprovements"] = list(repaired.get("optionalImprovements") or [])
            repaired["assumptions"] = list(repaired.get("assumptions") or [])
            repaired["proposedToolActions"] = list(repaired.get("proposedToolActions") or [])
            repaired["productionBibleReferences"] = list(repaired.get("productionBibleReferences") or [])
            repaired["contentDropped"] = content_dropped
            return SpecialistFinding.model_validate(repaired)

    @staticmethod
    def _unwrap_provider_payload(raw: Any) -> dict[str, Any]:
        """Remove provider/schema wrappers while retaining the actual finding."""
        payload = raw
        for _ in range(8):
            if not isinstance(payload, dict):
                return {}
            if len(payload) == 1:
                key, value = next(iter(payload.items()))
                key_norm = str(key).strip().lower().replace("_", "-")
                if isinstance(value, dict) and (
                    key_norm in _WRAPPER_KEYS or key_norm.endswith("-finding-v1") or len(payload) == 1
                ):
                    payload = value
                    continue
            return payload
        return payload if isinstance(payload, dict) else {}

    @classmethod
    def _normalize_provider_payload(cls, raw: dict[str, Any]) -> dict[str, Any]:
        payload = dict(cls._unwrap_provider_payload(raw))
        normalized = dict(payload)
        lowered = {str(key).lower().replace("_", "").replace("-", ""): key for key in payload}
        for target, aliases in _FIELD_ALIASES.items():
            if normalized.get(target):
                continue
            for alias in aliases:
                source = payload.get(alias)
                if source is None:
                    source = payload.get(lowered.get(alias.lower().replace("_", "").replace("-", ""), ""))
                if source is not None:
                    normalized[target] = cls._coerce_list(source) if target not in {"summary", "recommendation"} else cls._coerce_text(source)
                    break
        if not normalized.get("summary") or not normalized.get("recommendation"):
            text_values = [
                cls._coerce_text(value)
                for key, value in payload.items()
                if key not in {"specialistId", "status", "confidence"} and isinstance(value, (str, int, float))
            ]
            if text_values:
                normalized.setdefault("summary", text_values[0])
                if len(text_values) > 1:
                    normalized.setdefault("recommendation", text_values[1])
        return normalized

    @staticmethod
    def _coerce_text(value: Any) -> str:
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (list, tuple)):
            return "; ".join(str(item).strip() for item in value if str(item).strip())
        if isinstance(value, dict):
            return "; ".join(f"{key}: {text}" for key, item in value.items() if (text := str(item).strip()))
        return str(value).strip() if value is not None else ""

    @classmethod
    def _coerce_list(cls, value: Any) -> list[str]:
        if isinstance(value, (list, tuple, set)):
            return [cls._coerce_text(item) for item in value if cls._coerce_text(item)]
        text = cls._coerce_text(value)
        return [text] if text else []

    @classmethod
    def _has_substantive_content(cls, payload: dict[str, Any]) -> bool:
        for key in ("summary", "recommendation", "requirements", "risks", "blockingIssues", "optionalImprovements", "assumptions"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return True
            if isinstance(value, (list, tuple, dict)) and value:
                return True
        return False

    def _heuristic_finding(
        self,
        definition: SpecialistDefinition,
        package: ContextPackage,
        user_message: str,
    ) -> SpecialistFinding:
        lowered = user_message.lower()
        brief_anchor = " ".join(user_message.strip().split()[:12]) or "unspecified brief"
        domain_note = {
            "storyteller": "narrative beats and character stakes",
            "story-analyst": "structure and conflict arcs",
            "production-bible": "canon locks and protected terms",
            "continuity-analyst": "wardrobe/geography continuity",
            "director": "shot order and pacing",
            "cinematographer": "lens, framing, and camera language",
            "sound-producer": "dialogue, ambience, and music policy",
            "sound-designer": "SFX and spatial cues",
            "music-supervisor": "temp/score placement honesty",
            "editor": "cut rhythm and transitions",
            "virtual-production-coordinator": "stage logistics and asset readiness",
            "qa": "preflight and delivery risks",
        }.get(definition.id, "bounded Production Bible context")
        recommendation = (
            f"{definition.display_name} for brief «{brief_anchor}»: focus on {domain_note}."
        )
        requirements: list[str] = [f"Honor filmmaker brief: {brief_anchor}"]
        risks: list[str] = []
        blockers: list[str] = []
        tool_actions: list[ProposedToolAction] = []

        if "no music" in lowered or "sin música" in lowered or "pas de musique" in lowered:
            if definition.id in ("sound-producer", "music-supervisor", "sound-designer"):
                recommendation = (
                    f"{definition.display_name}: music prohibited for «{brief_anchor}»; "
                    "plan ambience/SFX only; do not schedule generative score."
                )
                requirements.append("generate_audio=false / music=prohibited")
        if "dialogue" in lowered and ("no dialogue" in lowered or "without dialogue" in lowered):
            if definition.id in ("storyteller", "sound-producer", "director"):
                requirements.append("Dialogue-free picture; ambient sound only")
        if "electric vehicle" in lowered or "commercial" in lowered:
            if definition.id in ("storyteller", "director", "cinematographer"):
                requirements.append("30s commercial pacing and product-hero beats")
        if "sister" in lowered or "estranged" in lowered:
            if definition.id in ("storyteller", "continuity-analyst", "sound-producer"):
                requirements.append("Two-character emotional continuity and dialogue coverage")
        if "music video" in lowered:
            if definition.id in ("editor", "music-supervisor", "director"):
                requirements.append("Imported audio timing; do not claim generative music")
        if "storyboard" in lowered and definition.id in ("director", "cinematographer", "prompt-architect"):
            recommendation = (
                f"For «{brief_anchor}»: locked medium two-shot with subtle movement, "
                "preserving practicals and readable facial exposure."
            )
            requirements.extend(["Approved character references", "Location architecture reference"])
        if definition.id == "technical-director":
            comfy = package.capabilities.get("comfyui")
            if comfy is None or not comfy.get("available"):
                blockers.append("ComfyUI workflow is not currently available.")
                risks.append("Generation step may require fallback or deferral.")
            else:
                requirements.append("Configured storyboard image workflow")
        if definition.id == "continuity-analyst":
            requirements.append("Match wardrobe and geography to adjacent shots.")
        if definition.id == "vision-reviewer":
            requirements.append("Define M2.5 visual validation criteria after generation.")
        if definition.id == "prompt-architect" and "storyboard" in lowered:
            tool_actions.append(
                ProposedToolAction(
                    toolId="propose_storyboard_generation",
                    purpose="Prepare storyboard image generation package",
                    requiresApproval=True,
                    arguments={"sceneId": package.activeScope.get("sceneId")},
                )
            )

        return SpecialistFinding(
            specialistId=definition.id,
            summary=(
                f"{definition.display_name} reviewed «{brief_anchor}» "
                f"({domain_note}; limited-analysis)."
            ),
            recommendation=recommendation,
            requirements=requirements,
            risks=risks,
            blockingIssues=blockers,
            optionalImprovements=[],
            proposedToolActions=tool_actions,
            assumptions=[LIMITED_ANALYSIS_ASSUMPTION],
            confidence=0.55,
        )
