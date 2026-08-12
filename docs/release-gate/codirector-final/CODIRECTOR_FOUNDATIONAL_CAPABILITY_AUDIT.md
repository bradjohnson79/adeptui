# Co-Director Foundational Capability Audit

**Branch:** `feature/ai-guided-setup`  
**Starting SHA:** `fa09c99d6395c29461cdec4555055faad116c435`  
**Audit date:** 2026-08-03  
**Beta URL:** http://127.0.0.1:8760/  
**API health:** http://127.0.0.1:8758/api/health  
**Authoritative matrix:** [`CODIRECTOR_CAPABILITY_MATRIX.md`](./CODIRECTOR_CAPABILITY_MATRIX.md)

## Foundational contract

> **Receive → perceive → understand → retrieve → assimilate → decide → respond → inquire → act → remember.**

This audit certified Layer 1–2 UX honesty and receiving basics first. It did **not** begin by swapping models.

## Scope completed

| Layer | Result |
|---|---|
| Receiving (text, long text, Library, mic) | Repaired / certified with live Playwright |
| Perception honesty (attachments, vision unavailable) | Metadata + honesty blocks; no fake sight |
| Assimilation (Wiki residue) | Questions/commands filtered from Wiki |
| Conversation (canned Next defect) | Synthesis filler removed |
| Library browser | Large modal with All / Images / Video / Audio / Documents |
| Viewport lock | Framed ~90vw workspace; page scroll locked |
| Inquiry intelligence | Still weak — blocker for full GO |
| True media cognition | Not implemented in main chat |

## Repairs

1. **Library browser** — `CoDirectorAssetPicker.tsx` + `codirector-library-browser.css`  
   Large portal modal, sticky header/footer, search, filters, multi-select, creator empty states, testids.
2. **Viewport lock** — `CoDirectorPage.tsx`, `CoDirectorFullScreen.tsx`, fullscreen CSS  
   `app-shell-fixed`; internal panes only scroll; ~5% framing.
3. **Synthesis** — `intelligence/synthesis.py`  
   Removed canned “Continue with the recommended direction” and invented storyboard packages.
4. **Wiki residue** — `wiki.py`  
   Questions, greetings, short commands excluded from Wiki candidates.
5. **STT** — `useSpeechToText.ts`, `CoDirectorComposer.tsx`  
   Permission/listening/processing/denied/unavailable/cancel states; editable transcript; no auto-send; audio accept on file input.
6. **Context enrichment** — `context_enrichment.py`, chat body `attachment_ids`, intelligence `ContextCompiler`  
   Wiki snapshot + honest attachment metadata for chat **and** intelligence paths.

## Evidence

### Unit / semantic

```text
studio-api pytest:
  tests/test_codirector_wiki_residue.py
  tests/test_codirector_attachment_context.py
  tests/test_codirector_intelligence.py::test_synthesis_conflict_priority_and_compression
→ 6 passed
```

### Live Playwright (Beta)

```text
ADEPT_BETA_TARGET=1
tests/e2e/codirector/codirector-foundational-capabilities.spec.ts
tests/e2e/codirector/codirector-library-browser.spec.ts
tests/e2e/codirector/codirector-media-cognition.spec.ts
tests/e2e/codirector/codirector-microphone-stt.spec.ts
→ 7 passed (~3.0m)
```

Disposable run-scoped projects only. Manual Beta Handoff project not contaminated.

### Beta verification

- Restarted via `Restart-AdeptUI-Beta.ps1`
- READY at http://127.0.0.1:8760/
- Manual review: open Co-Director with a project → Library picker → mic (browser SpeechRecognition) → attach image → confirm framed workspace without page scroll

## Subagent ledger

| Subagent | Role | Scope | Files | Result | Evidence | Blockers |
|---|---|---|---|---|---|---|
| Wave1 explore (arch) | Discovery | Receive→remember map | service, synthesis, session, wiki | PARTIAL inventory | Matrix draft inputs | Retrieve/inquiry/vision gaps |
| Wave1 explore (media) | Discovery | Library/STT/vision/layout | AssetPicker, STT, vision, CSS | PARTIAL inventory | Root-cause list | Small picker; no ML vision |
| [Library UX](ccbde8dc-3d41-49bf-b3bb-ff9594bc6ecf) | Implement | Large Library modal | AssetPicker + CSS | PASS | Playwright library | Secondary taxonomy filters deferred |
| [Viewport](53b18674-f559-4741-a7f9-a919d466acb6) | Implement | Viewport lock | Page/FullScreen/CSS | PASS | Playwright framing | Ultrawide screenshot matrix incomplete |
| [Tests](9de94a56-4e9a-42a5-a4a5-e4a9c698c20a) | Author | Playwright suites | 4 specs + helper | PASS | 7/7 Beta | webServer EADDRINUSE noise |
| [Wave3 review](60b8a240-c080-42f2-bb34-56f1d27e7bc4) | Independent | 8 areas | code inspection | NO-GO lean | Attach flatten / vision / retrieve | Pre-enrichment wiring |
| [Wave4 verifier](0217cacd-3110-44e7-bf48-c47a91ae4023) | Independent | Claim check | repaired paths | NO-GO lean | Inquiry + multimodal | Did not re-run tests |

Overlaps prevented: Library vs Viewport vs Tests owned separate files; primary owned synthesis/wiki/STT/enrichment/report.

## Remaining limitations (honest)

- No true ML vision/audio/video perception in the main Co-Director chat turn.
- Inquiry policy does not ask one useful stage-aware question by default.
- Attachments still include a text `[Attached: …]` marker in addition to structured ids.
- Knowledge-state lifecycle (rejected / superseded / reference-only) incomplete.
- Performance latency instrumentation not certified in this pass.
- STT depends on browser SpeechRecognition (no backend STT).

## Manual review path

1. Open http://127.0.0.1:8760/
2. Open or create a disposable project → Co-Director
3. Confirm workspace is framed (~5% margins) and the page does not scroll
4. Open Library → large modal, All selected, Images/Video/Audio filters
5. Mic → listen → stop → edit transcript → send (no auto-send)
6. Attach an image as temporary reference → confirm no absolute path leak
7. Ask “What should we do next?” → confirm it does not land in Wiki as canon

## Final verdict

**CONDITIONAL GO**

Foundation receiving, Library UX, viewport lock, Wiki residue safety, synthesis filler removal, STT honesty path, attachment metadata honesty, and live Playwright evidence are certified.

Full **GO** remains blocked until intelligent inquiry, true media cognition (or a permanently explicit unavailable UX that creators always see), and first-class multimodal chat (without text-only attachment markers as the sole perception channel) are repaired and re-certified.
