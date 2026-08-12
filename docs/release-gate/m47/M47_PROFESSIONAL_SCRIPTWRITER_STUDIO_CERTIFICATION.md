# M4.7 — Professional Scriptwriter Studio Certification

| Field | Value |
| --- | --- |
| Milestone | **M4.7** |
| Product | Adept UI Studio |
| Feature | Professional Scriptwriter Studio |
| Integration | Co-Director / Production Bible / Scenes / Timeline / Prompt Intelligence |
| Branch | `feature/m4-7-professional-scriptwriter-studio` |
| Feature docs | `docs/scriptwriter/m4-7-professional-scriptwriter-studio/` |
| Playwright | `tests/e2e/m47/m47-professional-scriptwriter-studio.spec.ts` |
| Schema versions | `script-document@1`, `script-revision@1`, `script-transaction@1` |
| Base SHA (branch point) | `f758744168ec93f559d7fa0d9098ce47c39fe3ff` |
| Certification date | 2026-08-01 |

## Verdict: CONDITIONAL GO

Foundation production path is implemented and covered by unit/integration tests. Remaining gaps are honestly limited to estimated pagination, incomplete FDX, and no multi-user collaboration — allowed CONDITIONAL GO items per M4.7 plan.

## GO path evidence

| Step | Status | Evidence |
| --- | --- | --- |
| Structured screenplay editing | PASS | TipTap `ScriptwriterStudio` + element model; `studio-web/src/components/scriptwriter/` |
| Reliable autosave / recovery | PASS | `/autosave` + recovery buffer on conflict; save-state UI |
| Co-Director proposal review | PASS | Closed `script.*` tools; UI proposal accept → `apply_codirector_proposal` transaction |
| Production Bible proposal | PASS | `/bible/propose` + `script.sync_production_bible` create `entity_create` proposals only |
| Scene linkage | PASS | `/scenes/link` + sceneSync statuses |
| Timeline preparation proposal | PASS | `/timeline/prepare` + `/timeline/apply-metadata` (`apply_timeline_prep_metadata`); viz prompts side-channel |
| PDF and Fountain output | PASS | Fountain round-trip; PDF via reportlab or labeled fallback |
| Reload / migration validation | PASS | `get_or_create_document` migrates legacy segments conservatively; studio reload returns same doc |

Plus: transaction-backed undo for multi-element ops; revision create/compare; unit suite green (`studio-api/tests/test_m47_scriptwriter_studio.py` — 6 passed).

## Feature matrix

| Capability | Status | Notes |
| --- | --- | --- |
| ScriptDocument / elements | Shipped | `script_documents_v2` + JSON elements |
| ScriptTransaction layer | Shipped | Named kinds incl. insert/delete/move/apply_codirector_proposal/restore/import/convert/timeline |
| TipTap screenplay editor | Shipped | Enter/Tab + Mod-1..6; Focus/Dialogue/Production modes |
| Navigator / Inspector | Shipped | Scenes, revisions, continuity, Co-Director panel |
| Outline / Cards / Beats / Compare | Shipped | Bound to same document |
| Search/replace + command palette | Shipped | Transactional replace; Ctrl/Cmd+K |
| Co-Director `activeDocumentId` | Shipped | Bound from Scriptwriter Studio |
| Co-Director `script.*` tools | Shipped | inspect/scene_context/character_context/analyze_*/suggest/generate_*/propose_*/convert/sync/prepare |
| Bible proposals | Shipped | Never silent canon |
| Scene sync | Shipped | Linked / sync metadata |
| Timeline prep | Shipped | Proposal + metadata only; no auto clips |
| PI visualization side-channel | Shipped | `visualizationPrompt` on timeline prep only |
| Fountain I/O | Shipped | Import/export |
| PDF export | Shipped | Estimated pagination labeled |
| FDX | Limited | Not certified — Known Limitation |
| Exact print pagination | Limited | Estimated only — Known Limitation |
| Multi-user collaboration | Absent | Known Limitation |

## Test evidence

### Unit / integration

```text
studio-api/tests/test_m47_scriptwriter_studio.py
6 passed
```

Coverage: registry bindings, bootstrap/insert/undo/autosave, Fountain/PDF, proposal/revision/timeline/bible, transitions/stats, search-replace.

### Playwright

Suite: `tests/e2e/m47/m47-professional-scriptwriter-studio.spec.ts`

```text
2 passed (chromium)
```

- Full production path (API + studio UI shell + writer alias)
- Transaction undo + revision compare

Run:

```bash
npx playwright test tests/e2e/m47/m47-professional-scriptwriter-studio.spec.ts --project=chromium
```

## Known limitations

1. **Pagination is estimated** — status bar and PDF path label estimated page counts; not certified as production page-accurate.
2. **FDX import/export incomplete** — Fountain / plain / Adept JSON / PDF first; FDX deferred until real-file round-trip validates.
3. **No multi-user collaboration** — single-creator autosave + revision conflict recovery only.
4. **Storyboard panels** remain on legacy `segment_id` during transition; Storyboard workspace still available via `workspace=script` / `storyboard`.
5. **Manual UX checklist** at 1366×768–2560×1440 requires human review (not auto-passed).

## Architecture notes

- Creator edits autosave directly through transactions.
- Co-Director / Bible / Scene / Timeline mutators are proposal-gated; apply paths commit named `ScriptTransaction` records.
- Prompt Intelligence visualization prompts are generated as Timeline prep side-channel fields and are never injected into screenplay action by default.

## Binary verdict summary

**CONDITIONAL GO** — Professional Scriptwriter foundation path is complete and evidenced. Exact pagination, FDX, and multi-user collaboration remain documented limitations and do not block the M4.7 foundation.
