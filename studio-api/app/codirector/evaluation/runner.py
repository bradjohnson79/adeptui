"""Co-Director M2.4 prompt evaluation runner."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..intelligence.intent import classify_intent
from ..intelligence.planning import PlanBuilder
from ..intelligence.schemas import SpecialistFinding
from ..intelligence.specialist_selector import SpecialistSelector
from ..intelligence.synthesis import SynthesisEngine
from ..intelligence.specialist_runner import SpecialistRunner
from ..prompts.loader import PromptLibrary

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@dataclass
class EvaluationResult:
    scenario_id: str
    passed: bool
    checks: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenarioId": self.scenario_id,
            "passed": self.passed,
            "checks": self.checks,
            "failures": self.failures,
        }


class EvaluationRunner:
    def __init__(self, fixtures_dir: Path | None = None) -> None:
        self.fixtures_dir = fixtures_dir or FIXTURES_DIR
        self.selector = SpecialistSelector()
        self.synthesis = SynthesisEngine()
        self.plan_builder = PlanBuilder()
        self.runner = SpecialistRunner()
        self.prompt_library = PromptLibrary()

    def load_scenarios(self) -> list[dict[str, Any]]:
        scenarios: list[dict[str, Any]] = []
        for path in sorted(self.fixtures_dir.glob("scenario_*.json")):
            scenarios.append(json.loads(path.read_text(encoding="utf-8")))
        return scenarios

    def evaluate_scenario(self, scenario: dict[str, Any]) -> EvaluationResult:
        message = str(scenario.get("userMessage") or "")
        intent = classify_intent(message)
        selection = self.selector.select(intent)
        result = EvaluationResult(scenario_id=str(scenario.get("id") or "unknown"), passed=True)

        expected_intent = scenario.get("expectedIntent")
        if expected_intent and intent.primaryIntent != expected_intent:
            result.failures.append(f"intent expected {expected_intent}, got {intent.primaryIntent}")
        else:
            result.checks.append("intent")

        expected_playbook = scenario.get("expectedPlaybook")
        if expected_playbook and intent.playbookId != expected_playbook:
            result.failures.append(f"playbook expected {expected_playbook}, got {intent.playbookId}")
        elif expected_playbook:
            result.checks.append("playbook")

        expected_specialists = scenario.get("expectedSpecialists") or []
        if expected_specialists:
            selected = set(selection.all_selected)
            missing = [sid for sid in expected_specialists if sid not in selected]
            if missing:
                result.failures.append(f"missing specialists: {missing}")
            else:
                result.checks.append("specialists")

        if scenario.get("maxSpecialists"):
            if len(selection.all_selected) > int(scenario["maxSpecialists"]):
                result.failures.append("too many specialists selected")

        findings = []
        for sid in selection.all_selected[:3]:
            definition = self.selector.registry.require(sid)
            finding = SpecialistFinding(
                specialistId=sid,
                summary=f"{definition.display_name} evaluated fixture.",
                recommendation="Proceed with bounded context.",
                confidence=0.8,
            )
            findings.append(finding)
        synthesis = self.synthesis.synthesize(user_message=message, intent=intent, findings=findings)
        if scenario.get("requiresApproval") and not intent.requiresApproval and scenario.get("expectedTool"):
            result.failures.append("expected approval requirement")
        else:
            result.checks.append("synthesis")

        if scenario.get("expectedTool"):
            plan = self.plan_builder.build(
                project_id="eval-project",
                intent=intent,
                synthesis=synthesis,
                prompt_versions=self.prompt_library.version_map(),
            )
            tool_ids = [step.toolId for step in plan.steps if step.toolId]
            if scenario["expectedTool"] not in tool_ids:
                result.failures.append(f"expected tool {scenario['expectedTool']} not in plan")
            else:
                result.checks.append("plan-tool")

        if self.prompt_library.diagnostics.skipped:
            result.failures.append(f"{self.prompt_library.diagnostics.skipped} invalid prompt files")

        result.passed = not result.failures
        return result

    def run_all(self) -> list[EvaluationResult]:
        return [self.evaluate_scenario(scenario) for scenario in self.load_scenarios()]
