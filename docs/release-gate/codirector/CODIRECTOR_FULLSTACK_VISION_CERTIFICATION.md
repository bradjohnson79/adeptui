# Co-Director Full-Stack Multimodal Vision — Certification

## HISTORICAL (Ollama images[] era, 2026-08-19)

Current chat vision authority: `docs/architecture/codirector/CODIRECTOR_CHAT_VISION_ATTACHMENT_CERTIFICATION.md`

## SUPERSEDED AS CURRENT

Previously marked current:

```text
GO — CODIRECTOR FULL-STACK MULTIMODAL VISION CERTIFIED
```

Governing document for this milestone. Do not cite older vision notes as current truth.

Live target: local Beta `http://127.0.0.1:8760/` + Studio API `http://127.0.0.1:8758/`.
Selected brain: Ollama `qwen3.6:35b-a3b` (`vision` capability advertised).
Project: Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278`.
Character: Korri `c49371ed-ba6b-4c16-ba98-a8b28b72118b`.

Branch: `feat/voice-studio-identity-and-global-ux`
HEAD: `959be5ad4196b55f5c9a3fd87c5a7fe9516deaaf`
API started (cert process): `2026-08-19T22:15:35Z` (`apiRevision` `959be5a`)

---

## Verdict

**GO — CODIRECTOR FULL-STACK MULTIMODAL VISION CERTIFIED**

Core proof observed on live Beta:

```text
Korri CRS 067453ce-6204-434a-bfed-e6d0333e0e67
→ JPEG 1536×1536 (image/jpeg)
→ images[] survived foundation rebuild
→ Ollama qwen3.6:35b-a3b /api/chat stream (num_ctx 16384)
→ vision_trace hasImages=true imageCount=1 firstImageLength=1035292
→ reply named image-only details: boots, apron, tattered
```

---

## What was broken

Pixels already loaded in `_prepare_chat_request`. The live foundation stream rebuilt a text-only last user turn, so Qwen never saw the JPEG.

Secondary: CRS was not preferred; `_character_context_block` crashed on `.get()`; failed loads returned `b""`; Ollama `num_ctx` ignored vision tokens (2048 vs 4417); stream loop dropped `vision_trace`; Character Creator bind could be wiped; no Visual context chip.

---

## Implementation

| Area | Change |
| --- | --- |
| Shared resolver | `studio-api/app/character_identity/visual_context.py` — CRS sheet → hero_identity → reference_image; readable in-project image only |
| Pixel keep | `build_generation_messages` / trim / `_prepare_foundation_request` / repair copy `images[]` onto last user |
| Honest vision | `VISION_UNAVAILABLE` (422) for explicit attach fail, visual-inspection turn with no pixels, or non-vision Ollama tag |
| Context block | IDs / CRS revision / approval only — **no** `visual_description` dump |
| Ollama | Copy `capabilities`; vision `num_ctx` ≥ 8192 (observed 16384); stream `vision_trace` |
| Frontend | Merge-safe `bindWorkspace`; chip `Visual context · {name}` (`codirector-visual-context`); `VISION_UNAVAILABLE` on send-error card |
| Mini | `_identity_for_character.approvedAssetId` uses the same resolver |

---

## Anti-leak corpus (measured, not assumed)

Saved: `docs/release-gate/codirector/evidence/korri-leak-corpus.json`

Profile / Co-Director text available on the turn includes:

- name, description, visual_description (black wrapped crop top, skirt/shorts, **sandals**, wooden hoop earrings, Light Circuitry on left arm, twin ponytails, purple eyes)
- visual_style `realistic_anime`, species `human`, body `Petit`, age `18`
- `_character_context_block` after fix (ids, `crs_sheet`, revision 2, `@Korri`, approved — **no captions**)
- CRS summary JSON (revision / tag / status / asset id)

**Not** in that corpus (visible on CRS `imagegen_edit_b0117276.png`):

- tattered scavenger **apron** / olive drab tunic (not the prose crop top)
- heavy combat **boots** with buckles (not sandals)
- pouches / utility straps
- magenta / pink thermal central panel
- chest label **STARBUCKS COFFEE** / model-read **SCHNICK'S COFFEE**
- dirt / grime / smudge

Question (no leaked answers):

```text
Describe the exact arrangement of Korri's visible outfit and the
placement/pattern of major markings in the current reference.
Include any unusual labels, color treatments, or footwear.
```

Smoke image-only hits (absent from leak corpus): **boots**, **apron**, **tattered**.

Text-only contrast:

- Co-Director without pixels → `VISION_UNAVAILABLE` (honest block)
- Direct Ollama same question, no `images[]` → **zero** image-only token hits

---

## Evidence

| Gate | Result |
| --- | --- |
| Unit `test_codirector_multimodal_vision.py` | **16 passed** |
| Live Ollama `/api/show` | capabilities include `vision` + vision encoder keys |
| Live smoke `scripts/codirector_vision_smoke.py` | **PASS — CODIRECTOR FULL-STACK VISION SMOKE** |
| Playwright `codirector-fullstack-vision.spec.ts` | **9 passed** (clean run, `--retries=0`, 4.9m) |
| Mini shared resolver | `approvedAssetId` = `067453ce-6204-434a-bfed-e6d0333e0e67` (same as Co-Director CRS) |
| Beta | `http://127.0.0.1:8760/` 200, `__beta_web_health` 200, `http://127.0.0.1:8758/api/health` 200 |

