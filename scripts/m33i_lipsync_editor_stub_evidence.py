#!/usr/bin/env python3
"""Record disposable lipsync/editor handoff evidence for M3.3i when runtime allows.

Uses product-cert dialogue assets. Does not touch Hitchhiker scenes.
If LatentSync/Comfy unavailable, writes honest NO-GO evidence for those stages only.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "m33" / "character-profile"
PRODUCT = OUT / "voice-design" / "product-cert.json"
DIALOGUE = OUT / "dialogue" / "two-lines.json"


def main() -> int:
    now = datetime.now(timezone.utc).isoformat()
    if not PRODUCT.is_file():
        payload = {"ok": False, "reason": "Run m33i_product_voice_cert.py first", "at": now}
        (OUT / "lipsync" / "cert.json").parent.mkdir(parents=True, exist_ok=True)
        (OUT / "lipsync" / "cert.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps(payload, indent=2))
        return 3
    product = json.loads(PRODUCT.read_text(encoding="utf-8"))
    dialogue = json.loads(DIALOGUE.read_text(encoding="utf-8")) if DIALOGUE.is_file() else {}
    api = os.environ.get("STUDIO_API_BASE", "http://127.0.0.1:8758")
    evidence = {
        "ok": False,
        "at": now,
        "projectId": product.get("projectId"),
        "characterId": product.get("characterId"),
        "voiceProfileId": product.get("designVoiceId"),
        "dialogue": dialogue,
        "protected": product.get("protectedUntouched"),
        "api": api,
        "note": (
            "Disposable lipsync/editor requires a short local video + LatentSync runtime. "
            "Voice product cert is independent and already proven."
        ),
    }
    try:
        import urllib.request

        with urllib.request.urlopen(f"{api}/api/health", timeout=3) as resp:
            evidence["apiHealth"] = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        evidence["apiHealthError"] = str(exc)
        evidence["lipsync"] = "SKIPPED_API_UNAVAILABLE"
        evidence["editor"] = "SKIPPED_API_UNAVAILABLE"
        (OUT / "lipsync").mkdir(parents=True, exist_ok=True)
        (OUT / "editor").mkdir(parents=True, exist_ok=True)
        (OUT / "lipsync" / "cert.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        (OUT / "editor" / "cert.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        print(json.dumps(evidence, indent=2))
        return 3

    # Prefer explicit ADEPT_M33_LIPSYNC=1 with pre-created disposable scene id.
    scene_id = os.environ.get("ADEPT_M33_DISPOSABLE_SCENE_ID", "").strip()
    if not scene_id:
        evidence["lipsync"] = "PENDING_DISPOSABLE_SCENE"
        evidence["editor"] = "PENDING_DISPOSABLE_SCENE"
        evidence["message"] = (
            "Set ADEPT_M33_DISPOSABLE_SCENE_ID to a non-Hitchhiker scene with video, "
            "then re-run with ADEPT_M33_LIPSYNC=1."
        )
        (OUT / "lipsync").mkdir(parents=True, exist_ok=True)
        (OUT / "editor").mkdir(parents=True, exist_ok=True)
        (OUT / "lipsync" / "cert.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        (OUT / "editor" / "cert.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        print(json.dumps(evidence, indent=2))
        return 3

    evidence["sceneId"] = scene_id
    evidence["ok"] = False
    evidence["lipsync"] = "READY_TO_SUBMIT"
    (OUT / "lipsync" / "cert.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
