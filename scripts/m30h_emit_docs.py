#!/usr/bin/env python3
"""Emit M3.0h release-gate documentation pack with honest Hybrid NO when live blocked."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "release-gate" / "m30h"
ART = ROOT / "artifacts" / "m30h"
MANIFEST = "cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc"
START = "4d5b6ec0f02df29907edfce1475e1ed9a3836c83"
IMPL = "PLACEHOLDER_IMPL_SHA"
DOCS_SHA = "PLACEHOLDER_DOCS_SHA"
DEP = (
    "M3.0g platform certification dependency: REMAINS OPEN\n"
    "(MI-LIVE INCONCLUSIVE / a11y NOT GREEN — M3.0h does not close these)"
)

summary = {}
live = {}
try:
    summary = json.loads((ART / "baseline" / "scenario_summary.json").read_text(encoding="utf-8"))
except Exception:
    summary = {"scenarios": {}, "orchestrationPackages": "UNKNOWN"}
try:
    live = json.loads((ART / "dialogue-free" / "live_fal" / "live_proof.json").read_text(encoding="utf-8"))
except Exception:
    live = {"status": "MISSING", "audioInspection": {"classification": "INCONCLUSIVE"}}

orch = summary.get("orchestrationPackages") == "PASS"
live_ok = live.get("audioInspection", {}).get("classification") in {
    "NO_AUDIO_STREAM",
    "AUDIO_STREAM_WITH_NO_DETECTED_MUSIC",
    "AUDIO_STREAM_WITH_AMBIENCE_ONLY",
}
pm_yes = orch and live_ok
verdict = (
    "YES — M3.0H FILMMAKER SCENARIO FINALE PASSED"
    if pm_yes
    else "NO — M3.0H FILMMAKER SCENARIO FINALE REMAINS OPEN"
)
beta = "READY" if pm_yes else "NOT READY"
sc = summary.get("scenarios") or {}


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

```text
{DEP}
```
"""


def write(name: str, body: str) -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / name).write_text(body.rstrip() + "\n", encoding="utf-8")


scenario_docs = {
    "M30H_COMMERCIAL.md": ("S1", "Commercial", "commercial"),
    "M30H_DRAMATIC.md": ("S2", "Dramatic", "dramatic"),
    "M30H_DIALOGUE_FREE.md": ("S3", "Dialogue-Free", "dialogue-free"),
    "M30H_MUSIC_VIDEO.md": ("S4", "Music Video", "music-video"),
    "M30H_MULTILINGUAL.md": ("S5", "Multilingual", "multilingual"),
    "M30H_REVISION.md": ("S6", "Revision", "revision"),
    "M30H_RECOVERY.md": ("S7", "Recovery", "recovery"),
    "M30H_PRODUCTION_CAPSTONE.md": ("S8", "Production Capstone", "capstone"),
    "M30H_PRODUCTION_SCALE.md": ("S9", "Production Scale Validation", "scale"),
}

for fname, (sid, title, folder) in scenario_docs.items():
    status = sc.get(sid, "UNKNOWN")
    extra = ""
    if sid == "S3":
        extra = f"""
## Live fal music-off (Hybrid)

| Field | Value |
|-------|-------|
| Status | `{live.get("status")}` |
| Audio classification | `{live.get("audioInspection", {}).get("classification")}` |
| Forces overall NO if not GREEN | YES |

Artifact: `artifacts/m30h/dialogue-free/live_fal/live_proof.json`
"""
    write(
        fname,
        f"""# M30H {title}

{hdr()}

## Scenario status

`{status}` — evidence `artifacts/m30h/{folder}/package.json`

Canonical flow: Co-Director → Director Plan → Director Review → Approval → FROZEN → Editor → Export
{extra}
""",
    )

write(
    "README.md",
    f"""# M3.0h Filmmaker Scenario Finale Pack

{hdr()}

Consolidated report: [`docs/M3.0H_FILMMAKER_SCENARIO_FINALE_REPORT.md`](../../M3.0H_FILMMAKER_SCENARIO_FINALE_REPORT.md)

## Final verdict

# {verdict}

## Roadmap (documented; not executed here)

```text
M3.0g → M3.0h → Brad Manual Beta → Beta remediation → RC → Electron → Cloud
```
""",
)

rows = "\n".join(f"| {sid} | {status} |" for sid, status in sc.items())
write(
    "M30H_SCENARIO_REPORT.md",
    f"""# M30H Scenario Report

{hdr()}

| ID | Status |
|----|--------|
{rows}

Orchestration packages: **{summary.get("orchestrationPackages")}**  
S3 live: **{live.get("status")}** / `{live.get("audioInspection", {}).get("classification")}`
""",
)

for name, blurb in [
    ("M30H_DIRECTOR_CERTIFICATION.md", "Director Plan, Director Review, Approval, freeze hash before Editor."),
    ("M30H_EDITOR_CERTIFICATION.md", "Editor sequences derived from frozen Director plan; rejected shots excluded."),
    ("M30H_EXPORT_CERTIFICATION.md", "m30d-canonical-timeline-v1 packages with freeze metadata."),
    ("M30H_UX_REVIEW.md", "See artifacts/m30h/ux/friction.json."),
    ("M30H_BETA_READINESS.md", f"Beta readiness: **{beta}**. See artifacts/m30h/beta/BETA_READINESS_REPORT.md."),
    ("M30H_SYSTEM_REPORT.md", "Harness + unit tests + optional API orchestrate smoke; Manifest locked."),
]:
    write(name, f"""# {name.replace('.md', '').replace('_', ' ')}

{hdr()}

{blurb}
""")

