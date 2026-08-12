# Co-Director 2.0 — Operator / Navigation / Mock-Surface Audit (Phase 1, READ-ONLY)

**Audit scope:** Operator-like (fire-and-forget) tools in `studio-api/app/codirector/tools/handlers/` and their frontend reception in `studio-web/src`, plus every mock / E2E / scripted-injection surface that could leak into creator/Beta/production mode (Law 8 fail-closed).

**Date:** 2026-08-08 · **Phase:** 1 (audit only — no implementation performed) · **Classification:** operator / navigation / mock-surface

All citations are `file:line` relative to `studio-api/` or `studio-web/` as noted. This is a **sibling** to `CODIRECTOR2_INTENT_STAGE_ROUTER_AUDIT.md`, `CODIRECTOR2_CONVERSATION_SUBSYSTEM_AUDIT.md`, and `CODIRECTOR2_REQUEST_LIFECYCLE_AUDIT.md`.

---

## PART A — Operator-like actions (fire-and-forget navigation)

### A.1 Inventory

Eight tools are registered as navigation/UI-handoff surfaces. **All eight are `kind="read"`** (`definitions.py` — no preview/apply, no proposal, no approval), so they execute instantly during a chat turn and their handler return value is the **only** output. There is no separate operator/action lane: "open X" is just a read tool whose result the LLM reads back and paraphrases.

| # | Tool id (exposed to Co-Director) | Handler fn | Definition `kind` | Registry binding |
|---|---|---|---|---|
| 1 | `timeline.focus_ui` | `director_timeline_tools.focus_ui` (director_timeline_tools.py:698-733) | read | registry.py:278 |
| 2 | `posecraft.open_scene` | `posecraft.open_scene` (posecraft.py:82-85) | read | registry.py:320 |
| 3 | `voice_performance.open_workspace` | `voice_performance.open_workspace` (voice_performance.py:111-120) | read | registry.py:142 |
| 4 | `audio.open_studio` | `audio_studio_tools.open_studio` (audio_studio_tools.py:486-493) | read | registry.py:187 |
| 5 | `runtime.open_manager` | `docker_runtime_tools.runtime_open_manager` (docker_runtime_tools.py:83-88) | read | registry.py:215 |
| 6 | `character_creator.open_voice_creator` | `character_creator.open_voice_creator` (character_creator.py:795-805) | read | registry.py:127 |
| 7 | `references.open` | `scene_references_w6p.open_pane` (scene_references_w6p.py:82-89) | read | registry.py:260 |
| 8 | `continuity.open_workspace` | `continuity_w5.open_workspace` (continuity_w5.py:119-129) | read | registry.py:270 |

A ninth surface is a **mutating** tool, not read: `voice_environment.open_audio_studio` (registry.py:481-484; preview `voice_environment.py:1025-1036`, apply `voice_environment.py:1039-1049`) — it goes through proposal→approval and only then returns `uiAction:"open_audio_studio"`. It is the only "open" that is approval-gated.

Additional passive navigation *hints* embedded in unrelated read results (no dedicated tool):
- `scriptwriter_tools.py:27` — `recommended_action="open_scriptwriter"` on the **error** path of `_doc_id` (no script document in project). Not a success path; nothing navigates.
- `voice_environment._voice_handoff` (voice_environment.py:75-82) returns `uiAction/workspaceUrl/routeHint` and is reused by several voice read handlers (voice_environment.py:224, 262, 276) and the mutation `apply_open_audio_studio` (:1044-1045).
- `audio_studio_tools` embeds `workspaceUrl` in ~10 preview/read results (audio_studio_tools.py:203, 284, 353, 376, 397, 436, 465, 478, 543, 641, 710) **without** `uiAction` — these never trigger navigation (see A.3).

### A.2 What each handler actually does

