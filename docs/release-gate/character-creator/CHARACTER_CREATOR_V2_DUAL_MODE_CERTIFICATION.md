# Character Creator V2 — Dual-Mode Generation Certification

**Date:** 2026-08-23  
**Branch:** `feat/character-creator-final-closure`  
**Governing law (user, 2026-08-23):** Front is text-to-image when no reference is attached; Front is image-to-image when a reference is attached. Back / Close-up stay I2I from the approved Front.  
**Review URLs:** local creator UI `http://127.0.0.1:5173/` · Studio API `http://127.0.0.1:8758/`  
**Retired:** do not use `:8760`  
**Owner fixtures not touched:** Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278`, Korri `c49371ed-ba6b-4c16-ba98-a8b28b72118b`

The earlier plan line “Character Creator image generation = I2I only” is superseded by the user clarification above. Do not cite it as current product law.

## Dual-mode law (V2)

| Front input | Path | Bind |
|---|---|---|
| No reference | T2I from Character Profile description | no `source_asset_id` |
| Reference attached | I2I / ref | `source_asset_id` = reference asset |
| Back / Close-up | I2I from approved Front | `source_asset_id` = Front asset |

No silent family swap. No T2I when a reference is present. No I2I remap when no reference is present. Auto-Prompt is not the Front visual lock.

## Independent live check (primary)

| Character | Mode | Key | Pixels | Asset HTTP |
|---|---|---|---|---|
| Mira Vale `cf4437c7-fd89-4baa-90f3-8098d19eac31` | Front I2I + approved + lock `ok` | `qwen2512.ref` | ref `b7ab0ef7-…` | `/api/assets/7867b14e-…/file` **200** 4.0MB |
| same | Back I2I | `qwen2512.ref` | Front `7867b14e-…` | `/api/assets/86719bb2-…/file` **200** 5.1MB |
| Mira Vale Open `9cc4c839-c0f9-40fb-bb44-28bb2f5abcc8` | Front T2I, `hasReference=false` | `qwen2512.txt2img` | none | `/api/assets/b2263863-…/file` **200** 4.6MB |

Live inventory on Mira (has reference): Front current op is I2I (`qwen2512.ref` / `flux.img2img` / `zimage.ref_edit`); `frontFromDescription` still advertises T2I keys for the no-ref case.

## Tests (from implementation pass)

- API: `42 passed` (`tests/test_cc_v2.py` + `tests/test_cc_v2_catalogue.py`)
- Frontend vitest: `32` + `3` passed
- Playwright Express / Standard / assets: `8 passed`

## Peers (Law 27 gap)

GPT 5.4 is not on the Task allowlist. Review-only:

- [Claude Fable](2b7c9d26-e8c0-4114-bd4d-7509449ee6c8) — `READY FOR PRIMARY REVIEW`
- [Kimi K3](32cfc324-85b2-4d97-8f47-99c6a0c36493) — `READY FOR PRIMARY REVIEW`

## Remaining (not a dual-mode law fail)

- Close-up: UI/Standard path only; no live Close-up GPU job this pass.
- First with-ref Front `4405895c` hit the old 180s history cap and is not Adept evidence. Later jobs are.
- One Back poller hang after Comfy success was recovered; JobQueue core was not rewritten.

## Verdict

**GO — CHARACTER CREATOR T2I ONLY WHEN NO REFERENCE; I2I WHEN REFERENCE PRESENT**

Gates 2–6 from the I2I-correction pass remain GO for Front I2I, Qwen/Comfy catalogue, Auto-Prompt, Front visual lock, and asset/progress E2E. Close-up GPU remains uncertified.
