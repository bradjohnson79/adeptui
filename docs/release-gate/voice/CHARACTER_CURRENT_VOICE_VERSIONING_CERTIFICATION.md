# Character Current Voice + Versioning

**Date:** 2026-09-16  
**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `99665cf7` (working tree includes this mission; not committed unless requested)  
**Studio API:** `http://127.0.0.1:8758/` PID 27140 (recycled from 43540)  
**Creator UI:** `http://127.0.0.1:5173/`  
**Review URL:** `http://127.0.0.1:5173/project/fb24ff0f-8772-4d50-a602-ac69d14b5a6b?workspace=voicestudio&characterId=85e37d4b-a32e-4374-888b-1389fc0b3720`  
**COMFY BEFORE:** PID 34484 (Comfy Desktop) healthy, ~32 GB free  
**COMFY AFTER:** PID 34484 healthy  
**COMFY RESTARTED?:** NO  
**WHY?:** Ordinary API recycle only (`restart_studio_api_only.py`). `:8188` observed, never restarted.

Governing report for this mission. Voice generation progress remains certified in `docs/release-gate/voice/VOICE_PROGRESS_AND_GLOBAL_ASSET_SCOPE_CERTIFICATION.md`.

---

## ROOT CAUSE

`approve_voice_profile` treated an already-approved Voice Profile as a 409 `LOCKED_VERSION` ("Approved Voice Profiles are immutable. Create a new version.").

That rule is correct for **profile bytes**. It was incorrectly applied to **reassignment of the character's current voice**.

Owner path that hit it:

1. Cade already had approved `Cade O'Connor Clone` (`active_voice_profile_id`).
2. A new clone generated a **new draft** Voice Profile (correct).
3. Voice Creator still bound Approve to the **already-approved** `voiceId` after the last completed job, or a second Approve / Use Existing targeted that approved id.
4. API 409 → red `.vip-error` banner. Workflow blocked.

Double-submit after a successful first approve of a new draft produced the same 409.

---

## VOICE PROFILE IMMUTABILITY

**PRESERVED.** Approving a draft stamps that row once (`approval_status=approved`, preview asset, lineage). Re-approving / Use Existing does **not** rewrite approved lineage, preview bytes, or the source recording.

`fork_draft_voice_profile` still copies to a new draft and **no longer steals** `active_voice_profile_id`.

---

## CHARACTER CURRENT VOICE POINTER

**Canonical field:** `CharacterProfileRow.active_voice_profile_id`  
JSON: `active_voice_profile_id` / `activeVoiceProfileId`

One authority. No parallel `currentVoice` / `defaultVoice` fields.

Approve (new draft or already-approved) only moves that pointer. Exactly one current/default.

---

## APPROVE NEW SAMPLE

Trace:

`Approve selected voice` → `handleApprove` → `POST .../voice/approve` → `approve_voice_candidate` → stamp **draft only** → `approve_voice_profile` (approve if needed + set pointer) → Prompt Package refresh → workspace reload → Approved Voice card.

Live Cade (Cade Scenes `fb24ff0f-…`, Cade `85e37d4b-…`):

| Step | Result |
| --- | --- |
| Re-approve current v5 | HTTP 200, `pointerOnly=true`, no 409 |
| Clone 1 from `Cade Sample.mp3` | job complete 100%, voice `0c890a32-…` v6 |
| Approve selected | HTTP 200, current → v6, previous = v5 |
| Preview play | asset `679c5059-…` HTTP 200 |
| Clone 2 | voice `43f8a0d9-…` v7 |
| Approve | current → v7, previous = {v5, v6} |

Evidence: `.runtime/_voice_current_pointer_smoke.json`

---

## OLD VERSION RETAINED

v5 `bc3d9abc-…` Cade O'Connor Clone remains approved. Not overwritten, not deleted.

---

## SECOND REPLACEMENT

v7 current, v6 + v5 in `previousApprovedVoices`. PASS.

---

## USE EXISTING

`POST /voice/approve` with `voiceId` only. `pointerOnly=true`. No duplicate Voice Profile.

API: pointer returned to v5 while v6 and v7 stayed in history.  
UI: **Use this version** on v6 → Approving… → card **Approved Voice — Cade O'Connor Clone v2 Pointer / Current v6** / **Approved ✓**. No red banner.

