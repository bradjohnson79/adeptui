# M4.12 Avatar Studio UX Specification

Status: implementation-aligned UX specification for the artist-facing Avatar Studio rebuild.

Scope of this document:

- Long-form presenter workspace chrome
- Creator-facing control model
- Honest blocked states for approved voice and avatar runtimes
- Review flow for sections, takes, progress, and completed videos

Out of scope for this pass:

- Full long-form section engine
- Fake live generation claims
- Provider certification or production-ready labels

## Product goal

Avatar Studio should feel like a clean presenter workspace, not a developer inspector or a generic video prompt surface.

The creator story is:

1. Select Avatar
2. Add Script or attach an Approved Voice
3. Choose Presentation Style
4. Choose Framing
5. Choose Background
6. Generate Avatar Video
7. Review sections and takes
8. Retake as needed
9. Send the best result to Timeline

## Layout

### Top header

- Workspace title: `Avatar Studio`
- Current presenter session name
- Session switcher
- `New Session`
- `Source Manager`
- `Save Draft`

### Main split layout

Left / center:

- Large `Avatar Preview`
- Big visual area for reference still or latest take
- Summary chips for framing, presentation style, and provider status
- Quick readiness summary for voice and timeline state

Right:

- `Create` panel
- Card-based creator controls
- One primary action: `Generate Avatar Video`
- `Advanced` drawer collapsed by default

### Bottom review area

Tabs:

- `Sections`
- `Takes`
- `Progress`
- `Completed Videos`

## Creator-facing controls

### Select Avatar

- Show visual presenter cards, not a raw profile picker first
- Switching avatars should reopen or create that avatar's presenter session
- Character choice remains project-scoped

### Mode

Replace the old crowded row with:

- `Talking Head`
- `Presenter`
- `Full-Body Presenter`
- `Existing Video Dubbing`

Do not surface `cinematic` or `stylized` as primary mode names. Those belong under presentation style / advanced styling decisions.

### Script or Approved Voice

Primary inputs:

- `Script`
- `Approved Voice`

Behavior:

- `Script` shows the section text area plus a route to Scriptwriter
- `Approved Voice` shows approved voice takes for the selected character when available
- If no approved take exists, show a blocked state that routes to Voice Studio

Honesty rule:

- Voice Studio remains the source of truth for approved voice
- Avatar Studio may attach an approved take, but must not pretend to have generated or approved it locally

### Presentation Style

Card-based, plain-language choices:

- `Direct Presenter`
- `Warm Host`
- `Guided Explainer`
- `Stylized Performance`

These map to saved session styling and performance notes, but the UI should stay creator-first.

### Framing

Card-based shot choices:

- `Tight Headline`
- `Presenter Frame`
- `Desk or Podium`
- `Full Stage`

### Background

Card-based choices:

- `Studio`
- `Branded Set`
- `Environment`
- `Graphic Canvas`

### Duration

Use creator-facing section-size classes:

- `Quick Update`
- `Story Section`
- `Chapter Pass`

This is a planning aid for long-form assembly, not a promise that the current generation backend already outputs a finished chapter-length render.

## Advanced drawer

Collapsed by default.

Contains:

- `Provider Mode`: `Best Match`, `Choose Provider`, `Compare`
- Provider cards with honest status
- Reference image
- Fallback audio
- Spoken rewrite
- Creative notes
- Exclude notes
- Continuity lock
- Link to Source Manager

### Provider honesty

Avatar runtimes must show only truthful states:

- `Experimental`
- `Not Installed`
- `Needs Repair`

Never show `Ready` or `Certified` for the M4.12 avatar providers in Avatar Studio from this pass alone.

## Blocked and empty states

### No character selected

Show:

- clear explanation that Avatar Studio starts with a character
- `Choose Avatar`
- `Open Character Profiles`

### No approved voice take

Show:

- explanation that Voice Studio owns approved performance
- `Open Voice Studio`
- copy that distinguishes between missing voice identity approval and missing approved takes

### No avatar runtime installed

Show:

- explanation that the runtime lives in Source Manager
- `Open Source Manager`
- current truthful install state

## Review area behavior

### Sections

This tab should be honest about current scope:

- show what is already planned and attached for the current presenter section
- do not fake a full section engine if it is not implemented yet
- guide the user to Scriptwriter, Voice Studio, or Timeline as the next step

### Takes

- Show generated takes in reverse chronological order
- Each take should support:
  - `Retake`
  - `Send to Timeline`

### Progress

Show plain-language readiness:

- voice readiness
- runtime status
- setup issues
- `Validate Setup`

### Completed Videos

- Show takes already treated as final / timeline-ready
- Keep the final handoff close to Timeline

## Copy standards

- Use creator language: `Avatar`, `Presenter`, `Approved Voice`, `Background`, `Retake`, `Timeline`
- Avoid implementation jargon in primary UI:
  - raw provider IDs
  - dependency paths
  - node graphs
  - prompt/negative prompt wording in the main flow

Technical capability may still exist, but it belongs in `Advanced`.

## Test expectations

Playwright smoke should verify:

- simplified Avatar Studio workspace loads with a selected character
- presenter modes are visible
- `Advanced` is collapsed by default
- the old `Avatar Inspector` chrome is gone
- review tabs are present

## Implementation notes for this pass

- The UI rebuild may reuse existing avatar session persistence
- Approved voice choices may be read from Voice Studio records
- Setup / Source Manager status may be read from the setup status API
- This pass should not fake a section engine or provider certification

**READY FOR PRIMARY REVIEW**
