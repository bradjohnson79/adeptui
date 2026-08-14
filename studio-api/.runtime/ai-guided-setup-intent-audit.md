# AI-Guided Setup intent audit

**Verdict: READY TO IMPLEMENT**

Date: 2026-08-14 14:45 PT  
Scope: read-only. No files edited except this audit. No commit/push/deploy. No API bounce. Character Creator untouched.

This is a copy + mapping extension on the existing recommender. Do not invent a new recommender.

---

## 1. Verdict

**READY TO IMPLEMENT**

Reasons:

- The UI copy, example strings, and client matcher live in one file.
- The backend intent mapper already exists (`recommendation_reason` + `search_components` + component `bestFor` / `capabilityTags`).
- Film / commercial / presenter / storyboard intents are **new mappings**, not a missing subsystem. Target components already exist in the authoritative catalog and already report live readiness.
- Readiness already comes from `setup/catalog.py` + `verify_component` + `lifecycle_state` via `setup/status.py`. Do not add a second readiness source.
- Tests already pin the current image-centric placeholder and the anime reason string. Extend those; do not replace the harness.

Blockers: none for a smallest repair. Two existing matcher bugs must be respected (see §7) or the new examples will look “missing” even when video models are Ready.

---

## 2. Exact files

### Examples / placeholder / copy (edit these)

| Role | Path |
|---|---|
| **Primary UI copy + client matcher + client reason strings + default brief + ranking** | `studio-web/src/setup/lifecycle/AiGuidedSetupPanel.tsx` |
| Mode-chooser blurb (not the example list) | `studio-web/src/components/SetupWizard.tsx` (AI-Guided button + one-line description) |
| Docs that restate the image-only rules | `docs/setup/ai-guided-setup/certified-image-catalog.md` |
| Co-Director catalog-truth examples | `docs/setup/ai-guided-setup/codirector-catalog-truth.md` |

### Intent classifier / recommender (extend these; do not replace)

| Role | Path |
|---|---|
| **Canonical metadata + `search_components` + `recommendation_reason`** | `studio-api/app/setup/lifecycle/service.py` |
| HTTP: `GET /api/setup/lifecycle/components?query=` | `studio-api/app/setup/lifecycle/router.py` |
| Co-Director tool `setup.search_components` (thin wrapper) | `studio-api/app/codirector/tools/handlers/setup_guided.py` |
| Authoritative inventory | `studio-api/app/setup/catalog.py` |
| Authoritative readiness surface used by the panel | `studio-api/app/setup/status.py` |
| Architecture (already correct) | `docs/setup/ai-guided-setup/architecture.md` |

### Tests to extend

| Role | Path |
|---|---|
| E2E pins placeholder + anime reason | `tests/e2e/setup/ai-guided-setup-lifecycle.spec.ts` |
| API lifecycle tests — **no intent coverage today** | `studio-api/tests/test_setup_lifecycle.py` |

No `studio-web` unit test currently covers `matchesIntent` / `creatorRecommendation`.

Do **not** add a new recommender module, new API, or new Co-Director tool.

---

## 3. Current UI copy (source of truth)

From `AiGuidedSetupPanel.tsx` (also present in the live `:8760` bundle `index-6gpd03hm.js` on 2026-08-14):

| Surface | Current string |
|---|---|
| Heading | `AI-Guided Setup` |
| Support text | `Describe the kind of work you want to do, then review certified options, install plans, and safety checks.` |
| Field label | `What are you trying to create?` |
| **Default input value** (visible on load; hides placeholder) | `photoreal character` |
| Placeholder | `photoreal character, anime poster, fast preview, product mockup` |
| Visible example line | `Try prompts like \`photoreal character\`, \`anime poster\`, or \`fast preview\`.` |
| Recommendations heading | `Recommended For This Goal` |
| Recommendations support | `Recommendations prefer certified recipes and creator-facing fit, not uncertified upstream latest.` |

There are **no clickable example chips**. Examples are default value + placeholder + muted helper text only.

SetupWizard mode chooser (not the example list):

- Button: `AI-Guided`
- Blurb: `AI-Guided recommends certified providers, compares options, and walks you through install, calibration, and certification.`
- Default mode is last-saved `adept.setup.mode`, else `guided` (not AI-Guided).

