#!/usr/bin/env python3
"""Emit M3.0e documentation pack under docs/release-gate/model-intelligence/."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "release-gate" / "model-intelligence"
DOC.mkdir(parents=True, exist_ok=True)

BRANCH = "phase2/codirector-m2-9-production-suite"
START = "5af34eff0a5207febf05ef6cc4a3e4f7d572eb15"
IMPL = "PLACEHOLDER_IMPL_SHA"
DOCS = "PLACEHOLDER_DOCS_SHA"
MANIFEST = "cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc"


def hdr(title: str) -> str:
    return f"""# {title}

| Field | Value |
|-------|-------|
| Branch | `{BRANCH}` |
| Starting SHA | `{START}` |
| Implementation SHA | `{IMPL}` |
| Documentation SHA | `{DOCS}` |
| Provider Manifest SHA | `{MANIFEST}` |
| Date | 2026-07-27 |

"""


def w(name: str, body: str) -> None:
    (DOC / name).write_text(hdr(name.replace(".md", "").replace("_", " ")) + body.strip() + "\n", encoding="utf-8")


def main() -> None:
    w(
        "README.md",
        """
# M3.0e Model Intelligence Certification Pack

Index of reports for the Model Intelligence Layer.

See also: `docs/M3.0E_MODEL_INTELLIGENCE_TASK_REPORT.md` (written at tip stamp).
""",
    )

    reports = {
        "M30E_MODEL_INTELLIGENCE_ARCHITECTURE.md": """
## Architecture

Module: `studio-api/app/codirector/model_intelligence/`

Canonical flow: intent → audio normalize → Bible package → selector → pack resolve → compiler → preflight → Studio job params → evaluator → experience → m212 candidates.

Does not create a parallel provider registry. Binds to `ltx`/`wan`/`zimage`/`fal_*` engines and capability IDs.

## Verdict

Architecture implemented and wired to Co-Director API + fal queue params.
""",
        "M30E_MODEL_KNOWLEDGE_REGISTRY.md": """
## Packs

| modelId | status | runtime |
|---------|--------|---------|
| z_image | ACTIVE | production |
| ltx_2_3 | ACTIVE | not_production_ready |
| wan_2_2 | ACTIVE | not_production_ready |
| fal_seedance | ACTIVE | production |
| fal_kling / fal_veo / fal_runway | VERIFIED | experimental |
| seedream / nano_banana_pro / gpt_image_fal | QUARANTINED | product_approval_required |

## Commands

`python -c "from app.codirector.model_intelligence.loader import validate_all; print(validate_all())"`
""",
        "M30E_KNOWLEDGE_PACK_SCHEMA.md": """
Schema: `schemas.PackManifest` + required YAML files per pack (fail closed).

Malformed packs raise `PackLoadError`. Unsafe `!!python` / template injection rejected.
""",
        "M30E_DOCUMENTATION_PROVENANCE.md": """
Every pack has `provenance.yaml` with sourceType confidence levels.

`docs_sync.propose_pack_update` never auto-activates. External docs are untrusted input.
""",
        "M30E_PROMPT_COMPILER_REPORT.md": """
Compiler: `compiler.compile_intent`.

Records `appliedRules`, strips example contamination, applies deterministic audio rules.

Test: `tests/test_m30e_model_intelligence.py`.
""",
        "M30E_MODEL_SELECTION_REPORT.md": """
Selector: `selector.recommend` with versioned weights `m30e-scoring-v1`.

Never silently replaces `forceModelId`. Explainable scores returned.
""",
        "M30E_PREFLIGHT_CERTIFICATION.md": """
Statuses: READY | READY_WITH_WARNINGS | APPROVAL_REQUIRED | BLOCKED.

BLOCKED prevents job creation. Paid duplicate guard supported.
""",
        "M30E_LTX23_AUDIO_MUSIC_REPORT.md": """
## Classification

**BEST_EFFORT_EXTERNAL_AUDIO**

LTX 2.3 does not generate native soundtrack (`supportsNativeAudio: false`).

No-music requests → external audio pipeline + negative prompt music terms. Not a guaranteed soundtrack toggle.

Seedance/Veo: `generate_audio=false` when music prohibited (wired through queue_worker).
""",
        "M30E_PRODUCTION_BIBLE_INTEGRATION.md": """
Compiler accepts `biblePackage` with style/continuity constraints and conflicts.

