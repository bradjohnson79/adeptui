# Creator + Co-Director End-to-End Smoke — Certification

**Date:** 2026-09-16  
**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `99665cf7` plus working tree (this report is not in that SHA alone)  
**Author:** independent evidence review (no new live generate; Comfy observe only)  
**Governing:** this file (Law 30)  
**Supersedes addendum section of:** `docs/release-gate/prop-creator/PROP_USER_UPLOAD_VIEWS_AND_CREATOR_E2E_CERTIFICATION.md`  
**Does not reopen:** `docs/release-gate/prop-creator/PROP_OPTIONAL_VIEW_GATING_CERTIFICATION.md` (**GO** — separate gate)

Local UI: `http://127.0.0.1:5173/`  
Studio API: `http://127.0.0.1:8758/`  
Project A: Cade Scenes `fb24ff0f-8772-4d50-a602-ac69d14b5a6b`  
Project B: `77a189a3-826f-41fb-ace2-44f8e53035eb`  
Cade: `85e37d4b-a32e-4374-888b-1389fc0b3720`  
Upload Smoke Advanced Ship: `a0dae8b5-7b3b-4540-bc62-f88a8c4f6358`  
Cade's Starfighter (canonical from owner prompt): `8a79697b-4ecf-4428-a314-4f15370bf3df`

This gate is the owner **ADDENDUM — CREATOR + CO-DIRECTOR END-TO-END SMOKE**.  
It is **not** the Prop user-upload views GO and **not** the Primary-required / optional-views contract GO.

No live GPU generate was run for this write-up. Verdicts below are from existing evidence only.

---

## Recommended verdict

**NO-GO — CHARACTER + CO-DIRECTOR spoken chat+attachmentIds adopt did not emit mutation_proposal; PROP + CO-DIRECTOR spoken chat+attachmentIds adopt did not emit mutation_proposal; CHARACTER generate_angles cancelled (GPU blocked, not executed); PROP generate_view cancelled (GPU blocked, not executed)**

Owner listed those Co-Director tests as required. Evidence does **not** prove they were optional.

Do **not** read this as:

- `GO — CREATOR + CO-DIRECTOR END-TO-END SMOKE CERTIFIED`

Proposal → approve on canonical Co-Director tools **is** the authorized mutation path and **did** move the same Character / Prop stores. That does **not** convert chat-without-proposal into a spoken-mutation PASS, and it does **not** convert GPU-blocked generate into PASS.

---

## Contract (do not reopen)

| Item | Law |
| --- | --- |
| Prop identity | Approved **Primary** only |
| Additional Prop views (Front / Back / Left / Right / Top / Bottom / Hero) | **Optional** enrichment |
| PRS button / compose | Primary first, then approved optionals; skip missing |
| Source (`generated` / `uploaded`) | Metadata only |
| **Superseded** | “all six views required for PRS” |

That contract is already certified in `PROP_OPTIONAL_VIEW_GATING_CERTIFICATION.md`. This smoke must not reintroduce six-view gating.

---

## Authorized Co-Director mutation path

Canonical write path:

1. `POST /api/codirector/projects/{id}/tools/proposals`
2. `POST /api/codirector/projects/{id}/proposals/{proposalId}/approve`

`POST …/tools/audited` returning **502** “requires an approved proposal” is **expected** for approval-gated tools. It is **not** a PASS and was not used as one.

Spoken `/api/codirector/chat` with `attachmentIds` is a **separate** owner test. On this pass it stayed on the help / LLM path and **did not** emit `mutation_proposal`.

---

## Evidence used (no invented runs)

