# Timeline Inspector — Generator Settings + Continuity + Advanced Restore

Governing document for this gate.

| Field | Value |
| --- | --- |
| Date | 2026-09-17 |
| Branch | `feat/character-creator-final-closure` |
| HEAD (committed baseline) | `99665cf76693e359cedc60c50c4405daf1b4e3a1` |
| Review URLs | Creator UI `http://127.0.0.1:5173/` · Studio API `http://127.0.0.1:8758/` |

## Verdict

**GO** — generator settings sit under Generator, Native Audio is live, Continuity and Advanced are restored from history.

| Reviewer | Verdict |
| --- | --- |
| Kimi K3 | AGREE |
| GLM 5.2 | AGREE |
| GPT-5.6 Sol | AGREE |

## Historical audit (source/history, not invented)

| Previous control | Surface | Still exists? | Wiring | Restore? |
| --- | --- | --- | --- | --- |
| MiniMax H3 Megapixels (`timeline-batch-resolution`, `timeline-inspector-megapixels`) | Scene Generation + Batch (was dumped into Batch Advanced) | EXISTS | CONNECTED (`h3Resolution` patch) | YES — move under Generator; show only when registry `qualityControl=h3_megapixels` |
| LTX Video Quality (`timeline-batch-quality`, `timeline-inspector-quality`) | Scene Generation + Batch Advanced dump | EXISTS | CONNECTED (`ltxQuality` patch) | YES — move under Generator; show only when `qualityControl=ltx_quality` |
| Native Audio provenance (`timeline-batch-audio-provenance`) | Batch Advanced read-only label | EXISTS, was stale | DISCONNECTED join (`audio_generation` dropped on Production Control path) | YES — live capability status under Generation, not Advanced |
| Co-Director Continuity enable / Review / Protection / Deep Review / next-shot note | Scene Extend & Continuity (`1e4f10c2`) | EXISTS | CONNECTED | YES — same implementation reused on Batch |
| Auto Continuity window / local lock / extend status | Scene | EXISTS | CONNECTED | YES — same panel |
| Continuity bridge status / Retry / Continue without matching | Batch (`timeline-batch-continuity-status`) | EXISTS | CONNECTED | YES — keep Batch-only bridge block |
| Scene Advanced LoRA (`LoRASelector`) | Scene Advanced (`d6b5a7f9`) | EXISTS | CONNECTED | YES — last owner-approved Advanced contents |
| Batch Advanced quality dump | Batch Advanced (accordion restore 2026-09-16) | EXISTS, wrong place | CONNECTED | NO as Advanced — relocate to Generation |
| Native Audio On/Off | never existed | MISSING | n/a | NO — do not invent; H3/LTX are not user-toggled |

## Architecture

```
selected generator
  → adapter VideoGeneratorCapabilities
  → timelineAdapters / generators snapshot
  → joinProductionControlVideoOptions
  → Inspector GeneratorQualityControls + resolveNativeAudioState
```

- `qualityControl`: `h3_megapixels` \| `ltx_quality` \| none. Declared on the adapter. Not inferred from `generator.includes("minimax")`.
- Native Audio distinguishes **SUPPORTED BY MODEL** (`audio_generation`) from **AVAILABLE IN CURRENT RUNTIME** (`executable` / readiness). Status: Checking… / SUPPORTED / NOT SUPPORTED / OFFLINE / UNAVAILABLE.
- Per-batch persistence: `h3Resolution` and `ltxQuality` remain independent fields. Switching H3 → LTX swaps the control immediately and restores the saved value on switch-back.
- Extend & Continuity: existing Scene policy controls + existing Batch bridge actions. No new continuity settings.
- Advanced: LoRA only (last owner-approved Advanced). Megapixels, LTX quality, and Native Audio are not in Advanced.

## Tests

| Suite | Result |
| --- | --- |
| Vitest `draftCapabilities` + Inspector preflight | **15 passed** |
| pytest `test_native_audio_preservation.py` | **16 passed** |
| Playwright `timeline-inspector-generator-capabilities.spec.ts` live `:5173`/`:8758` | **1 passed (12.3s)** |

Live registry after API recycle:

- MiniMax H3 (`minimax-h3-t2v-local`): `qualityControl=h3_megapixels`, `audio_generation=True`
- LTX 2.5 (`ltx-2.5-distilled`): `qualityControl=ltx_quality`, `audio_generation=True`

## Runtime / Comfy

| Check | Result |
| --- | --- |
| COMFY BEFORE | PID **34484** / health 200 |
| COMFY AFTER | PID **34484** / health 200 |
| COMFY RESTARTED? | **NO** |
| Studio API | recycled only (`scripts/restart_studio_api_only.py`) · `/api/healthz` **200** |
| Creator UI | `http://127.0.0.1:5173/` **200** |

## Peer question

Does this implementation correctly colocate generator-specific settings beneath Generator, drive those settings from the capability registry/runtime rather than display-name strings or mocks, show Native Audio from the selected generator’s actual adapter/runtime contract, restore Extend & Continuity from the existing Scene/Batch implementation rather than inventing controls, and restore Advanced as LoRA rather than a miscellaneous settings bucket?

## Limitations

- Native Audio On/Off is not offered; adapters do not expose a user toggle.
- Generator inventory refreshes on `reloadKey`, not a new polling engine.
- Playwright uses a disposable Korri scene. No GPU generate was queued.