1. **`timeline.focus_ui`** (director_timeline_tools.py:698-733): validates `target` against `_FOCUS_TARGETS` (:686-695), returns `ok:True`, a `uiFocus`/`_uiFocus` directive, `message`, and a `_evidence` receipt. **It does not touch state** — no DB write, no event, no flag. It is a pure structured return. The one genuine navigation directive in the family.
2. **`posecraft.open_scene`** (posecraft.py:82-85): despite the name it **is not navigation** — it returns the live PoseCraft scene document (`scene.model_dump()` + `semantic` summary). It is a data read mislabeled as "open". No UI directive of any kind in the result.
3. **`voice_performance.open_workspace`** (voice_performance.py:111-120): returns `ok:True`, `uiAction:"open_voice_performance"`, `characterId`, `projectId`, `workspaceUrl` (`/project/{id}?workspace=voicestudio&characterId=…`), `_evidence`. Fire-and-forget: the frontend **may** navigate (A.3).
4. **`audio.open_studio`** (audio_studio_tools.py:486-493): returns `ok:True`, `uiAction:"open_audio_studio"`, `projectId`, `workspaceUrl`. Fire-and-forget: frontend **may** switch tab (A.3).
5. **`runtime.open_manager`** (docker_runtime_tools.py:83-88): returns `route:"/runtime-manager"`, `hint`, `_summary`. **No `uiAction`, no `workspaceUrl`, no `ok` flag** — the frontend has no consumer for `route` (A.3). Pure text claiming a deep-link.
6. **`character_creator.open_voice_creator`** (character_creator.py:795-805): returns `ok:True`, `uiAction:"open_voice_creator"`, `characterId`, `workspaceUrl`, `routeHint`, `mock:False`. Fire-and-forget: frontend **may** navigate (A.3).
7. **`references.open`** (scene_references_w6p.py:82-89): returns `workspace:"timeline"`, `pane:"references"`, `scopeType/scopeId`, `_evidence`. **No `uiAction`, no `workspaceUrl`, no `ok` flag** — the frontend has no consumer for `workspace`+`pane` from a tool result (A.3).
8. **`continuity.open_workspace`** (continuity_w5.py:119-129): returns `action:"navigate"`, `workspace` (whitelisted to continuity/identityregistry/timeline/magi/bible, default continuity), `projectId`, `message`, `_evidence`. **No `uiAction`, no `workspaceUrl`, no `ok`** — the frontend has no consumer for `action:"navigate"` (A.3).

**Ack channel:** none of the eight (nor the `voice_environment.open_audio_studio` mutation) has any acknowledgement, ack channel, pending UX, timeout, retry, or origin-session/tab correlation. Every handler returns synchronously from pure logic; there is no way for the server to know (or for the creator to learn) whether the UI actually honored the directive.

### A.3 Frontend reception channel (`studio-web/src`)

The single reception point is the SSE `tool_completed` handler in `components/CoDirector/CoDirectorSession.tsx:1710-1762`. The server emits `tool_completed` carrying `invocation.result` (codirector/service.py:755-760; read path `service.py:703-760`). The frontend then inspects the result:

- **`uiAction`** (CoDirectorSession.tsx:1713-1749) — the **only** result field that triggers navigation:
  - `open_voice_performance` / `open_voice_creator` (1714-1734): if `workspaceUrl` present → `navigate(workspaceUrl)` (:1718) — real route change to `?workspace=voicestudio`. Else `onGoTab("characters")` + dispatch `adept:open-character-voice` (:1726) → consumed by `components/CharacterProfileWorkspace.tsx:331`.
  - `open_audio_studio` (1735-1749): `onGoTab("audiostudio")` + dispatch `adept:open-audio-studio` (:1742) — **this CustomEvent has no listener anywhere** (grep across `studio-web/src` finds only the dispatcher). The effective channel is the `onGoTab("audiostudio")` tab binding.
- **`_uiFocus`/`uiFocus`** (1750-1762): if `target` present → `onGoTab("timeline")` + dispatch `adept-timeline-focus` (:1758) → consumed by `timeline-master/TimelineEditorShell.tsx:202` (event name `TIMELINE_FOCUS_EVENT`, timelineMaster/timelineFocus.ts:35). This is the one end-to-end focus bus that is actually wired: CoDirectorSession dispatches, TimelineEditorShell focuses (TimelineEditorShell.tsx:182-204).
- **No consumer** for: `result.action==="navigate"` (continuity), `result.workspace`/`result.pane` (references), `result.route` (runtime manager), or any scriptwriter navigation. `recommendedAction`/`recommended_action` from the server is preserved into `classifyCoDirectorError` (api.ts:730-775) and rendered as a *label* (`capabilities.ts:177`), **never** used to navigate.

