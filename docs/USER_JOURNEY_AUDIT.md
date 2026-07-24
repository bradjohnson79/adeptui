# First-Time Filmmaker User Journey Audit

**Journey:** Launch → Create Project → Create Scene → Story → Profiles → Scene Sheet → Director → Generate → Audio → Editor → Export  
**Authority:** `docs/ADEPT_UI_SYSTEM_ARCHITECTURE.md`  
**Scope:** Current-state documentation and bounded recommendations only; no UI redesign is proposed.  
**Evidence:** Static inspection of the current web routes, project shell, dashboard, and named workspaces on 2026-07-23. Runtime click-through is pending because the terminal/runtime runner is unavailable.

## How to read this audit

- “Clicks” is the minimum obvious pointer-action path after the relevant page has loaded. Text entry, selecting a file, and optional settings are called out separately.
- Counts are source-derived estimates, not executed usability measurements.
- “Shortcut” means an existing direct handoff that can reduce navigation.
- Recommendations favor labels, links, context preservation, enabled-state honesty, and removal of duplicate entry. They do not change the approved target layout.

## Journey summary

The first-time path is possible through Editor assembly, but it is not presented as one continuous production flow. The main workspace menu has 18 choices across Generation Modes, Production, Assets, and Planning. A new filmmaker must infer ordering, find scene creation inside Director, translate current names to the intended product language, and re-enter scene/profile intent across disconnected stores. Audio and final Editor export are not complete.

The largest current blockers are:

1. **Create Scene is hidden in Director.**
2. **Story is not reliably bound to the selected Scene.**
3. **Profiles cannot be explicitly attached to the project/scene from the Profiles workspace.**
4. **Scene Master Sheet ingredients duplicate Profile data.**
5. **Generate is fragmented across several workspaces and labels.**
6. **Audio is a stated stub.**
7. **Editor has assembly and clip preview, but no final render/export action.**
8. **Home Explore deep links write `?tab=...`, but the project shell does not consume it.**

## 1. Launch

### Current path and clicks

- Launch the API and web app externally, then open `/`.
- The Home page shows a cinematic hero, New Production card, templates, Projects, Explore Adept UI, system status, and Co-Director.
- From the hero, **Create** scrolls to New Production: 1 click.
- **Open Existing** scrolls to Projects: 1 click.

### Friction inventory

- **Navigation:** The initial page has multiple valid starts, but no explicit ordered first-film path.
- **Duplication:** New Production, templates, an empty-state Create Project action, Explore cards, and Co-Director can all initiate work.
- **Hidden behavior:** An Explore card silently creates an `Untitled Project` when none exists.
- **Dead ends:** Explore intends to open a chosen workspace, but the `?tab=` query is ignored after project navigation.
- **Repeated entry:** The silently created project bypasses production-type/default selection, so settings may need to be entered later.
- **Shortcuts:** Hero anchors, templates, recent project cards, and Co-Director are useful entry shortcuts.
- **Terminology:** “Production,” “Project,” “command center,” and “workspace” all describe adjacent concepts before the user has learned the model.

### Recommendation without redesign

- Add one sentence of ordered guidance near New Production: “Create a project, add a scene, then begin in Story.”
- Make Explore require project choice/confirmation when no project exists rather than silently creating one.
- Consume the existing workspace query parameter or stop presenting Explore as a direct workspace link until it works.
- Use “Project” for the saved object and “production” only as descriptive filmmaking language.

## 2. Create Project

### Current path and clicks

- Direct path from the visible New Production card: enter project name, optionally choose a production type, then **Create Project**: 1 required action after entry.
- Hero path: **Create** → **Create Project**: 2 clicks after entry.
- Template path: **Use Template**: 1 click.
- Optional defaults add **Show optional defaults** plus aspect, resolution, FPS, and storyboard-style selections.
- Successful creation opens `/project/:id` at Project Home.

### Friction inventory

