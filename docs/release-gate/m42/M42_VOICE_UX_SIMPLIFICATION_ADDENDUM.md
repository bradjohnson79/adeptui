# M42 Voice UX Simplification Addendum

**Date:** 2026-07-31  
**Scope:** Character Profile → Voice + Voice Performance UI only  
**Mock data:** false  
**Functionality removed:** none

---

## Goal

Replace engineering-dashboard chrome with a GarageBand / Canva / CapCut-style creative studio so a first-time user can create, preview, and approve a voice in under two minutes without documentation.

---

## Before → After (information architecture)

### Voice Creator

| Before | After |
|---|---|
| 9 sub-tabs (Overview, Create, Clone, Candidates, Audition, Pronunciation, Reactions, Versions, Provenance) | **4 sections:** Create Voice · Voice Personality · Listen · Advanced |
| Always-on 3-column engineer grid | Vertical studio stack, one primary action per section |
| “Candidates / Reject / Owner approve / Provenance” | **Voice Versions / Pass / Approve / History** |
| 25 brief fields up front | Personality **sliders** + full brief in Advanced |
| No HelpTips | `PanelHeading` + `(?)` on every unfamiliar control |
| No Co-Director entry | **Ask Co-Director** chips |

### Voice Performance

| Before | After |
|---|---|
| 9 view tabs + Direction column + pipeline buttons | **5 steps:** Dialogue · Performance · Delivery · Preview · Listen |
| Raw markup editor first | Plain dialogue first; markup synced in background |
| Emotion `<select>` | Large **emotion cards** (incl. Sarcastic) |
| Pace/delivery engineering selects | Pace + Strength **chips** |
| Parse → Create plan → Generate as separate engineer actions | **Generate Preview** primary CTA (runs pipeline under the hood) |
| Provider Translation / Segments / Provenance always exposed | Renamed **Voice Engine / Voice Clips / History** inside **Advanced** |
| No Co-Director entry | Ask Co-Director chips + `uiAction` open wiring |

---

## Language map (UI only)

| Engineering | Creative |
|---|---|
| Provider Translation | Voice Engine |
| Performance Plan | Performance Style |
| Segments | Voice Clips |
| Candidates | Voice Versions |
| Provenance | History |
| Preview request | Preview voice |
| Reject | Pass |
| Owner approve | Approve |
| Refine (new child…) | Regenerate / Adjust notes |

---

## Functionality preserved matrix

| Capability | Where it lives now |
|---|---|
| Voice design generate / preview | Create Voice → Generate |
| Clone + consent + reference file | Create Voice → Clone / Upload |
| Personality brief fields | Sliders + Advanced full brief |
| Candidate shortlist / reject / refine / approve | Listen → Voice Versions |
| A/B compare | Listen → Compare |
| Audition test lines | Advanced |
| Pronunciation + reactions | Advanced |
| Versions + provenance JSON | Advanced → History |
| Markup parse / plan / compile / generate | Preview + always-available Check / Apply style |
| Provider translation JSON | Advanced → Voice Engine |
| Assemble + timeline place | Listen → Add to Timeline |
| Co-Director `open_voice_performance` / `open_voice_creator` | Wired → Characters workspace + Voice / Voice Performance tab |

---

## Co-Director

- Chips open Co-Director with creative prompts (`useOpenCoDirector`).
- Tool results with `uiAction: open_voice_performance | open_voice_creator` navigate to Characters and dispatch `adept:open-character-voice`.
- Creative direction (emotion / pace / delivery) patches markup client-side via `buildPerformanceMarkup` — no cert API surface change.

---

## Files

- `studio-web/src/components/VoiceCreatorWorkspace.tsx`
- `studio-web/src/components/VoicePerformanceWorkspace.tsx`
- `studio-web/src/styles.css` (`.voice-studio-*`)
- `studio-web/src/components/CoDirector/CoDirectorSession.tsx` (`uiAction` handler)
- `studio-web/src/components/CharacterProfileWorkspace.tsx` (voice tab event)
- `tests/e2e/m42/m42-w43-korri-voice-creator.spec.ts`
- `tests/e2e/m42/m42-w44-voice-performance.spec.ts`

---

## Beginner test

1. Open Character Profile → Seed Korri → **Voice**  
2. **Generate Voice** → adjust sliders → Generate → **Play** → **Approve**  
3. Open **Voice Performance** → type dialogue → pick **Sarcastic** → Normal delivery → **Generate Preview** → **Play** → **Approve**

Pass criterion: completable in under two minutes without docs; Advanced still holds full production tooling.

---

## Certification note

This addendum is UX chrome only. W43/W44 binary gates and API contracts are unchanged. E2E retains pipeline assertions (`mock=false`, apply style → markup emotion → parse → segment list).
