# Co-Director Pre-Beta Playwright Certification

> Historical pre-closure certification report. The current closure verdict and handoff state now live in `docs/release-gate/codirector-final/CODIRECTOR_PREBETA_CLOSURE.md`, which supersedes this earlier conditional report.

Date: 2026-08-02  
Repo: `C:\AdeptFilmWorks\AIVideoStudio`  
Branch: `feature/ai-guided-setup`  
HEAD: `fa09c99d6395c29461cdec4555055faad116c435`  
Live Beta: UI `http://127.0.0.1:8760/` API `http://127.0.0.1:8758/`

## Verdict

**CONDITIONAL — MANUAL BETA BLOCKED**

The live Dreamweaver certification suite passed again on Beta after an in-scope Project Wiki export repair, and the fresh offline HTML package now includes real project media payloads plus a creator-visible media section. Manual beta is still blocked because the direct composer file-input send path is not proven end-to-end and source inspection shows it is still effectively attachment-note-only, the Dreamweaver plan workspace still did not load as a certified pass, and seven independent reviews agreed the previously reported scope was broader than the suite actually proves.

## Scope

This gate implemented and ran a live-Beta Playwright certification flow against the existing Dreamweaver project:

- suite: `tests/e2e/codirector/codirector-prebeta-certification.spec.ts`
- fixtures: `tests/e2e/fixtures/codirector-prebeta/`
- repaired frontend defects:
  - `studio-web/src/components/CoDirector/CoDirectorProjectContent.tsx`
  - `studio-web/src/components/CoDirector/codirector-cinematic.css`
- target project during certification: `fcd7b4b0-7d36-4757-ac82-a701e6e1a50c` (`The Dreamweaver`)

The suite exercises:

- startup on live Beta
- seeded conversation A-D
- wiki approval, rejection, ambiguity, and clarified follow-up approval
- library-backed media attachment via creator UI
- PDF + HTML export path
- tabs: Wiki, Library, Plans, Bible, Approvals
- persistence after reload
- fullscreen layout envelope
- hard-fail hygiene for `m214/plan`, 5xx Co-Director API failures, and console/tool-registry errors
- accessibility gate on the fullscreen Co-Director shell

## Live Result

Command run:

```text
$env:ADEPT_BETA_TARGET='1'
$env:PLAYWRIGHT_BASE_URL='http://127.0.0.1:8760'
$env:STUDIO_API_BASE='http://127.0.0.1:8758'
$env:STUDIO_API_PORT='8758'
npx playwright test tests/e2e/codirector/codirector-prebeta-certification.spec.ts --project=chromium --reporter=line
```

Passing result:

```text
1 passed (1.3m)
```

Important live notes:

- Beta was restarted after the accessibility fixes so the passing run reflected the repaired UI.
- A follow-up Beta rerun passed after the export repair: `1 passed (1.6m)`.
- The latest passing summary artifact is `docs/release-gate/codirector-final/artifacts/prebeta-playwright/PB-1785713690077-summary.json`.
- The latest HTML export artifact is `docs/release-gate/codirector-final/artifacts/prebeta-playwright/PB-1785713690077-dreamweaver-wiki.zip`.
- The repaired ZIP now contains packaged media files and `data/wiki.json` reports `assets_count: 42`; the generated `index.html` also contains the new `media-section` surface.
- The latest passing summary still records `planWorkspaceLoaded: false`; durable plan draft creation and plan retrieval were proven, but the dedicated Dreamweaver plan workspace still was not.

## Artifacts

Primary artifacts:

- `docs/release-gate/codirector-final/artifacts/prebeta-playwright/PB-1785713690077-summary.json`
- `docs/release-gate/codirector-final/artifacts/prebeta-playwright/PB-1785713690077-dreamweaver-wiki.pdf`
- `docs/release-gate/codirector-final/artifacts/prebeta-playwright/PB-1785713690077-dreamweaver-wiki.zip`
- `docs/release-gate/codirector-final/artifacts/prebeta-playwright/PB-1785713690077-01-fullscreen-shell.png`
- `docs/release-gate/codirector-final/artifacts/prebeta-playwright/PB-1785713690077-02-wiki.png`
- `docs/release-gate/codirector-final/artifacts/prebeta-playwright/PB-1785713690077-03-library.png`
- `docs/release-gate/codirector-final/artifacts/prebeta-playwright/PB-1785713690077-04-plans.png`
- `docs/release-gate/codirector-final/artifacts/prebeta-playwright/PB-1785713690077-05-bible.png`
- `docs/release-gate/codirector-final/artifacts/prebeta-playwright/PB-1785713690077-06-attachments-and-chat.png`
- `docs/release-gate/codirector-final/artifacts/prebeta-playwright/PB-1785713690077-07-wiki-after-approvals.png`
- `docs/release-gate/codirector-final/artifacts/prebeta-playwright/PB-1785713690077-08-reload-persistence.png`

## Repairs Made

1. Invalid ARIA state on content tabs