- **Navigation:** Project creation correctly lands on Project Home, but Project Home emphasizes “Continue Production,” “View Timeline,” and workspace cards rather than the next required object: Scene.
- **Duplication:** Project settings can be entered here or revisited in Project Settings.
- **Hidden behavior:** A template uses its title as the new project name; Explore creates a project with different defaults.
- **Dead ends:** None in the direct creation action.
- **Repeated entry:** Starting through Explore may require renaming and entering defaults later.
- **Shortcuts:** Templates provide a low-click start.
- **Terminology:** The card says “New production” but the button and stored object say “Project.”

### Recommendation without redesign

- After creation, show a contextual “Next: Add your first scene” action using the existing Project Home card/action patterns.
- Preserve the current template shortcut, but prompt for or visibly confirm the project name.
- Make all creation entry points use the same defaults and confirmation path.

## 3. Create Scene

### Current path and clicks

- The only clear scene-creation control found is **Add scene** in the compact `Timeline` used by the Director shell.
- From Project Home, the likely path is **View Timeline** → **Add scene**: 2 clicks.
- From another workspace, the path is hamburger → **Director** → **Add scene**: 3 clicks.
- The scene is created immediately as `Scene N`, using the project’s default engine, 5-second duration, and a blank prompt.

### Friction inventory

- **Navigation:** Scene creation is not surfaced on Project Home, Story, or a scene list outside Director.
- **Hidden behavior:** A core object is created from a control inside a specialized downstream workspace.
- **Duplication:** Storyboard → Director can create Director scenes, potentially adding scenes through a second path.
- **Dead ends:** Scene Sheet says “Add a scene first” but gives no link to the place where that can be done.
- **Repeated entry:** The auto-created scene name, duration, and prompt may need correction in Director; Story maintains separate segments.
- **Shortcuts:** **View Timeline** is the shortest current route from Project Home, though its label does not say it creates/scopes scenes.
- **Terminology:** “Timeline” can mean the scene strip, Director Prompt Timeline, Generate Timeline, or Editor assembly.

### Recommendation without redesign

- Add an **Add Scene** action to Project Home and every no-scene empty state, calling the existing scene API.
- After creation, keep the new scene selected and offer **Open Story** as the next action.
- Label the compact control “Scenes” consistently; reserve “Timeline” for Director/Editor time-based work.
- Prevent storyboard handoff from silently creating duplicate scenes when an intended scene already exists.

## 4. Story

### Current path and clicks

- Hamburger → **Script / Storyboard**: 2 clicks.
- Create content with **+ Segment**, edit on blur, optionally **+ Panel**, **Generate Storyboard**, **Approve**, then **Send to Director**.
- Existing view shortcuts are Split, Script, Storyboard, and Shot List.

### Friction inventory

- **Navigation:** Story is under Planning, while the approved journey calls it the first creative workspace after Scene.
- **Duplication:** A separate top-level Shot List entry opens another view of the same component.
- **Hidden behavior:** Segment `scene_id` exists but the UI does not reliably bind work to the selected project Scene.
- **Dead ends:** Story can send to Director, but it does not provide a clear next step to Profiles or Scene Sheet.
- **Repeated entry:** Speaker, character, location, and action text are entered as strings rather than selected from Profiles/Scene.
- **Shortcuts:** **Send to Director** and **Approved only → Director** are valuable direct handoffs.
- **Terminology:** The current label “Script / Storyboard” describes tools; the governing plan names the unified workspace “Story.”

### Recommendation without redesign

- Display the active Scene prominently and require explicit scene binding before Director handoff.
- Keep Shot List as an internal Story view and treat the top-level entry as a compatibility shortcut.
- Add existing Profile pickers for speaker/character/location where IDs are available, while preserving free text.
- Add lightweight next-step links to Profiles and Scene Sheet after story content exists.

## 5. Profiles

### Current path and clicks

- Hamburger → **Profiles**: 2 clicks.
- Select a kind if needed, enter Name/Tag/Category/Description, then **Create**.
- Character profiles can shortcut to **Open in Avatar Studio**.

### Friction inventory

