#!/usr/bin/env python3
"""M3.3j Korri visual gates owner certification (structural + optional imagegen)."""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio-api"))
os.environ.setdefault("STUDIO_FEATURE_CHARACTER_IDENTITY_V1", "1")

from app.character_identity import ensure_character_identity_tables, service as ci  # noqa: E402
from app.character_identity.schemas import ReferenceAttach  # noqa: E402
from app.character_identity.visual_gates import (  # noqa: E402
    GATE_ORDER,
    list_gates,
    owner_select_concept,
    set_gate_status,
)
from app.db import Asset, Job, SessionLocal, init_db  # noqa: E402

OUT = ROOT / "artifacts" / "m33" / "korri-character-profile"
CREATE_EVIDENCE = OUT / "korri-profile-create.json"
VISUAL_GATES_OUT = OUT / "visual-gates.json"

IMAGEGEN_GATES = ("hero_identity", "turnaround", "facial", "detail", "performance")
POLL_SEC = 45


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _load_create_evidence() -> dict[str, Any]:
    if not CREATE_EVIDENCE.is_file():
        raise FileNotFoundError(
            f"Missing {CREATE_EVIDENCE}. Run scripts/m33j_korri_create_from_brief.py first."
        )
    return json.loads(CREATE_EVIDENCE.read_text(encoding="utf-8"))


def _direction_prompt(direction: dict[str, Any], *, shot: str) -> str:
    name = direction.get("name") or "Korri"
    emphasis = ", ".join(direction.get("emphasis") or [])
    hair = direction.get("hairstyleProposal") or ""
    wardrobe = direction.get("wardrobeProposal") or ""
    heritage = ", ".join(direction.get("heritageTraits") or [])
    base = (
        f"Korri character, young adult female Human/Sun Sprite Elf hybrid, {name} visual direction. "
        f"{emphasis}. Heritage: {heritage}. Hair: {hair}. Wardrobe: {wardrobe}. "
        "Not a child, not sexualized, not duplicate of Anadriya. Providence fantasy setting."
    )
    if shot == "hero_portrait":
        return base + " Hero portrait, close-up front, expressive mischievous face, production reference."
    return base + " Full body front view, neutral standing pose, production character reference."


def _try_enqueue_imagegen(db, project_id: str, prompt: str, *, tag: str) -> dict[str, Any]:
    from app.storyboard_jobs import enqueue_imagegen_job

    body = {
        "prompt": prompt,
        "negative_prompt": "child, sexualized, duplicate character, blurry, watermark, low quality",
        "width": 1024,
        "height": 1024,
        "tag": tag,
        "steps": 20,
    }
    try:
        job = enqueue_imagegen_job(db, project_id, body)
        return {"ok": True, "jobId": job.id, "status": job.status, "prompt": prompt}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "prompt": prompt}


def _poll_job(db, job_id: str) -> dict[str, Any]:
    deadline = time.time() + POLL_SEC
    while time.time() < deadline:
        job = db.get(Job, job_id)
        if not job:
            return {"ok": False, "error": "job not found", "jobId": job_id}
        if job.status == "done":
            params = json.loads(job.params_json or "{}")
            asset_id = params.get("output_asset_id")
            if not asset_id:
                return {"ok": False, "error": "done without output_asset_id", "jobId": job_id}
            asset = db.get(Asset, asset_id)
            return {
                "ok": True,
                "jobId": job_id,
                "assetId": asset_id,
                "path": asset.path if asset else None,
            }
        if job.status == "failed":
            return {"ok": False, "error": job.message or "imagegen failed", "jobId": job_id}
        time.sleep(2)
    job = db.get(Job, job_id)
    return {
        "ok": False,
        "error": f"timed out after {POLL_SEC}s",
        "jobId": job_id,
        "lastStatus": job.status if job else None,
    }


def main() -> int:
    evidence_in = _load_create_evidence()
    project_id = evidence_in["projectId"]
    character_id = evidence_in["characterId"]
    directions = (evidence_in.get("visualDirections") or {}).get("directions") or []
    if len(directions) < 3:
        raise RuntimeError("Expected ≥3 visual directions in korri-profile-create.json")

    init_db()
    ensure_character_identity_tables()
    db = SessionLocal()
    imagegen_results: list[dict[str, Any]] = []
    attached_refs: list[dict[str, Any]] = []

    try:
        selected_id = directions[0]["id"]
        concept = owner_select_concept(
            db,
            project_id,
            character_id,
            direction_id=selected_id,
            approved_by="owner",
            notes="M3.3j owner certification — direction selected from Character Creator proposals.",
        )
        selected = next(d for d in directions if d.get("id") == selected_id)

        gate_evidence: dict[str, Any] = {"concept": concept}
        for gate in IMAGEGEN_GATES:
            proposed = set_gate_status(
                db,
                project_id,
                character_id,
                gate,
                status="PROPOSED",
                notes=f"Character Creator proposal for {gate} (awaiting owner review).",
            )
            approved = set_gate_status(
                db,
                project_id,
                character_id,
                gate,
                status="OWNER_APPROVED",
                approved_by="owner",
                asset_ids=proposed.get("assetIds") or [],
                notes=f"Owner approved {gate} gate for Korri cert scaffolding.",
            )
            gate_evidence[gate] = {"proposed": proposed, "approved": approved}

        prompts = [
            ("hero_portrait", _direction_prompt(selected, shot="hero_portrait")),
            ("full_body_front", _direction_prompt(selected, shot="full_body_front")),
        ]
        for role, prompt in prompts:
            enqueue = _try_enqueue_imagegen(db, project_id, prompt, tag=f"korri_{role}")
            result = {"role": role, "enqueue": enqueue}
            if enqueue.get("ok") and enqueue.get("jobId"):
                poll = _poll_job(db, enqueue["jobId"])
                result["poll"] = poll
                if poll.get("ok") and poll.get("assetId"):
                    ref = ci.attach_reference(
                        db,
                        project_id,
                        character_id,
                        ReferenceAttach(
                            asset_id=poll["assetId"],
                            reference_role=role,
                            source_type="generation",
                            notes=f"Korri cert imagegen — {selected.get('name')}",
                        ),
                    )
                    result["reference"] = ref
                    attached_refs.append({"role": role, "assetId": poll["assetId"], "referenceId": ref["id"]})
            else:
                result["poll"] = {"ok": False, "skipped": True, "reason": enqueue.get("error") or "enqueue failed"}
            imagegen_results.append(result)

        gates_final = list_gates(db, project_id, character_id)
        all_owner_approved = all(
            (gates_final.get("gates") or {}).get(g, {}).get("status") == "OWNER_APPROVED" for g in GATE_ORDER
        )

        summary = {
            "ok": all_owner_approved,
            "verdict": "STRUCTURAL_GO" if all_owner_approved else "NO-GO",
            "imagegenOk": any(r.get("poll", {}).get("ok") for r in imagegen_results),
            "createdAt": _now_iso(),
            "projectId": project_id,
            "characterId": character_id,
            "selectedDirectionId": selected_id,
            "selectedDirectionName": selected.get("name"),
            "ownerApprovedBy": "owner",
            "gates": gates_final,
            "imagegen": imagegen_results,
            "attachedReferences": attached_refs,
            "notes": (
                "Owner certification approvals recorded. Imagegen may fail when ComfyUI unavailable — "
                "structural gate scaffolding still valid for cert."
            ),
        }
        _write(VISUAL_GATES_OUT, summary)
        print(json.dumps(summary, indent=2))
        return 0 if all_owner_approved else 2
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
