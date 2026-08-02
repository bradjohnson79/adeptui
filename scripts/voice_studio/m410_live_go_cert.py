"""M4.10 live GO-gate: multi-take IndexTTS2 + timeline + lipsync evidence."""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8758"
OUT = Path("artifacts/m410/live-go-cert.json")


def req(method: str, path: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    try:
        with urllib.request.urlopen(request, timeout=600) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} -> {exc.code}: {detail}") from exc


def main() -> int:
    evidence: dict = {"startedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    status = req("GET", "/api/voice-performance/m410/runtime/status")
    evidence["runtimeStatus"] = status
    if not status.get("ready"):
        print("NO-GO: IndexTTS2 not ready:", status.get("message"))
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        return 2

    projects = req("GET", "/api/projects")
    items = projects if isinstance(projects, list) else projects.get("items") or projects.get("projects") or []
    project = next((p for p in items if "Korri" in str(p.get("name") or "")), None)
    if not project:
        created = req("POST", "/api/projects", {"name": "Korri Character Production"})
        project_id = str(created.get("id") or created.get("projectId"))
    else:
        project_id = str(project["id"])
    evidence["projectId"] = project_id

    seed = req("POST", f"/api/projects/{project_id}/characters/seed-korri", {})
    character_id = str(seed.get("id"))
    evidence["characterId"] = character_id

    voice_ws = req("GET", f"/api/projects/{project_id}/characters/{character_id}/voice")
    voices = voice_ws.get("voices") or []
    approved = next(
        (
            v
            for v in voices
            if str(v.get("approval_status") or "").lower() == "approved"
            or str(v.get("status") or "").lower() == "approved"
        ),
        None,
    )
    if not approved and voice_ws.get("activeVoice"):
        av = voice_ws["activeVoice"]
        if str(av.get("approval_status") or "").lower() == "approved":
            approved = av
    if not approved:
        evidence["voiceWorkspace"] = {
            "activeVoiceProfileId": voice_ws.get("activeVoiceProfileId"),
            "voiceCount": len(voices),
        }
        print("NO-GO: no approved Qwen Voice Identity for Korri")
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        return 3

    voice_before = {
        "id": approved.get("id"),
        "version": approved.get("version") or approved.get("version_number"),
        "approval_status": approved.get("approval_status") or approved.get("status"),
        "reference_asset_id": approved.get("reference_asset_id") or approved.get("referenceAssetId"),
        "approved_preview_asset_id": approved.get("approved_preview_asset_id")
        or approved.get("approvedPreviewAssetId"),
    }
    evidence["voiceIdentityBefore"] = voice_before

    record = req(
        "POST",
        "/api/voice-performance/m410/records",
        {
            "projectId": project_id,
            "characterId": character_id,
            "voiceIdentityId": voice_before["id"],
            "voiceIdentityVersion": str(voice_before.get("version") or "1"),
            "dialogueText": "I never cuss.",
            "language": "en",
            "directionMode": "codirector",
            "scriptElementId": "m410-live-line-1",
            "sceneId": None,
        },
    )
    record_id = record["id"]
    evidence["recordId"] = record_id

    planned = req(
        "POST",
        f"/api/voice-performance/m410/records/{record_id}/performance-plan",
        {"context": {"parenthetical": "quietly", "objective": "be believed"}},
    )
    evidence["codirectorPlan"] = planned.get("performancePlan") or planned.get("codirectorPlan")

    takes1 = req(
        "POST",
        f"/api/voice-performance/m410/records/{record_id}/generate-takes",
        {"count": 1, "labels": ["Take 1 — Co-Director recommended"]},
    )
    evidence["take1"] = takes1

    req(
        "POST",
        f"/api/voice-performance/m410/records/{record_id}/direction-mode",
        {
            "directionMode": "manual",
            "performancePlan": {
                "primaryEmotion": "Embarrassed",
                "secondaryEmotion": "Defensive",
                "intensity": 0.55,
                "delivery": "Restrained",
                "pacing": "Measured",
                "breath": "Light",
                "emphasis": ["never"],
                "subtext": "She wants belief without sounding defensive",
            },
        },
    )
    # Supported IndexTTS2 vectors only (no invented dimensions)
    req(
        "PATCH",
        f"/api/voice-performance/m410/records/{record_id}/performance-plan",
        {
            "mode": "manual",
            "emotionSource": "advanced_mix",
            "emotionVector": {"sadness": 0.28, "fear": 0.12, "joy": 0.05, "anger": 0.05},
            "performancePlan": {
                "primaryEmotion": "Embarrassed sincerity",
                "intensity": 0.4,
                "delivery": "Soft and restrained",
                "pacing": "Natural",
                "breath": "Small inhale",
                "emphasis": ["never"],
            },
        },
    )
    takes2 = req(
        "POST",
        f"/api/voice-performance/m410/records/{record_id}/generate-takes",
        {"count": 1, "labels": ["Take 2 — alternate emotional interpretation"]},
    )
    evidence["take2"] = takes2

    req(
        "PATCH",
        f"/api/voice-performance/m410/records/{record_id}/performance-plan",
        {
            "mode": "manual",
            "emotionSource": "preset",
            "performancePlan": {
                "primaryEmotion": "Calm",
                "intensity": 0.35,
                "delivery": "Conversational",
                "pacing": "Natural",
                "breath": "None",
            },
        },
    )
    takes3 = req(
        "POST",
        f"/api/voice-performance/m410/records/{record_id}/generate-takes",
        {"count": 1, "labels": ["Take 3 — manual direction"]},
    )
    evidence["take3"] = takes3

    listed = req("GET", f"/api/voice-performance/m410/records/{record_id}/takes")
    evidence["allTakes"] = listed
    completed = [t for t in (listed.get("takes") or []) if t.get("status") == "completed" and t.get("audioAssetId")]
    if len(completed) < 1:
        print("NO-GO: no completed takes with audio")
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        return 4

    approve_id = completed[0]["id"]
    approved_take = req(
        "POST",
        f"/api/voice-performance/m410/records/{record_id}/takes/{approve_id}/approve",
        {"approvedBy": "m410-live-cert"},
    )
    evidence["approved"] = approved_take

    compare = req(
        "POST",
        f"/api/voice-performance/m410/records/{record_id}/compare",
        {"takeIds": [t["id"] for t in completed[:2]]},
    )
    evidence["compare"] = compare

    timeline = req(
        "POST",
        f"/api/voice-performance/m410/records/{record_id}/timeline",
        {"trackId": "dialogue-main", "startMs": 0, "confirmReplace": True},
    )
    evidence["timeline"] = timeline

    lipsync = req(
        "POST",
        f"/api/voice-performance/m410/records/{record_id}/lipsync",
        {"confirm": True, "setSceneAudioAsset": True},
    )
    evidence["lipsync"] = lipsync

    voice_ws_after = req("GET", f"/api/projects/{project_id}/characters/{character_id}/voice")
    voices_after = voice_ws_after.get("voices") or []
    approved_after = next((v for v in voices_after if v.get("id") == voice_before["id"]), None)
    evidence["voiceIdentityAfter"] = {
        "id": (approved_after or {}).get("id"),
        "version": (approved_after or {}).get("version") or (approved_after or {}).get("version_number"),
        "approval_status": (approved_after or {}).get("approval_status"),
        "reference_asset_id": (approved_after or {}).get("reference_asset_id")
        or (approved_after or {}).get("referenceAssetId"),
    }
    evidence["voiceIdentityUnchanged"] = evidence["voiceIdentityAfter"].get("id") == voice_before.get("id") and (
        evidence["voiceIdentityAfter"].get("version") == voice_before.get("version")
        or voice_before.get("version") is None
    )

    # scene batch (2 lines) — plans only + one generate if possible
    batch = req(
        "POST",
        "/api/voice-performance/m410/scene-batch",
        {
            "projectId": project_id,
            "items": [
                {
                    "characterId": character_id,
                    "voiceIdentityId": voice_before["id"],
                    "voiceIdentityVersion": str(voice_before.get("version") or "1"),
                    "dialogueText": "Line one — restrained uncertainty.",
                    "directionMode": "codirector",
                    "scriptElementId": "m410-scene-line-1",
                },
                {
                    "characterId": character_id,
                    "voiceIdentityId": voice_before["id"],
                    "voiceIdentityVersion": str(voice_before.get("version") or "1"),
                    "dialogueText": "Line two — quiet collapse.",
                    "directionMode": "codirector",
                    "scriptElementId": "m410-scene-line-2",
                },
            ],
        },
    )
    evidence["sceneBatch"] = {
        "ok": batch.get("ok"),
        "recordCount": len(batch.get("records") or []),
        "progression": batch.get("sceneProgressionPlans"),
        "autoApproved": any(r.get("approvedTakeId") for r in (batch.get("records") or [])),
    }

    evidence["finishedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    evidence["verdictCandidate"] = (
        "GO_CANDIDATE"
        if evidence.get("voiceIdentityUnchanged")
        and approved_take.get("approvedTakeId")
        and timeline.get("persisted")
        and len(completed) >= 1
        else "CONDITIONAL"
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(OUT), "verdictCandidate": evidence["verdictCandidate"], "completedTakes": len(completed)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