- **Navigation:** Profiles is under Assets, not connected in sequence from Story.
- **Duplication:** Character/environment/prop identity is also represented in Story strings, Master Sheet ingredients, Spatial data, and Avatar sessions.
- **Hidden behavior:** Profiles are a cross-project global library; project/scene ownership is not visible.
- **Dead ends:** There is no explicit **Attach to Scene** action or next step to Scene Sheet.
- **Repeated entry:** Names, tags, and descriptions must be recreated or manually mirrored in downstream workspaces.
- **Shortcuts:** Character → Avatar is direct, but it diverts from the approved first-film path.
- **Terminology:** The “Scenes” profile kind can be confused with the core Scene object; “Production DNA” is evocative but not a data-scope explanation.

### Recommendation without redesign

- Show profile scope (“Global” or project-linked) and usage.
- Add an explicit attach-to-active-scene action when the existing data model can safely support it.
- Rename the profile kind label “Scenes” to “Environments” in UI copy when compatibility permits.
- Reuse selected Profile IDs in Story, Scene Sheet, Director, and Generate instead of copying fields.

## 6. Scene Sheet

### Current path and clicks

- Hamburger → **Scene Master Sheet**: 2 clicks.
- For a selected scene: add ingredient types, select each tile, edit its inspector values, **Build Prompt**, **Validate**, **Save**, and optionally **Set Scene Authority**.
- **Spatial** opens the separate Spatial workspace.

### Friction inventory

- **Navigation:** The current workspace is available, but the active scene is inherited indirectly from selection elsewhere.
- **Duplication:** Ingredients repeat character, wardrobe, environment, camera, and lighting data rather than attaching unified Profiles.
- **Hidden behavior:** “Scene Authority” controls prompt authority but is not explained as the handoff contract to Director/Generate.
- **Dead ends:** **Export** and **Generate** are visible but disabled. The no-scene message does not link to Add Scene.
- **Repeated entry:** Profile descriptions and production intent must be retyped as ingredient fields and prompts.
- **Shortcuts:** **Build Prompt** reduces manual prompt composition; **Spatial** is a direct but legacy detour.
- **Terminology:** “Scene Master Sheet,” “Whole-Scene Package,” “Visual Sheet,” and target “Scene Sheet” compete.

### Recommendation without redesign

- Use “Scene Sheet” as the primary label and retain “formerly Scene Master Sheet” only as transitional help text.
- Show the active Scene selector/identity and link no-scene state to Add Scene.
- Attach existing Profiles as ingredients where possible; distinguish linked values from scene-specific overrides.
- Remove disabled controls from the action emphasis or label them “Not available” with an explanation.
- Explain “Set Scene Authority” in plain language: downstream prompts use this approved sheet.

## 7. Director

### Current path and clicks

- Hamburger → **Director**: 2 clicks.
- Story can shortcut directly through **Send to Director**.
- Select a Scene, work in Director Monitor/Tracks and nested Timeline/Prompt/Lip Sync/Settings tabs, then save/package/approve and **Send to Editor**.

### Friction inventory

- **Navigation:** Director is both where scenes are created and where downstream timed prompting happens.
- **Duplication:** Director JSON, Director Sequences, and Generate Timeline overlap as planning/timeline records.
- **Hidden behavior:** Editor-to-Director focus hints are written to session storage but are not reliably consumed for exact sequence focus.
- **Dead ends:** Some handoffs arrive at Director without selecting the intended scene/sequence.
- **Repeated entry:** Prompt, duration, model, references, and audio intent can repeat Story, Scene Sheet, and Generate inputs.
- **Shortcuts:** Story → Director, Director → Editor, and Editor → Open in Director are strong intended shortcuts.
- **Terminology:** “Director Timeline,” “Prompt Timeline,” “Generate Timeline,” and nested “Timeline” are difficult to distinguish.

### Recommendation without redesign

- Keep Director’s role in copy: “time and direct an approved shot plan.”
- Preserve active Scene, Story panel, Scene Sheet, and Profile context on entry.
- Consume exact scene/sequence handoff keys before showing the default selection.
- Reserve “Director Prompt Timeline” for this workspace and rename helper labels that imply a second product timeline.

## 8. Generate

### Current path and clicks

- There is no single current Generate workspace.
- Hamburger requires 2 clicks to choose one of **ImageGen**, **1 Frame**, **Txt2Vid**, **3 Frame**, or **Avatar**.
- A separate Planning entry, **Generate Timeline**, is also 2 clicks away.
- Director itself can queue generation-related work.

