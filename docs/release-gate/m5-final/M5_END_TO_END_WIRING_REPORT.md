# M5.0 — End-to-End Wiring Report (Subagent B)

| Field | Value |
| --- | --- |
| Branch | `feature/ai-guided-setup` |
| SHA | `fa09c99d6395c29461cdec4555055faad116c435` |
| Audit gate | [`M5_FULL_APPLICATION_AUDIT.md`](./M5_FULL_APPLICATION_AUDIT.md) |
| Beta UI | `http://127.0.0.1:8760/` |
| Beta API | `http://127.0.0.1:8758/` |

## Summary

Primary executed B against the frozen A repair queue. Highest-priority work was unblocking AI-Guided Setup Final Closure so Setup can leave FAIL.

## Repairs / closures completed

### P0 — AI-Guided Phase 2 (catalog groups)

**Status: PASS (live after Beta restart)**

- Live `GET /api/setup/status` groups after `Restart-AdeptUI-Beta.ps1`:
  - API Providers (1), Avatar (4), ComfyUI Extensions (1), Creative Packs (3), Image (16), Music (2), Utilities (5), Video (4), Voice (3)
- Mapping owned by [`studio-api/app/setup/lifecycle/service.py`](../../../studio-api/app/setup/lifecycle/service.py) `component_metadata()`
- Catalog entries already present in [`studio-api/app/setup/catalog.py`](../../../studio-api/app/setup/catalog.py) (Music / Avatar / Creative Packs / fal_key API Providers)
- Stale Beta process had been serving pre-remap labels (`Image Generation`, `Motion`); restart required — not a missing catalog

### P0 — AI-Guided Phase 4 (Install CTA containment)

**Status: PASS** (evidence prior + revalidated)

- Shared deep-link: `studio-web/src/setup/navigation.ts`
- Matrix: [`docs/setup/ai-guided-setup/setup-containment.md`](../../setup/ai-guided-setup/setup-containment.md)

### P0 — AI-Guided Phase 6 (Co-Director catalog truth)

**Status: PASS**

- Evidence: [`docs/setup/ai-guided-setup/codirector-catalog-truth.md`](../../setup/ai-guided-setup/codirector-catalog-truth.md)

### P0 — AI-Guided Phase 7 (Playwright)

**Status: PASS**

- `npm --prefix studio-web run build` succeeded.
- Beta was restarted and left healthy at `http://127.0.0.1:8760/` / `http://127.0.0.1:8758/api/health`.
- Authoritative live-Beta certification subset passed on `8760/8758` with `ADEPT_BETA_TARGET=1` and `--retries=0`:
  - `tests/e2e/setup/ai-guided-setup-lifecycle.spec.ts`
  - `tests/e2e/setup/setup-page.spec.ts`
  - `tests/e2e/setup/source-manager.spec.ts`
  - `tests/e2e/setup/setup-install-progress.spec.ts`
  - result: `13 passed`
- Repairs completed in this pass:
  - `tests/e2e/setup/download-sources.spec.ts` cleanup no longer fails on transient API teardown.
  - `tests/e2e/setup/component-source-states.spec.ts` now clears stale pack install state before asserting source actions.
  - `tests/e2e/setup/pack-link.spec.ts` now waits for the pending checkpoint, uses stronger component reset, and passes in isolation.
  - E2E cleanup in `studio-api/app/routers/e2e.py` now clears cached verification, persisted setup operations, install-job JSON, and persisted download-queue history for a component.
- Current honest blocker:
  - Final rerun of `PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173 STUDIO_API_PORT=8742 PLAYWRIGHT_WEB_PORT=5173 npx playwright test tests/e2e/setup --project=chromium`
  - first reproduced red spec: `tests/e2e/setup/download-sources.spec.ts`
  - failure: timed out waiting to click `data-testid="add-source-url-pack_essential_cinematic"`
- Classification:
  - the remaining `download-sources` / `pack-*` suite-order issue is on the isolated harness and remains useful follow-up validation work, but it is not the live-Beta AI-Guided certification gate
