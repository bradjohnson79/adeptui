# Co-Director Adept System + Generator Knowledge Foundation

**HISTORICAL for Adept Platform Production Readiness score.** This document certified the knowledge corpus and spoken cards. It does **not** govern the 2026-09-14 Operational Knowledge Convergence score. Current authority: `docs/release-gate/codirector/CODIRECTOR_KNOWLEDGE_FOUNDATION_OPERATIONAL_CONVERGENCE.md`.

**Governing document for this (historical) mission.**

Co-Director must operate Adept as a native product: registered systems, generators, modes, and prompting contracts — not generic acronym guesses.

**Verdict:** `GO — CO-DIRECTOR ADEPT SYSTEM + GENERATOR KNOWLEDGE FOUNDATION E2E CERTIFIED`

---

## Identity

| Field | Value |
| --- | --- |
| Branch | `feat/character-creator-final-closure` |
| Knowledge schema | `adept-codirector-knowledge/v1` |
| Knowledge version | `2026.09.04` |
| Review URLs | Creator UI `http://127.0.0.1:5173/` · Studio API `http://127.0.0.1:8758/` |

---

## Part A — hamburger

The upper-left Co-Director hamburger (`codirector-menu-button` / `CoDirectorNavDrawer`) is removed.

Viewport production navigation remains: Wiki · Notes · Story · Script Writer · Character Creator · Voice Creator · Prop Creator · Spatial Map · Scene Creator · Timeline · Library.

Leftover hamburger-only rooms (Casting, Vision, Pitch & Launch, Bible, Plans, Approvals, Jobs) live under viewport **More**. System Status stays on the header chip. Conversation is the chat itself.

Header identity no longer reserves a button-sized gap.

---

## Part B — knowledge architecture (converged)

No sixth documentation tree. Conversation authority is:

`studio-api/app/codirector/knowledgebase/`

| Existing (kept) | Role |
| --- | --- |
| `video-generators/*.md` | Video compile + spoken identity |
| `environment-reference-sheet/ERS_SPEC.md` | ERS compiler spec |
| `config/codirector/creative-knowledge/*.json` | Craft doctrine only |
| `generator_knowledge/profiles/` | Timeline compile machine layer |

| Added | Role |
| --- | --- |
| `adept/` | Authority order, platform, terminology, system map, readiness |
| `systems/` | Wiki through MAGI |
| `generators/image|audio|voice/` | Registered still / audio / voice profiles |
| `workflows/` | CRS / PRS / Prompt Names / continuity / ERS law |
| `MANIFEST.yaml` | Versioned inventory |
| `lexicon.yaml` | Domain-first aliases |
| `loader.py` `lexicon.py` `retrieve.py` `platform_replies.py` | Runtime path |

**Authority order (frozen):** live project → Adept registry → this Markdown → installed workflow → upstream docs → general LLM knowledge.

**Terminology freeze:** Circular viewport = RETIRED. Circle-in-square placement grid = REQUIRED.

---

## Retrieval path (live)

```text
Markdown
  → loader (mtime cache)
  → lexicon.resolve_terms (domain-first)
  → retrieve_knowledge (limit 4)
  → knowledge_reply (deterministic identity/mode)
  → service.py after grounding, before situational / LLM
  → if no spoken hit: ≤2000-char snippet inject into LLM context
```

Measured (`What is WAN?`): 53 corpus docs, **4 retrieved**, **978 context chars**, **21 ms**. Not a full-corpus dump.

Overflow `list_models` no longer advertises `wan_2_2` / `ltx_2_3` as text-to-video.

---

## Root cause of the WAN mistake

Generic LLM knowledge treated WAN as Wide Area Network, and stale Overflow/M30E packs still called WAN a T2V model.

Repair: domain-first lexicon (production → `wan-2.2`; explicit networking → Wide Area Network) plus Adept-integrated spoken cards. Scene grounding no longer swallows “which generator creates an ERS?”.

---

## Peer review

Independent review: [Peer review](6a4f43e2-6f5f-4432-b513-1ddb0c535668).

Blocker: WAN compile YAML / body said start-only one picture while Production Control is First/Last Frame.

**Resolved:** `required_frames: first_last`, `frame_inputs: [start_image, end_image]`, body now requires two pictures. Prompt `max_images: 1` remains the extra-identity name slot (not a second CLIP tensor). Timeline `wan_single_cond` mechanism unchanged.