Workspace routing itself: `pages/ProjectEditor.tsx:537-557` reads `?workspace=` / `?tab=` on load and `resolveWorkspace` (core/workspaces.ts:480-492) canonicalizes; `go()` at ProjectEditor.tsx:564-580 pushes a `?workspace=` route. Named workspaces exist for `voicestudio` (workspaces.ts:310), `audiostudio` (:402), `scriptwriter` (:428), `continuity` (:362), `identityregistry` (:348), `timeline` (:145), `magi` (:375), `bible` (:335). So the *routes* are all resolvable — but **no tool result ever produces a navigation to most of them**.

**Reception summary:** only voice (`navigate`/`onGoTab`), audio (`onGoTab`), and timeline-focus (`adept-timeline-focus` bus) have working channels. `adept:open-audio-studio` and `adept:open-character-voice` (when no `workspaceUrl`) are partially dead; `references.open`, `continuity.open_workspace`, `runtime.open_manager` results are **completely inert on the frontend**.

### A.4 The specific 2.0 defect — "Co-Director claimed Script Writer was open when nothing opened"

Exact false-success path today:

1. Creator asks Co-Director to "open Script Writer" (or Co-Director decides to). The intent classifier has **no NAVIGATE intent** (see `CODIRECTOR2_INTENT_STAGE_ROUTER_AUDIT.md:120`) and **no `open` handler** (`:142`). There is **no registered tool that opens the Script Writer workspace** — the `script.*` domain is reads + proposal mutations only (registry.py:199-211, 705-725).
2. The model therefore selects the closest available read tool — typically `script.inspect` (`scriptwriter_tools.py:45-58`) or `script.get`/`script.list`. These execute fine and return the document JSON. Server emits `tool_completed` with `invocation.result` (service.py:755-760). Result contains **no `uiAction`, no `workspaceUrl`, no `uiFocus`**.
3. Frontend `CoDirectorSession.tsx:1710-1762` finds no actionable field → **no navigation occurs**. The tab stays wherever it was.
4. The model, seeing a successful tool result containing a script document (rendered back via `render_result_for_model`, tools/sanitize.py:293-296), paraphrases in prose: *"Script Writer is open"* / *"I've opened the Script Writer document"*. Nothing opened. There is no server-side grounding gate on "opened/opened the script" phrasing (the existing premature-claim gate at `service.py:2230-2236` only corrects wiki-claim phrasings *after* the fact, never retracts streamed tokens — see `CODIRECTOR2_REQUEST_LIFECYCLE_AUDIT.md:224`), and no ack channel to contradict the claim.
5. Error-adjacent variant: when no script document exists, `_doc_id` raises `TOOL_TARGET_NOT_FOUND` with `recommended_action="open_scriptwriter"` (scriptwriter_tools.py:22-28). The model may say "let me open Script Writer" — the `recommendedAction` is a string label only; nothing navigates.

Root cause is a **three-part contract gap**: (i) no `open/scriptwriter` tool and no navigation intent, (ii) the `script.*` reads return data that looks like an opened workspace, (iii) the frontend navigation contract only keys on `uiAction`/`uiFocus` — absent here, nothing happens, and nothing verifies. The same pattern threatens `runtime.open_manager` ("Open Runtime Manager" claim, docker_runtime_tools.py:86-87), `references.open`, and `continuity.open_workspace` ("navigation hint only — no mutation", definitions.py:2357, 2453).

### A.5 Duplicate implementations

