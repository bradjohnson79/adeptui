# Co-Director Full Avatar Studio Orchestration — Certification Report

**Date:** 2026-08-18 (Beta closure pass)  
**Branch:** `feat/movement-segments`  
**HEAD SHA at report:** `aa6b72b`  
**Project:** Schnick Coffee (`2347bf46-3762-4763-86c5-4a6032522278`) — never `POST /api/projects`  
**Session:** `avs-a10ef709c2` (Anadriya Presenter Session)  
**Law 27:** GPT 5.4 was unavailable. Subagent C used **inherit**. C does not issue GO/NO-GO.

This document is the **single governing report** for Co-Director Avatar Studio orchestration. Compact multi-speaker UX remains historically certified in `AVATAR_STUDIO_COMPACT_MULTI_SPEAKER_COMPLETION_REPORT.md`; that report does not govern this milestone.

Avatar Studio product code (compact UX, session contract, packet, tools, `workspaceTab`, events, memory, InfiniteTalk adapters) stayed **frozen** this pass. Work was identity-verified `:8758` recycle, live Beta recertification, and a small healthy-vs-current adoption guard.

Governing cert this pass: Co-Director understands and **writes the real compact `AvatarSessionRow`**, preserves dialogue, obeys `certifiedReady`, stays in sync with the UI contract, and uses the same `create_job` path when a runtime is later certified. It is **not** a live InfiniteTalk / LongCat talking-head movie.

---

## Verdict

**NO-GO — CO-DIRECTOR AVATAR STUDIO ORCHESTRATION NOT CERTIFIED**

The **stale adopted Studio API / item 15** blocker is **cleared**. Live `:8758` now serves the Avatar State Packet (`Avatar Studio session inspected.`) with `apiRevision=aa6b72b`.

Remaining blocker: **live Beta Co-Director conversation**. Plan GO requires browser CD chat to read and write the same `AvatarSessionRow` the compact UI uses, on the new process. Observed on that process: chrome **Degraded** (`qwen3.6:35b-a3b · Connected`), user turn `What have I set up in Avatar Studio?` received, then **“Co-Director stopped before finishing the reply.”** No packet summary, no Korri/Anadriya lines, no InfiniteTalk / 16:9 / Repair Required in the chat transcript. Approved-proposal `create_plan` / `create_job` writes are **not** a substitute for that chat gate.

---

## Why `:8758` was stale (root cause)

`scripts/beta_runtime/supervisor.py` `preflight` adopted any healthy `/api/health` listener. `Stop-AdeptUI-Beta.ps1` then left adopted APIs running. `Restart-AdeptUI-Beta.ps1` therefore could not refresh Python.

Authoritative Studio-API-only recycle used this pass:

```powershell
.\Restart-AdeptBetaBackend.ps1 -Service studio_api -Force
.\Start-AdeptUI-Beta.ps1 -NoBrowser
```

That targets identity-verified `uvicorn` + `app.main` (or port owner). ComfyUI `:8188` was never killed.

---

## PID trees

Do not trust PIDs from earlier reports (`35484` / `11688`). Re-measured this pass.

### Before recycle (prior governing blocker)

| Field | Value |
|---|---|
| Listener / worker | `35484` / `11688` |
| Supervisor spawn | `2026-08-18T20:16:59Z` |
| `--workers` | `2` |
| Inspect | `_summary` = `Avatar presentation session inspected.` + `presentationPlan` |
| Catalog | omitted `avatar.open_studio` / `avatar.detect_speakers` |

Check A at the start of **this** closure already returned the **new** packet on a later tree (parent `47804` / listener `7124`, `start_api.py`, workers=1). Recycle still ran so recert and the health-revision guard loaded on a process started in this pass.

### Recycle method

`Restart-AdeptBetaBackend.ps1 -Service studio_api -Force`, then `Start-AdeptUI-Beta.ps1 -NoBrowser`. Intermediate trees (`51476`/`3684`, later `45852`/`50036`, `51988`/`21080`) died or were superseded during chat timeouts. Comfy `:8188` PID **`39708`** (`ComfyUI\main.py`, started 2026-08-17 17:48) was left alone throughout.

### Current process (recert authority)

| Field | Value |
|---|---|
| Supervisor | PID **8356** `scripts\beta_runtime\supervisor.py run` (started 2026-08-18 16:22:29 local) |
| Uvicorn parent | PID **46808** `studio-api\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8758 --workers 2` |
| Workers | **53872**, **57320** (listen `:8758`) |
| `apiRevision` | `aa6b72b` |
| `apiStartedAt` | `2026-08-18T23:39:02Z` |
| `data/runtime/beta/status.json` | `adopted: false` (supervisor **spawned** current API) |
| Comfy | PID **39708** on `:8188` — untouched |
| Web | `http://127.0.0.1:8760/` **200**; `__beta_web_health` **200** |
| API | `http://127.0.0.1:8758/api/health` **200** |