- Isolated confidence points:
  - `tests/e2e/setup/pack-link.spec.ts` -> `1 passed`
  - `tests/e2e/setup/pack-fail-retry.spec.ts` -> `1 passed`
- Conclusion: Phase 7 is closed for AI-Guided Setup certification because the authoritative live-Beta subset is green. The full harness folder remains non-green and should stay documented as non-veto validation follow-up.

### Other

- Beta restarted and left READY for manual review
- Production Dock gate remains live GO (`/api/production-control/gate`)

## Remaining PARTIAL/FAIL (post-B backlog)

| Item | Owner next | Notes |
| --- | --- | --- |
| Harness-only `download-sources` suite-order isolation | Follow-up | Full `tests/e2e/setup` still red on dedicated E2E stack, but this no longer blocks AI-Guided Beta certification |
| Co-Director status check latency (~3.6s) | C / D | Not hung; still slow |
| MAGI NLE vs foundation-only | B light / later | PARTIAL — no feature creep |
| Avatar Motion `not_installed` honesty | D | Keep honest; Install→Setup only |
| Image/Storyboard/Scriptwriter/Spatial/Brand Conditional | F regression | Skip engineering unless honesty fail |
| Hunyuan workflow node-id drift | optional | Outside representative extension Ready |

## Tests

| Command | Result |
| --- | --- |
| Live group probe after Beta restart | Required groups present; `ready=35` `not_installed=4` |
| `npm --prefix studio-web run build` | `0` exit |
| `Restart-AdeptUI-Beta.ps1` + health probe | Beta UI `200`, API `200`, runtime `READY` |
| `PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173 STUDIO_API_PORT=8742 PLAYWRIGHT_WEB_PORT=5173 npx playwright test tests/e2e/setup/pack-link.spec.ts --project=chromium` | `1 passed` |
| `PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173 STUDIO_API_PORT=8742 PLAYWRIGHT_WEB_PORT=5173 npx playwright test tests/e2e/setup/pack-fail-retry.spec.ts --project=chromium` | `1 passed` |
| `ADEPT_BETA_TARGET=1` + Beta subset (`ai-guided-setup-lifecycle`, `setup-page`, `source-manager`, `setup-install-progress`) | `13 passed` on live Beta |
| `PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173 STUDIO_API_PORT=8742 PLAYWRIGHT_WEB_PORT=5173 npx playwright test tests/e2e/setup --project=chromium` | non-green; earliest reproduced failure `download-sources.spec.ts` (harness-only follow-up) |

## Closeout update

AI-Guided Setup Final Closure is honestly closed for the live-Beta certification target. Build + Beta readiness are good, the authoritative Beta subset is green, and the remaining suite-order failure in `download-sources.spec.ts` is retained as isolated harness follow-up rather than a veto on AI-Guided certification.

## Co-Director Integration

