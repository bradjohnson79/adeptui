# Co-Director Universal Scene Intelligence Convergence — Governing Design

Status: ACTIVE governing document for this milestone (Law 30).
Mission: upgrade Co-Director into a universal, independent scene-planning and
Timeline prompt-synthesis system. Cursor builds the capability; Co-Director
proves it. Scene 3 (project `fb24ff0f`, scene `d0162b33`) is a read-only
regression specimen — never manually completed or repaired.

## Baseline failure (measured 2026-09-17, read-only probe)

Original Scene 3 request (Cade O'Connor + Venture Corridor Scene, door-breach
reveal, one dialogue line, 30s / 2 batches / 21:9 / 1.0 MP / MiniMax H3) through
the current pipeline:

1. `intent_parser._extract_references` misses "Character reference of Cade
   O'Connor" (name after the label) — only the environment is queried. Cade
   silently vanishes.
2. `generator_validator` hard-fails: 30s > H3 max 15s. "2 batches" semantics
   (2 × 15s) are not understood.
3. `scene_breakdown` is a Venture-spaceship regex template (portal / orbit /
   horizon / starfighter). Door breach, reveal gating, steam, dialogue, mood —
   all destroyed. ACTION collapses to "Cade O'Connor already established in
   Venture Corridor Scene."