- **Same navigation offered by multiple tools:**
  - `?workspace=voicestudio` — reachable from `voice_performance.open_workspace` (voice_performance.py:118), `character_creator.open_voice_creator` (character_creator.py:801), `voice_environment._voice_handoff` (voice_environment.py:71-82; reused in inspect_studio :224, inspect_character :262, inspect_identity :276). Three registrations, one destination.
  - `?workspace=audiostudio` — `audio.open_studio` (audio_studio_tools.py:491), `voice_environment.apply_open_audio_studio` (voice_environment.py:1045), plus ~10 non-navigating `workspaceUrl` embeddings (audio_studio_tools.py:203, 284, 353, 376, 397, 436, 465, 478, 543, 641, 710).
  - Timeline workspace: `continuity.open_workspace` with `workspace:"timeline"` (continuity_w5.py:121) overlaps `timeline.focus_ui`'s implicit timeline switch (CoDirectorSession.tsx:1753) — two divergent mechanisms (inert `action:navigate` vs live `adept-timeline-focus` bus).
  - `references.open`'s `workspace:"timeline"` + `pane:"references"` (scene_references_w6p.py:84-85) also targets the timeline surface.
- **Frontend surface aliases** (core/workspaces.ts compatibilityAliases): `audiostudio` accepts `audio`/`audio-studio` (:407); `voicestudio`/`characters` accept several (characters: `character`,`character-profile`,`character-identity`,`identity` :327); `scriptwriter` accepts `script-writer`/`writer` (:433) plus `resolveWorkspace` hard-maps `script-writer`/`writer` → `scriptwriter` (:490). Multiple spellings of the same destination, none driven by a tool result.
- **No two handlers perform the same *server-side* navigation** (because no handler navigates at all — all are returns). Duplication is in *destination strings*, not behavior.

### A.6 Operator-tool classification matrix

| Surface | Current Role | Handler fn / citations | Classification | Target Role in 2.0 | Risk |
|---|---|---|---|---|---|
| `timeline.focus_ui` | read directive, live bus | director_timeline_tools.py:698-733; CoDirectorSession.tsx:1750-1762; TimelineEditorShell.tsx:202 | **KEEP/EXTEND** | Deterministic focus command in a real operator action lane with server-verified receipt + pending UX | Medium (bus works, but claim is unverified; `adept-timeline-focus` gap: no pending/ack) |
| `posecraft.open_scene` | mislabeled data read | posecraft.py:82-85 | **SUPERSEDE** | Rename to `posecraft.get_scene`; navigation only if 2.0 operator lane opens PoseCraft | High (name claims "open", does data read — prime false-success shape) |
| `voice_performance.open_workspace` | read handoff (works) | voice_performance.py:111-120; CoDirectorSession.tsx:1714-1734 | **ADAPT** | Move into operator lane; add pending UX + ack + tab-correlation | Medium (works today via navigate; unverified) |
| `audio.open_studio` | read handoff (partially works) | audio_studio_tools.py:486-493; CoDirectorSession.tsx:1735-1749 | **ADAPT** | Operator lane; drop dead `adept:open-audio-studio` event or wire a listener | Medium |
| `runtime.open_manager` | inert text route | docker_runtime_tools.py:83-88 | **SUPERSEDE/REMOVE** | Operator lane with real `/runtime-manager` route or remove until navigable | High (claims "Open Runtime Manager", frontend ignores `route`) |
| `character_creator.open_voice_creator` | read handoff (works) | character_creator.py:795-805; CoDirectorSession.tsx:1714-1734 | **ADAPT** | Merge with `voice_performance.open_workspace` — duplicate destination | Medium (duplication) |
| `references.open` | inert pane hint | scene_references_w6p.py:82-89 | **SUPERSEDE/REMOVE** | Navigate via operator lane or remove; no consumer today | High (inert) |
| `continuity.open_workspace` | inert navigate dict | continuity_w5.py:119-129; definitions.py:2453 ("navigation hint only") | **SUPERSEDE/REMOVE** | Operator lane with validated surface or remove | High (inert; overlaps timeline surface) |
| `voice_environment.open_audio_studio` (mutation) | approval-gated open | voice_environment.py:1025-1049; registry.py:481-484 | **KEEP** | Only real proposal-gated open; keep as template for 2.0 operator lane | Low-Medium |
| `script.*` reads + `recommended_action="open_scriptwriter"` | data reads, no open | scriptwriter_tools.py:22-28, 45-58 | **ADAPT** | Add deterministic `open scriptwriter` tool/intent (Phase-8 gap per CONVERSATION_SUBSYSTEM_AUDIT.md:116); ground "opened" phrasing | **HIGH — the 2.0 target defect** |
| `workspaceUrl` embeddings without `uiAction` (audio previews etc.) | inert hints | audio_studio_tools.py:203,284,353,376,397,436,465,478,543,641,710 | **REMOVE/ADAPT** | Only operator-lane results may carry navigation payloads | Medium (confusing model + dead payload) |

