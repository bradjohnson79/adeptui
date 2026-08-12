# Production Memory, Visual Wiki, and History

This note locks four M5.4 product refinements into a single creator-engineering brief:

1. **Decision Records** for why production choices were made
2. **Visual Wiki** pages that are enjoyable to browse
3. **Project Intelligence Landing** as the default Co-Director project entry
4. **Project History** as the creative evolution log

The goal is simple: when a creator opens a project like **The Dreamweaver**, Co-Director should already understand the current production state, show rich visual context, remember why past choices happened, and expose the project's evolution without confusing that history with the editing Timeline.

## 1. Decision Records

**Decision Records** are a first-class production-memory type for *why* something changed.

They are not the same thing as:
- **Production Bible**: authoritative approved truth
- **Wiki article prose**: readable production knowledge and browse pages
- **Library assets**: the actual images, audio, scripts, and media
- **Timeline**: shot and edit placement workspace

Typical Decision Record examples:
- Why Korri was redesigned
- Why WAN was chosen over LTX for a sequence
- Why a specific take was approved
- Why an image batch was rejected
- Why Scene 12 was replaced
- Why Barnes' office lighting changed

### Rules

- Decision Records must be queryable later in creator language, not only technical language.
- Mutation remains proposal-gated under the existing authority model.
- Decision Records must extend and unify existing `m211_decision_records` memory rather than creating a third memory store.
- Each record should link to the affected Wiki article(s), graph nodes, Bible entities, Library assets, and Project History events.

### What a Decision Record contains

- Plain-language title
- Short rationale summary
- What changed
- Why it changed
- Alternatives considered when relevant
- Authority state
- Related people, scenes, episodes, locations, props, or styles
- Related assets and history events
- Created/approved timestamps and provenance

## 2. Visual Wiki

The Wiki should feel closer to an IMDB-like production guide than a text wall.

Character, Location, Episode, Prop, and similar pages should show:
- Portrait or hero media
- Current status
- Appears-in / used-in context
- Relationships
- Voice and performance notes where relevant
- Wardrobe or look continuity where relevant
- Timeline usage summary
- Latest assets
- Recent changes
- Notes

### Visual Wiki rules

- Use thumbnails and hero media from the project Library or References.
- Do not expose raw IDs in primary UI.
- Keep creator-facing language plain and cinematic.
- Preserve authority and provenance, but present them in lightweight, readable chrome.
- Decision Records should appear as linked "why" context on relevant pages, not as buried backend metadata.

## 3. Project Intelligence Landing

Opening Co-Director on a project should not drop the creator into a blank chat.

The default entry should be a **Project Intelligence Landing** dashboard that gives immediate ambient context:
- Project title and format
- Season / production progress
- Counts for episodes, characters, locations, props, images, videos, voice, music, and SFX
- Story Bible completeness
- Continuity status
- **Current Task**: the episode, scene, location, and characters currently in focus

### Why this matters

This dashboard lets the conversation inherit project context so the creator can say:

> "Korri needs to look more tired here."

...without re-explaining who Korri is, which scene is active, what wardrobe is already approved, or what lighting and reference context is already in play.

## 4. Project History

**Project History** is the creative evolution log for the project.

It is **not** the editing Timeline.

Think of it as git-for-filmmaking:
- created episode
- approved character version
- updated location
- generated references
- changed style direction
- approved voice identity
- rejected image or audio batch
- updated Bible entry
- published a version

### Project History rules

- History must be browseable, filterable, and exportable.
- It must preserve past states rather than silently rewriting them.
- When a meaningful why exists, the history event should link to a Decision Record.
- History belongs in the production intelligence surface, not inside the editing Timeline metaphor.

## How These Layers Differ

Use this separation consistently:

- **Bible** = what is approved and authoritative
- **Wiki** = what the production knows and browses
- **Decision Records** = why the production chose a direction
- **Project History** = when and how the project evolved
- **Library** = the actual files and assets
- **Editing Timeline** = where editorial placement and sequence work happens

If a creator asks, "Why did we change this?", the answer should usually come from a **Decision Record**.
If they ask, "What changed over time?", the answer should usually come from **Project History**.
If they ask, "What is currently true?", the answer should usually come from the **Bible**.
If they ask, "Show me the character page / latest approved image / related notes," the answer should usually come from the **Visual Wiki** plus the **Library**.

## Dreamweaver Decision Record Q&A

Example creator-language queries Co-Director should be able to answer months later:

**Q: Why was Korri redesigned in Dreamweaver?**  
**A:** Because the prior version read too polished for the exhaustion beat in Episode 3. The approved direction added under-eye fatigue, softened posture, and reduced costume shine to support the scene's emotional state. Related links: `Korri` article, Episode 3 scene context, approved reference batch, redesign decision record, and approval history.

**Q: Why did we use WAN instead of LTX for this sequence?**  
**A:** WAN was approved for this sequence because it held facial continuity and mood better on the selected references, while LTX tests introduced drift during the long move. Related links: sequence article, comparison assets, provider test notes, decision record, and generation history.

**Q: Why was Scene 12 replaced?**  
**A:** Scene 12 was replaced after the team concluded it repeated information already carried by the Barnes hallway exchange and slowed the episode's reveal pace. Related links: old scene article, replacement scene article, Bible update, and history events showing the replacement.

**Q: Why did Barnes' office lighting change?**  
**A:** The lighting was shifted warmer and lower contrast to separate memory-space scenes from present-tense investigation scenes and to keep Barnes visually less confrontational in the revised performance pass. Related links: location article, style article, look references, and the linked Decision Record.

## Export expectation

Complete Wiki and status exports should include:
- Visual Wiki content
- Linked Decision Records
- Project History summaries
- Asset references and provenance

This keeps long-running productions portable and understandable outside the live product.
