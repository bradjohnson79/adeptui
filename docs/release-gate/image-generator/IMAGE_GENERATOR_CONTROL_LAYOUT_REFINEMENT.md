# Image Generator — Control Layout Refinement

**Date:** 2026-08-17  
**Branch:** `beta` (local working tree; not a new milestone)  
**Scope:** Hosted API Usage + Prompt Intelligence accordion layout only.

## Verdict

**GO — IMAGE GENERATOR CONTROL LAYOUT REFINEMENT CERTIFIED**

## What changed

CIS-scoped CSS plus light markup wrapping. Existing `hostedChoice`, Prompt Intelligence module flags, strategy mode, enhance/apply handlers, and pricing estimates are unchanged.

- Hosted API: compact left-aligned segmented chips. Radio + label live in the same clickable control. Selected chip uses Adept teal. Cost stays under the group, muted when local-only.
- Prompt Intelligence: mode chips keep the Manual / Co-Director / Certified Auto pattern. Modules are horizontal rows (label + helper left, On/Off right). Actions sit in a separated footer. Disabled actions expose why via `title` plus a Preview hint.

## Visual verify (Schnick Coffee, local Beta)

Desktop: radio 16×16, 6px gap to label, label inside chip; Hosted body ~608px vs card ~855px. Toggle rows consistent height; control on the right. Hosted Local ↔ Allow and Production On ↔ Off restored the same state.

Narrow: Generation Source and mode chips stack as whole options. Toggle rows stay label-left / control-right.

## URLs

- Creator UI: `http://127.0.0.1:8760/`
- Studio API: `http://127.0.0.1:8758/`
