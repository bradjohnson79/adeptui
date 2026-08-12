## Adept MiniMax H3 Request Contract

`AdeptMiniMaxH3Request` is the shared planning request for the MiniMax H3 surface.

### Core fields

- `projectId`: open project owner for all planning state
- `prompt`: creator-written motion direction
- `territory`: host territory code used for fail-closed license gating
- `sourceSurface`: where the request came from (`api`, `codirector`, `timeline`, `production-control`, `other`)
- `mode`: `text-to-video` | `one-frame` | `first-last` | `three-frame` | `reference`
- `deployment`: `local_weights` | `api`
- `durationSec`: allowed planning range is 4 to 15 seconds at preflight
- `referenceAssignments`: role-tagged assets such as `start`, `middle`, `end`, `reference`
- `audioAssetId`: optional source audio for honest native-audio intent tracking
- `approvalId`: explicit creator approval token for hosted requests
- `timelineContext`: optional scene and shot context
- `creatorNotes`: optional plain-language guidance

### Three-frame contract truth

- Three-frame requests must provide three distinct roles: `start`, `middle`, and `end`.
- MiniMax H3 native three-frame support is false.
- Adept defaults to `segmented-a`:
  - `Start -> Middle`
  - `Middle -> End`

### Preflight outcomes

- `blocked`: request cannot proceed honestly
- `needs_approval`: hosted request is structurally valid but lacks explicit approval
- `ready`: reserved for structurally valid surfaces; this build still blocks real execution honestly

### License summary

- Local weights are blocked in excluded territories including the US.
- EU member territories, the UK, and the Republic of Korea are excluded for local community-license use.
- Unknown territory fails closed.

### Fallback

- LTX is the permanent fallback.
- Fallback is never silent.
- Prompt, frame references, and audio attachment stay preserved when fallback is offered or accepted.
