#!/usr/bin/env python3
"""Emit M3.0F multilingual certification pack (honest NO default)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "release-gate" / "multilingual"

IMPL = "PLACEHOLDER_IMPL_SHA"
DOCS_SHA = "PLACEHOLDER_DOCS_SHA"
START = "9899315ce4161524c4f3bb89b9a9cbc839bb117f"
MANIFEST = "cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc"
BRANCH = "phase2/codirector-m2-9-production-suite"

HEADER = f"""| Field | Value |
|-------|-------|
| Branch | `{BRANCH}` |
| Starting SHA | `{START}` |
| Implementation SHA | `{IMPL}` |
| Documentation SHA | `{DOCS_SHA}` |
| Provider Manifest SHA | `{MANIFEST}` |
| Date | 2026-07-27 |
"""

REPORTS = {
    "README.md": f"""# M3.0F Multilingual Platform Certification Pack

{HEADER}

Consolidated task report: `docs/M3.0F_MULTILINGUAL_PLATFORM_TASK_REPORT.md`.

See `M30F_*.md` in this directory.
""",
    "M30F_I18N_ARCHITECTURE.md": f"""# M30F I18N Architecture

{HEADER}

## Stack

- Frontend: `i18next` + `react-i18next` under `studio-web/src/i18n/`
- Offline JSON namespaces for twelve locales
- Backend: `studio-api/app/codirector/language_intelligence/`
- Preferences: interface / conversation / project / prompt policy / export (decoupled)

## Verdict

**VERIFIED** for architecture foundation.
""",
    "M30F_LOCALE_REGISTRY.md": f"""# M30F Locale Registry

{HEADER}

Twelve locales: en, fr, es, ja, zh-Hans, hi, ru, pt, ar, bn, id, ur.

Portuguese (`pt`) uses **Brazilian Portuguese** (`pt-BR`) date/number conventions.

Arabic and Urdu are RTL.

## Verdict

**VERIFIED**
""",
    "M30F_LANGUAGE_PACK_SCHEMA.md": f"""# M30F Language Pack Schema

{HEADER}

Namespaces under `studio-web/src/i18n/locales/<locale>/*.json`.

Validator: `studio-web/src/i18n/validation.ts` + coverage script `scripts/m30f_coverage_report.py`.

## Verdict

**VERIFIED**
""",
    "M30F_TRANSLATION_COVERAGE.md": f"""# M30F Translation Coverage

{HEADER}

English is authoritative. Non-English packs are **MACHINE_DRAFT**.

Identical English strings in beta-critical namespaces are not counted as translated.

Artifact: `artifacts/m30f-i18n/translation_coverage.json`

## Verdict

**KEY COVERAGE PRESENT** / **LINGUISTIC REVIEW: MACHINE_DRAFT** (except English HUMAN_APPROVED)
""",
    "M30F_RTL_CERTIFICATION.md": f"""# M30F RTL Certification

{HEADER}

`dir="rtl"` applied for ar/ur via `applyDocumentDirection`.

Logical CSS helpers in `styles.css`. Timeline/playback remain LTR isolated.

## Verdict

**IMPLEMENTED** — full visual RTL certification incomplete without archived screenshot suite GREEN.
""",
    "M30F_UNICODE_AND_SCRIPT_CERTIFICATION.md": f"""# M30F Unicode and Script Certification

{HEADER}

UTF-8 JSON packs; system font fallbacks for CJK/Devanagari/Arabic/Bengali/Cyrillic.

No restricted font binaries committed.

## Verdict

**PARTIAL** — persistence APIs UTF-8 safe; complex-script visual GREEN not fully archived.
""",
    "M30F_CODIRECTOR_LANGUAGE_INTELLIGENCE.md": f"""# M30F Co-Director Language Intelligence

{HEADER}

Conversation locale injected into system prompt via `_prepare_chat_request`.

API: `/api/codirector/language-intelligence/*`

## Verdict

**VERIFIED** (preference-authoritative responses; LLM quality locale-dependent)
""",
    "M30F_MODEL_LANGUAGE_INTEGRATION.md": f"""# M30F Model Language Integration

{HEADER}

MIL packs include `languageSupport`. CompileResult stores original/source/prompt language provenance.

Multilingual audio exclusion phrases normalize to `music=prohibited`.

## Verdict

**VERIFIED** for policy wiring; do not claim native multilingual model strength beyond pack notes.
""",
    "M30F_PRODUCTION_BIBLE_LOCALIZATION.md": f"""# M30F Production Bible Localization

{HEADER}

Additive localization envelopes in `bible_localization.py` — canonical text never overwritten.

## Verdict

**VERIFIED** (schema helpers); full UI localization of all Bible fields is progressive.
""",
    "M30F_GLOSSARY_AND_CANON_PROTECTION.md": f"""# M30F Glossary and Canon Protection

{HEADER}

Project glossary in `settings_json.language.glossary` + platform protected terms.

## Verdict

**VERIFIED**
""",
    "M30F_DIALOGUE_SUBTITLE_ARCHITECTURE.md": f"""# M30F Dialogue and Subtitle Architecture

{HEADER}

Dialogue model with linked localized variants + migration `m019`.

## Verdict

**VERIFIED** (architecture); full subtitle UX deferred.
""",
    "M30F_ACCESSIBILITY_CERTIFICATION.md": f"""# M30F Accessibility Certification

{HEADER}

`lang`/`dir` attributes set. Localized a11y keys present.