Live `:8760` JS contains `photoreal character` / `anime poster` / `fast preview` / `product mockup` / `Try prompts like`. It does **not** contain `short film` or `talking presenter`. A `storyboard` hit in the bundle is from other workspaces, not this panel.

---

## 4. How intent maps to recommendations today

There is **no separate ML/LLM classifier**. Two parallel keyword recommenders share the same idea and already drift.

### A. Frontend (what the Setup page actually uses)

`AiGuidedSetupPanel` filters `status.components` from `GET /api/setup/status`.

`matchesIntent(component, brief)`:

- Haystack = name + description + `capabilityTags` + `badges` + `bestFor` + `strengths`
- Brief is split on whitespace; stopwords dropped (`a an the for and or to of with`)
- **Any remaining term** hitting the haystack is a match (OR)

`creatorRecommendation(component, brief)` hardcoded reasons:

| Brief tokens | Component IDs | Reason |
|---|---|---|
| `photoreal` OR `character` | `flux1_kontext_dev_local` | `Best match for photoreal character work with reference-following edits.` |
| `anime` | `sana_15_local`, `qwen_image_2512_models`, `zimage_models`, `pack_essential_anime` | `Strong fit for anime and stylized illustration work.` |
| `preview` OR `fast` | `flux1_schnell_local` | `Best fit for quick creative previews before a final-quality pass.` |
| else | first `lifecycle.recommendations[]` or generic | `Matches this setup goal and current certified posture.` |

Ranking (then `slice(0, 4)`):

1. `flux1_kontext_dev_local`
2. `sana_15_local`
3. `qwen_image_2512_models`
4. `zimage_models`
5. everyone else

This ranking is **image-first**. New video/avatar matches will lose the top-4 slot unless ranking is extended.

### B. Backend (Co-Director + `GET /api/setup/lifecycle/components`)

`search_components(query)` in `service.py`:

- Haystack = id + name + description + `capabilityTags` + `badges` + `bestFor`
- Match requires the **entire query string** as a substring (`if q and q not in haystack`)
- Does **not** OR individual terms

`recommendation_reason(component_id, intent)`:

| Intent tokens | Component IDs | Reason |
|---|---|---|
| `photoreal` OR `character` OR `reference` | `flux1_kontext_dev_local` | `Best fit for photoreal character work and reference-following edits.` |
| `anime` | `sana_15_local`, `qwen_image_2512_models`, `zimage_models` | `Best fit for anime or stylized illustration intent.` |
| `fast` OR `preview` OR `quick` | `flux1_schnell_local` | `Best fit for quick preview passes.` |
| else | generic | `Matches the requested capability tags and certified setup posture.` |

Frontend includes `pack_essential_anime` in the anime reason; backend does not. Copy also differs slightly (`Best match` vs `Best fit`).

### C. Metadata that makes keyword match work

Rich `bestFor` / `capabilityTags` exist only on **local image** components and a few overrides (packs, music, `fal_key`). Video and avatar entries are group-only.

Image examples that already work because metadata contains the words:

- `flux1_kontext_dev_local` bestFor: `Photoreal character work`, `Reference matching`, `Director notes` — tags: `photoreal`, `character`, `reference`, `editing`
- `flux1_schnell_local` bestFor includes `Fast preview` — tags: `preview`, `speed`, `ideation`
- `sana_15_local` / `qwen_image_2512_models` / `zimage_models` carry `anime`
- `flux1_dev_local` tags include `cinematic`, `marketing` — bestFor: `Marketing stills`
- `pack_essential_cinematic` bestFor: `Lighting looks`, `Cinematic scene setups`
- `fal_key` bestFor includes `Commercial image models` (this is why query `commercial` hits a credential)

Video overrides today (`ltx_checkpoint`, `wan_models`): group/subgroup/surfaceGroups only. **Empty `bestFor` and `capabilityTags`.**

Avatar runtimes inherit empty `bestFor` / `capabilityTags` from `component_metadata()`.

---

## 5. Do film / commercial / product / presenter / storyboard intents already exist?

**No as first-class mappings. Partial collisions only.**