| Artifact | Role |
| --- | --- |
| `.runtime/CREATOR_E2E_ADDENDUM_GAP_CLOSE.json` | Gap-close live Voice / CD tools / chat grounding / Timeline / IG / Library |
| `.runtime/_creator_addendum_smoke.json` | Earlier Character upload + sheet + Global lists + local-negative 400 |
| `.runtime/creator_e2e_addendum_shots/*.png` | Timeline, Voice Studio, Image Generator, Character Creator |
| `docs/release-gate/prop-creator/PROP_USER_UPLOAD_VIEWS_AND_CREATOR_E2E_CERTIFICATION.md` | Prior Prop upload GO; **stale addendum NO-GO reasons** (Voice / Timeline / IG since closed) |
| `docs/release-gate/prop-creator/PROP_OPTIONAL_VIEW_GATING_CERTIFICATION.md` | Separate optional-views **GO** |
| `studio-api/tests/test_codirector_project_grounding.py::test_prop_ready_grounding_is_primary_only` | Unit: “is this prop ready?” = Primary only |
| Worker [Close addendum E2E gaps](9dc9b76e-187d-4a73-b6e3-419c232fafd6) | IDs and HTTP codes reconciled against the JSON |

This review did **not** enqueue Voice, Character, or Prop GPU jobs. Comfy was observed only.

---

## Owner FINAL REPORT

### CHARACTER CREATOR

| Field | Result |
| --- | --- |
| Upload Side | **PASS** — live upload then CD re-adopt. Store after gap-close: Side `f5b5e1a0-…` uploaded, approved, same `characterId` `85e37d4b-…`. Earlier upload proof: `cdb70dcc-…` |
| Upload 3/4 | **PASS** — `05939962-…` uploaded, approved |
| Upload Back | **PASS** — `bf7ab8d4-…` uploaded, approved |
| Approve | **PASS** — upload stayed candidate until Approve; Front `3869398f-…` already approved (`source=upload`) |
| Character Sheet enablement | **PASS** — `sheetGate.ready=true`, `missing=[]` |
| Character Sheet creation | **PASS** (Character Creator API) — sheet `a35ea523-…` PNG **200** / 261789 bytes. **Not** a Co-Director create-sheet mutation |
| Library | **PASS** — Front PNG **200** / 1.8MB; Side / sheet resolve **200** |
| Reload | **PASS** — GET cc-v2 same character; approved pointers persist |

### CHARACTER + CO-DIRECTOR

| Field | Result |
| --- | --- |
| Use uploaded angle | **FAIL (spoken)** / **PASS (tools)** — `character_creator.adopt_angle` proposal `35a26e22` **completed**; same cc-v2 store. Chat+`attachmentIds` adopt **did not** emit `mutation_proposal` |
| Approve | **PASS (tools)** — `character_creator.approve_angle` proposal `db5a161b` **completed**. `tools/audited` 502 was not used as the pass |
| Generate missing angle | **FAIL** — proposals `ed7250f9` / `e39c7c46` **cancelled**. Blocker: Qwen Image Edit GPU. Not executed. Not a PASS |
| Create sheet | **NOT EXECUTED via CD** — no create-sheet proposal in the gap-close set. Sheet exists from Character Creator API only |
| State parity | **PASS** — “Which character views are approved for Cade?” → `Front (upload), Side (uploaded), 3/4 (uploaded), Back (uploaded)` HTTP **200**, `fallbackUsed: false` |

### VOICE CREATOR

| Field | Result |
| --- | --- |
| Progress | **PASS** — job `2dd7cc08-5f54-4b3d-9267-90dc0d2bf971` reached **100%** only at `phase==complete`; complete stamps after sample asset register (`progressNever100BeforeAudio: true`) |
| Clone | **PASS (live)** — `POST …/voice/clone/generate` `asyncJob=true` `sampleCount=1` **200** from existing clone reference `dd98f7be-…` MP3 **200** / 208073 bytes. No invented credentials |
| Approve new current voice | **PASS** — pointer **0c890a32 → 400ca4f5** (`Cade Addendum Clone Sample`, CLONE, v8). Preview WAV `3b86c422-…` **200** / 65324 bytes |
| Version history | **PASS** — prior approved profiles remain (`8ab53b2c`, `bc3d9abc`, `0c890a32`, `43f8a0d9`). `oldVersionRemains: true`. Version count **8** |
| Use Existing | **PASS (history present)** — previous versions remain selectable in workspace; Voice Studio body showed approved current + prior versions. Formal CD “use previous voice” command was **not** the path that moved `400ca4f5` |
| Reload | **PASS** — `reloadPointerMatches: true`; approved-status **200** pointer `400ca4f5` |