---

## PART B — Mock / E2E injection surfaces (Law 8: fail closed)

### B.1 Provider selection + mock providers

**Co-Director LLM provider** (`codirector/service.py`):
- `e2e_enabled()` service.py:90-91 — `STUDIO_E2E ∈ {1,true,TRUE,yes,YES}`.
- `_mock_provider_allowed()` service.py:94-131 — mock requires **STUDIO_E2E AND** (not `ADEPT_ENV=production` OR explicit opt-in `config allowMockProvider=true` OR `ADEPT_ALLOW_MOCK_PROVIDER` env). Hard production block even with a stray `STUDIO_E2E` (service.py:102-106).
- `active_provider_id()` service.py:137-161 — `ADEPT_CODIRECTOR_PROVIDER` wins only if `_mock_provider_allowed()` for `mock` (else falls back to `ollama`, :147-156); with E2E on and no override, defaults to `mock` (:159-160).
- `list_provider_ids()` service.py:164-168 — mock hidden from the selectable list unless allowed.
- `build_provider()` service.py:171-197 — instantiating `mock` without the guard raises `PROVIDER_NOT_CONFIGURED` (:172-183). **Gate complete at the service layer.**
- `MockCoDirectorProvider` providers/mock.py:189-528 — deterministic responses; health always `test_only:True` (:223). Scenario read from `ADEPT_CODIRECTOR_MOCK_SCENARIO` (:21-22).

**Vision provider** (`codirector/vision/providers/__init__.py:17-35`): `provider=="mock"` requires `STUDIO_E2E`, else `VisionProviderUnavailable` (:28-34). Default `get_provider` falls through to `LocalVisionProvider` (:35). `MockVisionProvider` (vision/providers/mock.py:78-106) is fixture-only. **Gate complete.** Executive validate path hard-blocks `provider=="mock"` at `executive/handlers.py:209-214`.

**ImageGen closed-loop** (`codirector/executive/imagegen_adapter.py`): `mock_imagegen_env_enabled()` (:25-30) is **informational only**; `should_use_mock_imagegen()` always returns False (:50-52) and the poller never mock-completes (`del allow_mock`, :121; raises on Comfy-unavailable, :157-194). **Gate complete by construction (no mock path exists on the runtime path).**

### B.2 E2E / script-injection endpoints