---

## Inspect before / after

| Check | Before (stale class) | After (current process) |
|---|---|---|
| `_summary` | `Avatar presentation session inspected.` | `Avatar Studio session inspected.` |
| Payload | `presentationPlan` | Packet keys: sessionId, source*, mode, speakers, order, dialogue A/B, voice A/B, generator, runtimeStatus, certifiedReady, gateLine, aspect, lora, directionPrompt, active job |
| Catalog | omitted `avatar.open_studio` / `avatar.detect_speakers` | 516 tools; both present plus `create_plan` / `inspect` / `create_job` |

Live inspect now (`docs/release-gate/avatar/_closure-inspect-now.json`):

- Conversation, Korri / Anadriya, `order=b_then_a`
- Dialogue A `Absolutely not.` / B `Fresh pot, coming up.`
- InfiniteTalk, 16:9, `certifiedReady: false`
- Gate: InfiniteTalk needs repair — Open Runtime Setup
- Active job `avjob-a3f073aa25` queued, `resultAssetIds: []`

GET `AvatarSessionRow` matches: `dialogue_original` = those two lines, speakers Korri/Anadriya, `provider_choice=infinitetalk-local`.

---

## Live Schnick recert (Phases 7–12)

Principal proofs on live Beta `:8758` / `:8760`. Compact MAIN unchanged: Source → Speaker → Dialogue → Generator → Aspect → Generate. Session picker must be **Anadriya Presenter Session** (`avs-a10ef709c2`), not default Presenter 4.

| Phase | Action | Result |
|---|---|---|
| 7 | Live `avatar.inspect` | **PASS** — full packet on current revision |
| 8 | Browser CD chat: `What have I set up in Avatar Studio?` | **FAIL** — Degraded; “stopped before finishing the reply”; no packet in transcript |
| 9 | Chat: change Korri’s line / Switch them | **FAIL** via chat. **PASS** via approved `avatar.create_plan` proposal `f27f7ce2-172e-4f01-8368-06fab70c83cc` → Korri `Absolutely not.` (not a chat substitute) |
| 10 | Manual compact UI edit, then inspect | **PASS** — Speaker B `Fresh pot, coming up.`; GET + inspect + UI agree |
| 11 | `Generate it with InfiniteTalk.` | **FAIL** via chat. **PASS** via approved `avatar.create_job` `0318d600-b916-4478-9940-7aa64fd136af`: `executed: false`, runtime gate, `timelinePlacements: []`, job queued — no fake Library/Timeline/video |
| 12 | `Which Avatar Studio generators are ready?` | **FAIL** via chat. **PASS** via live `avatar.get_provider_status` / `inspect_runtime` (`certifiedReady: false`, both generators listed, not a static list) |

Unaudited `POST .../tools/audited` `avatar.create_plan` returned **502** `TOOL_EXECUTION_FAILED`: `'avatar.create_plan' requires an approved proposal.` (`requires_approval` defaults true even though `ROUTINE_TOOLS` includes `create_plan`). Schnick execution authority is not `AUTHORITY_DIRECT`, so `should_auto_approve` does not fire. Follow-up only — product tools frozen this pass.

No M4.10 approved takes; voice bindings stayed none (no silent substitute). Source asset still `c2ce0cc0-659a-49c3-8aa4-04a6ec5eda59`. Top-level `sourceCharacterId` may still be Anadriya (legacy); `speakers[]` are Korri/Anadriya. Schema not reopened.

Screenshots:

- `docs/release-gate/avatar/closure-session-ui-parity.png` — compact UI matches packet (conversation, Korri/Anadriya, B then A, InfiniteTalk, 16:9, Needs Repair)
- `docs/release-gate/avatar/closure-codirector-chat-fail.png` — CD Degraded, inspect question did not complete

Request/response logs: `_closure-inspect-now.json`, `_closure-session-now.json`, `_closure-live-writes.json`, `_closure-approve.json`.

---

## Tests

| Suite | Result |
|---|---|
| `studio-api/tests/test_codirector_avatar_orchestration.py` + `test_avatar_compact_speakers.py` + `test_api_revision_health.py` | **21 passed** |
| `studio-web` `npx vitest run src/avatar/compact.test.ts` | **10 passed** |

HealthOut unit/API test asserts `apiStartedAt` is a non-empty timestamp string and `apiRevision` is either null or a short SHA.

---

## Stale-adoption guard (Phase 16)

Implemented without rewriting the supervisor lifecycle:

