# M4.12 MuseTalk Repair Notes

MuseTalk is treated as a repair specialist in Avatar Studio.

## Role

- Provider id: `musetalk-1-5-local`
- Creator-facing role: `Lip-Sync Repair`
- Scope: existing video dubbing, lip-sync repair, and section-level repair planning

## What changed

- Existing-video mode now uses `Prepare Lip-Sync Repair`
- Avatar Studio no longer routes this mode as if it were a full avatar generation path
- `avatar.repair_lipsync` checks MuseTalk installation honestly before recording a repair plan

## Failure behavior

If MuseTalk is not installed, the system returns:

- `AVATAR_LIPSYNC_REPAIR_PROVIDER_REQUIRED`

Recovery:

- open Source Manager
- install MuseTalk 1.5
- retry the repair request

## Honest limitation

This pass records a repair plan and provenance only. It does not fabricate a repaired render.