- **`routers/e2e.py`** (all routes `POST/GET/DELETE /api/e2e/*`): every handler begins `if not e2e_enabled(): raise HTTPException(404)` (e2e.py:19-20, 32-33, 49-50, 62-63, 73-74, 140-141, 166-167, 189-190, 216-217, 234-235, 277-278, 293-294, 332-333). The router is **also** only mounted when `STUDIO_E2E` is set (`main.py:510-516`). Double gate: mount-level + per-handler.
- **Scripted mock injection**: `POST/DELETE /api/e2e/codirector/script` (e2e.py:177-221) installs/clears `_SCRIPTED_STEPS` (module-level list, providers/mock.py:38). Reachable only through the gated router; the scripted branch only fires when `scenario=="scripted"` (providers/mock.py:328-339) and the mock provider is active. **Gate complete.**
- **Scenario injection**: `POST /api/e2e/codirector/scenario` (e2e.py:158-174) flips `ADEPT_CODIRECTOR_MOCK_SCENARIO` for the process — same gate. **Gate complete.**
- **Feature-flag mutation**: `POST /api/e2e/feature-flags` (e2e.py:224-271) mutates the live `feature_flags` singleton via env (`STUDIO_FEATURE_*`). Gated. **Gate complete** (this is powerful; worth noting it mutates module-level singletons).
- **In-process mock-LLM/injection on the live chat path**: `_e2e_overrides()` in `tools/capabilities.py:79-91` and `_e2e_execution_fault()` in `tools/execution.py:58-71` both start with `if not e2e_enabled(): return False/{}`. **Gate complete.**
- **`m213` `/api/codirector/m213/e2e/guided`** (codirector/m213/api.py:449-457): route is **mounted unconditionally** via the codirector router (`routers/codirector.py:56` → `main.py:284`), but the handler 403s unless `persistence.e2e_enabled()` (m213/api.py:452-456). Fixtures env-gated (m213/flags.py:19-27). Gate is **handler-level, not mount-level** — a working-but-ungated-at-mount route; functionally closed, but flag for defense-in-depth.
- **`m28` fixtures** (m28/fixtures.py:28-34), **`m29` fixture bridge** (m29/providers.py:46-63; client `fixtureComplete`/`mockAdapter`/`forceMock` payload keys are stripped/sanitized, m29/providers.py:29, 66-70), **`m211`** (m211/api.py:260-264 labels heuristic), **`m214` honesty labels** (m214/honesty.py:24-43): all env-gated (`STUDIO_E2E` or dedicated `ADEPT_M2x_FIXTURE_MODE`), all return `unavailable`/honest labels outside E2E.
- **`generation_tools/ops.py`** fixture paths (ops.py:21-22 `_e2e()`, and fixture branches at :198, :385, :574, :664, :711, :725, :753): E2E-only synthesized placeholder assets/WAVs/Jobs are **honestly marked** (`e2eFixture:True`, `model="e2e-fixture"`, ops.py:215-217, 397-398, 680). Outside E2E these branches are unreachable and the tools DEFER/BLOCK instead (e.g. ops.py:711-724). **Gate complete.**
- **`source_manager/providers/fixture.py`** FixtureProvider (fixture.py:19-60): enabled only by `STUDIO_E2E` OR explicit `ADEPT_PACK_PROVIDER=fixture_http` OR `ADEPT_ENABLE_FIXTURE_PROVIDER` opt-in (:32-41). **Gate complete** (opt-in surface, not silent).
- **`docker_runtime/platform.py:42`, `setup/orchestrator.py:898-899`, `setup/download_sources/security.py:43`, `codirector/session_context.py:16`, `generation_tools/ops.py:22`**: STUDIO_E2E-gated behavioral toggles (native dialogs skipped, fixture roots, etc.). Consistent gate.

### B.3 Scripted proposal material outside E2E

- Scripted mock **proposal fences** exist only in `providers/mock.py` (e.g. `proposal_character_update` :357-391, `malformed_proposal` :392-396, tool scenarios :434-503). They are emitted by `MockCoDirectorProvider.generate` — unreachable when mock is disallowed (service.py:171-183).
- `codirector/structured_output.py` — no mock/E2E/scripted references (grep clean).
- No other place produces a `[mock]`/`scripted` proposal in the live provider path. **No leak found for scripted proposals.**

### B.4 Mock/E2E surface classification matrix

