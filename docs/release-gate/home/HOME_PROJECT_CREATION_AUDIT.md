# HOME_PROJECT_CREATION_AUDIT

Verdict: **GO**

Live Beta target: `http://127.0.0.1:8760/`  
API target: `http://127.0.0.1:8758/`  
Audit date: `2026-08-03`

## Executive Summary

Home project creation now passes the release gate on live Beta:

- the zero-project `/?setupMode=ai_guided&setupSource=workspace_launch` entry now opens the same shared creator-facing drawer instead of silently materializing an `Untitled Project`
- the upper `Project -> Create project` entry, lower empty-state `Create Project` entry, and redirected setup-intent path now converge on one confirmed create flow
- the drawer keeps a sticky `Cancel / Create Project` footer, validates name entry, prevents duplicate submit, and preserves failure/retry on create-request failure
- the create flow performs one confirmed `POST /api/projects` mutation and only enters Setup after an explicit create action
- live Beta audit execution passed and an independent GPT-5.4 verification pass reproduced the repaired zero-project behavior without any silent create request

Certification is now **GO** because the previously blocking Home-originated zero-project `ai_guided` path was repaired and revalidated on live Beta.

## Root Causes Confirmed

1. The upper Home create entry was not creating a project at all. It only scrolled the page instead of opening a real project-creation flow.
2. The lower empty-state create entry had the same problem: it only scrolled instead of invoking creation.
3. The prior drawer path closed optimistically and relied on fragmented create logic, so failure/retry and duplicate-submit handling were not reliable.
4. The first repair pass still used a second `PATCH` after `POST /api/projects`, which created a partial-success duplicate risk. This was removed.
5. The blocking zero-project `/?setupMode=ai_guided...` route and the Co-Director `createProject` action could bypass the shared Home create contract, which allowed an `Untitled Project` path to materialize outside the creator-confirmed drawer flow.

## What Was Repaired

- `Home` now owns one canonical `openCreateProject()` flow and one shared right-side drawer.
- `Project -> Create project`, the Home `+ Create Project` card button, and the empty-state `Create Project` button all open the same drawer.
- The zero-project `/?setupMode=ai_guided&setupSource=workspace_launch` route now opens that same shared drawer and waits for the creator to confirm creation before entering Setup.
- Forced create intents now preserve setup destination through the Home drawer and return cleanly to `/` on cancel.
- Co-Director `createProject` intents now redirect to the shared Home create route instead of calling `api.createProject()` directly.
- Studio launch and Explore cards now prefer the creator's recent visible project instead of arbitrarily taking the first project.
- The drawer keeps a sticky footer and maintains validation, `Creating...`, cancel protection, and retry on create-request failure.
- The create flow now performs a single project create mutation and then refreshes/navigates, instead of creating and then immediately patching project metadata.
- Creator-facing preview text now shows display labels instead of raw internal slugs.
- The drawer preserves intended post-create destination when a creator pivots from the drawer to templates.
- Suggested project names can now flow into the shared drawer when a create intent originates elsewhere.

## Blocking Path Result

- Re-ran on live Beta in the latest `tests/e2e/home/home-project-creation-audit.spec.ts`
- Scenario: zero visible projects, then open `/?setupMode=ai_guided&setupSource=workspace_launch`
- Observed result: Home remains visible, the shared `Create a Project` drawer opens, `No Projects Yet` remains visible underneath, and no `POST /api/projects` request fires until the creator confirms creation
- Evidence:
  - Passing Playwright run: `npm run test:e2e -- tests/e2e/home/home-project-creation-audit.spec.ts`
  - Saved audit artifacts: `docs/release-gate/home/artifacts/home-project-create-events.json`, `docs/release-gate/home/artifacts/home-project-audit-state.json`
  - Independent verification screenshot: `docs/release-gate/home/artifacts/independent-home-beta-check.png`

Because this Home-originated zero-project path now stays inside the creator-confirmed drawer flow and avoids any silent project creation, the blocking defect is resolved.

## Home Control Inventory

| Area | Interactive control(s) | Status in this audit | Notes |
| --- | --- | --- | --- |
| Chrome | `Adept UI Studio` brand link | Inventory only | Returns to Home |
| Chrome | `Project` menu | Audited and repaired | `Create project` now opens shared drawer |
| Chrome | `Setup` menu | Audited | Visible Setup launch now prefers recent project or shared create flow |
| Chrome | `Production` menu | Inventory only | Not modified in this repair |
| Chrome | `Status` menu | Inventory only | Opens status panel |
| Chrome | `Co-Director` button | Audited | Remains live |
| Chrome | `Search Adept UI` | Inventory only | Command/search entry unchanged |
| Co-Director card | Composer textarea | Audited | Remains live |
| Co-Director card | Send button | Audited | Remains live |
| Co-Director card | Prompt starters (`Start a storyboard`, `Generate a shot list`, `Build a character`, `Create a trailer`, `Analyze a script`) | Audited | Remain live |
| Co-Director card | `Enter Co-Director` | Audited | Remains live |
| Launch row | `Open Timeline` | Audited | Now prefers recent visible project when one exists |
| Launch row | `Open MAGI Editor` | Audited | Same recent-project preference |
| Project templates | `Use Template` for `Narrative Film`, `Dialogue Scene`, `Product Film`, `Music Video`, `Animation`, `Explainer`, `Documentary`, `Social Short`, `Cinematic Trailer`, `Talking Avatar` | Audited | Still wired to real creation |
| Projects section | `+ Create Project` card CTA | Repaired | Opens shared drawer |
| Projects section | Template carousel slides | Inventory only | Continue to open selected template |
| Projects section | Carousel previous / next arrows | Inventory only | Continue to rotate cards |
| Projects section | Carousel dots / page indicator | Inventory only | Continue to rotate cards |
| Projects section | `Browse all templates` | Audited | Works with preserved post-create intent from drawer pivot |
| Library | Search input | Inventory only | Unchanged |
| Library | Status chips: `All`, `Active`, `Rendering`, `Complete` | Inventory only | Unchanged |
| Library | View toggle: `Grid`, `List` | Inventory only | Unchanged |
| Library empty state | Lower `Create Project` | Repaired | Opens same shared drawer |
| Library project cards | Card open action | Audited | Library refresh survives reload |
| Library project cards | `Continue` | Inventory only | Unchanged |
| Library project cards | Overflow menu button | Audited | Still opens after create/reload |
| Library project cards | Overflow actions: `Open`, `Rename`, `Duplicate`, `Export`, password actions, `Archive`, `Delete` | Inventory only | Not modified by this repair |
| Explore | `Timeline`, `MAGI Editor`, `Storyboard`, `Spatial Map`, `Image Generation`, `Text to Video`, `Avatar Studio`, `Library` cards | Audited | Now prefer recent visible project when one exists |
| System Status | Status badges / actions inside the strip | Inventory only | Not modified |
| Capability Readiness | Readiness panel interactions | Inventory only | Not modified |

