# Session Memory: 2026-09-27 evening through 2026-09-28 ~8:30 PM PT

Chief Code Bot coordination on BRAD-5090. Branch `feat/character-creator-final-closure` (dirty LOCAL-ONLY working tree). Prefer live tree over CloudAgent. Comfy `:8188` was **not** restarted across these missions (standing rule unless Brad asks). Studio API `:8758` / Vite `:5173`.

Owner protocols in force: double-check + smoke before GO; Law 65 parse-check touched TS/TSX; full Adept reports pasted in chat (not path-only).

Related prior note: `memory/session-2026-09-26-27-timeline-v2.md` (Render Shot still NO-GO at that cutoff).

---

## CLOSED — GO / certified
### 8. Timeline reference tag chip double-prefix
**TAG PREFIX — COMPLETE** (2026-09-28 ~8:41 PM PT).
Root: FilmTimelineShell `${prefix}${ref.tag}` when tag already had @/#.
Fix: `filmReferenceChipLabel()` single-authority. Browser: @Renkoka / #Abode.
Evidence: `theme_walk/timeline_tag_prefix/`
Bot: `5a769dc0-2ce2-4775-b9f7-3f076cc3d638`

### 1. FilmTimeline Render Shot + MiniMax H3 legal canvas
**GO** — Scene canvas (e.g. 1920×824) must not be submitted to H3. Authoritative H3 megapixel table + resolver; default 0.7 MP → 1152×640; fail-before-Comfy; Preview error + clear generating; Continue/Retake preserve size.
Evidence: `theme_walk/timeline_v2_render_shot/`, `theme_walk/timeline_v2_h3_canvas_gate_removal/`

### 2. Preview Cancel always visible
Cancel control always top-left in Preview (not only while generating).
Evidence: `theme_walk/timeline_v2_cancel_preview/`

### 3. MiniMax H3 Director live cutover (Bots A/B/C)
- **A** Cutover (`0d7e9026…`): CUTOVER PATH LIVE (`useDirector`, fail-closed)
- **B** Present (`986e725c…`): PRESENTATION LIVE PASS (label MiniMax H3 Director — Local)
- **C** Accept (`dc853b97…`): mechanical pass; continuity phases initially NO-GO

Evidence: `theme_walk/timeline_v2_h3_director_cutover/`

### 4. H3 Continuity / Continue identity handoff
**GO — H3 DIRECTOR 15+5 CONTINUITY + IDENTITY HANDOFF CERTIFIED**
Root: bridge wrote `timeline.continuity.enabled` while Director reads `output.continuityEnabled`; native continuity needed `segment_count >= 2`; `comfy_render_scene` dropped continuity options.
Cert job `55e03207` / prompt `d42a81df`: opening_loop false; A_last vs B_first MAD improved.
Evidence: `theme_walk/timeline_v2_h3_director_continuity/`

### 5. H3 R2V architecture eradication
**GO — TIMELINE V2 H3 R2V ARCHITECTURE ERADICATED; DIRECTOR IS SOLE AUTHORITY**
Caveat: LIVE_GPU_PARTIAL (fresh job entered Director; session-cancelled mid-sample).
Evidence: `theme_walk/timeline_v2_h3_r2v_eradication/`

### 6. Timeline V2 universal Aspect Ratio (thin slice)
**GO — TIMELINE V2 UNIVERSAL END-TO-END ASPECT RATIO ARCHITECTURE CERTIFIED**
Owner stamp at ship time: **A** hard-refuse H3 non-16:9 · **B** unify H3 adapters `≈16:9`+`16:9` · **C** refuse unknown on Timeline generate.
Browser smoke: FilmTimelineShell Picture Shape under `minimax-h3-i2v-local` = `["16:9"]` only; LTX shows full set incl 9:16.
**SUPERSEDED for H3 callers later same day** by Director Aspect Unify mission (see IN FLIGHT / stamp change below).
Evidence: `theme_walk/timeline_v2_aspect_ratio/`
Bot: Timeline Aspect Ratio Bot `6609e3a6-961b-4fa0-9f4c-b8e5ae9a5afb`