| Desired example | Exists as mapping? | Live `GET /api/setup/lifecycle/components?query=` (2026-08-14 PT) | What already exists to map onto |
|---|---|---|---|
| photoreal character | **Yes** (keep) | 1 hit: `flux1_kontext_dev_local` **Ready**, specific reason | Keep |
| anime poster | Partial | **0 hits** (phrase `anime poster` is not in any haystack). Query `anime` → 5 image/pack hits. Query `poster` → `qwen_image_2512_models` | Keep image mapping; put the phrase in metadata so backend search matches the advertised example |
| fast preview | **Yes** (keep) | 4 hits; only Schnell gets the specific reason | Keep |
| product mockup | Advertised, **unmapped** | Phrase → 0. Query `product` false-hits `Production Quality` badges on FLUX/SD3.5 | Image-only keep-candidate: `flux1_dev_local` / `qwen_image_2512_models` (marketing stills / poster). Not a video intent. |
| short film | **New** | 0 | Ready video: `hunyuan_video_15`, `hunyuan_video_13b`, `wan_models`, `ltx_checkpoint`, `ltx_2_5_*` |
| commercial | Collision, not film | 1 hit: `fal_key` **Ready** (credential “Commercial image models”) | New video mapping. Do not let `fal_key` remain the only/top hit. |
| branded product video | **New** | 0 | Same Ready video set; optional stills via `flux1_dev_local` (`marketing`) |
| talking presenter | **New** | 0 (`talking`/`presenter` both 0) | Avatar catalog already exists: `longcat-video-avatar-1-5-local` **Repair Required**, `infinitetalk-local` **Repair Required**, `musetalk-1-5-local` **Repair Required**, `echomimic-v2-local` **Not Installed**. E2E mock already uses `bestFor: ["Talking avatars"]` — **not in live metadata**. |
| storyboard | **New** | 0 | No setup component named storyboard. Workspace-only (`ScriptStoryboardWorkspace`, Co-Director `storyboard.py`). Map to image previs (`flux1_dev_local` / `pack_essential_cinematic`) plus optional video. Do not invent a storyboard installer. |

Query `video` already returns 8 catalog rows (LTX, Hunyuan, ComfyUI, LongCat) with the **generic** reason only. Query `film` returns 0. Query `cinematic` returns `flux1_dev_local` + `pack_essential_cinematic` (image/pack, not video).

Live inspect:

- `hunyuan_video_15`: `bestFor=[]`, `capabilityTags=[]`, `statusLabel=Ready`
- `longcat-video-avatar-1-5-local`: `bestFor=[]`, `capabilityTags=[]`, `statusLabel=Repair Required`

So the targets are real. The mappings and creator-facing tags are missing.

---

## 6. How readiness is resolved (authoritative; no false missing)

Documented in `docs/setup/ai-guided-setup/architecture.md` and implemented:

1. **Inventory:** `studio-api/app/setup/catalog.py` (`COMPONENTS`) — canonical list.
2. **Live verify:** `verify_component()` in `setup/diagnostics.py`.
3. **Lifecycle label:** `lifecycle_state()` → `_component_status_label()`:
   - healthy → `Ready`
   - update available → `Update Available`
   - failed/repair job → `Repair Required`
   - summary contains not ready / missing / not installed → `Not Installed`
   - else → `Repair Recommended`
   - Certification records **do not** replace live verification.
4. **Creator surface:** `setup/status.py` attaches `lifecycle_status_label`, `lifecycle`, `bestFor`, `capabilityTags` from that same `lifecycle_state` + `component_metadata`. This is what the panel consumes.
5. **Certified recipes:** `config/setup/certified-recipes/*.json` via `list_certified_recipes()` / `recipe_for_component()`. Used for install plans and “update available”, not as a shadow inventory.

Frontend `statusTone()`:

- label contains `ready` → CSS `ready`
- `repair` or `update` → `attention`
- else (including `Not Installed`) → CSS `missing`

That CSS class is a presentation bucket, not a second registry. Live video models that are installed already report **Ready**. Avatar presenter runtimes honestly report **Repair Required** / **Not Installed**. Recommendations must keep showing those labels; do not hide Repair Required as if the component does not exist.

**False-missing risk if the repair is sloppy:**

- Backend phrase-match: advertised `anime poster` / `short film` return 0 today even when the right Ready models exist. New example phrases **must** be placed in `bestFor` (or search must term-OR like the frontend).
- Frontend top-4 image ranking can hide Ready video matches.
- Do not derive readiness from empty `bestFor`. Empty tags mean “unmapped”, not “missing install”.

---

## 7. Existing tests for intent examples