### VOICE + CO-DIRECTOR

| Field | Result |
| --- | --- |
| Current voice awareness | **PASS** — “Cade O'Connor is assigned Cade Addendum Clone Sample (qwen3-tts, approved).” HTTP **200**, `fallbackUsed: false` |
| Version awareness | **PASS** — versions list **200**; `get_voice_status` same store (prior addendum + gap-close pointer) |
| Pointer change | **PASS via Voice Creator approve** — not via a spoken CD “use previous voice” mutation |
| State parity | **PASS** — chat matches `400ca4f5` |

### PROP CREATOR BASIC

| Field | Result |
| --- | --- |
| Upload | **PASS** — Upload Smoke Basic Cup `f04cfdb6-…`, identity `888c465f-…`, origin uploaded, Library PNG **200** (prior upload smoke) |
| Generate | **NOT RE-RUN this addendum** — Basic mixed generate was not a second required view after the optional-views contract. Historical generated Left on the Advanced ship remains the mixed-source proof |
| Approve | **PASS** — cup identity approved |
| Reference output | **PASS** for Basic identity persistence; Advanced PRS is the sheet proof |
| Reload | **PASS** — GET same `propId` |

### PROP CREATOR ADVANCED

| Field | Result |
| --- | --- |
| Front | **PASS** — uploaded `d3a43c47-…` approved |
| Back | **PASS** — uploaded `1fb059eb-…` approved |
| Left | **PASS** — generated `3d1e3d61-…` approved (historical Qwen job; not re-generated this pass) |
| Right | **PASS** — uploaded `8c07e542-…` approved |
| Top | **PASS** — CD adopt/approve replaced pointer with `aa2f27e8-…` uploaded, approved |
| Bottom | **PASS** — uploaded `8d4654fa-…` approved |
| Hero | **PASS** — uploaded `e628f67d-…` approved (optional) |
| Mixed source | **PASS** — Left generated, remaining uploaded, same `propId` `a0dae8b5-…` |
| PRS | **PASS (historical file)** — ship PRS `579355ac-…` PNG **200** / 222227 bytes. After Top re-adopt, live `advanced_sheet` / `prs` on the ship row was **idle / null**. That is **not** a six-view gate. Lean Primary-only PRS `eb16642a-…` **200** belongs to the **separate** optional-views GO |
| Reload | **PASS** — GET ship + Starfighter **200**; Primary `940be337-…` / `8c07b994-…` persist |

Cade's Starfighter Advanced UI was **not** opened this pass (leave-alone for the other agent). API: Primary approved, `identityReady: true`.

### PROP + CO-DIRECTOR

| Field | Result |
| --- | --- |
| Upload routing | **FAIL (spoken)** / **PASS (tools)** — `prop_creator.adopt_view` top on Upload Smoke Advanced Ship proposal `e0a17841` **completed**. Chat+`attachmentIds` “use this image as top view” **did not** emit `mutation_proposal`. Cade Starfighter Primary was left to the other agent |
| Generate routing | **FAIL** — `prop_creator.generate_view` proposals `376df18b` / `635d836b` **cancelled**. Blocker: GPU generate. Not executed. Not a PASS |
| Approve routing | **PASS (tools)** — `prop_creator.approve_view` proposal `acd5c31e` **completed**. Same store (`sameStore: true`) |
| PRS | **NOT EXECUTED via CD** — no create-PRS proposal in the gap-close set |
| State parity | **PASS** — approved-view list matches store (Primary uploaded, Left generated, remaining uploaded). “Is this prop ready?” → **ready. Primary is approved. Additional views are optional.** `prop_creator.get_views`: `propReady=true`, `missingViewsBlockReadiness=false` |

