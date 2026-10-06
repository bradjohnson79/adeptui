# Scene Creator Mini Camera Production Certification

**Governing document for this milestone.**

Upgrade Scene Creator Mini so cameras own rendering (Local sequential / API concurrent), lens and lighting mood live on Spatial Map cameras, Camera Shot References leave the map chrome, and Save Spatial Map sits beside Generate ERS.

**Verdict:** `GO — SCENE CREATOR MINI CAMERA FIDELITY + API CONCURRENCY + LOCAL SEQUENTIAL + INPAINT + APPROVAL PIPELINE LIVE E2E CERTIFIED`

Addendum (2026-08-29): live Playwright re-proved API A/B overlap. Take `5770d67b-b028-445e-8bd5-b94a34f554cf` — C1-A `b1762592-…` and C1-B `40464ae6-…` both `generating` on the same persist (`concurrency=api_concurrent`). Hook-order crash was not reproduced. API Mini is not gated by Local-generation readiness. Local remains sequential.

---

## Identity

| Field | Value |
| --- | --- |
| Branch | `feat/character-creator-final-closure` |
| HEAD SHA | `b6156455e643d5fa430784b3130756f2d8038651` (working tree includes this mission; not committed unless requested) |
| Named project | Adept Stability Cert `2bc632b8-b329-4d3b-bc40-b68dc41b6bb1` |
| Production map (never write Atlas) | Supplementary View Assist Cert `e6f64c3b-2533-4549-a476-bf0dcb90d298` / Atlas `9f7d4571-9444-41fa-b4c2-29c27919736a` |
| Live cert map | ERS Production Cert `d7c721c3-9377-4eca-bea7-3c2be2e5e5fc` |
| Review URLs | Creator UI `http://127.0.0.1:5173/` · Studio API `http://127.0.0.1:8758/` |
| LLM review | Composer 2.5 only (review-only). First pass BLOCK (Send Selected provenance). Repair. Second pass **PASS**. |

Success string: `GO — SCENE CREATOR MINI CAMERA FIDELITY + API CONCURRENCY + LOCAL SEQUENTIAL + INPAINT + APPROVAL PIPELINE LIVE E2E CERTIFIED`

Failure string: `NO-GO — SCENE CREATOR MINI CAMERA PRODUCTION PIPELINE NOT CERTIFIED`

---

## Concurrency law

| Class | Rule |
| --- | --- |
| Local (`qwen2512` / Comfy / GPU) | Sequential. The next Mini Local job is not launched until the previous GPU job leaves `running`. |
| API (`gpt-image-2`) | Concurrent child jobs. Cap is `STUDIO_MINI_API_MAX_CONCURRENT` (default **6**), not a camera-count hardcode of 4. |
| Status | Queued / Generating / Validating / Ready / Failed / Approved. |
| Siblings | One camera failure does not cancel the others. |
| Out of scope | Character Creator, Atlas, and ERS queues unchanged. Supplementary mutex not expanded. |

Prior incomplete evidence: take `0624ad36-…` persisted A+B job ids but the Studio job worker still ran them one-at-a-time (`A generating`, `B queued`). That is **not** API concurrency.

Required API behavior now: persist every `camera × variant` child, then dispatch all hosted Mini children. The job worker runs those children concurrently up to `STUDIO_MINI_API_MAX_CONCURRENT` (default 6) or a provider-advertised cap when one exists. Variant A and Variant B of the same camera must be generating together.

Local remains one GPU job at a time: `C1-A → C1-B → C2-A → C2-B`.

A failed API sibling does not cancel the other. Retry is per-shot (`cameraId` + `variation`).

Local: take `5d9baaf6-…` `concurrency=local_sequential`. Qwen refused honestly (CRS is not a Mini still path). No silent API swap.

---

## Lens / FOV reconciliation

Canonical sensor (not in UI): **Full Frame 36 mm horizontal**.

| Control | Authority |
| --- | --- |
| `lens = auto` | Current `fovPreset` remains authority. |
| Manual lens (`18`…`135`) | Lens is framing authority. Derive `fovDegrees`. Snap `fovPreset` (wide ≥ 65°, medium, narrow ≤ 35°). Set `lensMm`. |
| `lens = fisheye` | Special cinematic fisheye projection. **No** focalLength → rectilinear FOV. Packet records `lens: "fisheye"`. Not 18mm. |
| FOV buttons after a manual lens | `lens` returns to `auto`. Last explicit control wins. |

Missing `lens` / `lightingMood` hydrate to `auto` / `auto`. Lighting mood is packet/prompt only. `auto` follows ERS / scene intent — no forced generic daylight.