Non-blocking leftovers: Overflow July catalog files are superseded, not deleted; hidden catalog-only stills are listed only in `image-generation.md`.

---

## Tests

| Suite | Result |
| --- | --- |
| `tests/test_codirector_platform_knowledge.py` | **passed** (17+) |
| `test_ers_generator_question_is_not_scene_grounding` | **passed** |
| Vitest header + viewport nav | **2 passed** |
| Playwright `codirector-platform-knowledge.spec.ts` | **1 passed** (12.9s) |

Live UI (disposable project, then reload): hamburger gone; WAN = First/Last Frame; ERS = GPT Image 2; PoseCraft not Express; Spatial Map rectangular + placement grid; On Demand ≠ offline.

---

## Inventory

Canonical table: `studio-api/app/codirector/knowledgebase/MANIFEST.yaml` (53 entries).

Every production-facing system and registered generator used in Co-Director conversation has a knowledge id. Catalog-only hidden image rows are documented in `systems/image-generation.md` rather than given fake ready profiles.

| Entity | Type | Knowledge File | Registry ID | Runtime Retrieval | Test |
| --- | --- | --- | --- | --- | --- |
| WAN 2.2 | video | `video-generators/wan-2.2.md` | `wan-local` | Yes | unit + Playwright |
| LTX 2.3 / 2.5 | video | `ltx-2.3.md` / `ltx-2.5.md` | `ltx-local` / `ltx-2.5-*` | Yes | unit + Playwright |
| MiniMax H3 | video | `minimax-h3.md` | `minimax-h3` | Yes | unit + Playwright |
| Seedance / Kling / Veo / Hunyuan | video | existing video-generators | matching PC ids | Yes | unit retrieve |
| GPT Image 2 / ERS | image / workflow | `gpt-image-2.md` + `ers-law.md` + `ERS_SPEC.md` | `gpt-image-2-kie` | Yes | unit + Playwright |
| Qwen / FLUX / Krea / Z-Image / Illustrious | image | `generators/image/*` | matching PC ids | Yes | unit loader |
| ACE-Step / MMAudio / Qwen TTS / IndexTTS2 | audio/voice | `generators/audio|voice/*` | matching ids | Yes | unit loader |
| Spatial Map / PoseCraft / Character / Voice / Timeline / … | system | `systems/*` | workspaces | Yes | unit + Playwright |
| Readiness / authority / terminology | platform | `adept/*` | — | Yes | On Demand test |

---

## Runtime

- `http://127.0.0.1:8758/api/healthz` → 200
- `http://127.0.0.1:5173/` → Vite creator UI
- `GET http://127.0.0.1:8188/system_stats` → 200

**COMFY BEFORE:** PID 69108 / health 200  
**COMFY AFTER:** PID 69108 / health 200  
**COMFY RESTARTED?:** NO  
**WHY?:** Knowledge + header only. Studio API recycled via control plane `/restart-api`.

---

## E2E TRACE

| Stage | Result |
| --- | --- |
| User action | PASS — hamburger gone; ask WAN / ERS / PoseCraft / Spatial Map |
| Frontend | PASS — viewport tabs + More; composer |
| API | PASS — `knowledge_reply` after grounding |
| Backend | PASS — lexicon + retrieve |
| Persistence | PASS — answers survive reload (same retrieval, not test injection) |
| Runtime | PASS — Comfy untouched |
| Result | PASS |
| Reload | PASS |
| Downstream | N/A — Q&A, not generation |

---

## Limitations

- Overflow Prompt Knowledge still lists July `knowledgebase/generation/video_models/` files; they are superseded and `text_to_video` is forced false at list time.
- Hidden catalog-only stills do not have full generator profiles (intentional).
- `test_ers_knowledgebase_compiler.py::test_camera_lock_uses_spatial_map_slots_not_prose_guesses` remains a pre-existing compiler/test mismatch (HEAD never contained `CAMERA PLACEMENT IS CANONICAL` in `ers_compiler.py`).
- Working tree is not committed unless requested.

---

## Final verdict

**GO — CO-DIRECTOR ADEPT SYSTEM + GENERATOR KNOWLEDGE FOUNDATION E2E CERTIFIED**
