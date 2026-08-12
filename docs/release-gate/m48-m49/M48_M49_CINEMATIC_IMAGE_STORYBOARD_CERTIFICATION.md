# M48 / M49 Cinematic Image + Storyboard — Certification

| Field | Value |
| --- | --- |
| Branch | `feature/m4-8-m4-9-cinematic-image-storyboard` |
| Project | `e32dae30-a014-4ea4-a2f2-69f4b7809bde` |
| Unit tests | `test_m48_m49_contracts.py`, `test_m48_image_providers.py`, `test_m48_cert_blockers.py` — **17 passed** |
| Playwright | `tests/e2e/m48-m49/m48-m49-cinematic-image-storyboard.spec.ts` — **5 passed** |
| Live evidence | `artifacts/m48-m49/` |
| Artist checklist | [`M48_M49_ARTIST_TEST_CHECKLIST.md`](M48_M49_ARTIST_TEST_CHECKLIST.md) |

## Five gates (binary)

| Gate | Status | Evidence |
| --- | --- | --- |
| Technical Certification | **PASS** | Unit 17/17; Playwright technical mounts + families `qwen2512` + providers + `export.pdf` magic `%PDF` |
| Creative Workflow Certification | **PASS** | Live enqueue job `41acdcbe-…` → asset `4a10784e-…`; Approve → Add to Storyboard; reopen provenance; PDF export; timeline prepare+confirm payload |
| Continuity Certification | **PASS** | Scene 12 inherit stable across 3 calls; approve into `approvedImageIds`; session JSON under `artifacts/m48-m49/continuity/` |
| Manual UX Certification | **PENDING HUMAN** | 60s Artist Test never auto-passed — see checklist |
| Live Generation Evidence | **PASS** | `artifacts/m48-m49/creative/live-generated.png` + job JSON + storyboard/PDF artifacts |

## Implemented for GO blockers

- Explicit **Approve** on result cards (no silent auto-approve)
- **Replace panel** / Undo replace APIs + Image Studio replace target
- **Re-open** provenance (prompt + refs + controls + continuity)
- **Confirm Proposal** → Director Timeline scenes (no silent clips)
- Real **Export PDF** (`application/pdf`)
- All Models **per-provider failure isolation**
- Scriptwriter scene linkage stamped + badge opens Scriptwriter

## Deferred (honest)

- HiDream / extra FLUX Schnell-Dev multi-provider live matrix when `not_installed`
- 16-image (4×4) gallery perf soak — not blocking core creative/continuity PASS

## Verdict

**CONDITIONAL GO**

Reason: four automated gates **PASS**; **Manual UX Certification** remains **PENDING HUMAN** until the 60-Second Artist Test is stamped PASS in [`M48_M49_ARTIST_TEST_CHECKLIST.md`](M48_M49_ARTIST_TEST_CHECKLIST.md).

**GO** only when all five gates are PASS.

## How to finish GO

1. Run the Artist Test with a non-engineer creator  
2. Stamp PASS on the checklist  
3. Update this table: Manual UX → PASS; Verdict → **GO**
