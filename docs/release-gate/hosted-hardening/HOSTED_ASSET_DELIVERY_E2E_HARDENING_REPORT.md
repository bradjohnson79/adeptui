# ADEPT UI — Hosted Asset Delivery + E2E Hardening
## Unified Completion Report

**Branch:** `beta`
**HEAD SHA:** `93a254abed038ac3dc9e987afee92b4afdaa264a`
**Remote:** `origin/beta` (pushed: `2b4962e..93a254a`)
**Vercel production URL:** https://adeptui.vercel.app/
**Vercel production bundle (new):** `assets/index-C82RLv9-.js` (supersedes `index-CVdmA7nh.js`)
**Secure API bridge:** https://api-beta.adeptui.org → http://127.0.0.1:8758 (Cloudflare Tunnel)
**Studio API runtime:** running with `93a254a` working-tree code, `STUDIO_FEATURE_CHARACTER_IDENTITY_V1=1`, ComfyUI reachable, RTX 5090 GPU ready

This is a **small infrastructure hardening pass only**. No Co-Director content tools (Character Creator, Wiki, Script Writer, Library grid logic, Spatial Map, Scene Creator) were rewritten or expanded.

---

## 1. Hosted Thumbnail / Binary Asset Bridge ✅ PASS

### Root cause
The backend (`studio-api/app/project_library/service.py:516`) serializes `thumb_url` as a **relative** path: `f"/api/assets/{asset.id}/thumb"`. The frontend's `getCardPreviewUrl` (`studio-web/src/components/CoDirector/library/assetModel.ts`) returned `asset.thumb_url` **directly**, bypassing `apiUrl()`. On hosted Vercel, `API_BASE` is set to the secure bridge (`https://api-beta.adeptui.org` via `VITE_API_BASE`), but the relative `thumb_url` resolved against the Vercel origin → **404**. The API client's `api.assetUrl(id)` already used `apiUrl()` correctly; only `thumb_url`/`preview_url` bypassed it.

### Fix (minimal, frontend-only)
- Added `resolveAssetUrl(url)` helper in `assetModel.ts`:
  - `undefined`/falsy → `undefined`
  - absolute (`http://`, `https://`, protocol-relative `//`) and `data:` URIs → returned unchanged
  - `/`-prefixed relative paths → routed through `apiUrl()` (picks up `API_BASE` on hosted; stays relative in local dev where Vite proxies `/api`)
  - other strings → unchanged
- `getCardPreviewUrl` now resolves `thumb_url`, `preview_url`/`previewUrl` through `resolveAssetUrl`. The `api.assetUrl(asset.id)` image fallback is preserved (already correct).
- **No backend changes. No `vercel.json` changes. No content-tool changes.** Only URL string construction changed — asset IDs, project scoping, security, and caching are untouched.

### Consumers covered (all go through the now-correct `getCardPreviewUrl`)
- Character Reference preview/picker — `CharacterCompactView.tsx`, `CharacterReferenceAssetPicker.tsx`
- Library — `LibraryMediaGrid.tsx`
- Spatial Map / Atlas — `EntityPicker.tsx`
- Scene Creator / generic — `CoDirectorAssetPicker.tsx`

### Hosted verification (deployed `index-C82RLv9-.js`)
Two consecutive full Playwright runs against `https://adeptui.vercel.app/`:

| Observer metric | Before fix | After fix |
|---|---|---|
| `consoleErrors` (thumbnail 404s) | 5 per run | **0** |
| `apiFailures` (`/api/assets/{id}/thumb` 404) | 5 per run | **0** |
| `pageErrors` | 0 | 0 |

The thumbnail 404s are **eliminated** in production. Thumbnails now resolve through `https://api-beta.adeptui.org/api/assets/{id}/thumb` and return 200.

---

## 2. Script Writer Playwright Determinism ✅ PASS

### Root cause
The Script Writer backend (`studio-api/app/scriptwriter/service.py:49` `get_or_create_document`) seeds a default document with a `scene_heading` "INT. LOCATION - DAY" for a brand-new project. The inline editor (`ScriptwriterInlineEditor.tsx`) hydrates asynchronously via `api.scriptwriter.studio(projectId)` → `editor.commands.setContent(resolveInitialHtml(d))`. The test cleared the editor (`Ctrl+A → Delete`) **before** hydration completed → on retry, the clear was a no-op and the default `<h1>` remained, failing the formatting assertions.

### Fix (test-only)
In `tests/e2e/master-correction.spec.ts` test D, the clearing preamble now:
1. Waits for the editor to contain `/INT\. LOCATION/i` (timeout 15s) — **proves hydration completed**.
2. Clears via `Ctrl+A → Delete`.
3. Asserts the editor no longer contains `/INT\. LOCATION/i` (timeout 5s) — **proves the clear succeeded**.

All other test D logic (typing, formatting, assertions, reload-persistence) is unchanged. **No product code changed.** No actual product race was found — this was a test-timing issue.

### Determinism verification
- Subagent ran test D twice (normal + repeat): both PASS (28.9s, 26.3s), zero console/page/network errors.
- Main agent full suite run 1: test D PASS (28.8s), no retry needed.
- Main agent full suite run 2: test D PASS (20.5s), no retry needed.

---

## 3. Test Results

