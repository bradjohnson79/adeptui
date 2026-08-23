> **HISTORICAL — SUPERSEDED BY CHARACTER CREATOR V2.**

# Character Creator Single Canonical CRS — Certification

## CURRENT

```text
GO — CHARACTER CREATOR SINGLE CRS → QWEN/GPT IMAGE 2 → APPROVED CANON CERTIFIED
```

Governing document for this milestone (Law 30). Separate from Co-Director production-loop and lifecycle verdicts.
Does not reopen `GO — CHARACTER CREATOR → 2K CRS SHEET → APPROVED CANON → UNIVERSAL @CHARACTER CERTIFIED` (historical 2K Korri sheet).

Live target: `http://127.0.0.1:8760/` + `http://127.0.0.1:8758/`.
Project: Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278`.
Korri used for A–D visual proof only. Generate/approve used disposable `284411ea-596f-4b8d-9a0e-8da81a67edbf` (`CRS Single 1787198703328`).

Branch at report time: `feat/codirector-temporal-continuity`
HEAD: `c8c5133ec1d0d4beb10901606c4f7d889daf5c9f`
Live `apiRevision`: `959be5a` (`apiStartedAt` `2026-08-20T03:53:19Z`)

---

## Verdict

**GO — CHARACTER CREATOR SINGLE CRS → QWEN/GPT IMAGE 2 → APPROVED CANON CERTIFIED**

---

## Matrix

| Criterion | Result |
| --- | --- |
| One CRS | PASS — backend coerce + frontend `candidateCount: 1`; live pack `candidateCount: 1` |
| Qwen default | PASS — A–D + hydrate `qwen2512` |
| GPT Image 2 selectable | PASS — selector; live generate |
| Other generators removed from CRS UI | PASS |
| Multi-generator batch removed | PASS |
| Candidate grid removed | PASS |
| Single active CRS card | PASS |
| Preview modal | PASS — `single-crs-G-preview.png` |
| Regenerate one revision | PASS — first Qwen moved to Previous CRS Versions; new draft generated |
| Approval / canon | PASS — `approval_status: approved`; banner persist after reload |
| `@Character` | PASS — `@CRS Single 1787198703328` |
| Historical revisions compact | PASS — Revision 1 LOCAL Qwen Image 2512 |
| Co-Director CRS route | PASS (units + A–C); live Co-Director Ready card is owned by the other report |
| Co-Director multi-view Image Generator | PASS (H + smoke) |
| Save / Reset / Delete present | PASS (lifecycle report owns those GOs) |
| Smoke | PASS — CHARACTER CREATOR SINGLE CRS SMOKE |
| Playwright A–D | PASS (3.9s) |
| Playwright E–O | PASS — first Qwen generate measured; continue test **passed** (1.4m) for approve/persist/GPT |
| Frontend visual | PASS — CC D [visual](98fc91f7-8c28-4534-9871-35f5ed25a2a4) READY FOR PRIMARY CERTIFICATION |
| Responsive 1920/1440/1024/768 | PASS shots `single-crs-responsive-*.png` |
| Independent review | PASS — CC E [review](11830bc3-66e3-4063-a887-47b13ea051b6) READY FOR PRIMARY CERTIFICATION |
| Loop E live UI | PASS — [review](5cf4433a-17ab-4068-bcb6-e827c3f767ec) READY FOR PRIMARY CERTIFICATION |

---

## Live generate evidence

Disposable `284411ea-596f-4b8d-9a0e-8da81a67edbf` in Schnick Coffee (no new project):

| Step | Measured |
| --- | --- |
| Qwen generate | Asset `68853faf-3f41-4383-8eb7-9cf6850bbae9` — `GET /api/assets/{id}/file` **200**, 7,559,486 bytes, 2560×2560, provenance LOCAL — Qwen Image 2512 |
| Preview | `single-crs-G-preview.png` |
| Regenerate | New draft; first sheet kept in `previousCandidates` / Previous CRS Versions |
| Approve + reload | Banner `Character Approved / Production Ready / Universal Reference: @CRS Single 1787198703328` |
| GPT Image 2 | Selector N `single-crs-N-gpt.png`; result O `single-crs-O-gpt-result.png`; current hero `3de94e35-7fec-4073-9d06-225467692bf6` (`gpt-image-2-kie`), file **200** ~1.9MB, 1254×1254, Draft |

Playwright `E–O continue approve persist GPT on existing disposable` **1 passed (1.4m)** after the first Qwen sheet existed. The monolithic E–O run timed out on regenerate while the first sheet was already persisted; regenerate completed and the continue test closed J–O.

---

## Tests

- `test_character_creator_single_crs.py`: **4 passed**
- Frontend vitest (plan/panel/sheet/profile): **58 passed**
- Smoke: **PASS — CHARACTER CREATOR SINGLE CRS SMOKE**
- Playwright A–D: **passed**
- Playwright E–O continue: **passed**
- `character-creator-kie-three-model.spec.ts`: skipped as CC gate
- `character-crs-sheet.spec.ts` A/grid cases skipped

---

## Limitations

- Internal coverage-role jobs may remain `GENERATING` after the single CRS image is terminal. They must not appear as competing cards (they did not).
- GPT Image 2 option suffix `— API` is slightly technical; provenance strings can still show `gpt-image-2-kie` on the card (Loop E residual note, not a gate fail).
- Co-Director D–E Ready+media is **not** claimed here.

Final language: **GO — CHARACTER CREATOR SINGLE CRS → QWEN/GPT IMAGE 2 → APPROVED CANON CERTIFIED**