- `GET /api/health` optional `apiRevision` (short git SHA of API cwd, or `ADEPT_API_REVISION`) and `apiStartedAt` (process start UTC), cached at import — no extra probes.
- Supervisor `preflight` adopts only when healthy **and** `apiRevision` matches repo `HEAD`. **Missing revision = stale.** If identity matches (`app.main` / `start_api.py` / uvicorn+port, skip ComfyUI `main.py`), recycle that listener then spawn. Unmanaged occupant without identity → `SystemExit`.
- Beta web proxy timeout `10s` → **`180s`** (connect 5s). Browser chat through `:8760` was cut by `STUDIO_API_TIMEOUT` because `avatar.inspect` alone is ~20–45s. Proxy still buffers the full response (not SSE streaming).

Follow-up (not this commit): true SSE proxy for `/api/codirector/chat/stream`; `create_plan` `requires_approval` vs `ROUTINE_TOOLS`; Co-Director LLM Degraded / stop-before-finish on `qwen3.6:35b-a3b`.

---

## Beta URLs (leave running)

| URL | Status |
|---|---|
| `http://127.0.0.1:8760/` | **200** creator UI |
| `http://127.0.0.1:8760/__beta_web_health` | **200** |
| `http://127.0.0.1:8758/api/health` | **200** `apiRevision=aa6b72b` |

---

## E2E TRACE

| Stage | Result |
|---|---|
| User action | PASS (compact UI + CD tools). FAIL (browser CD chat did not complete) |
| Frontend | PASS compact persist / Voice A/B / MAIN. FAIL CD chat (Degraded, stopped before reply) |
| API | **PASS** — current-process inspect packet, catalog includes `open_studio` / `detect_speakers` |
| Backend | PASS `create_plan` / `create_job` gate on approved proposals |
| Persistence | PASS Schnick `AvatarSessionRow`; GET matches inspect and UI |
| Runtime | N/A / honest refuse (`certifiedReady: false`) |
| Result | N/A (no fake media) |
| Reload | PASS row survives GET |
| Downstream Library/Timeline | N/A (Repair Required, `timelineWritten` not claimed) |

---

## Limitations (honest)

- InfiniteTalk / LongCat remain uncertified. Generation stays blocked with creator-facing Runtime Setup copy. No hosted InfiniteTalk claim.
- Live Beta CD **chat** did not read or write the session on the new process.
- Proxy is still a buffering reverse proxy; 180s is a timeout floor, not streaming.
- Schnick has no M4.10 approved takes; CD must offer Voice Studio rather than copy another character’s take.

---

## Manual review path

1. Open Schnick Coffee at `http://127.0.0.1:8760/` → Avatar Studio → session **Anadriya Presenter Session**.
2. Confirm Korri `Absolutely not.` / Anadriya `Fresh pot, coming up.` / B then A / InfiniteTalk / 16:9 / Generate disabled / Repair Required.
3. Co-Director is currently **Degraded**. Asking “what have I set up?” is the remaining GO gate: reply must cite conversation, both names, order, exact lines, InfiniteTalk, 16:9, Repair Required — not a presentation-plan summary.
4. Generate must report InfiniteTalk needs repair — no fake clip, no silent generator switch.

---

## Subagent C (item 15 recert)

Law 27: GPT 5.4 unavailable; C used **inherit**. C does not issue GO/NO-GO.

[C recert item 15](44f9ea38-29f2-418a-810f-a0dff929adc2): **READY FOR PRIMARY REVIEW**.

| # | Item | C |
|---|---|---|
| 1 | Same `AvatarSessionRow` | PASS (spot-check) |
| 4 | Packet in snapshot + live inspect | PASS (spot-check) |
| 8 | Honest `create_job` gate | PASS (spot-check) |
| 9 | `workspaceTab` + exposure | PASS (spot-check) |
| 14 | Live Schnick write + GET parity | PASS (spot-check) |
| 15 | Live Beta inspect packet | **PASS** |
| 17 | InfiniteTalk not claimed complete | PASS (spot-check) |

Independent tests: 21 pytest / 10 vitest. Chat LLM not observed by C and must not fail item 15.

Prior C [d56c3e07-5e84-45d3-91b0-5b7c27ae589c] item 15 FAIL (stale API) is superseded by this pass.

Primary final line remains: `NO-GO — CO-DIRECTOR AVATAR STUDIO ORCHESTRATION NOT CERTIFIED` until live Beta CD chat reads and writes the same row the UI uses.

---

## Files in this closure commit (do not mix Mini / Spatial / Movement / Timeline)

- `studio-api/app/schemas.py` — `HealthOut.apiRevision` / `apiStartedAt`
- `studio-api/app/routers/api.py` — health revision fields only
- `scripts/beta_runtime/supervisor.py` — refuse-adopt when revision missing/mismatch
- `scripts/beta_runtime/web_server.py` — 180s proxy timeout
- `studio-api/tests/test_api_revision_health.py`
- this report + recert screenshots