Smoke pixel proof (`docs/release-gate/codirector/evidence/codirector-vision-smoke.json`):

| Field | Observed |
| --- | --- |
| assetId | `067453ce-6204-434a-bfed-e6d0333e0e67` |
| source | `crs_sheet` |
| jpeg | 1536×1536 `image/jpeg` |
| modelId | `qwen3.6:35b-a3b` |
| hasImages | true |
| imageCount | 1 |
| firstImageLength | 1035292 (base64 chars, not raw bytes) |
| numCtx | 16384 |
| upload fixture | yellow triangle / purple field grounded |

Screenshots: `docs/release-gate/codirector/evidence/vision-{A–H}.png` and `vision-I-responsive-{1920,1440,1024,768}.png`.

---

## Playwright A–I

| Test | Result |
| --- | --- |
| A Character context shows Korri reference | PASS |
| B Visual context · Korri chip | PASS |
| C Visual question completes | PASS |
| D Grounding uses image-only details | PASS |
| E Direct upload vision | PASS |
| F Character switch updates visual context | PASS |
| G Missing vision asset is visible | PASS (`Vision input failed: no visual reference is available for this Character.`) |
| H Reload keeps conversation + visual-context chip | PASS |
| I Responsive 1920 / 1440 / 1024 / 768 | PASS |

---

## E2E TRACE (Korri)

| Layer | Result | Evidence |
| --- | --- | --- |
| User action | PASS | Character Creator → Korri → Co-Director visual question |
| Frontend | PASS | `character_id` / `characterId`; chip `Visual context · Korri` |
| API | PASS | `POST /api/codirector/chat/stream` |
| Backend | PASS | Resolver CRS `067453ce-…`; JPEG load; `images[]` on last user through foundation rebuild |
| Persistence | PASS | Conversation + chip survive reload (test H) |
| Runtime | PASS | Ollama `qwen3.6:35b-a3b` vision, `num_ctx` 16384, `hasImages` |
| Result | PASS | Image-only: boots / apron / tattered; also Schnick's Coffee on pink panel in later turns |
| Reload | PASS | Test H |
| Downstream | PASS | Mini `approvedAssetId` equals Co-Director CRS asset (shared visual truth, not Mini I2I) |

---

## Certification matrix

| Criterion | Status |
| --- | --- |
| Pixels reach the request that is sent | PASS |
| CRS preferred over draft reference | PASS |
| No silent omit / no text-only pretend | PASS |
| Non-vision model blocked | PASS (unit) |
| Character switch does not reuse Korri pixels | PASS (Anadriya `VISION_UNAVAILABLE`) |
| Anti-leak vs live corpus | PASS |
| Direct upload grounded | PASS |
| Persistence after reload | PASS |
| Creator-facing error | PASS |
| Real runtime, no mock completion | PASS |

---

## Limitations

- Hosted Kie / fal / Gemini is **not** the cert brain. A small OpenAI-parts conversion exists on the hosted adapter only.
- Scene Creator Mini stamps the same `approvedAssetId`; it still generates from the ERS plate. No Mini I2I vision path was added.
- The last Ollama `vision_trace` SSE overwrites the richer service trace (`assetIds` / `dimensions` live on the first service event; smoke recorded the last event).
- Working tree is dirty relative to HEAD `959be5a`; cert is against the running Beta process started `2026-08-19T22:15:35Z` with this tree.
- Independent review ([Vision cert review](5ed484f9-fe46-4535-99a7-cc9bd0641d59)): `READY FOR PRIMARY REVIEW`. Cursor Task did not expose `gpt-5.4-medium` (Law 27); review used inherit.

---

## Manual review

1. Open `http://127.0.0.1:8760/` (creator UI) and `http://127.0.0.1:8758/` (Studio API).
2. Schnick Coffee → Character Creator → Korri.
3. Confirm Co-Director chip `Visual context · Korri`.
4. Ask the visual question above. Expect scavenger apron / boots, not the prose sandals/crop-top as the only description.
5. Switch to Anadriya and ask a visual question. Expect the visible Vision input failed card.

Leave Beta running.