Automated a11y GREEN across en/ja/ar/hi **not** archived as certification evidence in this milestone.

## Verdict

**NOT GREEN**
""",
    "M30F_SECURITY_AUDIT.md": f"""# M30F Security Audit

{HEADER}

Language packs scanned for script injection in tests.

i18next interpolation escaping enabled.

## Verdict

**CLEAN** for pack injection tests; secret audit at stamp.
""",
    "M30F_VISUAL_REGRESSION_REPORT.md": f"""# M30F Visual Regression Report

{HEADER}

RTL/layout CSS landed. Full Playwright visual matrix for six locales not archived GREEN.

## Verdict

**INCOMPLETE**
""",
    "M30F_RUNTIME_EVIDENCE.md": f"""# M30F Runtime Evidence

{HEADER}

- Locale packs seeded (12)
- Coverage artifact: `artifacts/m30f-i18n/translation_coverage.json`
- Backend LF API + audio exclusion tests: `tests/test_m30f_language_intelligence.py`

## Verdict

**PARTIAL_RUNTIME**
""",
    "M30F_TEST_REPORT.md": f"""# M30F Test Report

{HEADER}

See SYSTEM/PM reports for exit suite totals.

Focused suite: `tests/test_m30f_language_intelligence.py`

## Verdict

Focused suite **PASS** required before certification docs stamp.
""",
    "M30F_MASTER_REMEDIATION_REGISTER.md": f"""# M30F Master Remediation Register

{HEADER}

| ID | Family | Status |
|----|--------|--------|
| LF-I18N | Application i18n | CLOSED (foundation) |
| LF-LP | Language packs | CLOSED (MACHINE_DRAFT) |
| LF-RT | RTL | PARTIAL |
| LF-UC | Unicode/scripts | PARTIAL |
| LF-CD | Co-Director multilingual | CLOSED (wiring) |
| LF-MI | MIL language | CLOSED (wiring) |
| LF-PB | Bible localization | CLOSED (helpers) |
| LF-GL | Glossary | CLOSED |
| LF-DS | Dialogue/subtitles | CLOSED (architecture) |
| LF-AC | Accessibility | OPEN (not GREEN) |
| LF-SC | Security | CLOSED |
| LF-VR | Visual regression | OPEN |
| LF-RTM | Runtime evidence | PARTIAL |
""",
    "M30F_SYSTEM_REPORT.md": f"""# M30F SYSTEM REPORT

{HEADER}

## Summary

Multilingual foundation shipped: i18n core, twelve packs, language intelligence API, MIL languageSupport, multilingual audio exclusion, RTL shell hooks, glossary/Bible/dialogue helpers.

Open: linguistic review, a11y GREEN, full visual RTL archive.

## Technical verdict

Implementation complete for foundation; certification blocked by honest review/evidence bars.
""",
    "M30F_PM_REPORT.md": f"""# M30F PM REPORT

{HEADER}

## Final verdict

# NO — M3.0F MULTILINGUAL PLATFORM NOT CERTIFIED

## Rationale

Non-English language packs are **MACHINE_DRAFT** without native-speaker production approval. Accessibility is not GREEN. Visual RTL/complex-script certification evidence is incomplete.

Foundation and beta-critical key coverage plumbing are in place so certification can become YES when review and evidence bars are met.
""",
    "M30F_ELECTRON_PREP.md": f"""# M30F Electron Preparation (documentation only)

{HEADER}

M3.0F does **not** implement Electron.

Later Electron should supply:

- OS locale to `resolveInterfaceLocale`
- Native menu / installer / updater / file-dialog / notification language

Language preferences remain in the platform-neutral `adept_ui_language_prefs_v1` store.
""",
}


def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    for name, body in REPORTS.items():
        (DOCS / name).write_text(body, encoding="utf-8")
    task = ROOT / "docs" / "M3.0F_MULTILINGUAL_PLATFORM_TASK_REPORT.md"
    task.write_text(
        f"""# M3.0F — Multilingual Platform and Co-Director Language Intelligence

{HEADER}

## Final verdict

# NO — M3.0F MULTILINGUAL PLATFORM NOT CERTIFIED

## What shipped

| Area | Location |
|------|----------|
| Frontend i18n | `studio-web/src/i18n/` |
| Locale packs | 12 locales × namespaces |
| Language settings | Project Settings → Language |
| Backend LI | `studio-api/app/codirector/language_intelligence/` |
| API | `/api/codirector/language-intelligence/*` |
| MIL languageSupport | pack manifests + CompileResult provenance |
| Multilingual audio | `audio_phrases.py` + MIL compiler |
| Migration | `m019_language_intelligence` |
| Tests | `tests/test_m30f_language_intelligence.py` |
| Docs | `docs/release-gate/multilingual/` |

## Linguistic review

| Locale | Review level |
|--------|--------------|
| en | HUMAN_APPROVED |
| all others | MACHINE_DRAFT |

## Completion summary

```text
Branch: {BRANCH}
Starting SHA: {START}
Implementation SHA: {IMPL}
Documentation SHA: {DOCS_SHA}
Provider Manifest SHA: {MANIFEST}
Secret-audit result: (stamp)
Font-licensing audit result: CLEAN (system fallbacks only)
Languages active: 12 (selectable)
Final verdict:
NO — M3.0F MULTILINGUAL PLATFORM NOT CERTIFIED
```
""",
        encoding="utf-8",
    )
    print("Wrote", len(REPORTS), "reports + task report")


if __name__ == "__main__":
    main()
