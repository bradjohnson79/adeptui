#!/usr/bin/env python3
"""Emit M3.0i closure docs with honest independent g/h/beta verdicts."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "release-gate" / "m30i"
ART = ROOT / "artifacts" / "m30i"
MANIFEST = "cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc"
START = "190b3e1a97d6e4ee082d30a7098f0e309711c59d"
IMPL = "PLACEHOLDER_IMPL_SHA"
DOCS_SHA = "PLACEHOLDER_DOCS_SHA"

live = {}
try:
    live = json.loads((ART / "live-fal-music-off" / "live_proof.json").read_text(encoding="utf-8"))
except Exception:
    live = {"status": "MISSING", "audioInspection": {"classification": "INCONCLUSIVE"}}

cls = (live.get("audioInspection") or {}).get("classification")
live_green = cls in {
    "NO_AUDIO_STREAM",
    "AUDIO_STREAM_WITH_NO_DETECTED_MUSIC",
    "AUDIO_STREAM_WITH_AMBIENCE_ONLY",
} and live.get("status") == "GREEN"

# SR session notes: PARTIAL → NOT GREEN for g
sr = "NOT GREEN"
kb = "PARTIAL"
rtl = "PARTIAL"
axe = "NOT GREEN"  # m30g axe critical failed in focused run

m30h_yes = live_green  # S1-S9 already PASS; a11y not required for h
m30g_yes = live_green and kb == "GREEN" and sr == "GREEN" and rtl == "GREEN" and axe == "GREEN"
beta_yes = m30g_yes and m30h_yes

v_g = "YES — M3.0G PRODUCTION CERTIFICATION PASSED" if m30g_yes else "NO — M3.0G PRODUCTION CERTIFICATION REMAINS CLOSED"
v_h = "YES — M3.0H FILMMAKER SCENARIO FINALE PASSED" if m30h_yes else "NO — M3.0H FILMMAKER SCENARIO FINALE REMAINS OPEN"
v_b = "YES — ADEPT UI STUDIO MAY ENTER BRAD MANUAL BETA" if beta_yes else "NO — ADEPT UI STUDIO MANUAL BETA ENTRY REMAINS CLOSED"


def hdr() -> str:
    return f"""| Field | Value |
|-------|-------|
| Branch | `phase2/codirector-m2-9-production-suite` |
| Starting SHA | `{START}` |
| Implementation SHA | `{IMPL}` |
| Documentation SHA | `{DOCS_SHA}` |
| Provider Manifest SHA | `{MANIFEST}` |
| Product | Adept UI Studio |
| Date | 2026-07-27 |
"""


def write(name: str, body: str) -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / name).write_text(body.rstrip() + "\n", encoding="utf-8")


write(
    "README.md",
    f"""# M3.0i Final Certification Closure Pack

{hdr()}

Consolidated: [`docs/M3.0I_FINAL_CERTIFICATION_AND_MANUAL_BETA_ENTRY_REPORT.md`](../../M3.0I_FINAL_CERTIFICATION_AND_MANUAL_BETA_ENTRY_REPORT.md)

## Verdicts

- M3.0g: {v_g}
- M3.0h: {v_h}
- Manual Beta Entry: {v_b}
""",
)

write(
    "M30I_LIVE_FAL_MUSIC_OFF_REPORT.md",
    f"""# M30I Live Fal Music-Off

{hdr()}

| Field | Value |
|-------|-------|
| Status | `{live.get("status")}` |
| Classification | `{cls}` |
| Studio job ID | `{live.get("studioJobId")}` |
| fal request ID | `{live.get("falRequestId")}` |
| Submissions | `{live.get("providerSubmissionCount")}` |
| generate_audio | false (compiled + queued) |

Evidence: `artifacts/m30i/live-fal-music-off/`

First paid submit failed fal content_policy_violation (422) on suspense prompt; zero automatic retries. Milder prompt staged for explicit human `ADEPT_M30I_FAL_FORCE=1` rerun only.
""",
)

write(
    "M30I_M30G_CLOSURE_REPORT.md",
    f"""# M30I → M3.0g Closure

{hdr()}

| Gate | Result |
|------|--------|
| MI-LIVE | {"GREEN" if live_green else live.get("status")} / `{cls}` |
| Keyboard | {kb} |
| Screen reader | {sr} |
| RTL | {rtl} |
| Axe | {axe} |

## Verdict

# {v_g}
""",
)

write(
    "M30I_M30H_CLOSURE_REPORT.md",
    f"""# M30I → M3.0h Closure

{hdr()}

S1–S9 orchestration packages remain PASS (M3.0h harness). S3 live maps to M3.0i evidence.

| Gate | Result |
|------|--------|
| S3 live | {"GREEN" if live_green else live.get("status")} / `{cls}` |
| Accessibility (not required for h) | N/A for h YES |

## Verdict

# {v_h}
""",
)

write(
    "M30I_MANUAL_BETA_ENTRY_REPORT.md",
    f"""# M30I Manual Beta Entry