Starfighter ready reply **repeats** because two Prop rows share the label “Cade's Starfighter”: `8a79697b-…` and `6868078f-…` (`cade-s-starfighter-2`). Both Primary-approved. Select by id.

### GLOBAL

| Field | Result |
| --- | --- |
| Character | **PASS** — Cade `85e37d4b-…` visible in Project B, same id, `isGlobal=true` |
| Prop | **PASS** — ship same id in B |
| Environment | **PASS** — Anadriya's Quarters `84ef72cb-…` listed in A and B; ERS `e4c10cdb-…` PNG **200** from A and B |
| Local negative test | **FAIL** — prior addendum create local-only prop returned **400**; `pass: false`. Gap-close did not close it |
| Backing media | **PASS** — Cade Front, ship Primary, ERS resolve from A and from B (**200**) |
| Cross-project | **PASS** — no copy; foreign mutate **403** `OWNER_REQUIRED` (prior upload smoke) |

### GLOBAL + CO-DIRECTOR

| Field | Result |
| --- | --- |
| Discovery | **PASS** — Project A/B chat lists the same global characters / props / environments (prior addendum). Gap-close confirmed globals still resolve as files |
| Selection | **NOT EXECUTED** — no live “Use global Cade / Starfighter / Anadriya's Quarters” bind this pass |
| Canonical IDs | **PASS** — list ids match creator stores |

### DOWNSTREAM

| Field | Result |
| --- | --- |
| Timeline | **PASS (open + resolve)** — `http://127.0.0.1:5173/project/{A}?workspace=timeline` HTTP **200**. Scene `8a385844-…` **200**. In-page canonical assets **200**. Console **[]**. One non-file `timelineDoc` GET was **404**; that is **not** a broken Library/asset URL |
| Image Generator | **PASS (open + resolve)** — `?workspace=imagegen` HTTP **200**. Providers **200** (24). Same in-page asset resolve **200**. Console **[]** |
| Library | **PASS** — list **200** / 20 sampled rows including CD-adopt titles (`ship-top-cd-adopt.png`, `cade-side-cd-adopt.png`) and clone WAV `3b86c422-…` |

### CONSOLE / NETWORK

| Field | Result |
| --- | --- |
| CONSOLE | **PASS** on opened Vite surfaces — `consoleErrorCount: 0`, `pageErrorCount: 0` (Timeline, Voice Studio, Image Generator, Character Creator). MCP browser tabs were unstable; Playwright harvested `:5173`. Prop Advanced was **not** opened |
| NETWORK | **PASS** on opened surfaces — `failedApiCount: 0`. Canonical asset files **200** (no 403/404/500). `tools/audited` **502** is the expected proposal gate, not a smoke network defect |

---

## Additional owner-required paths still open

These are **not** converted to PASS. They are **not** hidden inside the optional-views GO.

1. Spoken chat+`attachmentIds` adopt → `mutation_proposal` (Character and Prop) — **failed**
2. CD `generate_angles` / `generate_view` live execute — **blocked / cancelled** (GPU; Comfy leave-alone)
3. CD create Character Sheet / create PRS mutations — **not executed**
4. Global local-only negative create — **failed** (HTTP 400)
5. Global CD selection/bind — **not executed**

---

## What did close versus the stale addendum write-up

The 2026-09-16 `PROP_USER_UPLOAD_VIEWS_AND_CREATOR_E2E_CERTIFICATION.md` addendum listed three remaining items. Those three are **no longer** the blockers:

