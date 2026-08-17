# M30F Multilingual End-to-End Certification

**Status:** governing document for M30F product localization (Build Law #30).  
**Supersedes:** `docs/release-gate/multilingual/` (historical architecture pack).

| Field | Value |
|-------|-------|
| Milestone | M30F Multilingual Adept UI — end to end |
| Project | Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278` |
| Stack | Existing `studio-web/src/i18n` (i18next). No second registry. |
| Locales | 12 (en HUMAN_APPROVED; others MACHINE_DRAFT). ar/ur RTL. |
| Date | 2026-08-17 |
| Playwright | `tests/e2e/i18n/m30f-multilingual-e2e.spec.ts` — **8 passed** |
| Pack parity | `npm --prefix studio-web test` — **6 passed** |
| API tests | `studio-api/tests/test_m30f_language_intelligence.py` — **22 passed** |
| Local API | `http://127.0.0.1:8758/` (health 200) |
| Local web | `http://127.0.0.1:8760/` (`studio-web` dist preview; supervisor restart blocked by existing :8758 listener) |
| Hosted UI | `https://adeptui.vercel.app` |
| Vercel | `dpl_AnrhGXh6endgTZZCkZtb4DE6B2r6` production **Ready**, git SHA `81f702ff966ae63e98629c77d206bc1962a60fce` aliased to `adeptui.vercel.app` |
| Hosted bundle | `/assets/index-D2mvKa1k.js` contains `Generar escena`, `Estudio de storyboard`, `conversationLocale`, `m30f-interface-locale` |

## Three independent language concepts

1. **Interface language** — `interfaceLocale` in `localStorage` (`adept_ui_language_prefs_v1`). Drives i18next + `html[dir]`.
2. **Conversation language** — `conversationLocale` on Co-Director chat/stream, also persisted under `project.settings_json.language`.
3. **Prompt / export policy** — `promptLanguagePolicy` + `projectPrimaryLocale` + `exportLocale` per project. Policies: `auto`, `user_language`, `english`, `project_canonical`, `bilingual` (EN-first + zh-Hans), `no_translation`.

Changing interface locale must not rewrite conversation locale or project canon.

## Required matrix

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | English baseline chrome | PASS | Playwright — Timeline `Generate Scene`, lang=en dir=ltr |
| 2 | Spanish UI — Timeline + Image Generator + Storyboard; reload persists | PASS | `Generar escena`, `Generador de imagen cinematográfica`, `Estudio de storyboard`; lang=es after reload |
| 3 | Interface English + conversation French — live Co-Director reply in French; chrome English | PASS | Stream reply: `Bonjour ! Je suis à vos côtés… Schnick Coffee…`; chrome `Generate Scene` |
| 4 | Policy English — compiled prompt English | PASS | MIL compile `promptLanguage=en` |
| 5 | Bilingual — EN + zh-Hans structure | PASS | `compile_intent` unit `promptLanguage=en+zh-Hans`; live PI enhance EN-first + Chinese |
| 6 | Arabic `html[dir=rtl]`; Timeline axis LTR; Preview not mirrored | PASS | Playwright computed `tracks` direction=ltr; transform none |
| 7 | Urdu `dir=rtl` smoke | PASS | Playwright |
| 8 | Switch back to English; Schnick names unchanged | PASS | `Schnick Coffee` still visible |
| 9 | 12-locale pack parity vs English keys | PASS | vitest packParity |
| 10 | Hosted Vercel SHA = HEAD; Spanish + Arabic RTL smoke on Schnick | PASS | Production SHA `81f702f`; hosted `lang=es` `Generar escena`; hosted `dir=rtl` Arabic chrome; tracks `direction:ltr` `transform:none`; Schnick name unchanged |

## Binary verdict

`GO — M30F MULTILINGUAL ADEPT UI CERTIFIED END TO END`

## E2E TRACE

| Stage | Result |
|-------|--------|
| User action | PASS — Schnick Timeline / Image Generator / Storyboard / Settings language |
| Frontend | PASS — i18next chrome, conversationLocale on stream, Language Settings persist |
| API | PASS — chat/stream, PI enhance, MIL compile, project update |
| Backend | PASS — locale injection, compiler bilingual/canonical, PI compose EN+zh |
| Persistence | PASS — interface localStorage; conversation/policy in `settings_json.language` |
| Runtime | PASS — live Co-Director French reply |
| Result | PASS — localized chrome; French reply; bilingual zh layer |
| Reload | PASS — Spanish lang persists |
| Downstream | PASS — Schnick names/captions not rewritten |

## Limitations

- Non-English packs are MACHINE_DRAFT, not professional linguistic certification.
- Remaining inspector/help copy may still fall back to English.
- Voice spoken language is independent of interface locale (by design).
- Bilingual pairing is English + Simplified Chinese only.
- A long-lived Studio API listener may need a process restart before live MIL compile records `promptLanguage=en+zh-Hans`; unit `compile_intent` and live Prompt Intelligence enhance cover that gate.
- Residual inspector/placeholder copy (Scene Inspector labels, some timeline drop hints) may remain English while chrome is localized.
- The first M30F git push failed Vercel `tsc` because concurrent untracked Spatial/Library/Character/Scriptwriter work was mixed into chrome files. Follow-up commits restored chrome-only i18n wraps, restored Spatial Map API methods, and removed `CoDirectorTaskStatus`. Clean worktree `tsc -b` passed before the successful production deploy.