## Live Verification

### Beta runtime

- `npm run beta:restart` succeeded
- Beta runtime reported `READY`
- Confirmed `8760` UI and `8758` API healthy before test execution

### Playwright

1. Expanded Home audit:
   - `tests/e2e/home/home-project-creation-audit.spec.ts`
   - Result: `1 passed (14.4s)`
   - Verified end-to-end behaviors:
     - zero-project `ai_guided` entry opens the shared drawer and does not create a project on load
     - duplicate-submit protection
     - create-request failure + retry
     - template creation
     - library refresh after create
     - project menu visibility
     - Explore / Co-Director / responsive drawer checks

2. Focused independent reviewer pass:
   - GPT-5.4 medium verification agent: `fef1caee-6c09-4a71-8def-9ab0ada55620`
   - Result: **pass**
   - Verified on live Beta with zero visible projects that:
     - final URL stayed on `/?setupMode=ai_guided&setupSource=workspace_launch`
     - Home remained visible
     - the shared drawer was visible with title `Create a Project`
     - `No Projects Yet` remained visible
     - `createPostCount: 0`
     - no redirect into `/project/...` or Setup occurred before explicit create

### Evidence saved

- `docs/release-gate/home/artifacts/home-project-create-events.json`
- `docs/release-gate/home/artifacts/home-project-audit-state.json`
- `docs/release-gate/home/artifacts/home-project-creation-console.log`
- `docs/release-gate/home/artifacts/scenario-a-zero-project-state.png`
- `docs/release-gate/home/artifacts/scenario-j-create-failure.png`
- `docs/release-gate/home/artifacts/independent-home-beta-check.png`

## Reviewer Pass

Seven independent GPT-5.4 reviews were run on the changed code plus live artifacts:

- [Home review 1](3d374ec3-f9a3-40ee-b86e-521746e00509)
- [Home review 2](6b6ab1db-a1fc-43c7-ba60-065e1293d83e)
- [Home review 3](319c726e-fb0a-47c1-9eb9-1e70069c0284)
- [Home review 4](6acfee99-7694-4eca-9aa6-a9a1e74b11fc)
- [Home review 5](773870d4-f77f-47d2-9ea8-3db65d6feb65)
- [Home review 6](e1f4c5c4-8b31-45d6-be84-ffae5ade570e)
- [Home review 7](a8ce2bb2-0b0f-4169-b506-28309e839e35)

Repeated reviewer findings included:

- partial-success duplicate risk after `POST /api/projects`
- lost post-create destination when pivoting from drawer to templates
- creator-facing slug leakage
- `auto` fps mismatch with actual create payload
- unresolved zero-project `ai_guided` path

All repeated findings listed above are repaired in this audit pass, including the previously blocking zero-project `ai_guided` route.

## Cleanup And Project State

- Disposable audit projects created during successful visible-flow runs were deleted
- Additional stray `Untitled Project` audit leftovers from failed exploratory reruns were deleted
- Final visible project count after cleanup: `1`
- Handoff project status:
  - prior handoff ID `b53bf82b-1081-46b9-acf2-d7899fe204e3` remained absent and was not deleted by this audit
  - one fresh creator handoff project was created through the normal Home drawer flow
  - final handoff project: `Manual Beta Handoff` (`a7f665ce-c2d1-4e77-8aa0-b217cc977b56`)
  - final visible count confirmed through `GET /api/projects`: `1`

## Files Changed

- `studio-web/src/pages/Home.tsx`
- `studio-web/src/components/dashboard/NewProductionCard.tsx`
- `studio-web/src/components/generationStudio/HomeCreateProjectDrawer.tsx`
- `studio-web/src/setup/navigation.ts`
- `studio-web/src/codirector/execute.ts`
- `tests/e2e/home/home-project-creation-audit.spec.ts`

## Final Gate

**GO**

Home project creation now meets the shared create-flow expectation on live Beta, including the previously blocking zero-project `ai_guided` entry. The repaired flow was validated by the full Home audit, an independent GPT-5.4 verification pass, and final Beta cleanup that leaves exactly one human handoff project ready for review.