- Root cause: `role="tab"` buttons in `CoDirectorProjectContent` were using the shared `Button` component's `selected` prop, which injected `aria-pressed`.
- Fix: keep visual selected styling via `className="is-selected"` while relying on `aria-selected` for the tab role.

2. Insufficient contrast for cinematic shell eyebrow labels

- Root cause: the global `.eyebrow` color inherited a darker accent tone that did not meet contrast on cinematic Co-Director content cards.
- Fix: scope `.codirector-shell.cinematic .eyebrow` to the brighter Co-Director text-muted palette.

3. Offline HTML export now packages and surfaces project media

- Root cause: `studio-api/app/codirector/wiki_export.py` filtered export media to `production_approval == "approved"` only, so the certification fixtures never entered the package, and the offline HTML page ignored `data.assets` entirely even when media existed.
- Fix: include supported non-rejected project media in the export package, warn when a referenced asset is unapproved, and render a `Project Media` section in the offline HTML output.
- Regression proof: `studio-api/tests/test_codirector_runtime_repair.py -k export` now passes, and the live Beta rerun produced `PB-1785713690077-dreamweaver-wiki.zip` with packaged image/audio entries plus `assets_count: 42` in `wiki.json`.

## Blocking Findings

1. Direct composer file-input send path is not proven and source inspection shows it is still not end-to-end wired

- The certification uses library-backed asset attachment through the creator UI and proves attachment-note persistence in chat.
- It does **not** prove that the composer's direct binary file-input path survives the actual send flow end-to-end.
- Source inspection is worse than the original report implied: `studio-web/src/components/CoDirector/CoDirectorSession.tsx` converts attachments into a `[Attached: ...]` note, and `studio-api/app/routers/codirector.py` only accepts chat `messages` with `role` and `content`. No live evidence or code path was found that uploads file-input blobs into Co-Director chat on send.

2. Dedicated Dreamweaver plan workspace still did not load as a proven pass

- The passing summary explicitly records `planWorkspaceLoaded: false`.
- Durable plan creation and retrieval succeeded, so the plan surface is partially covered, but the dedicated workspace render on Dreamweaver is still a documented limitation.

3. The certified scope is broader than the suite actually proves

- The suite materially covers a routed Dreamweaver happy path: wiki rendering, library retrieval, approval persistence, export invocation, reload persistence, and absence of a few watched hard failures.
- Seven focused independent reviews agreed that this evidence does **not** fully certify creator-driven project selection, grounded wiki intelligence, true proposal-correction lineage, Production/Jobs surfaces, or exercised failure-recovery behavior.
- Several reviewers judged the original `CONDITIONAL` verdict directionally honest but too lenient in rationale; no reviewer recommended `READY FOR MANUAL BETA`.

## Independent Review Coordination

Seven focused independent reviews were run across:

- framework/session lifecycle
- wiki intelligence/correction
- media/library/approval/export
- plans/bible/production/jobs
- accessibility/layout
- console/network/failure recovery
- final evidence/verdict

Reviewer consensus after the follow-up repair was aligned:

- framework/session lifecycle: route-bound reload persistence is real, but lifecycle/project-selection confidence is overstated
- wiki intelligence/correction: suite proves approval persistence, not grounded intelligence or real revision lineage
- media/library/export: export gap was repaired on live Beta, but direct file-input attach/send remains effectively unwired
- plans/bible/production/jobs: plan retrieval is real, plan workspace is still unproven, and Production/Jobs were not actually exercised by this suite
- accessibility/layout: cited repairs are narrowly safe, but the evidence remains desktop-only and does not fully certify tab accessibility semantics
- console/network/failure recovery: the run shows absence of a few watched failures, not exercised recovery behavior
- final evidence/verdict: partial live workflow coverage is real, but the conservative verdict should remain beta-blocking

Given the live export repair plus the unanimous reviewer agreement that important scope and wiring gaps remain, the conservative final verdict remains **CONDITIONAL — MANUAL BETA BLOCKED**.

## Environment State

Current live state after certification:

- exactly one project remains: `The Dreamweaver`
- project id: `fcd7b4b0-7d36-4757-ac82-a701e6e1a50c`
- certification residue remains on that project (PB-tagged assets, plans, proposal history, and repaired export artifacts from `PB-1785713690077`)

Because the verdict is not READY:

- the requested READY-only cleanup was **not** performed
- no brand-new empty handoff project was created
- the environment was **not** reset to `Environment reset complete. Ready for manual beta testing.`

## Ready Path

To upgrade this gate from conditional to ready, the next pass must prove all of the following on live Beta:

1. the direct composer file-input send path is exercised end-to-end with real binary attachment delivery, or the visible control is narrowed/reworked so the certified claim is honest
2. either the dedicated Dreamweaver plan workspace loads successfully, or the certification scope/report is narrowed so that no reader could confuse retrieval coverage with workspace certification
3. the report and suite are aligned to the surfaces actually exercised (especially Production/Jobs, wiki intelligence, and failure recovery)
4. after the next re-run, the environment is cleaned and replaced with one brand-new empty project for manual handoff