---

## APPROVED CARD

Shows profile name, **Current vN**, play/seek, **Default voice across Adept UI**, previous versions with **Use this version**. Not an error state.

---

## RED BANNER REMOVED

Immutable 409 copy is gone from this path. Replacement copy is muted, not error:

> Approving a new sample will make it Cade O'Connor's current voice. The previous approved voice will remain in version history.

---

## PLAYBACK

Approved card play → Pause (audio running). Asset file 200 on home project and from Global Scope B.

---

## RELOAD

Hard navigation back to Cade Voice Studio: current still v6 Pointer, history v5 + v7, no immutable error, Clone / Create New Voice still available, GENERATE enabled.

---

## CHARACTER SWITCH

Opened `CharacterGlobalTest9c1f3f`: empty “No approved default voice” (no Cade bleed). Returned to Cade: v6 still current.

---

## GLOBAL CHARACTER

Cade is Global. `active_voice_profile_id` lives on the canonical character. Project B workspace returns the same current id. Voice rows are listed by `character_id`, not copied per project. Approve/generate still require home-project ownership (`OWNER_REQUIRED` from B).

---

## BACKING AUDIO ACCESS

`resolve_readable_asset` now grants Global Character voice preview / reference / candidate audio to a viewing project. Project B GET of Cade's current preview: HTTP 200. Local (non-global) audio from another project remains denied.

---

## TIMELINE / DOWNSTREAM

`resolve_approved_voice_audio` uses `active_voice_profile_id`. Same-project approved voices unchanged. Global characters now resolve from another project without rewriting explicit scene `voiceProfileId` bindings.

Live bind home + Project B both resolve Cade current → `36789d91-…` when v5 was current; after UI Use this version, consumers read v6 via the same pointer.

---

## CO-DIRECTOR

`character_creator.get_voice_status` after API use-existing:

> Cade O'Connor's current default voice is Cade O'Connor Clone (v5).

After UI Use this version, current is v6 Pointer. Status reads `active_voice_profile_id` only when that row is approved.

---

## CONSOLE / NETWORK

Browser DOM: 0 `.vip-error`, `immutable=false`. Approve path: first 200, no 409. 0 unexpected 4xx on approve / asset file in the live smoke. Duplicate approve submissions guarded (`approvingRef` + disabled Approving…).

---

## TESTS

```
studio-api: tests/test_voice_current_pointer.py — 6 passed
studio-api: test_timeline_voice_bind resolve + global — passed
studio-api: test_creator_asset_scope global voice audio — passed
studio-web: defaultVoiceCopy / voiceIdentityBrief / voiceSamplePlayers — 16 passed
```

---

## LIMITATIONS

- Mid-generation cancel is still not surfaced.
- New clone still requires re-picking the recording file in the browser (`cloneFile` is in-memory).
- Historical Timeline clips that stored an explicit `voiceProfileId` stay on that id; only default/new resolutions follow current.

---

## FINAL REPORT

| Field | Result |
| --- | --- |
| ROOT CAUSE | 409 LOCKED_VERSION on already-approved Voice Profile blocked current-pointer reassignment |
| VOICE PROFILE IMMUTABILITY | PRESERVED (bytes / lineage) |
| CHARACTER CURRENT VOICE POINTER | `active_voice_profile_id` — mutable, one current |
| APPROVE NEW SAMPLE | PASS |
| OLD VERSION RETAINED | PASS |
| SECOND REPLACEMENT | PASS |
| USE EXISTING | PASS (no duplicate asset) |
| APPROVED CARD | PASS |
| RED BANNER REMOVED | PASS |
| PLAYBACK | PASS |
| RELOAD | PASS |
| CHARACTER SWITCH | PASS |
| GLOBAL CHARACTER | PASS (pointer travels; no copy) |
| BACKING AUDIO ACCESS | PASS (Global relationship only) |
| TIMELINE/DOWNSTREAM | PASS |
| CO-DIRECTOR | PASS |
| CONSOLE | PASS |
| NETWORK | PASS |

## FINAL VERDICT

**GO — CHARACTER CURRENT VOICE + VERSIONING CERTIFIED**