| Prior remaining item | Gap-close evidence |
| --- | --- |
| Voice Clone-from-Recording generate / progress | **Closed** — live job `2dd7cc08`, pointer `400ca4f5` |
| Open Timeline and Image Generator | **Closed** — both opened; canonical assets **200** |
| CD adopt/approve through an authorized proposal path | **Closed for tools/proposals** — still **open** for spoken chat+attach |

The current NO-GO is the remaining owner Co-Director mutation tests, plus the still-open Global local-negative and CD selection/create-sheet paths above.

---

## E2E TRACE

| Stage | Verdict |
| --- | --- |
| User action | **PARTIAL** — Voice clone, CD tools adopt/approve, Timeline / IG open were live. Spoken attach adopt and generate-missing were not completed |
| Frontend | **PASS** where opened (`:5173` Timeline / Voice / IG / Character). Prop Advanced not opened |
| API | **PASS** for executed paths (Voice clone, proposals, grounding chat, asset files) |
| Backend | **PASS** for executed stores (cc-v2, Voice, Prop, `identity_ready`) |
| Persistence | **PASS** — Voice pointer, CD-adopted Side/Top, Character / Prop GET after reload |
| Runtime | **FAIL for required CD generate** — GPU blocked; proposals cancelled. Voice clone runtime **PASS**. Comfy not used for this review |
| Result | **PARTIAL** — authorized tool mutations landed; spoken attach and generate-missing did not |
| Reload | **PASS** for persisted pointers |
| Downstream | **PASS** for Timeline / IG / Library file resolve on canonical assets |

---

## Tests (existing; not re-invented)

- `test_prop_ready_grounding_is_primary_only` — worker reported **passed**. Grounding copy is Primary-only; does not require six views
- Optional-views suite remains the **separate** contract GO
- Prop upload / Character angle-upload suites remain their own GOs

---

## Runtime / Comfy

This certification pass (observe only):

- `GET http://127.0.0.1:8758/api/healthz` → **200**
- `GET http://127.0.0.1:5173/` → **200**
- `GET http://127.0.0.1:8188/system_stats` → **200**

Gap-close worker (existing evidence):

- **COMFY BEFORE:** `GET :8188/system_stats` HTTP **200**; PID **34484**
- **COMFY AFTER:** `GET :8188/system_stats` HTTP **200**; PID **34484**
- **COMFY RESTARTED?:** **NO**
- **WHY?:** Observe only. API recycle `39016 → 40932 → 21972`. No supervisor action. No `:8188` stop/start. No GPU generate this review.

---

## Limitations (honest, not used to mint a GO)

- CD adopt Side / Top used small solid-color PNGs (Side file **271** bytes). That proves store pointers, not production artwork.
- Ship live `prs` / `advanced_sheet` idle after Top re-adopt. Historical PRS file still **200**.
- Two props share display label “Cade's Starfighter”; ready-reply duplicates. Select `8a79697b-…` vs `6868078f-…`.
- Prop Advanced UI was not opened on this addendum pass.
- `timelineDoc` GET **404** is a non-file probe; in-page asset resolve on Timeline was **200**.
- MCP browser tabs dropped; Playwright harvested the same local Vite surfaces.

---

## Out of scope

- Prop user-upload views GO — already issued; not reopened
- Prop Primary-required / optional-views GO — already issued; not reopened
- Spatial Map / PoseCraft / Fire3D / SceneCraft — v1.1 shelf

---

## Final language

Recommended binary verdict for primary:

**NO-GO — CHARACTER + CO-DIRECTOR spoken chat+attachmentIds adopt did not emit mutation_proposal; PROP + CO-DIRECTOR spoken chat+attachmentIds adopt did not emit mutation_proposal; CHARACTER generate_angles cancelled (GPU blocked, not executed); PROP generate_view cancelled (GPU blocked, not executed)**

Do not issue `GO — CREATOR + CO-DIRECTOR END-TO-END SMOKE CERTIFIED` on this evidence.

READY FOR PRIMARY REVIEW