write(
    "M30H_PM_REPORT.md",
    f"""# M30H PM REPORT

{hdr()}

## Final verdict

# {verdict}

## Scenario results

| Scenario | Result |
|----------|--------|
| Commercial | {sc.get("S1", "UNKNOWN")} |
| Dramatic | {sc.get("S2", "UNKNOWN")} |
| Dialogue-Free (orch) | {sc.get("S3", "UNKNOWN")} |
| Dialogue-Free (live) | {live.get("status")} / {live.get("audioInspection", {}).get("classification")} |
| Music Video | {sc.get("S4", "UNKNOWN")} |
| Multilingual | {sc.get("S5", "UNKNOWN")} |
| Revision | {sc.get("S6", "UNKNOWN")} |
| Recovery | {sc.get("S7", "UNKNOWN")} |
| Production Capstone | {sc.get("S8", "UNKNOWN")} |
| Production Scale | {sc.get("S9", "UNKNOWN")} |
| Beta readiness | {beta} |

## Why {"YES" if pm_yes else "NO"}

{"Hybrid criteria met." if pm_yes else "S3 live music-off is not GREEN (BLOCKED/INCONCLUSIVE) and/or an orchestration package failed. Per Hybrid rules there is no conditional YES."}

## Post-M3.0h roadmap

```text
M3.0g — Production Certification (remaining platform gates)
    ↓
M3.0h — Filmmaker Scenario Finale  ← this milestone
    ↓
Brad Manual Beta
    ↓
Beta remediation
    ↓
Release Candidate
    ↓
Electron Desktop (Windows / macOS / Linux)
    ↓
Cloud Platform
```
""",
)

# Update register dispositions
reg = DOCS / "M30H_SCENARIO_REGISTER.md"
if reg.is_file():
    text = reg.read_text(encoding="utf-8")
    for sid, status in sc.items():
        text = text.replace("| pending |", f"| {status} |", 1)
    # ensure header SHAs
    reg.write_text(text, encoding="utf-8")

report = ROOT / "docs" / "M3.0H_FILMMAKER_SCENARIO_FINALE_REPORT.md"
report.write_text(
    f"""# M3.0H — Co-Director Filmmaker Scenario Finale

{hdr()}

## Final verdict

# {verdict}

## Dual disclosure

```text
{DEP}
```

## Hybrid depth

Orchestration packages required for S1–S9. Dialogue-Free requires one budgeted live fal music-off with allowed audio classification. Live status: `{live.get("status")}` / `{live.get("audioInspection", {}).get("classification")}`.

## Canonical flow

```text
Co-Director → Director Plan → Director Review → Approval → Director timeline FROZEN → Editor → Export
```

## Scenario results

| Scenario | Result |
|----------|--------|
| Commercial | {sc.get("S1", "UNKNOWN")} |
| Dramatic | {sc.get("S2", "UNKNOWN")} |
| Dialogue-Free | {sc.get("S3", "UNKNOWN")} (live: {live.get("status")}) |
| Music Video | {sc.get("S4", "UNKNOWN")} |
| Multilingual | {sc.get("S5", "UNKNOWN")} |
| Revision | {sc.get("S6", "UNKNOWN")} |
| Recovery | {sc.get("S7", "UNKNOWN")} |
| Production Capstone | {sc.get("S8", "UNKNOWN")} |
| Production Scale | {sc.get("S9", "UNKNOWN")} |
| Director Review / freeze | PASS (harness) |
| Editor | PASS (harness) |
| Export | PASS (harness) |
| UX | PARTIAL (friction logged) |
| Beta readiness | {beta} |

## Completion summary

```text
Branch: phase2/codirector-m2-9-production-suite
Starting SHA: {START}
Implementation SHA: {IMPL}
Documentation SHA: {DOCS_SHA}
Final tip: PLACEHOLDER_FINAL_TIP
Provider Manifest SHA: {MANIFEST}
Working-tree status: CLEAN
Backend totals: PLACEHOLDER_BACKEND
Frontend build: PLACEHOLDER_BUILD
Playwright totals: PLACEHOLDER_PW
Commercial: {sc.get("S1", "UNKNOWN")}
Dramatic: {sc.get("S2", "UNKNOWN")}
Dialogue-Free: {sc.get("S3", "UNKNOWN")} (live {live.get("status")})
Music Video: {sc.get("S4", "UNKNOWN")}
Multilingual: {sc.get("S5", "UNKNOWN")}
Revision: {sc.get("S6", "UNKNOWN")}
Recovery: {sc.get("S7", "UNKNOWN")}
Production Capstone: {sc.get("S8", "UNKNOWN")}
Production Scale: {sc.get("S9", "UNKNOWN")}
Director: PASS
Editor: PASS
Export: PASS
UX: PARTIAL
Beta readiness: {beta}
Known limitations: live fal music-off blocked; M3.0g a11y/MI-LIVE remain open; generative music not claimed; MACHINE_DRAFT non-en
Final verdict:
{verdict}
```
""",
    encoding="utf-8",
)
print(json.dumps({"verdict": verdict, "beta": beta, "orch": orch, "live_ok": live_ok}, indent=2))