Conflicts surface as warnings and may force APPROVAL_REQUIRED in preflight. Canon is not overwritten.
""",
        "M30E_EXPERIENCE_LEARNING_GOVERNANCE.md": """
Table: `m30e_generation_experience` (migration M018).

Promotion to global rules requires m212 candidate + human approval (threshold ≥3). No auto pack mutation.
""",
        "M30E_SECURITY_AND_PROMPT_INJECTION_AUDIT.md": """
- Pack YAML rejects `!!python`, Jinja markers
- Experience params strip key/secret/token fields
- Advanced UI does not expose credentials
- SECRET AUDIT: CLEAN (milestone stamp)
""",
        "M30E_RUNTIME_EVIDENCE.md": """
Artifact: `artifacts/m30e-mil/runtime_evidence.json` (via `scripts/m30e_runtime_evidence.py`).

Includes: recommendation, LTX compile, fal_seedance no-music compile, z_image compile, unsupported preflight, evaluation/revision, fal motion reuse note.

Live fal music-suppression generate: NOT_RUN_IN_M30E (budget / reuse policy).
""",
        "M30E_TEST_REPORT.md": """
## Commands

```bash
cd studio-api
python -m pytest -q tests/test_m30e_model_intelligence.py
python -m pytest -q
```

## Totals (stamp after final suite)

See SYSTEM/PM reports for exact totals.
""",
        "M30E_MASTER_REMEDIATION_REGISTER.md": """
| ID | Family | Status | Evidence |
|----|--------|--------|----------|
| MI-KP-01 | Knowledge packs | Closed | validate_all + packs/ |
| MI-PC-01 | Prompt compiler | Closed | test_m30e_* |
| MI-MS-01 | Model selection | Closed | selector tests |
| MI-PF-01 | Preflight | Closed | MI-05/11 |
| MI-AU-01 | Audio intent | Closed | MI-01..04 |
| MI-PB-01 | Bible | Closed | MI-07 |
| MI-EX-01 | Experience | Closed | experience.py + M018 |
| MI-EV-01 | Evaluation | Closed | MI-12 |
| MI-SC-01 | Security | Closed | malformed/injection tests |
| MI-UI-01 | UI | Closed | ModelIntelligencePanel |
| MI-RT-01 | Runtime | Partial | compile proofs; live music-off fal not re-spent |
""",
        "M30E_SYSTEM_REPORT.md": """
## System summary

MIL module shipped and tested. Fal queue honors `generate_audio` from job/MIL params.

Open limitation: live LTX generation still NOT_PRODUCTION_READY; live fal music-off generate not re-run (motion proof reused).

## Verdict (technical)

Implementation complete; certification depends on PM evidence bar for runtime live music suppression.
""",
        "M30E_PM_REPORT.md": """
## Final verdict

# NO — M3.0E MODEL INTELLIGENCE NOT CERTIFIED

## Rationale

Critical runtime path for **live** music-prohibited fal generation was not re-executed in M3.0e (budget reuse). LTX music guarantee remains BEST_EFFORT_EXTERNAL_AUDIO / non-green for soundtrack toggle claims.

Compiler, packs, preflight, selection, UI, and unit/API scenarios MI-01..MI-12 are implemented and tested.

## Cleared

- Knowledge-pack schema/loader/registry
- Prompt compiler + deterministic rules
- Audio-intent normalization
- LTX honesty classification
- Preflight BLOCKED paths
- Example contamination prevention
- Security fail-closed pack load
- Secret audit CLEAN (at stamp)

## Blocking certification

- Live music-suppression generation evidence incomplete
- LTX/WAN production readiness unchanged (experimental / not production ready)
""",
    }

    for name, body in reports.items():
        w(name, body)

    # Fix README title collision — rewrite README cleanly
    (DOC / "README.md").write_text(
        f"""# M3.0e Model Intelligence Certification Pack

| Field | Value |
|-------|-------|
| Branch | `{BRANCH}` |
| Starting SHA | `{START}` |
| Implementation SHA | `{IMPL}` |
| Documentation SHA | `{DOCS}` |
| Provider Manifest SHA | `{MANIFEST}` |

## Reports

See `M30E_*.md` files in this directory.

Consolidated task report: `docs/M3.0E_MODEL_INTELLIGENCE_TASK_REPORT.md`.
""",
        encoding="utf-8",
    )
    print(f"Wrote pack to {DOC}")


if __name__ == "__main__":
    main()