### Unit tests: 15 PASS
- `studio-web/src/components/CoDirector/library/assetModel.test.ts` (NEW) — `resolveAssetUrl` + `getCardPreviewUrl` URL resolution (relative→absolute with API_BASE, relative stays relative when empty, absolute/data: unchanged, undefined handling, precedence). 15 passed / 0 failed.

### Playwright E2E (hosted, MANDATORY): 6/6 PASS × 2 consecutive runs
Run against `https://adeptui.vercel.app/` (fresh browser, deployed `93a254a` bundle `index-C82RLv9-.js`) via secure bridge `api-beta.adeptui.org`.

**Run 1 (1.2m):**
```
  ok 1  A — Character Reference Picker lifecycle (8.7s)
  ok 2  B — Wiki Story blank-state integrity (14.4s)
  ok 3  C — Open Character navigation from Wiki (6.7s)
  ok 4  D — Script Writer rich-text toolbar in Co-Director (28.8s)
  ok 5  E — Library bulk-delete with Select mode (6.0s)
  ok 6  Z — Observer summary (2ms)
  6 passed
```
Observer: `consoleErrors: []`, `pageErrors: []`, `apiFailures: []`.

**Run 2 (1.0m):**
```
  ok 1  A — Character Reference Picker lifecycle (8.6s)
  ok 2  B — Wiki Story blank-state integrity (16.0s)
  ok 3  C — Open Character navigation from Wiki (6.8s)
  ok 4  D — Script Writer rich-text toolbar in Co-Director (20.5s)
  ok 5  E — Library bulk-delete with Select mode (6.3s)
  ok 6  Z — Observer summary (1ms)
  6 passed
```
Observer: `consoleErrors: []`, `pageErrors: []`, `apiFailures: []`.

### Console / Network Inspection (both runs)
- **pageErrors:** 0
- **5xx API responses:** 0
- **apiFailures (4xx/5xx):** 0 — thumbnail 404s eliminated
- **consoleErrors:** 0 — thumbnail 404 console messages eliminated
- **failedRequests:** only `ERR_ABORTED` on optional endpoints (`/api/health`, `/api/production-control/status`, `/api/codirector/status/check`, and one scriptwriter `/autosave` aborted by test navigation) — these are client-cancelled/optional polls, not server failures. Non-blocking.

---

## 4. Independent Verifier Result

Independent read-only verifier ([Name](492e0b66-11b2-442b-8848-c709bbd1cd81)) confirmed:
- `resolveAssetUrl` logic correct (undefined/absolute/data/relative handling) — PASS
- `apiUrl` import path correct; contract consistent — PASS
- Backend emits relative `thumb_url` (frontend is the correct fix layer) — PASS
- Script Writer test D change: waits for hydration before clearing, asserts clear succeeded, rest unchanged, no other test modified — PASS
- Diff scope: exactly 3 files (`assetModel.ts`, `assetModel.test.ts`, `master-correction.spec.ts`); no backend, no `vercel.json`, no other content-tool components — PASS
- Test coverage meaningful (relative/absolute/data/undefined/precedence) — PASS
- All `getCardPreviewUrl` consumers benefit (5 files listed) — PASS
- No asset IDs/scoping/security/caching changes; no content-tool feature behavior change; Script Writer change test-only — PASS

**VERIFIED — changes are correct, minimal, and non-regressive**

---

## 5. Files Changed

```
studio-web/src/components/CoDirector/library/assetModel.ts       | 24 ++-  (resolveAssetUrl + getCardPreviewUrl fix)
studio-web/src/components/CoDirector/library/assetModel.test.ts   | 115 +++++++++  (NEW — 15 unit tests)
tests/e2e/master-correction.spec.ts                              | 15 +-   (test D hydration wait + post-clear assert)
3 files changed, 150 insertions(+), 4 deletions(-)
```

---

## 6. Manual Review Path

1. Open https://adeptui.vercel.app/ in a fresh/incognito browser
2. Open a project with image assets → Co-Director → Library → confirm thumbnails render (no broken-image icons, no 404s in DevTools Network)
3. Co-Director → Character Creator → select a character → "Choose from Library" → confirm picker thumbnails render → Select → confirm reference preview thumbnail renders
4. Co-Director → Spatial Map → open the environment/entity picker → confirm thumbnails render
5. Co-Director → Script Writer → type + format → reload → formatting persists (deterministic)

---

## 7. Known Limitations

1. **Optional endpoint `ERR_ABORTED`:** `/api/health`, `/api/production-control/status`, `/api/codirector/status/check` occasionally show `ERR_ABORTED` during Playwright navigation. These are optional intelligence/status polls that are client-cancelled on navigation or when intelligence is off — pre-existing, non-blocking, not introduced by this pass.
2. **Co-Director "Degraded" badge:** pre-existing intelligence/model-readiness configuration state, unchanged by this pass.

No thumbnail delivery limitations remain — the previously-permanent known limitation is resolved.

---

## 8. Final Verdict

Both hardening items pass with hosted evidence:
- Hosted thumbnails visibly work (zero 404s across two full Playwright runs; thumbnails resolve through the secure bridge)
- Script Writer E2E passes deterministically (4 consecutive passes: 2 subagent + 2 main-agent full runs, no retries needed)
- No Co-Director content tools were rewritten or expanded
- Independent verifier: VERIFIED

# GO — ADEPT UI HOSTED ASSET DELIVERY + E2E HARDENING CERTIFIED
