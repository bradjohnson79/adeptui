# M42 W43 Corrective Addendum — Generated Character Image Profile

| Field | Value |
|---|---|
| **Phase** | M42 Phase 4.3 Corrective Addendum |
| **Branch** | `phase2/m42-character-creator-completion` |
| **Gate flag** | `korriGeneratedImageProfileOperational` |
| **Authority** | `korri.v1.json` + approved Korri sheet (identity) |
| **Production proof** | Generated visual sheet via certified **Z-Image** (`zimage.txt2img` / `zimage.ref_edit` / `character_sheet`) |
| **Mock policy** | Forbidden — no placeholder, seeded fake, browser-only, or manual DB cert path |
| **Verdict** | **GO** (`korriGeneratedImageProfileOperational: true`) |
| **Stamped** | 2026-07-31 |
| **Live evidence** | `artifacts/m42/w43/visual_sheet_results.json` — 15 roles, owner-approved gates, Z-Image |

## Problem

Korri’s seeded Character Profile had structured domains (motion, performance, relationships, prompt package) without a **completed generated visual image profile**. That is insufficient for Character Creator certification.

## Mission

Complete Korri’s profile by generating, reviewing, approving, registering, and propagating a full visual character sheet through the real Character Creator workflow:

- Full-body turnaround: front / side / back  
- Facial close-ups: front / side / back  
- Material samples: skin, hair (front/side/back), wardrobe, accessories (circuit tattoos / wooden earrings)  
- Performance frames: expression + pose  

## Closed loop (what shipped)

```text
Seed Korri (canon)
  → propose visual directions (locked identity)
  → Generate Visual Sheet (Z-Image hero)
  → character_sheet tool (role-mapped turnaround + closeups)
  → detail ref_edit jobs (skin/hair/wardrobe/accessories)
  → performance frames (expression/pose)
  → attach Character Identity reference roles
  → gates AWAITING_OWNER with real assetIds
  → Owner Approve Visual Pack
  → promote identity (VisualIdentity + Bible + Prompt Package)
```

| Surface | Capability |
|---|---|
| API | `POST .../visual-sheet/generate`, `.../advance`, `.../owner-approve`, `GET .../visual-sheet` |
| UI | Character Profile → Visual Gates; Timeline Character Creator → **Generate Korri Visual Sheet** |
| Co-Director | `propose_visual_sheet`, `advance_visual_sheet`, `get_visual_sheet_status` (propose→approve→execute) |
| Cert | `scripts/m42_w43_korri_visual_sheet_cert.py` → `artifacts/m42/w43/visual_sheet_results.json` |

## Role mapping

`character_sheet` view keys → identity roles via `CHARACTER_SHEET_ROLE_MAP`:

| View | Role |
|---|---|
| front | `full_body_front` |
| side | `full_body_side_left` |
| back | `full_body_back` |
| front_closeup | `closeup_front` |
| side_closeup | `closeup_side_left` |
| back_closeup | `closeup_back` |

## Drift bans (enforced in prompts)

Blonde hair · aqua/blue eyes · metallic futuristic wardrobe · Anadriya facial identity · missing pointed ears · missing circuit markings.

## Co-Director as full-stack operator

Co-Director can seed/inspect Korri, propose visual sheet generation, advance job attach phases, read Prompt Package / Performance Bible / Motion, and never invent Korri traits when grounded products exist. Owner approval remains human-gated.

## Evidence

| Artifact | Role |
|---|---|
| `artifacts/m42/w43/visual_sheet_results.json` | Binary pack result |
| `artifacts/m42/w43/korri/generated_image_profile.json` | Role→asset evidence |
| Gate | `korriGeneratedImageProfileOperational` |

## How to run live cert

```bash
# ComfyUI must be healthy on the configured URL
python scripts/m42_w43_korri_visual_sheet_cert.py
python scripts/m42_w43_korri_certify.py
```

**Automatic NO-GO** if Comfy unhealthy, any required coverage role missing, gates approved without assetIds, or mock/placeholder assets used.
