#!/usr/bin/env python3
"""M3.3j Korri voice clone certification — voice/Korri_Voice_Sample.mp3 only."""

from __future__ import annotations

import json
import os
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio-api"))
os.environ.setdefault("STUDIO_FEATURE_CHARACTER_IDENTITY_V1", "1")

from app.character_identity import ensure_character_identity_tables, service as ci  # noqa: E402
from app.character_identity.schemas import DialogueGenerateRequest, VoiceConsentCreate  # noqa: E402
from app.character_identity.voice import provider_readiness, validate_voice_reference  # noqa: E402
from app.character_identity.voice_runtime import run_generate_dialogue, run_voice_clone  # noqa: E402
from app.codirector.m210b.qwen_voice_install import runtime_ready  # noqa: E402
from app.config import settings  # noqa: E402
from app.db import Asset, SessionLocal, init_db  # noqa: E402

OUT = ROOT / "artifacts" / "m33" / "korri-character-profile" / "voice"
CREATE_EVIDENCE = ROOT / "artifacts" / "m33" / "korri-character-profile" / "korri-profile-create.json"
VOICE_SAMPLE = ROOT / "voice" / "Korri_Voice_Sample.mp3"

KORRI_DIALOGUE = (
    "Oh great, another plan. Let me guess — we're waiting until the universe sends a memo?",
    "Anadriya, stop acting like the sky is going to file a complaint. It won't.",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(rel: str, data: dict) -> Path:
    path = OUT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def _register_voice_asset(db, project_id: str, src: Path) -> dict:
    dest_dir = Path(settings.data_dir) / "projects" / project_id / "assets" / "character_voice"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"korri_voice_sample_{uuid.uuid4().hex[:8]}{src.suffix}"
    shutil.copy2(src, dest)
    aid = str(uuid.uuid4())
    db.add(
        Asset(
            id=aid,
            project_id=project_id,
            kind="audio",
            filename=src.name,
            path=str(dest),
            tag="character_voice_reference",
            prompt_meta_json=json.dumps(
                {"source": "korri_voice_cert", "original": str(src.relative_to(ROOT))}
            ),
        )
    )
    db.commit()
    return {"assetId": aid, "path": str(dest), "filename": src.name}


def main() -> int:
    if not VOICE_SAMPLE.is_file():
        summary = {"ok": False, "verdict": "NO-GO", "reason": f"Missing {VOICE_SAMPLE}"}
        _write("cert-summary.json", summary)
        print(json.dumps(summary, indent=2))
        return 3

    if not CREATE_EVIDENCE.is_file():
        summary = {
            "ok": False,
            "verdict": "NO-GO",
            "reason": "Run scripts/m33j_korri_create_from_brief.py first.",
        }
        _write("cert-summary.json", summary)
        print(json.dumps(summary, indent=2))
        return 3

    create = json.loads(CREATE_EVIDENCE.read_text(encoding="utf-8"))
    project_id = create["projectId"]
    character_id = create["characterId"]

    clone_ready, clone_detail = runtime_ready("qwen_voice_clone_17b")
    readiness = provider_readiness()
    _write("provider-readiness.json", readiness)

    validation = validate_voice_reference(str(VOICE_SAMPLE), transcript="Korri voice reference sample.")
    _write(
        "reference-validation.json",
        {
            **validation,
            "sourceFile": str(VOICE_SAMPLE.relative_to(ROOT)),
            "note": "Metadata only — raw MP3 not embedded in evidence.",
        },
    )

    init_db()
    ensure_character_identity_tables()
    db = SessionLocal()
    try:
        registered = _register_voice_asset(db, project_id, VOICE_SAMPLE)
        _write("registered-reference.json", registered)

        if not clone_ready:
            summary = {
                "ok": False,
                "verdict": "NO-GO",
                "reason": "Qwen voice clone not runtime-ready",
                "clone": clone_detail,
                "validation": validation,
                "registered": registered,
            }
            _write("cert-summary.json", summary)
            print(json.dumps(summary, indent=2))
            return 3

        clone_body = SimpleNamespace(
            name="Korri Voice (clone)",
            reference_path=registered["path"],
            transcript="Korri voice reference sample.",
            test_line=KORRI_DIALOGUE[0],
            consent=VoiceConsentCreate(
                source_owner_name="Adept Film Works",
                performer_name="Korri (voice performer)",
                authority_type="rights_holder",
                consent_confirmed=True,
                commercial_use_allowed=True,
                synthetic_generation_allowed=True,
                project_scope="project",
                confirmed_by="owner",
            ),
        )
        clone_result = run_voice_clone(db, project_id, character_id, clone_body)
        _write(
            "clone-preview.json",
            {
                "voiceProfileId": clone_result.get("id"),
                "previewAssetId": clone_result.get("preview_asset_id"),
                "status": clone_result.get("status"),
                "validation": clone_result.get("validation"),
            },
        )
        clone_voice_id = clone_result["id"]
        ci.approve_voice_profile(db, project_id, character_id, clone_voice_id)

        dialogue_lines = []
        for line in KORRI_DIALOGUE:
            dlg = run_generate_dialogue(
                db,
                project_id,
                character_id,
                clone_voice_id,
                DialogueGenerateRequest(text=line, allow_kokoro_fallback=False),
            )
            dialogue_lines.append(
                {
                    "text": line,
                    "assetId": dlg.get("asset_id") or dlg.get("assetId"),
                    "path": dlg.get("path"),
                    "durationSec": dlg.get("duration_sec") or dlg.get("durationSec"),
                }
            )
        _write("dialogue-two-lines.json", {"lines": dialogue_lines, "voiceProfileId": clone_voice_id})

        evidence = {
            "ok": bool(clone_result.get("preview_asset_id")) and len(dialogue_lines) == 2,
            "verdict": "GO" if clone_result.get("preview_asset_id") else "NO-GO",
            "projectId": project_id,
            "characterId": character_id,
            "cloneVoiceId": clone_voice_id,
            "referenceAssetId": registered["assetId"],
            "validationDurationSec": validation.get("durationSec") or validation.get("duration"),
            "dialogueCount": len(dialogue_lines),
            "finishedAt": _now_iso(),
            "mediaConstraint": "Only voice/Korri_Voice_Sample.mp3 used; no character sheet.",
        }
        _write("cert-summary.json", evidence)
        print(json.dumps(evidence, indent=2))
        return 0 if evidence["ok"] else 3
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
