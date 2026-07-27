# M3.0d Accessibility Certification

| Field | Value |
|-------|-------|
| Date | 2026-07-27 |
| Status | **CONDITIONAL â€” not full Manual User Beta a11y GREEN** |
| Spec | `tests/e2e/a11y/production-critical.spec.ts` |
| Documentation SHA | `2ce772516ab518795d2279e2f02cbfd7f96bbbb1` |

## Verdict (this document)

Accessibility for Manual User Beta is **CONDITIONAL**. Automated axe critical checks and a minimal keyboard-focus probe exist, but **full keyboard-only journey completion and screen-reader certification are not proven**. Do **not** mark this area GREEN for PM authorization purposes.

## What was added in M3.0d

New Playwright spec: `tests/e2e/a11y/production-critical.spec.ts`

### Test 1 â€” axe critical violations

Iterates production-critical workspaces with `@axe-core/playwright`:

| Workspace | Route |
|-----------|-------|
| setup | `?workspace=setup` |
| codirector | `?workspace=codirector` |
| director | `?workspace=director` |
| editor | `?workspace=editor` |
| media | `?workspace=media` |

Assertion: **zero critical** violations under WCAG 2a/2aa tags.

**Note:** This spec is present in the repository. A captured green run with exit code and timestamp was **not** bundled into this documentation pack at stamp time. Until executed and archived, treat axe results as **pending execution evidence**.

### Test 2 â€” keyboard focus visibility (setup only)

Single-workspace probe: Tab from setup, expect `:focus` visible on an interactive element.

**Limitation:** One Tab press on setup does not certify keyboard-only completion of Co-Director, Director, Editor, export, or approval flows.

## What is NOT certified

| Area | Status |
|------|--------|
| Keyboard-only critical journeys (all workspaces) | **NOT PROVEN** |
| Focus order across multi-step dialogs | **NOT PROVEN** |
| Screen reader announcements (NVDA/JAWS/VoiceOver) | **NOT PROVEN** |
| Color contrast systematic audit | **NOT PROVEN** |
| Reduced motion preference | **NOT PROVEN** |
| 200% zoom reflow (Phase 0 noted gap) | **NOT RE-CAPTURED** |
| Semantic landmark completeness | **PARTIAL** (body visible check only) |

Prior M3.0c report (`docs/m3.0c/ACCESSIBILITY_AND_OPERABILITY_REPORT.md`) correctly stated PENDING. M3.0d expands automation but does not close the full operability gap.

## Available supporting evidence

- Playwright functional suite: 111 passed, 0 failed â€” demonstrates tested journeys work with default input modalities, **not** keyboard-only or SR.
- Functional-audit setup screenshots at 1024Ã—768, 1280Ã—720, 1440Ã—900, 1920Ã—1080 â€” layout snapshots, not a11y audit.

## Required follow-up before GREEN

1. Execute `tests/e2e/a11y/production-critical.spec.ts` and archive JSON report + exit code.
2. Keyboard-only scripts for: project create â†’ setup â†’ Co-Director â†’ Director place â†’ Editor handoff â†’ export.
3. SR spot-check on approval dialogs and job status regions.
4. Document findings with browser, viewport, tool versions.

## PM impact

Because full accessibility is **not** proven GREEN, the PM report final verdict must remain **NO â€” MANUAL USER BETA REMAINS CLOSED** per gate honesty rules.

## Status register entry

| ID | Item | Status |
|----|------|--------|
| A11Y | Production-critical accessibility | **Open / CONDITIONAL** |
