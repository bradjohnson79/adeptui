# M3.3j — Korri Sample Character Profile Report

| Field | Value |
|---|---|
| **Date** | 2026-07-28 |
| **Milestone** | M3.3j Korri Sample Character Profile |
| **Verdict** | **NO-GO — Korri sample Character Profile is not yet production-ready.** |
| **Evidence** | `artifacts/m33/korri-character-profile/` |
| **Certification JSON** | `artifacts/m33/korri-character-profile-certification.json` |

## Scope

Create Korri from **written brief only** via Character Creator — no character sheet import/inspect/crop. Allowed media: `voice/Korri_Voice_Sample.mp3` only.

## Protected assets (unchanged)

| Asset | ID |
|---|---|
| Hitchhiker project | `d1683511-1cc7-4d3d-8cb7-00f48cc36aa9` |
| M3.2f LTX Shot1 | `6b91bb7f-0dfd-44e6-92b3-7df7ac8cea4f` |
| M3.2g Test 2 WAN | `e277e621-189d-471e-b435-f01620f03d0d` |
| Dialogue WAV | `c5cdd736-8f89-42e3-a7a8-9cb97043bf8a` |

## Certification matrix

| Check | Status | Evidence |
|---|---|---|
| Brief-only profile create | **GO** | `korri-profile-create.json` |
| ≥3 visual directions proposed | **GO** | Wild Sun Sprite / Rebellious Hybrid / Sisterly Counterpoint |
| Owner concept selection | **GO** | `approved_by=owner`, direction `wild_sun_sprite` |
| Gates 1–6 OWNER_APPROVED (structural) | **GO** | `visual-gates.json` |
| Imagegen hero + turnaround pack | **NO-GO** | Comfy jobs timed out / not completed |
| Voice reference validation (MP3) | **GO** | `voice/reference-validation.json` (~26s) |
| Qwen new-text clone + consent | **GO** | `voice/clone-preview.json` |
| Two dialogue lines same clone voice | **GO** | `voice/dialogue-two-lines.json` |
| Lipsync + Editor disposable scene | **PENDING** | — |
| Hitchhiker protection | **GO** | E2E + cert scripts |

## Disposable IDs

| Field | Value |
|---|---|
| projectId | `1e156832-eb38-43d6-8b52-58694f6a6f2e` |
| characterId | `d1e2ec3c-74f0-46cb-8c04-40a9aaf42970` |
| cloneVoiceId | `7f0dfb04-a587-4a05-86a7-a1a490562696` |
| referenceAssetId | `4e7ac413-0ee1-4917-bf00-5cef1442ca6d` |

Raw voice sample is not embedded in this report.

## How to clear NO-GO

1. Complete Comfy imagegen for hero/turnaround/facial/detail/expression/pose packs; owner-approve assets to `USER_CONFIRMED` / `CANONICAL_FROM_USER_APPROVAL`.
2. Disposable Korri lipsync scene + Editor render.
3. Re-run M33-KORRI Playwright under real-local where required.

## Final language

**NO-GO — Korri sample Character Profile is not yet production-ready.**
