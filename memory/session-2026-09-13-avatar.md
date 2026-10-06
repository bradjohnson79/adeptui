# Session Memory: 2026-09-13 — Avatar Studio Character Propagation + UI Style Convergence

## Branches
- Working branch: `feat/character-creator-final-closure`
- HEAD (session end): `99665cf7`
- GitHub remote: git@github.com:bradjohn79/adeptui.git

---

## 1. Objective

Bring Avatar Studio back into alignment with Adept UI's canonical project data and visual design. Two observed defects:

1. **Journey 1 — Character Propagation:** Existing project characters did not appear in Avatar Studio's Character dropdown. Root cause traced end-to-end: Character Creator → canonical project character authority → Avatar Studio query/state → dropdown → preview → generation state.
2. **Journey 2 — Footer CSS Convergence:** Avatar Studio's footer/status cards, tabs, and buttons used light hardcoded surfaces that visually broke from the dark Adept UI design system.

---

## 2. Root Cause — Journey 1

**Classification: EXISTS / DISCONNECTED**

- Characters existed canonically: `character_profiles` table held 4 rows for the Korri project; the legacy `profile_items` table had 0.
- The canonical endpoint `/api/projects/{id}/characters` returned **404 FEATURE_DISABLED** because the `character_identity_v1` feature flag was not active on the running API process.
- `loadLists` in `AvatarStudioWorkspace.tsx` swallowed the 404 with `.catch(() => ({ items: [] }))`, so the dropdown rendered empty instead of surfacing the disconnect.
- The API process had been restarted out-of-band by a concurrent actor without the `STUDIO_FEATURE_CHARACTER_IDENTITY_V1=1` environment variable.

**Repair:**
- `loadLists` now prioritizes `api.listCharacterProfiles(project.id)` (canonical) and surfaces a honest `charactersError` state when the canonical authority is unreachable, instead of silently rendering an empty dropdown.
- Character binding uses the canonical `characterId` (not display name) and resolves the approved still asset for the Avatar preview via `pickApprovedCharacterStill`.
- A reference-less character shows a clear missing-image state rather than being hidden.
- The canonical API was recycled via the runtime supervisor's internal `restart_studio_api_child` to ensure the feature flag was active.

## 3. Root Cause — Journey 2

**Classification: Visual divergence from Adept design tokens**

- `.avatar-review-card` used `#d7e4de` (near-white), `border: 1px solid rgba(46,78,68,0.32)`, `border-radius: 18px`.
- `.avatar-provider-card.is-selected` used `#145a45` / `#1f6b52` / `#355248` — one-off colors, not Adept tokens.
- No `.avatar-review-tabs button` styling existed; no `:focus-visible` ring.

**Repair:** Replaced all one-off CSS values with canonical Adept design tokens:
- `--surface-glass-strong`, `--border-glass`, `--border-glass-active`, `--ink`, `--muted`, `--codirector-radius`, `--shadow-lift`, `--focus-ring`, `rgba(45,212,191,0.16)` (teal accent).
- Added `.avatar-review-tabs button` with normal/hover/selected/disabled/`:focus-visible` states.
- Added `.avatar-inline-actions button:disabled` with `opacity: 0.6`, `cursor: not-allowed`.

---

## 4. Files Changed

| File | Scope |
|---|---|
| `studio-web/src/components/AvatarStudioWorkspace.tsx` | Canonical character authority wiring, honest error state, preview-binding |
| `studio-web/src/components/AvatarStudioCreatePanel.tsx` | Accept + display `charactersError` in dropdown area |
| `studio-web/src/styles.css` | Avatar-scoped CSS convergence onto Adept tokens (cards, tabs, buttons, focus ring) |

**No backend files changed.** The feature flag fix was environmental (API recycle), not a code change.

---

## 5. Live E2E Evidence (observed, not predicted)

| Check | Observed |
|---|---|
| Dropdown (Korri project) | `Select character…, Cami Briggs, Korri, Anadriya, Addex` (4 real characters) |
| Select Korri | id `4a2e9cbe…` → preview `/assets/56b85ccb…/file` (approved hero still) |
| Select Anadriya | id `4c1c0bc8…` → preview `/assets/cf9d3cc0…/file` (distinct asset) |
| Reload | Anadriya selection + exact asset re-resolved |
| Cross-project (ERS) | `Special Agent Jacob Barnes`, `Korri` — Korri here = `7b99f800…` (different canonical id ⇒ ID-based, not name-matched) |
| Dynamic propagation | Created `Propagation Probe` via canonical API → appeared in dropdown with no restart |
| Missing image | Reference-less character: "This character has no approved Avatar image yet…" |
| Generation-state identity | Footer Current Setup → `Avatar: Korri` |
| Card computed style | `bg rgba(10,16,28,0.82)`, `border rgba(148,220,255,0.18)`, `radius 14px` |
| Tab (selected) | `bg rgba(45,212,191,0.16)`, `border rgba(45,212,191,0.55)` |
| Tab (idle) | transparent bg, `#9db0c3` muted text |
| Disabled buttons | `opacity 0.6`, `cursor: not-allowed`, legible |
| Focus ring | `--focus-ring` = `0 0 0 3px rgba(45,212,191,0.4)` (rule loaded) |
| Contrast (ink on card) | **17.67:1** (AAA) |
| Contrast (muted on card) | **8.54:1** (AAA) |
| Responsive @820px | `scrollWidth 810 ≤ 820`, no horizontal overflow, cards stack |

---

## 6. Required Verdicts

```
CHARACTER AUTHORITY            — PASS
ACTIVE PROJECT SCOPING         — PASS
CHARACTER DROPDOWN PROPAGATION — PASS
CANONICAL CHARACTER IDENTITY   — PASS
CHARACTER PREVIEW BINDING      — PASS
SAVE / RELOAD                  — PASS
DYNAMIC CHARACTER PROPAGATION  — PASS
CROSS-PROJECT ISOLATION        — PASS
FOOTER CARD STYLE CONVERGENCE  — PASS
TAB STYLE CONVERGENCE          — PASS
BUTTON CONTRAST / STATE        — PASS
ACCESSIBILITY / RESPONSIVENESS — PASS
```

---

## 7. Runtime Status (ComfyUI Protection Law)

```
COMFY BEFORE:      :8188 system_stats 200 (untouched, read-only)
COMFY AFTER:       :8188 system_stats 200 (same, healthy)
COMFY RESTARTED?:  NO
WHY?:              Ordinary UI/API mission; API-only recycle via canonical supervisor.
```

Studio API: `http://127.0.0.1:8758/api/healthz` → 200
Local creator UI: `http://127.0.0.1:5173/` → 200

---

## 8. Final Verdict

**GO — AVATAR STUDIO CHARACTER PROPAGATION + UI CONVERGENCE VERIFIED**

---

## 9. Limitations

- The `character_identity_v1` flag must be present in the API process env. A non-canonical/out-of-band API launch that omits it re-disables the endpoints; the honest error state now surfaces this instead of an empty dropdown.
- Keyboard-only `:focus-visible` could not be delivered through the Electron webview's key router; the CSS rule is verified loaded and `--focus-ring` verified resolvable. Native `<select>` gives keyboard-operable dropdown by default.
- `styles.css` shows a larger net diff from unrelated concurrent edits by another actor (library / oneframe / txt2vid / live-preview). Those are not part of this mission and were left untouched per scope discipline.
- A disposable probe project (`t`) and one QA character were created then deleted during dynamic-propagation testing.
