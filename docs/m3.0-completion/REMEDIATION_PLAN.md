# M3.0 Completion — Remediation Plan

Ordered phases matching the M3.0 Completion Closure plan. Phase 0 (this baseline) is complete when both files under `docs/m3.0-completion/` exist. **Do not edit the plan file.**

| Phase | Focus | Exit criteria (summary) |
|------:|-------|-------------------------|
| 0 | Baseline audit | `PHASE0_BASELINE_AUDIT.md` + this plan written (UTF-8); dirty tree + fal/Comfy/blockers/PW inventory recorded |
| 1 | **B4** — audio → Director timeline | Generate/import with real `assetId` + `sceneId` auto-places (or explicit promote); pytest + Playwright proof; `B4_AUDIO_TIMELINE_PROOF.md` |
| 2 | **B10** — Bible apply in browser | Fix mock/`CharacterData` field names; approve → version changes / reject → unchanged; `B10_BIBLE_BROWSER_PROOF.md` |
| 3 | **Flags** / Unified Experience E2E | Enable required M2.9/M2.14 flags in `e2e-start.mjs`; fix `/codirector` → `/co-director`; health serializes `unifiedExperienceEnabled`; ON/OFF UI proof |
| 4 | **Playwright** closure | Repair remaining five fails; classify every skip; 0 unexplained failures; update PW result docs + `PLAYWRIGHT_CLOSURE.md` |
| 5 | **Local** Comfy real artifact | Preflight only (no downloads); one real Adept-path local job; Asset + checksum + provenance; `REAL_LOCAL_ARTIFACT_PROOF.md`; gated local-live PW |
| 6 | **fal bridge** + Asset path | Bridge `.env` `FAL_API_KEY` → encrypted `fal_api_key`; reuse existing C2 MP4/`request_id` for Asset/queue/browser proof (no paid resubmit unless required); `REAL_FAL_ARTIFACT_PROOF.md` |
| 7 | **Catalog** truth | Update `FAL_AI_CAPABILITY_MATRIX.md`: Seedance T2V live-tested; I2V accurate; Seedream/Nano Banana/GPT Image not registered |
| 8 | **Intelligence** | `use_provider=True` when provider available and not E2E; limited-analysis labeling otherwise; two briefs → non-identical outputs when Ollama up; `CODIRECTOR_INTELLIGENCE_PROOF.md` |
| 9 | **Situations** (core reruns) | Fixtures OFF: dramatic, music video, animated/stylized, reconstruction (honest scope), short-form capstone — real artifact + persist + inspect + approval |
| 10 | **Situations** (full matrix eval) | Evaluate remaining situations toward the 12; `EXECUTED` only with real proof; `SITUATION_RERUN_RESULTS.md`; do not manufacture 12/12 |
| 11 | **Coverage** refresh | Update `CODIRECTOR_CAPABILITY_COVERAGE.md` + `FULL_STACK_WIRING_MATRIX.md` from post-fix chains |
| 12 | **Secrets** / trace audit | `SECRET_AND_TRACE_AUDIT.md`; grep key prefixes, Authorization, `.env` staging, PW traces; stop for rotation if exposure found |
| 13 | **Commit** + final reports | Stage source/docs/tests only; green backend + PW totals; commit implementation then docs; `M3.0_COMPLETION_*` reports; honest beta verdicts; clean tree for evaluated SHAs |

### Phase notes (locked product choices)

- Local proof uses **already-installed** Comfy weights (Z-Image UNET present; LTX/Wan checkpoints present). No new downloads.
- fal proof prefers existing Seedance T2V artifact (`019fa1fc-e05f-7d80-9908-e6d0c3e8d4fc`). Hard cap **$5**.
- Audio timeline proof may use a **real imported WAV** when generative audio is absent (honest scope).
- Manifest sha256 `cf99d7e5…` must remain unchanged through all phases.
- Phase 13 commits only when gates are green; Phase 0–12 do not commit unless separately mandated.

### Non-actions (hard)

No mocks to greenwash; no fixture fallbacks in production; no invented fal image endpoints; no Manifest edits; no silent Bible/timeline mutation; no key in logs/docs/chat; no dirty-tree "final" SHA.