### Friction inventory

- **Navigation:** Users must choose implementation mode before they understand model/workflow differences.
- **Duplication:** Prompt, references, settings, job display, and outputs are spread across at least six surfaces.
- **Hidden behavior:** Existing Python builders, not root workflow JSON descriptions, are runtime authority.
- **Dead ends:** Scene Sheet’s Generate button is disabled; Generate Timeline and generation modes do not form one obvious sequence.
- **Repeated entry:** Scene/profile/reference/prompt/model settings are reselected across modes.
- **Shortcuts:** Project Home links directly to ImageGen; mode-specific workspaces reduce clicks for experienced users.
- **Terminology:** “Generate,” “Generate Timeline,” “ImageGen,” “Txt2Vid,” “1 Frame,” and “3 Frame” mix task, implementation, and workflow names.

### Recommendation without redesign

- Until unified Generate is implemented, add consistent subtitles identifying each mode and its required inputs.
- Carry active Scene, Profiles, Scene Sheet prompt, references, and project defaults into every generation entry.
- Use the approved Workflow Registry to display stable workflow names and availability without changing builders.
- Use the Generation Provider Layer to normalize capabilities/errors while preserving current execution.
- Mark Generate Timeline as planning/orchestration rather than another media-generation mode.

## 9. Audio

### Current path and clicks

- Hamburger → **Audio Studio**: 2 clicks.
- **Upload audio** opens a file picker; each asset can be sent to music, SFX, ambience, or dialogue tracks.
- **Open Editor** and **Open Director (Audio Intent)** are direct shortcuts.

### Friction inventory

- **Navigation:** Audio is correctly grouped with production finishers.
- **Duplication:** Audio intent lives in Director, assets live in Library, and track placement is duplicated by direct Editor JSON updates.
- **Hidden behavior:** Added clips default to five seconds and append after existing clips.
- **Dead ends:** The workspace explicitly states that generation lands later; no Dialogue/Music/SFX/Ambience generation flow exists.
- **Repeated entry:** Track type is chosen per asset; timing and intent may need re-entry in Editor.
- **Shortcuts:** Direct Add to Editor and Open Director/Open Editor controls are useful.
- **Terminology:** “Audio Studio” implies a deeper creation/mixing tool than the current upload-and-handoff stub.

### Recommendation without redesign

- Label the current scope “Audio — Import and Handoff” until generation is available.
- Show the default five-second duration before insertion and let the user confirm the target track.
- Preserve Director audio-intent labels when creating placeholders/assets.
- Do not claim Audio phase completion based on the current stub.

## 10. Editor

### Current path and clicks

- Hamburger → **Editor**: 2 clicks.
- Director can shortcut with **Send to Editor**.
- In Editor, select a Director source and **Add to Video 1**, preview individual source media, select clips, and edit start/length/trim start.
- Audio can be added from Audio Studio; clips can **Open in Director** or **Generate Replacement**.

### Friction inventory

- **Navigation:** Director handoff is direct, but returning to the exact Director sequence is unreliable.
- **Duplication:** Editor assembly JSON overlaps with Director sequences and other timeline stores.
- **Hidden behavior:** “Editor Preview” displays the active clip source, not a rendered full assembly preview.
- **Dead ends:** There is no visible Editor preview-render or final-render/export action.
- **Repeated entry:** Timing is adjusted per clip; regenerated media may require manual version decisions.
- **Shortcuts:** Add source, Open in Director, Generate Replacement, and non-destructive Replace/Alternate/Compare/Ignore are valuable.
- **Terminology:** “Rough stitch preview” can imply an assembled playback that does not yet exist.

### Recommendation without redesign

- Relabel the current viewer “Selected Clip Preview” until whole-assembly preview exists.
- Keep source lineage visible and consume exact Director handoff context.
- Make incomplete render/export capability explicit rather than implying a finished NLE.
- Preserve the existing non-destructive version decision controls.

## 11. Export

### Current path and clicks

- No complete in-project Editor export path was found.
- A project card on Home exposes an **Export** menu action that queues the existing project export job.
- Scene Master Sheet also displays **Export**, but the button is disabled.

