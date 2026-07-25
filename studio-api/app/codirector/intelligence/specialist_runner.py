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


def _e2e_mode() -> bool:
    return os.environ.get("STUDIO_E2E", "").strip().lower() in ("1", "true", "yes", "on")


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
        raw.setdefault("specialistId", definition.id)
        try:
            return SpecialistFinding.model_validate(raw)
        except ValidationError:
            repaired = dict(raw)
            repaired["summary"] = str(repaired.get("summary") or definition.display_name)
            repaired["recommendation"] = str(repaired.get("recommendation") or repaired["summary"])
            repaired["requirements"] = list(repaired.get("requirements") or [])
            repaired["risks"] = list(repaired.get("risks") or [])
            repaired["blockingIssues"] = list(repaired.get("blockingIssues") or [])
            repaired["optionalImprovements"] = list(repaired.get("optionalImprovements") or [])
            repaired["assumptions"] = list(repaired.get("assumptions") or [])
            repaired["proposedToolActions"] = list(repaired.get("proposedToolActions") or [])
            repaired["productionBibleReferences"] = list(repaired.get("productionBibleReferences") or [])
            return SpecialistFinding.model_validate(repaired)

    def _heuristic_finding(
        self,
        definition: SpecialistDefinition,
        package: ContextPackage,
        user_message: str,
    ) -> SpecialistFinding:
        lowered = user_message.lower()
        recommendation = f"{definition.display_name} recommends proceeding with bounded Production Bible context."
        requirements: list[str] = []
        risks: list[str] = []
        blockers: list[str] = []
        tool_actions: list[ProposedToolAction] = []

        if "storyboard" in lowered and definition.id in ("director", "cinematographer", "prompt-architect"):
            recommendation = (
                "Use a locked medium two-shot with subtle movement, preserving corridor practicals "
                "and readable facial exposure."
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
            summary=f"{definition.display_name} reviewed the request.",
            recommendation=recommendation,
            requirements=requirements,
            risks=risks,
            blockingIssues=blockers,
            optionalImprovements=[],
            proposedToolActions=tool_actions,
            assumptions=["Heuristic specialist output (E2E/mock path)."],
            confidence=0.82,
        )