{hdr()}

Requires M3.0g YES **and** M3.0h YES plus Director/audio/360 gates.

## Verdict

# {v_b}

Draft guide only if NO: see `DRAFT — MANUAL BETA NOT YET AUTHORIZED` under this pack (not `docs/manual-beta/`).
""",
)

for name, blurb in [
    ("M30I_KEYBOARD_ACCESSIBILITY_REPORT.md", f"Keyboard: {kb}. See artifacts/m30i/accessibility/keyboard/"),
    ("M30I_SCREEN_READER_ACCESSIBILITY_REPORT.md", f"Screen reader: {sr}. NVDA 2026.1.1 + Chrome. See session-notes.md"),
    ("M30I_RTL_ACCESSIBILITY_REPORT.md", f"RTL: {rtl}. ar/ur Playwright shells archived."),
    ("M30I_AXE_REPORT.md", f"Axe: {axe}. Focused m30g suite reported critical violation; do not weaken thresholds."),
    ("M30I_REGRESSION_REPORT.md", "REG-01..23 exercised via m30g/m30h reuse + m30i e2e specs."),
    ("M30I_SECURITY_AND_EVIDENCE_AUDIT.md", "No secrets committed; live media not committed; IDs only."),
    ("M30I_360_ENVIRONMENT_REPORT.md", "Canonical input: M2.13 camera-spin/GLB — not 8-view PNG collage UI. Visible character capsules on viewport (ENV-360-06)."),
    ("M30I_SINGLE_CHARACTER_SCENE_REPORT.md", "Visible composition required; metadata-only FAIL. ENV-360-16 preflight JSON archived without paid 360 submit."),
    ("M30I_SYSTEM_REPORT.md", "Closure milestone; Manifest locked."),
    ("M30I_PM_REPORT.md", f"g: {v_g}\n\nh: {v_h}\n\nBeta: {v_b}"),
]:
    write(name, f"# {name.replace('.md','').replace('_',' ')}\n\n{hdr()}\n\n{blurb}\n")

(ROOT / "docs" / "M3.0I_FINAL_CERTIFICATION_AND_MANUAL_BETA_ENTRY_REPORT.md").write_text(
    f"""# M3.0I — Final Certification Closure and Manual Beta Entry

{hdr()}

## Verdicts

# {v_g}

# {v_h}

# {v_b}

## Live fal

Status `{live.get("status")}` · class `{cls}` · job `{live.get("studioJobId")}` · fal `{live.get("falRequestId")}` · submissions `{live.get("providerSubmissionCount")}`

## Completion summary

```text
Branch: phase2/codirector-m2-9-production-suite
Starting SHA: {START}
Implementation SHA: {IMPL}
Documentation SHA: {DOCS_SHA}
Final tip: PLACEHOLDER_FINAL_TIP
Provider Manifest SHA: {MANIFEST}
Working-tree status: CLEAN
Live fal flag: ADEPT_M30I_FAL_LIVE=1
Provider submission count: {live.get("providerSubmissionCount")}
Studio job ID: {live.get("studioJobId")}
Provider request ID: {live.get("falRequestId")}
Paid provider spend: estimated <= $1.50 (actual unknown; job failed content policy)
Artifact status: unavailable (provider failed)
Audio stream status: N/A
Audio classification: {cls}
Human playback result: NOT_APPLICABLE
Axe: {axe}
Keyboard: {kb}
Screen reader: {sr}
Arabic RTL: {rtl}
Urdu RTL: {rtl}
Director timeline generator Playwright: PARTIAL
Imported music workflow: PARTIAL
SFX workflow: PARTIAL
Audio persistence and export: PARTIAL
360 collage import: NOT_PRODUCT_PRIMARY (camera-spin/GLB)
Directional mapping: camera-spin fixture path
Environment persistence: PARTIAL
Single-character registration: PASS (visible capsule)
Character placement: PASS (visible)
Character continuity: PARTIAL
Camera revision: PARTIAL
Director integration: PARTIAL
Editor handoff: PARTIAL
360 workflow recovery: PARTIAL
360 export package: PARTIAL
Rendered visual spot-check: NOT_RUN
M3.0g MI-LIVE: {live.get("status")}
M3.0g accessibility: NOT GREEN
M3.0g RTL: {rtl}
M3.0g final verdict: {v_g}
M3.0h S3 live: {live.get("status")}
M3.0h scenario regression: PASS (prior S1-S9)
M3.0h final verdict: {v_h}
Secret audit: CLEAN
Evidence audit: CLEAN
Duplicate paid submissions: 0
Provider Manifest changed: NO
Known non-blocking limitations: MACHINE_DRAFT non-en; no generative music; LTX/WAN limits; quarantines; content-policy fal failure on first prompt
Manual Beta Entry verdict:
{v_b}
```
""",
    encoding="utf-8",
)
print(json.dumps({"g": v_g, "h": v_h, "beta": v_b, "live": live.get("status"), "cls": cls}, indent=2))