4. `prompt_compiler` hardcodes spacecraft exclusions ("Do not add extra
   vessels", "Do not equalize ship sizes") — nonsense for an interior scene.
5. No dialogue model, no reveal gating, no camera semantics, no mood, no
   exclusions extraction anywhere in Layer B.
6. Follow-up "retry" re-parses only the edit text → intent collapses
   (starts from blank).

## Three-layer architecture (frozen)

- **Layer A — Creator Request**: immutable `spec.source_user_prompt`.
- **Layer B — Director Scene Intent**: `DirectorSceneIntent`, expanded
  (below). Produced by `scene_understanding.extract_scene_understanding`
  (LLM-backed, schema-validated, deterministic universal fallback) mapped onto
  verified references by `scene_breakdown.build_director_scene_intent`.
- **Layer C — Generator Prompt**: `prompt_compiler` synthesizes H3 sections
  from Layer B only. ACTION is assembled from ordered `SceneBeat`s; runtime
  metadata never enters creative prose.

## Contract expansion (contracts.py)

New models:

- `DialogueLine`: speaker, speaker_tag, line (exact, never paraphrased),
  delivery, voice_characteristics, filtering, beat_index.
- `RevealConstraint`: subject, subject_tag, hidden_until (event language),
  hidden_until_beat, reveal_order (staged parts, e.g. eyes → armor lights →
  silhouette), condition.
- `SceneBeat`: index, kind (establish|approach|impact|pause|escalation|reveal|
  dialogue|reaction|exit|hold|transition|action), description (on-screen event
  prose), subjects, camera, hold_seconds, vfx.
- `CameraPlan`: shot_type, movement (semantic), framing, target, evolution.

`DirectorSceneIntent` gains: `scene_type`, `purpose`, `mood`, `scene_beats`,
`reveals`, `dialogue`, `subtitle_policy` ("none" when creator forbids
subtitles/text), `exclusions`, `camera_plan`. Legacy fields
(`opening_state`, `vfx_event`, `entrance`, `movement`, `stealth_intent`,
`end_state`, `beats`, `timed_beats`, `spatial_rules`, `continuity_rules`,
`action_text`) remain populated for backward compatibility.

## Scene understanding (new module scene_understanding.py)

- Primary path: active Co-Director provider (same resolution as chat:
  `service.get_provider()`), strict JSON-only extraction prompt, Pydantic
  validation, instruction-copy sanitization. Async provider bridged from sync
  orchestrator via a dedicated worker thread + `asyncio.run`.
- Fallback path: deterministic universal extractor (generic cinematic lexicons
  — camera moves, beat cues, reveal phrases, exclusion phrases, dialogue
  patterns, mood section). No franchise/project tokens anywhere.
- `llm_fn` is injectable for hermetic tests. LLM failure/invalid output →
  fallback + debug event `understanding_fallback` with reason (honest
  degradation; never fake success).
- Asset names from understanding are matched to resolved references
  (normalized fuzzy); canonical tags come only from the authoritative
  resolver. Never fabricate tags for unresolved names.

## Reference extraction fix (intent_parser.py)

Add patterns: "Character reference of X", "the X environment reference sheet",
"@Tag" / "%Tag" / "#Tag" explicit mentions, "using X as the setting".
LLM-extracted asset mentions are merged into `reference_queries` before
resolution so nothing the creator named is silently dropped.

## Multi-batch semantics (validator + timeline_builder)

- `duration_seconds` = total scene duration; `batch_count` = batches.
  Per-batch duration = duration / batch_count must be ≤ generator max
  (30s / 2 batches = 2 × 15s — legal H3).
- `timeline_builder` creates `batch_count` BatchBlocks; timed beats are
  partitioned by time window; each batch prompt segment = shared sections
  (SHOT/ENVIRONMENT/SUBJECTS/CONTINUITY/NEGATIVE) + ACTION scoped to its beat
  window. Idempotent via `sourceProductionRequestId` + batch index.

## Prompt compiler (prompt_compiler.py rewrite)

Sections from intent only: SHOT (shot/framing/camera summary), ENVIRONMENT
(verified env, generic), SUBJECTS (canonical tags, no redesign), SPATIAL
RELATIONSHIPS (spatial_rules + scale language), ACTION (synthesized beats,
dialogue embedded at its beat with exact quoted line + delivery, reveal
staging explicit), MOTION (movement beats), CAMERA (camera_plan semantics),
CONTINUITY / REFERENCE PRESERVATION (identity + reveal gating), NEGATIVE /
EXCLUSION CONSTRAINTS (intent.exclusions + subtitle policy + tag-drift guard).
No franchise hardcodes. Suffixed-tag-variant cleanup and instruction-copy
assertion retained.

## Retry semantics (orchestrator follow-up)

Follow-up edit: reuse prior validated references (re-resolve only newly named
assets), combined understanding input = original request + "Creator revision:"
+ edit, re-synthesize intent, re-compile, update the same shot/batches.
Attach dedupe is check-first (no duplicate bindings). Never restart from
blank; never copy the original instruction into ACTION.

## Scene addressing

"For Scene N" / "Scene N" in the request resolves to the project's scene with
index N-1 (or exact name match) when no explicit `scene_id` is passed, so CD
itself targets the existing blank scene.

## Visible preparation milestones (creator surface, grounded, no CoT)

Preparing scene... → ✓ Environment identified → ✓ Character/Prop references
identified → ✓ References verified → ✓ Scene structure analyzed (N beats) →
✓ Dialogue detected (N lines, only when present) → ✓ Reveal constraints
identified (only when present) → ✓ Camera plan identified → ✓ Continuity
locked → ✓ Runtime settings extracted → ✓ Timeline prompt synthesized →
Timeline ready.

## Testing law

- Unit: Scene 3 + samples A–F fixtures through both LLM-injected and
  deterministic paths; ACTION synthesis; runtime stripping; beats; reveal;
  dialogue; voice; tags; verification; retry; no alias leakage.
- API/persistence: intent + prompt persist; tags and bindings survive reload;
  retry does not duplicate bindings; multi-batch split legal.
- Playwright: samples A–F through the real CD UI on the live local stack,
  disposable project, references seeded via API (setup only — CD prepares the
  scenes alone). No mocks, no manual repair.
- Scene 3 regression: after samples pass, the original request is handed to CD
  untouched; CD must independently resolve Cade + Venture Corridor Scene,
  extract beats/reveal/dialogue/camera, keep runtime separate, use canonical
  tags, synthesize ACTION, and prepare the existing Scene 3 in Timeline.
- Peer review: Kimi K3, GLM 5.2, GPT-5.6 Sol — all AGREE or NO-GO.
