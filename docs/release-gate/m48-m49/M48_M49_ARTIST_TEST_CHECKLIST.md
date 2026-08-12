# M4.8–M4.9 — 60-Second Artist Test (Manual UX)

**Rule:** Human stamp only — never auto-pass.

## Instructions for the reviewer

Hand Adept UI (Beta) to someone unfamiliar with the codebase. No coaching.

Ask them to:

1. Create a cinematic frame  
2. Add it to Storyboard  
3. Prepare it for Timeline  

Timer: **60 seconds** to discover the three actions (not necessarily finish generation).

## Discoverability checklist

| Action | Expected discovery path | Pass? |
| --- | --- | --- |
| Create cinematic frame | Project → **Cinematic Image Generator** → Prompt → **Generate** | [ ] |
| Add to Storyboard | Result card → **Add to Storyboard** (or Replace panel) | [ ] |
| Prepare for Timeline | **Storyboard Studio** → **Prepare for Timeline** → **Confirm Proposal** | [ ] |

## Automated proxy (does not replace human stamp)

Playwright `M48/M49 Artist discoverability` verifies Generate / Open Storyboard / Prepare for Timeline controls are visible without instructions.

## Stamp

| Field | Value |
| --- | --- |
| Reviewer | ________________ |
| Date | ________________ |
| Result | **PENDING HUMAN** / PASS / FAIL |
| Notes | |

Until a human marks **PASS** above, Manual UX Certification remains **PENDING** (blocks full GO).