| Surface | Location | Gate | Complete? | Classification | Target Role in 2.0 | Risk |
|---|---|---|---|---|---|---|
| Co-Director mock provider selection | service.py:90-161, 171-197; providers/mock.py:189 | STUDIO_E2E + prod-block + explicit allow-mock | **YES (double-guarded)** | KEEP | Same contract; formalize allow-mock as the only leak path | Low |
| E2E router (`/api/e2e/*`) | routers/e2e.py; main.py:510-516 | mount-level + per-handler 404 | **YES** | KEEP | Keep mount gating as the canonical Law-8 choke point | Low |
| Scripted steps + scenario injection | e2e.py:158-221; providers/mock.py:38, 328-339 | behind E2E router + mock-active | **YES** | KEEP | Keep; assert empty at session start | Low |
| Feature-flag mutation endpoint | e2e.py:224-271 | behind E2E router | **YES** | KEEP/EXTEND | Note: mutates live singleton — add explicit reset/audit | Medium |
| Tool-layer E2E overrides (capabilities / execution fault) | tools/capabilities.py:79-91; tools/execution.py:58-71 | `e2e_enabled()` short-circuit | **YES** | KEEP | Keep short-circuit first-line pattern | Low |
| Vision mock provider | vision/providers/__init__.py:17-35; mock.py:78 | STUDIO_E2E gate + provider block | **YES** | KEEP | Same | Low |
| ImageGen closed loop | executive/imagegen_adapter.py:25-52, 114-121 | no mock path exists | **YES** | KEEP | Preserve the hard "no mock substitution" rule | Low |
| M28 / M29 / M211 / M213 / M214 fixtures | m28/fixtures.py:28-34; m29/providers.py:46-70; m211/api.py:260-264; m213/flags.py:19-27, api.py:449-457; m214/honesty.py:24-43 | env-gated + honest labels; m213 e2e/guided is **handler-gated, not mount-gated** | **PARTIAL (functional, but m213 route is live-mounted)** | EXTEND | Move m213 e2e/guided behind mount gating for defense-in-depth | Medium |
| Generation-tools fixture assets | generation_tools/ops.py:198, 385, 574, 664, 711, 725, 753 | `_e2e()`; honest `e2eFixture` provenance | **YES** | KEEP | Keep honest labels; confirm E2E DBs never surface to creators | Low-Medium |
| Source Manager FixtureProvider | source_manager/providers/fixture.py:19-60 | env opt-in only | **YES** | KEEP | Same | Low |
| `_mock_provider_allowed` allow-mock bypass in production | service.py:118-130; config_store.py:30, 51, 70 | explicit operator opt-in (config/env) | **YES by design** | KEEP (flag) | This is the **only** intentional non-E2E mock path — must be operator-audited and visible | Medium (deliberate, documented) |

**Overall Law-8 verdict: effectively CLOSED with two caveats.**
1. **`m213/api.py:449 /e2e/guided`** is mounted unconditionally (handler-gated 403). Functionally closed but violates the "no e2e route mounted in prod" pattern used everywhere else — the single concrete incompleteness found.
2. **Explicit allow-mock in production** (`ADEPT_ALLOW_MOCK_PROVIDER` / `allowMockProvider=true`, service.py:118-130) is an intentional operator escape hatch, not a leak; ensure it remains operator-only and surfaced in status/audit.

---

## Top risks (ranked)

1. **Script Writer false-success (the 2.0 target defect).** No `open scriptwriter` tool, no NAVIGATE intent, `script.*` reads look like an opened workspace, frontend only navigates on `uiAction`/`uiFocus`, and no ack/verification exists — so "Script Writer is open" is provable-false today. Path traced in A.4. **HIGHEST.**
2. **Inert navigation tools still claim success** — `runtime.open_manager`, `references.open`, `continuity.open_workspace`, `posecraft.open_scene` return success-shaped payloads the frontend never consumes (A.3). The model can truthfully report tool success while the UI did nothing. **HIGH.**
3. **No ack / pending UX / timeout / origin-tab correlation** for any operator action (A.2). Even working voice/audio channels are unverified claims. **MEDIUM-HIGH.**
4. **Dead / partially-dead frontend channels** — `adept:open-audio-studio` (no listener), `adept:open-character-voice` fallback, and ~10 inert `workspaceUrl`-only audio results. **MEDIUM.**
5. **Duplicate navigation destinations** (three voice-studio and two+ audio-studio producers, plus timeline-target overlap between continuity and focus_ui, A.5) → drift risk in 2.0. **MEDIUM.**
6. **`m213 /e2e/guided` handler-only gating** and the **allow-mock production escape hatch** are the only two Law-8 completeness caveats (B.4). **LOW-MEDIUM.**

---

*This is a Phase-1 read-only audit. No files were created or modified other than this document.*