### 7. MiniMax H3 Director R2V workflow verification (read-only)
**STATUS: DERIVED / CANONICAL DERIVATIVE**
**RECOMMENDATION: KEEP AS-IS (runtime)** + align docs to MiniMaxH3Director.
Production owner: `studio-api/app/film_timeline/h3_director_bridge.py::build_director_workflow` (groups graph).
Exact models: ref2va UNET, Qwen3-VL MiniMax encoder, video+audio VAEs. Co-Director same path. Qwen Omni continuity **alongside**, does not replace Director.
Reference `minimax_h3_director_r2v.json` = simple-mode exemplar, not Film Timeline graph SoT.
Evidence: `C:\Users\bradj\theme_walk\timeline_v2_h3_director_workflow_verify\`
Bot: H3 Director Workflow Verify Bot `3adc497c-4525-4899-8e6c-892be055832c`

---

## Owner stamp change (2026-09-28 evening)

Brad **superseded** Aspect Ratio A-stamp (H3 hard-refuse non-16:9) with:

**STRICT REPAIR — MiniMax H3 Director Aspect-Ratio Capability Unification**

- ONE authoritative MiniMax H3 picture-shape capability owner for standard H3 + Director + Timeline + Render/Continue + Co-Director
- Creative shapes incl **21:9** → legal H3 output dims (never Scene canvas passthrough)
- No Director-specific whitelist / 21:9 one-off / dual stack
- Dim authority **D1**: Comfy `ResolutionSelector(aspect, megapixels, multiple=32)` as Adept formula under `legal_canvas.py`
- COMPLETE only after runtime disposable generation: MiniMax H3 Director — Local + 21:9

---

## IN FLIGHT (as of ~8:30 PM PT 2026-09-28)

### A. H3 Director Aspect Unify (D1) — CLOSED COMPLETE
Bot: H3 Director Aspect Unify Bot `ac296ab0-c967-453c-9b60-2d4b5c6fd21d`
**MINIMAX H3 DIRECTOR ASPECT-RATIO REPAIR — COMPLETE** (2026-09-28 ~8:36 PM PT).
Owner: `legal_canvas.py` · Resolver: `resolve_h3_resolution_selector` (D1). Shapes: 1:1, 4:3, 16:9, 9:16, 21:9. 21:9@0.7MP → 1312×576. Runtime job `46680cb2…` Director+21:9 PASS. 1920×824 still refused. A-stamp superseded for H3 callers.
Evidence: `theme_walk/timeline_v2_h3_director_aspect_unify/`

### B. Timeline Library Remove button (X) — CLOSED COMPLETE
Bot: Timeline Library Remove Bot `6cec4ae6-3967-4f90-9792-c71ad217d8b6`
**LIBRARY REMOVE BUTTON — COMPLETE** (2026-09-28 ~8:34 PM PT).
Ownership: `scenes.director_json.timelineWorkspace.libraryAssetIds` (FilmTimelineShell hydrates from master; FE pinned retired).
Remove: far-right X → `api.directorTimelineSetLibraryAssets` → `PUT …/library-assets` soft-detach; tooltip "Remove reference"; no confirm.
Cert A–H PASS incl refresh. Files: FilmTimelineShell.tsx, film-timeline.css, trackFlags.test.ts.
Evidence: `theme_walk/timeline_library_remove/`

---

## Standing laws / contracts reinforced this window

- Creative canvas size ≠ H3 generation output size
- H3 legal megapixel / ResolutionSelector path; refuse illegal raw Scene dims (e.g. 1920×824)
- Timeline MiniMax path = MiniMax H3 **Director** (not R2V as product path)
- Never restart Comfy unless Brad asks
- Full reports in chat for copy/paste

---

## Active specialist bots (this window)

| Bot | Id | Role |
|-----|----|------|
| Timeline Aspect Ratio Bot | `6609e3a6…` | Aspect thin slice (CLOSED GO; A-stamp superseded for H3 unify) |
| H3 Director Aspect Unify Bot | `ac296ab0…` | D1 capability unify (IN FLIGHT) |
| Timeline Library Remove Bot | `6cec4ae6…` | Library X soft-detach (IN FLIGHT) |
| H3 Director Workflow Verify Bot | `3adc497c…` | R2V workflow verify (CLOSED DERIVED) |

---

## Still open after this note

1. ~~H3 Director Aspect Unify~~ CLOSED COMPLETE.
2. ~~Library Remove~~ CLOSED COMPLETE.
3. Optional: ALIGN DOCS to MiniMaxH3Director (from workflow verify recommendation).
4. Optional polish: clean 14s MP4 for R2V eradication PARTIAL; Continuity `ASSET_REGISTERED=false`.
5. Working tree remains uncommitted on `feat/character-creator-final-closure`.