| Test | What it locks |
|---|---|
| `tests/e2e/setup/ai-guided-setup-lifecycle.spec.ts` | Placeholder exact string `photoreal character, anime poster, fast preview, product mockup`. Fills `anime poster` and expects `Strong fit for anime and stylized illustration work.` Mock catalog already has video/avatar `bestFor` (`Long-form local video`, `Talking avatars`) that **live service.py does not emit**. |
| `studio-api/tests/test_setup_lifecycle.py` | Install plan, recipes, certify, monitor, archive. **Zero** `recommendation_reason` / `search_components` / example-phrase assertions. |
| `docs/setup/ai-guided-setup/codirector-catalog-truth.md` §6 | Documents Co-Director `setup.search_components` query `photoreal character` → Kontext Ready. Not an automated test. |

No frontend unit test for `matchesIntent` / `creatorRecommendation`.

Changing the placeholder or the anime reason string **will fail** the existing e2e unless that spec is updated in the same change.

---

## 8. Live :8760 / :8758 (2026-08-14 ~14:45 PT)

- UI `http://127.0.0.1:8760/` → 200, SPA. Served bundle still has the image-centric heading, label, placeholder, default brief, and helper examples. No `short film` / `talking presenter` in that bundle’s Setup copy.
- API `http://127.0.0.1:8758/api/setup/status` → 200.
- API `http://127.0.0.1:8758/api/setup/lifecycle/components` → 46 components. Video Hunyuan/WAN/LTX **Ready**. Avatar LongCat/InfiniteTalk/MuseTalk **Repair Required**. EchoMimic **Not Installed**.
- Live search results are in §5.

---

## 9. Smallest repair plan (copy + mappings + tests)

Do not invent a new recommender. Extend the three existing functions and the metadata tables they already read.

### Step 1 — Copy only (`AiGuidedSetupPanel.tsx`)

Keep the heading and the “describe the kind of work” support line.

Change:

- Default brief: `short film` (film-first on load)
- Placeholder: `short film, commercial, branded product video, talking presenter, storyboard, photoreal character`
- Helper: `Try prompts like \`short film\`, \`commercial\`, \`talking presenter\`, or \`photoreal character\`.`

Keep image-only examples in the list (at least `photoreal character`; `anime poster` / `fast preview` may stay in placeholder or helper). `product mockup` can stay as an image-only keep (see Step 3) or drop from the visible list if unused.

Update `SetupWizard.tsx` AI-Guided blurb only if you want one clause that it covers film/video/commercial, not just “providers”.

### Step 2 — Metadata on existing catalog IDs (`service.py`)

Add `bestFor` + `capabilityTags` on existing video/avatar overrides so **both** matchers can see the new phrases. Put the **full example phrase** in `bestFor` (backend is phrase-substring). Include the individual tokens the frontend ORs.

Suggested tags (reuse IDs; do not add components):

| Component | Add tags / bestFor phrases | Why |
|---|---|---|
| `hunyuan_video_15` | `short film`, `film`, `cinematic video` | Primary Ready short-film rec (catalog already calls it recommended Hunyuan) |
| `hunyuan_video_13b` | `short film`, `high-resource film` | Secondary; already Ready |
| `wan_models` | `branded product video`, `commercial`, `product video` | Commercial / branded product |
| `ltx_checkpoint` / `ltx_2_5_checkpoint` | `storyboard motion`, `image-to-video`, `previz` | LTX is catalogued as primary local I2V |
| `pack_essential_cinematic` | keep cinematic; add `storyboard` | Still/previs pack already exists |
| `flux1_dev_local` | add `storyboard`, `product mockup` (keep marketing/cinematic) | Image previs + product stills |
| `longcat-video-avatar-1-5-local` | `talking presenter`, `talking avatars`, `presenter` | Flagship avatar; e2e already mocked this |
| `infinitetalk-local` / `musetalk-1-5-local` / `echomimic-v2-local` | `talking presenter`, `talking avatars` | Same intent family; show honest Repair / Not Installed |
| `qwen_image_2512_models` | add `anime poster` to bestFor | Makes advertised example hit backend search |
| `sana_15_local` | add `anime poster` | Same |
| `fal_key` | narrow `Commercial image models` → `hosted commercial APIs` or similar | Stops query `commercial` from ranking a credential as the film commercial |

