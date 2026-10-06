"""Co-Director CRS production loop smoke — one real job id, not wrapper complete."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio-api"))

from app.codirector.conversation.foundation.speech_act import classify_speech_act, resolve_production_action
from app.codirector.conversation.foundation.sufficiency import evaluate_sufficiency
from app.codirector.execution.crs_lineage import bind_crs_child, extract_crs_job_id
from app.codirector.execution.contracts import ChildJobStatus, ExecutionPlan, ExecutionStatus
from app.codirector.routing.unified_intent import classify_intent


def main() -> int:
    text = "Create Korri's CRS."
    act = classify_speech_act(text)
    action = resolve_production_action(text)
    intent = classify_intent(text, {})
    sufficiency = evaluate_sufficiency(
        user_message=text,
        speech_act="COMMAND",
        project_id="2347bf46-3762-4763-86c5-4a6032522278",
        bound_character_id="c49371ed-ba6b-4c16-ba98-a8b28b72118b",
        db=None,
    )
    plan = ExecutionPlan(
        execution_id="smoke-exec",
        capability="character.generate_visual_sheet",
        project_id="2347bf46-3762-4763-86c5-4a6032522278",
    )
    bind_crs_child(
        plan,
        tool_id="character_creator.propose_visual_sheet",
        tool_result={
            "ok": True,
            "characterId": "c49371ed-ba6b-4c16-ba98-a8b28b72118b",
            "pack": {
                "jobs": {"hero": {"jobId": "job-qwen-smoke", "status": "queued"}},
                "candidates": [{"jobId": "job-qwen-smoke"}],
            },
        },
        ok=True,
        error=None,
        fallback_job_id="synthetic",
    )
    report = {
        "speech_act": act,
        "action": action,
        "capability": intent.capability,
        "context_sufficient": sufficiency.context_sufficient,
        "production_job_id": plan.plan_data.get("production_job_id"),
        "child_status": plan.child_jobs[0].status.value,
        "plan_status": plan.status.value,
        "extracted": extract_crs_job_id({"jobs": {"hero": {"jobId": "job-qwen-smoke"}}}),
    }
    print(json.dumps(report, indent=2))
    ok = (
        act == "COMMAND"
        and action == "create_character_reference_sheet"
        and intent.capability == "character.generate_visual_sheet"
        and sufficiency.context_sufficient
        and plan.child_jobs[0].job_id == "job-qwen-smoke"
        and plan.child_jobs[0].status == ChildJobStatus.QUEUED
        and plan.status == ExecutionStatus.QUEUED
    )
    print("PASS — CODIRECTOR CRS PRODUCTION LOOP SMOKE" if ok else "FAIL — CRS production smoke")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