### Friction inventory

- **Navigation:** The final journey step requires leaving the project to find a project-card export action.
- **Duplication:** “Export” appears for project packaging and Scene Master Sheet, while the target journey means final film render/export.
- **Hidden behavior:** The Home action reports only “Export job queued”; its output and relationship to Editor assembly are not explained.
- **Dead ends:** Editor has no final export; Scene Sheet Export is disabled.
- **Repeated entry:** A user may need to infer export settings outside Editor or use legacy render paths.
- **Shortcuts:** Home project-card export is useful for its existing purpose, but it is not an Editor final-film shortcut.
- **Terminology:** “Project Export,” “Editor Render,” “Final Export,” and sheet export must be distinguished.

### Recommendation without redesign

- Rename the current Home action to **Export Project Package** if that is its actual output.
- Do not present final film export as available until Editor can queue a validated render job and reveal the resulting Asset.
- When implemented, keep the final action in Editor and show job progress, output location, and Library lineage.
- Hide or clearly mark unavailable sheet export rather than using the same active-sounding label.

## Cross-journey findings

### Click and navigation burden

- Moving between most stages costs hamburger + workspace selection (2 clicks) because the URL does not encode workspace state.
- The hamburger presents 18 workspace choices and does not express the approved sequence.
- Existing direct handoffs are uneven: Story→Director, Director→Editor, and Audio→Editor exist; Project→Scene, Story→Profiles, Profiles→Scene Sheet, Scene Sheet→Director/Generate, and Editor→Export are absent or incomplete.

### Duplication and repeated entry

- Scene intent is split among core Scene, Story segments, Master Sheet, Spatial, Director, and generation panels.
- Character/environment/prop identity is split among Profiles, Story strings, Master Sheet ingredients, Spatial records, and Avatar sessions.
- Prompt/model/reference settings recur across Storyboard, Master Sheet, Director, ImageGen, Txt2Vid, Frames, and Avatar.
- Job progress appears inside several generating workspaces rather than one recoverable Jobs destination.

### Hidden state

- Active workspace is React/localStorage state rather than a route.
- Handoff context uses query strings and session storage inconsistently.
- Profile scope is global but not made prominent.
- The active Scene is not a shared, visibly authoritative context across all workspaces.

### Dead-end controls or paths

- Home Explore workspace query is ignored.
- Scene Sheet no-scene state cannot create/navigate to scene creation.
- Scene Sheet Generate and Export are disabled.
- Audio generation is absent.
- Editor whole-assembly preview/final export is absent.
- Jobs cards route to Director because there is no Jobs workspace.

### Existing shortcuts worth preserving

- Project templates.
- Continue Production and workspace cards.
- Story storyboard generation and Send to Director.
- Scene Sheet Build Prompt.
- Character Profile → Avatar.
- Director Send to Editor.
- Audio asset → Editor track.
- Editor Open in Director and non-destructive version choices.
- Search-based workspace opening, after terminology/alias handling is made reliable.

## Priority recommendations

1. Fix navigation truthfulness: consume existing deep-link context, preserve active Scene, and remove misleading destination claims.
2. Surface Add Scene from Project Home and all no-scene states.
3. Bind Story explicitly to Scene before adding new workspace behavior.
4. Reuse Profiles and Scene Sheet data instead of asking for repeated strings.
5. Clarify current labels with transitional copy; do not redesign the visual system in Phase 0.
6. Treat disabled controls and stubs honestly in labels and completion reports.
7. Preserve the strongest direct handoffs and make their destination context deterministic.
8. Distinguish Project Package Export from future Editor Final Export.

## Validation still required

When the terminal/runtime runner becomes available, execute this journey with a temporary data directory and record:

- actual clicks and time per stage;
- focus/selection retained at every handoff;
- browser back/refresh/reopen behavior;
- empty, loading, failure, and missing-provider states;
- whether each output appears in Library and survives restart;
- whether any step touches production data;
- the exact point where final-film export becomes impossible.

Until that executable walkthrough is recorded, this audit is a source-backed navigation assessment, not runtime usability proof.
