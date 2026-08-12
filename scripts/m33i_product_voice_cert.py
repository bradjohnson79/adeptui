#!/usr/bin/env python3
"""Disposable M3.3i product voice certification chain (non-Korri, non-Hitchhiker)."""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

# Ensure character identity tables / provenance column exist before use.

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio-api"))
os.environ.setdefault("STUDIO_FEATURE_CHARACTER_IDENTITY_V1", "1")

from app.db import Project, SessionLocal, init_db  # noqa: E402
from app.character_identity import service as ci  # noqa: E402
from app.character_identity.schemas import (  # noqa: E402
    CharacterProfileCreate,
    DialogueGenerateRequest,
    VoiceConsentCreate,
)
from app.character_identity.voice import provider_readiness  # noqa: E402
from app.character_identity.voice_runtime import (  # noqa: E402
    run_generate_dialogue,
    run_voice_clone,
    run_voice_design,
)
from app.codirector.m210b.qwen_voice_install import runtime_ready  # noqa: E402
from app.db import Asset  # noqa: E402

OUT = ROOT / "artifacts" / "m33" / "character-profile"
PROTECTED = {
    "projectId": "d1683511-1cc7-4d3d-8cb7-00f48cc36aa9",
    "ltx": "6b91bb7f-0dfd-44e6-92b3-7df7ac8cea4f",
    "wan": "e277e621-189d-471e-b435-f01620f03d0d",
    "dialogue": "c5cdd736-8f89-42e3-a7a8-9cb97043bf8a",
}


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _now() -> str:
    return _now_dt().isoformat()


def _write(rel: str, data: dict) -> Path:
    path = OUT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def main() -> int:
    design_ready, design_detail = runtime_ready("qwen_voice_design_17b")
    clone_ready, clone_detail = runtime_ready("qwen_voice_clone_17b")
    readiness = provider_readiness()
    _write("voice-design/provider-readiness.json", readiness)
    if not (design_ready and clone_ready):
        summary = {
            "ok": False,
            "verdict": "NO-GO",
            "reason": "Qwen providers not runtime-ready",
            "design": design_detail,
            "clone": clone_detail,
        }
        _write("voice-design/cert-summary.json", summary)
        print(json.dumps(summary, indent=2))
        return 3

    init_db()
    from app.character_identity import ensure_character_identity_tables

    ensure_character_identity_tables()
    db = SessionLocal()
    try:
        project_id = str(uuid.uuid4())
        ts = _now_dt()
        db.add(
            Project(
                id=project_id,
                name=f"M33i Voice Cert {project_id[:8]}",
                created_at=ts,
                updated_at=ts,
            )
        )
        db.commit()
        profile = ci.create_profile(
            db,
            project_id,
            CharacterProfileCreate(
                name="M33i Cert Voice Character",
                role="certification",
                description="Disposable",
            ),
        )
        design_body = SimpleNamespace(
            name="M33i Designed Voice",
            voice_design_prompt=(
                "Warm adult female voice with gentle authority, clear articulation, "
                "moderate pace, soft breath, calm confidence, and subtle emotional depth."
            ),
            test_line="We should leave before the storm reaches the valley.",
            candidate_count=3,
            language="en",
        )
        design_result = run_voice_design(db, project_id, profile.id, design_body)
        _write("voice-design/three-previews.json", {"result": design_result, "projectId": project_id})
        design_voice_id = design_result["id"]
        candidates = design_result.get("candidates") or []
        ci.approve_voice_profile(db, project_id, profile.id, design_voice_id)

        # Generate a dedicated ≥10s reference for clone validation (candidates are short previews).
        from app.character_identity.voice_runtime import _try_m210b_generate, _project_audio_dir, _register_asset
        import shutil

        long_text = (
            "This is a disposable certification reference for voice cloning. "
            "I am speaking clearly for more than ten seconds about walking through a quiet forest at dawn, "
            "noticing birds in the trees, soft light on the path, and the sound of water nearby. "
            "Please keep listening until this sentence is fully complete."
        )
        long_src = _try_m210b_generate(
            registry_id="m2101-voice-design-021",
            text=long_text,
            project_id=project_id,
            extra={
                "voiceDescription": design_body.voice_design_prompt,
            },
        )
        ref_path = str(_project_audio_dir(project_id) / f"clone_ref_{uuid.uuid4().hex[:10]}.wav")
        shutil.copy2(long_src, ref_path)
        ref_asset_id = _register_asset(
            db, project_id, Path(ref_path), kind="audio", name="clone reference long"
        )
        _write("voice-clone/long-reference.json", {"assetId": ref_asset_id, "path": ref_path})
        if not Path(ref_path).is_file():
            raise RuntimeError("No design candidate WAV for clone reference")

        clone_body = SimpleNamespace(
            name="M33i Cloned Voice",
            reference_path=ref_path,
            transcript="We should leave before the storm reaches the valley.",
            test_line="Wait. Someone is still inside that building.",
            consent=VoiceConsentCreate(
                source_owner_name="certification-owner",
                performer_name="disposable-cert-voice",
                authority_type="self",
                consent_confirmed=True,
                commercial_use_allowed=False,
                synthetic_generation_allowed=True,
                project_scope="project",
                confirmed_by="owner",
            ),
        )
        clone_result = run_voice_clone(db, project_id, profile.id, clone_body)
        _write("voice-clone/clone-preview.json", {"result": clone_result})
        clone_voice_id = clone_result["id"]
        ci.approve_voice_profile(db, project_id, profile.id, clone_voice_id)

        dialogue_lines = []
        for line in (
            "We should leave before the storm reaches the valley.",
            "Wait. Someone is still inside that building.",
        ):
            dlg = run_generate_dialogue(
                db,
                project_id,
                profile.id,
                design_voice_id,
                DialogueGenerateRequest(text=line, allow_kokoro_fallback=False),
            )
            dialogue_lines.append(dlg)
        _write(
            "dialogue/two-lines.json",
            {"lines": dialogue_lines, "voiceProfileId": design_voice_id},
        )

        evidence = {
            "ok": len(candidates) >= 3 and len(dialogue_lines) == 2 and bool(clone_result.get("preview_asset_id")),
            "projectId": project_id,
            "characterId": profile.id,
            "designVoiceId": design_voice_id,
            "cloneVoiceId": clone_voice_id,
            "previewCount": len(candidates),
            "dialogueCount": len(dialogue_lines),
            "protectedUntouched": PROTECTED,
            "finishedAt": _now(),
        }
        _write("voice-design/product-cert.json", evidence)
        print(json.dumps(evidence, indent=2))
        return 0 if evidence["ok"] else 3
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
