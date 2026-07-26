#!/usr/bin/env python3
"""Generate Adept UI v1.0 native capability baseline (planning/readiness artifact)."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SECTION_STATUS = {
    # M2.10 re-audit (2026-07-26) under redefined M2.9 DoD.
    # CONNECTED = wired to currently available native capability (not fixture-as-production).
    # PARTIAL = available native placement/process wired; generative generate deferred to M2.10.
    "Image Production": "CONNECTED",
    "Frame Production": "CONNECTED",
    "Text-to-Video and Image-to-Video": "CONNECTED",
    "Director Timeline Generation": "CONNECTED",
    "Lip Sync Timeline": "CONNECTED",
    "Mouth Rectangle Control": "CONNECTED",
    "Audio Production": "PARTIAL",
    "Editing and Post-Production": "CONNECTED",
    "SFX": "PARTIAL",
    "Music": "PARTIAL",
    "Rendering": "CONNECTED",
    "Co-Director Production Control": "CONNECTED",
}


def _registry_ids() -> list[str]:
    text = (ROOT / "studio-api/app/capabilities/registry.py").read_text(encoding="utf-8")
    ids = re.findall(r'id="([^"]+)"', text) + re.findall(r"id='([^']+)'", text)
    seen: set[str] = set()
    ordered: list[str] = []
    for item in ids:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _cap(
    capability_id: str,
    display_name: str,
    department: str,
    status: str,
    *,
    providers: list[str] | None = None,
    workflows: list[str] | None = None,
    jobs: list[str] | None = None,
    assets: list[str] | None = None,
    validation: str = "",
    approval: bool = True,
    timeline: bool = False,
    bible: bool = False,
    flag: str = "",
    limitations: list[str] | None = None,
    evidence: list[str] | None = None,
) -> dict:
    return {
        "capabilityId": capability_id,
        "displayName": display_name,
        "department": department,
        "status": status,
        "source": "native",
        "providerIds": providers or [],
        "workflowAdapterIds": workflows or [],
        "jobHandlerIds": jobs or [],
        "assetTypes": assets or [],
        "validationMode": validation,
        "approvalRequired": approval,
        "timelineCompatible": timeline,
        "productionBibleCompatible": bible,
        "featureFlag": flag,
        "version": "1.0.0-native-baseline",
        "acceptanceEvidence": evidence or [],
        "knownLimitations": limitations or [],
    }


def build() -> dict:
    native: list[dict] = []
    native.extend(
        [
            _cap(
                "storyboard.generate",
                "Storyboard Generate",
                "Image",
                "accepted",
                providers=["comfy.local"],
                workflows=["image.zimage_reference", "image.txt2img"],
                jobs=["storyboard_generate"],
                assets=["image", "storyboard_panel"],
                validation="m2.5_vision",
                timeline=True,
                bible=True,
                flag="STUDIO_FEATURE_PRODUCTION_EXECUTIVE_V1",
                evidence=[
                    "docs/codirector/M2.7.1_ACCEPTANCE_REPORT.md",
                    "docs/codirector/m2.7.1-storyboard-generate-live-validation.md",
                ],
                limitations=[
                    "Requires ComfyUI + Z-Image stack; M2.9 image_production_v1 is separate flag-gated suite path"
                ],
            ),
            _cap(
                "generation.image.queue",
                "Image Generation Queue",
                "Image",
                "accepted",
                providers=["comfy.local"],
                workflows=[
                    "image.txt2img",
                    "image.img2img_edit",
                    "image.zimage_reference",
                ],
                jobs=["image_generate"],
                assets=["image"],
                validation="m2.5_vision",
                timeline=True,
                bible=True,
                flag="STUDIO_FEATURE_PRODUCTION_EXECUTIVE_V1",
                evidence=["docs/codirector/M2.7.1_ACCEPTANCE_REPORT.md"],
                limitations=[
                    "Legacy queue_worker imagegen path also exists outside M2.7"
                ],
            ),
            _cap(
                "codirector.vision.validate",
                "M2.5 Vision Validate",
                "Validation",
                "accepted",
                providers=["vision.local"],
                jobs=["validate"],
                validation="m2.5_owns_lifecycle",
                approval=False,
                flag="STUDIO_FEATURE_VISION_VALIDATION_V1",
                evidence=["docs/codirector/M2.7.1_ACCEPTANCE_REPORT.md"],
                limitations=[
                    "Scores may be inconclusive on stub ML; pending clear only via M2.5 with planId"
                ],
            ),
            _cap(
                "codirector.bible.propose",
                "Bible Propose",
                "ProductionBible",
                "accepted",
                jobs=["create_proposal", "await_approval", "apply_canon"],
                validation="n/a",
                bible=True,
                flag="STUDIO_FEATURE_PRODUCTION_EXECUTIVE_V1",
                evidence=["docs/codirector/M2.7.1_ACCEPTANCE_REPORT.md"],
            ),
            _cap(
                "codirector.bible.approve",
                "Bible Approve",
                "ProductionBible",
                "accepted",
                validation="n/a",
                bible=True,
                evidence=["docs/codirector/M2.7.1_ACCEPTANCE_REPORT.md"],
                limitations=["Human approval only; never silent"],
            ),
            _cap(
                "codirector.bible.read",
                "Bible Read",
                "ProductionBible",
                "accepted",
                validation="n/a",
                approval=False,
                bible=True,
                evidence=["docs/codirector/M2.7.1_ACCEPTANCE_REPORT.md"],
            ),
            _cap(
                "generation.video.queue",
                "Video Generation Queue",
                "Video",
                "conditional",
                providers=["fal.api", "comfy.local"],
                workflows=["ltx.scene", "ltx.simple_i2v", "wan.first_last_frame"],
                assets=["video"],
                validation="not_in_executive_closed_loop",
                timeline=True,
                limitations=[
                    "BACKEND_ONLY registry baseline; no M2.7 video job type; env-dependent"
                ],
            ),
            _cap(
                "generation.lipsync.queue",
                "Lip Sync Queue",
                "LipSync",
                "conditional",
                providers=["comfy.local"],
                workflows=["lipsync.latentsync"],
                assets=["video", "lipsync"],
                validation="not_in_executive_closed_loop",
                timeline=True,
                limitations=[
                    "M2.9 lipsync/mouth jobs exist under fixture mode; production provider path not Accepted"
                ],
            ),
            _cap(
                "project.timeline.propose",
                "Timeline Propose",
                "DirectorTimeline",
                "conditional",
                validation="n/a",
                timeline=True,
                limitations=[
                    "DEGRADED/heuristic path; apply mutates scenes outside Bible proposal bus"
                ],
            ),
            _cap(
                "project.timeline.apply",
                "Timeline Apply",
                "DirectorTimeline",
                "conditional",
                timeline=True,
                limitations=[
                    "Direct scene mutation; not M2.9 approval-aware editorial bus"
                ],
            ),
            _cap(
                "director.timeline.read",
                "Director Timeline Read",
                "DirectorTimeline",
                "conditional",
                approval=False,
                timeline=True,
            ),
            _cap(
                "director.timeline.update",
                "Director Timeline Update",
                "DirectorTimeline",
                "conditional",
                timeline=True,
                limitations=["PARTIALLY_WIRED"],
            ),
            _cap(
                "editor.sequences.read",
                "Editor Sequences Read",
                "Editing",
                "conditional",
                approval=False,
                timeline=True,
                limitations=["Update capability not separately registered"],
            ),
            _cap(
                "virtual_stage.render",
                "Virtual Stage Render",
                "VirtualStage",
                "unavailable",
                limitations=[
                    "M2.8 Virtual Stage ships under CONDITIONALLY ACCEPTED; full Accepted / product review still open"
                ],
            ),
        ]
    )

    for capability_id, name, dept, flag, jobs in [
        ("frame.generate", "Frame Generate", "Frames", "STUDIO_FEATURE_FRAME_PRODUCTION_V1", ["frame_generate"]),
        ("audio.dialogue.generate", "Audio Dialogue Generate", "Audio", "STUDIO_FEATURE_AUDIO_PRODUCTION_V1", ["audio_generate"]),
        ("audio.sfx.generate", "SFX Generate", "SFX", "STUDIO_FEATURE_EDITING_PRODUCTION_V1", ["audio_generate"]),
        ("audio.music.generate", "Music Generate", "Music", "STUDIO_FEATURE_EDITING_PRODUCTION_V1", ["audio_generate"]),
        ("mouth.rectangle.generate", "Mouth Rectangle Generate", "LipSync", "STUDIO_FEATURE_LIPSYNC_PRODUCTION_V1", []),
        ("lipsync.generate", "Lip Sync Generate", "LipSync", "STUDIO_FEATURE_LIPSYNC_PRODUCTION_V1", ["lipsync_generate"]),
        ("scene.render", "Scene Render", "Rendering", "STUDIO_FEATURE_RENDER_PRODUCTION_V1", ["scene_render"]),
    ]:
        native.append(
            _cap(
                capability_id,
                name,
                dept,
                "conditional",
                jobs=jobs,
                flag=flag,
                limitations=[
                    "M2.9 Accepted-with-limitations: generative path deferred to M2.10 fill target",
                    "Do not mark accepted/CONNECTED until real generative provider proven",
                ],
            )
        )

    known = {item["capabilityId"] for item in native}
    for cid in _registry_ids():
        if cid in known:
            continue
        native.append(
            _cap(
                cid,
                cid,
                cid.split(".")[0],
                "conditional",
                validation="unknown",
                bible=cid.startswith("codirector.bible"),
                limitations=[
                    "Exported from runtime registry; section-level M2.9 acceptance not completed"
                ],
            )
        )

    ids = [item["capabilityId"] for item in native]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate capability IDs")

    for item in native:
        if item["status"] == "accepted" and item["source"] != "native":
            raise SystemExit(f"accepted non-native: {item['capabilityId']}")
        if item["status"] == "accepted" and "mock-only" in " ".join(
            item["knownLimitations"]
        ).lower():
            raise SystemExit(f"accepted mock-only: {item['capabilityId']}")

    return {
        "schemaVersion": 1,
        "baselineId": "adept-ui-v1.0-native",
        "displayName": "Adept UI v1.0 Native Capability Baseline",
        "sourceOfTruthNote": (
            "Runtime evaluation remains studio-api/app/capabilities/registry.py. "
            "This JSON is the versioned native baseline for M2.10 add-on comparison."
        ),
        "milestoneContext": {
            "m271": "Accepted",
            "m28": "Accepted (criteria not weakened)",
            "m29": "Accepted with documented native capability limitations",
            "m210": "Not started — awaiting Product authorization (discovery not authorized)",
            "m30": "Not started",
        },
        "sectionAuditClassification": SECTION_STATUS,
        "executiveJobHandlers": [
            "storyboard_generate",
            "image_generate",
            "validate",
            "create_proposal",
            "await_approval",
            "apply_canon",
            "generic",
            "frame_generate",
            "frame_sequence",
            "video_generate",
            "lipsync_generate",
            "mouth_track_generate",
            "audio_generate",
            "audio_process",
            "timeline_render",
            "scene_render",
            "edit_apply",
        ],
        "workflowAdaptersNative": [
            "ltx.scene",
            "ltx.simple_i2v",
            "ltx.ingredients_ic_lora",
            "wan.first_last_frame",
            "lipsync.latentsync",
            "image.txt2img",
            "image.img2img_edit",
            "image.zimage_reference",
        ],
        "providerKinds": {
            "builtInLocal": ["comfy.local", "vision.local"],
            "externalApiApprovedOptional": ["fal.api"],
            "deterministicProcessor": [],
            "addon": [],
        },
        "capabilities": native,
        "counts": {
            "capabilities": len(native),
            "accepted": sum(1 for c in native if c["status"] == "accepted"),
            "conditional": sum(1 for c in native if c["status"] == "conditional"),
            "unavailable": sum(1 for c in native if c["status"] == "unavailable"),
            "registryIdsExported": len(_registry_ids()),
        },
    }


def main() -> None:
    doc = build()
    out = ROOT / "config/capabilities/adept-ui-v1.0-native.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    out.write_text(raw, encoding="utf-8", newline="\n")
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    (ROOT / "config/capabilities/adept-ui-v1.0-native.sha256").write_text(
        digest + "\n", encoding="utf-8", newline="\n"
    )
    print(out)
    print("sha256", digest)
    print(json.dumps(doc["counts"], indent=2))


if __name__ == "__main__":
    main()