Do not mark Ready video as missing. Empty tags were the bug, not the verify path.

### Step 3 — Extend the two existing reason functions (keep image branches)

Add branches **beside** the current photoreal / anime / fast rules.

`recommendation_reason` and `creatorRecommendation` should stay aligned (same IDs, same reason sentences):

| Intent tokens | Prefer | Reason (draft; keep short) |
|---|---|---|
| `short` / `film` | `hunyuan_video_15` (then 13B / WAN / LTX) | Best fit for short-film and cinematic video generation. |
| `commercial` / `branded` / `product video` | `wan_models` (then Hunyuan) | Best fit for commercial and branded product video. |
| `talking` / `presenter` / `avatar` | `longcat-video-avatar-1-5-local` (then InfiniteTalk / MuseTalk) | Best fit for a talking presenter / avatar performance. |
| `storyboard` / `previz` / `previs` | `flux1_dev_local` + `pack_essential_cinematic` + LTX | Best fit for storyboard frames and motion previs. |
| `product` + `mockup` (require both, avoid `Production Quality` false hit) | `flux1_dev_local` / `qwen_image_2512_models` | Keep as image-only product mockup. |
| existing photoreal / anime / fast | unchanged | Keep |

Frontend `preferred()` ranking must add the video/avatar IDs above the catch-all `9`, or film briefs will still surface leftover image cards in the top 4.

### Step 4 — Tests (extend, don’t replace)

1. `test_setup_lifecycle.py`: table-drive `recommendation_reason` + `search_components` for:
   - `photoreal character` → Kontext + existing reason
   - `anime poster` → Sana/Qwen (after phrase is in metadata)
   - `fast preview` → Schnell
   - `short film` → Hunyuan 1.5
   - `commercial` → WAN (not `fal_key` as sole/top)
   - `talking presenter` → LongCat
   - `storyboard` → flux dev or cinematic pack or LTX
   - Assert `statusLabel` comes from `lifecycle_state` (Ready vs Repair Required), not from empty tags.
2. E2E: update the hardcoded placeholder; keep the anime assertion if that example stays; add one film example fill (`short film`) that expects the new reason and a Ready video card, not “missing”.
3. Optional: one frontend unit test for `matchesIntent` OR-terms vs the new phrases.

### Step 5 — Docs (one paragraph each)

Update the recommendation bullets in `certified-image-catalog.md` and add film/video examples to `codirector-catalog-truth.md`. Do not rewrite architecture.md.

---

## 10. What to keep for image-only intents

Keep all of these; they already work and are certified-image catalog truth:

- `photoreal character` → `flux1_kontext_dev_local`
- `anime` / `anime poster` → `sana_15_local`, `qwen_image_2512_models`, `zimage_models` (+ pack)
- `fast preview` → `flux1_schnell_local`
- Image metadata on `_LOCAL_IMAGE_COMPONENTS` (VRAM, badges, photoreal/anime/preview tags)
- Cloud provider separation
- `product mockup` as an **image** keep (FLUX Dev / Qwen), not a video intent
- E2E anime reason assertion (update only if the sentence is intentionally reworded)

Do not remove the image ranking preferences; **add** film/video/avatar preferences next to them.

---

## 11. Out of scope / do not do

- New recommender, new endpoint, new Co-Director tool
- New catalog components for “storyboard” or “commercial”
- Character Creator edits
- Treating Repair Required avatars as missing
- Bouncing APIs, commit, push, deploy
- Changing `verify_component` / status.py readiness math unless a real false-Ready/false-missing bug is found (none found for these IDs)

---

## 12. Implementer checklist

1. Edit copy in `AiGuidedSetupPanel.tsx` (default, placeholder, helper).
2. Add video/avatar `bestFor` + tags in `service.py` `_COMPONENT_METADATA_OVERRIDES` (and image phrase `anime poster` / `product mockup`).
3. Add matching branches in `recommendation_reason` and `creatorRecommendation`.
4. Extend frontend `preferred()` ranking for Hunyuan / WAN / LTX / LongCat.
5. Tighten `fal_key` “commercial” wording.
6. Extend `test_setup_lifecycle.py` + e2e placeholder/examples.
7. Touch the two docs listed above.

After that, live `query=short film` should return Ready Hunyuan (not 0), and the Setup page helper should lead with film/video/commercial examples while still offering photoreal character.