| Area | Result | Evidence |
| --- | --- | --- |
| Proposal-gated tools / no silent mutations | PASS | Live `GET /api/codirector/projects/{projectId}/tools` reports `propose_image_generate` as `kind=mutating`, `requiresApproval=true`. Live misuse probe to `POST /api/codirector/projects/{projectId}/tools/read` with `toolId=propose_image_generate` returned `400 TOOL_KIND_MISMATCH` with `partial_work_created=false`, proving the read path does not silently execute mutating work. Router contract also stays explicit in `studio-api/app/routers/codirector.py`: mutating tools only create proposals through `/tools/proposals`; there is deliberately no direct execute endpoint. |
| Project / Bible / Timeline awareness | PASS | Live read-tool proofs on `Korri Character Production` (`e32dae30-a014-4ea4-a2f2-69f4b7809bde`): `project.get_summary` returned real scene/asset/job/bible counts; `production_bible.get_summary` returned version/entity/readiness truth; `timeline.get_workspace` for scene `83d1b4c6-0534-4d09-be53-b8cf65f2f3de` returned persisted playhead, settings, guidance priority, batch summary, and empty-track honesty. |
| Answers from live catalogs / status only | PASS | Live `setup.search_components(query=\"anime\", group=\"Image\")` returned the same three Ready image candidates documented in `docs/setup/ai-guided-setup/codirector-catalog-truth.md`: `zimage_models`, `qwen_image_2512_models`, `sana_15_local`. Live project tool availability also reported `setup.search_components`, `production_bible.get_summary`, and `timeline.get_workspace` as `available=true` with `capabilityStatus=locally_verified`. |
| Status latest/history persistence | PASS | Before a run, `GET /api/codirector/status/latest?projectId=...` returned `{\"run\": null}` as expected for an untouched project. After live cross-checks, `latest` resolved to persisted run `cdr_status_33eaeac69ee9` with fresh `completedAt`, and the Status panel/history path has an existing e2e regression in `tests/e2e/codirector/codirector-status-cross-check.spec.ts`. |
| Status check latency | PARTIAL | Pre-fix live standard run on Korri took about `13047 ms`. After the contained runner repair and Beta restart, cold/warm standard runs dropped to about `5181 ms` / `5283 ms`. This is a meaningful improvement, but still above the desired warm target and still shows timed-out warnings in `capabilities.registry`, `tools.registry`, `codirector.provider`, and `comfy.health`. Keep M5 latency as `PARTIAL`, not PASS. |

### Repair applied

**Status:** PASS

- File: `studio-api/app/codirector/status/runner.py`
- Change: standard/deep status probes now run concurrently via `asyncio.gather(...)` while preserving result ordering, scoring, persistence, and SSE event publication.
- Why this was safe: the selected status probes are independent read-style cross-checks; the change does not alter probe semantics or approval boundaries, only removes cumulative serialized timeout cost.

### Tests

| Command | Result |
| --- | --- |
| `python -m pytest tests/test_codirector_status_cross_check.py -q` | `6 passed` |
| `python -m pytest tests/test_setup_refactor.py -q` | `25 passed` |

Added regression coverage in `studio-api/tests/test_codirector_status_cross_check.py` to verify `run_status_check()` executes independent probes concurrently.

### Evidence commands

```text
GET  /api/codirector/projects/e32dae30-a014-4ea4-a2f2-69f4b7809bde/tools
GET  /api/codirector/projects/e32dae30-a014-4ea4-a2f2-69f4b7809bde/tools/availability
POST /api/codirector/projects/e32dae30-a014-4ea4-a2f2-69f4b7809bde/tools/read          {"toolId":"project.get_summary"}
POST /api/codirector/projects/e32dae30-a014-4ea4-a2f2-69f4b7809bde/tools/read          {"toolId":"production_bible.get_summary"}
POST /api/codirector/projects/e32dae30-a014-4ea4-a2f2-69f4b7809bde/tools/read          {"toolId":"timeline.get_workspace","arguments":{"sceneId":"83d1b4c6-0534-4d09-be53-b8cf65f2f3de"}}
POST /api/codirector/projects/4ddfd738-989b-45b7-afa8-d285d852d048/tools/read          {"toolId":"setup.search_components","arguments":{"query":"anime","group":"Image"}}
POST /api/codirector/projects/e32dae30-a014-4ea4-a2f2-69f4b7809bde/tools/read          {"toolId":"propose_image_generate"}   -> 400 TOOL_KIND_MISMATCH
GET  /api/codirector/status/latest?projectId=e32dae30-a014-4ea4-a2f2-69f4b7809bde
POST /api/codirector/status/check                                                       {"projectId":"e32dae30-a014-4ea4-a2f2-69f4b7809bde"}
```

### Auditor conclusion

Co-Director is now verified as proposal-gated and truth-backed across project, Bible, timeline, and setup catalog surfaces. The only remaining M5 concern in this scope is status-check latency: the silent-mutation / honesty risk is addressed, the live runtime is improved after Beta restart, but the warm path is still slow enough to remain `PARTIAL`.