Playwright: C1 lens `35` + Lighting Mood Sci-Fi → Save Spatial Map beside ERS → reload persist. Camera Shot References absent from the map.

---

## Shot packet

`CameraShotPacket.camera` includes `lens`, `lightingMood`, `fovDegrees` (when derived), and `distanceMeters` only when a real primary subject exists. Light environmental context uses existing anchors and map extent.

---

## Creator surface

ERS action row:

```text
[ Generate / Regenerate Environment Reference Sheet ]  [ Save Spatial Map ]  [ Reset Map ]
```

Same Save Gate. Reset stays secondary. `CameraReferenceStrip` removed from Spatial Map. `camera_reference.py` remains Mini-internal conditioning.

Scene Creator Mini: Generation Method Local | API. No silent swap. Cards + regenerate one camera. Ready thumbnail → modal with exact caption:

`Shot not looking right? Consider adjusting your cameras in the Spatial Map, save then retry.`

Inpaint / Correct stays on the same provider class. Drafts stay `libraryVisible: false` until Approve (or Send Selected, which now uses the same provenance stamp).

---

## Live inpaint + approve

Take `0624ad36-…` variation B `7701be79-…`:

1. Inpaint job `2a194016-…` queued on GPT Image 2 (same API class).
2. Completed as revision `1` with a new asset.
3. Approve → `approved=true`, `inLibrary=true`, `approvedAt=2026-08-28T17:49:05.499415+00:00`.

---

## Tests

| Gate | Result |
| --- | --- |
| Spatial Map vitest | **166 passed** |
| Backend optics + packet + approve + regenerate + alignment protect | **21 passed** (scoped) then regenerate/approve recheck **2 passed** |
| Playwright Mini camera production | **3 passed** (2026-08-29 addendum, live Vite `:5173` + API `:8758`) |
| Protected Playwright movement | **passed** |
| Protected Playwright ERS generator | **passed** |
| Protected Playwright direct-use | **passed** |
| Protected Playwright background alignment | **passed** (1 flaky + retry) |
| Composer 2.5 | **PASS** after Send Selected provenance repair |

Pre-existing Mini compile/library helpers remain failed outside this mission (`qwen2512` CRS compile refuse, `_library_visible` import, ERS prompt camera-grid line). Not used as this gate.

---

## E2E TRACE

| Stage | Verdict |
| --- | --- |
| User action | PASS — lens 35 / Sci-Fi / Save beside ERS; Mini API generate; inpaint; Approve |
| Frontend | PASS — cards, Local/API selector, modal caption, Save row, refs off map |
| API | PASS — updateCamera, save, mini-take, inpaint, approve |
| Backend | PASS — optics, packet, sequential/concurrent enqueue, provenance stamp |
| Persistence | PASS — lens/mood survive reload; approved asset `libraryVisible` |
| Runtime | PASS — GPT Image 2 A/B jobs; Local honest refuse |
| Result | PASS — two completed API stills; inpaint revision 1 |
| Reload | PASS — lens 35 + Sci-Fi persist |
| Downstream | PASS — Approve to Project Library with provenance |

---

## Addendum — API fan-out is a worker dispatch rule

Mini enqueue already created all child job rows. The missing layer was `JobQueue._loop`, which `await`ed each imagegen job to completion (including the hosted HTTP wait) before starting the next. Hosted Mini children (`miniTakeId` + Kie/fal/`cloudPaid`) now spawn concurrent worker tasks. Local/Comfy jobs stay serial. Character Creator, Atlas, and ERS queues are unchanged.

```text
API:  build children → persist parent + children → dispatch all → each child reports independently
Local: build children → persist → dispatch first GPU child → when terminal, dispatch next
```

Hard E2E: one camera, two variants, API — a single poll must observe both children `generating`.

---

## Addendum — Fisheye lens

`fisheye` is a first-class camera lens enum value (dropdown label **Fisheye**). Auto and numeric focal lengths keep rectilinear FOV math. Fisheye uses special projection language in the Mini packet and prompt and is recorded as `lens: "fisheye"` on approve provenance. It is never converted to 18mm.

---

## Limitations

- ERS Production Cert currently has one placed camera. API concurrency was evidenced as overlapping A/B child jobs, not C1+C2.
- Certified Local Mini still is not available on this machine (Qwen CRS refuse). Sequential law is implemented; live GPU evidence is an honest skip.
- Scene Creator Standard is unchanged.

---

## Verdict

`GO — SCENE CREATOR MINI CAMERA FIDELITY + API CONCURRENCY + LOCAL SEQUENTIAL + INPAINT + APPROVAL PIPELINE LIVE E2E CERTIFIED`
