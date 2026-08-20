# Co-Director Temporal Video Intelligence — Governing Document

**Status:** GOVERNING for Revision A  
**Branch:** `feat/codirector-temporal-continuity`  
**Law 30:** This is the single governing document for this milestone. Older Timeline and Co-Director reports remain historical.  
**Live evidence / unified completion report:** [REVISION-A-UNIFIED-COMPLETION.md](./REVISION-A-UNIFIED-COMPLETION.md). [03-LIVE-CLOSURE.md](./03-LIVE-CLOSURE.md), [02-LIVE-CERTIFICATION.md](./02-LIVE-CERTIFICATION.md), and [01-IMPLEMENTATION-AND-CERTIFICATION.md](./01-IMPLEMENTATION-AND-CERTIFICATION.md) are historical.

## Product law

More intelligence underneath. Less manual configuration on top.

Co-Director is the persistent visual intelligence layer for Timeline. Video understanding models never submit generation.

## MULTI-BATCH GOVERNANCE LAW

When Co-Director Continuity is enabled, every successfully completed batch that has a subsequent dependent batch MUST pass through the CD temporal review pipeline **before** that subsequent batch is submitted.

Timeline invokes Co-Director as an embedded governing service. The filmmaker does not open chat.

```text
Batch N complete
      ↓
CD review required
      ↓
READY
 ├─ review succeeds → compile packet
 └─ review unavailable → explicit degraded packet
      ↓
Batch N+1 may submit
```

A missing packet is not a valid state. Review after N+1 is already in the provider queue is a defect. Unavailable perception must not deadlock generation.

## Models

| Role | Model | Setup |
|---|---|---|
| Fast Timeline vision | VideoChat3-4B | Required essential (`videochat3_4b`) |
| Deep sequence review | InternVideo3-8B-Instruct | Optional, hardware-gated |
| TimeLens | — | Excluded (academic-only license) |

License memos:

- [docs/models/videochat3-4b/LICENSE_CLEARANCE.md](../../models/videochat3-4b/LICENSE_CLEARANCE.md)
- [docs/models/internvideo3-8b/LICENSE_CLEARANCE.md](../../models/internvideo3-8b/LICENSE_CLEARANCE.md)
- [docs/models/timelens/EXCLUSION.md](../../models/timelens/EXCLUSION.md)

## Contracts

- `TemporalContinuityPacket` (`temporal-continuity-v1`) — never `ContinuityPacket`
- `CoDirectorContinuityPolicy` on `SceneTimelineMaster` — never overload last-frame `ContinuityPolicy.configuredTailDuration`
- Pixel bridge (`ContinuityBridge`) remains last-frame I2V authority

## Reuse

Do not replace Timeline Master, ContinuityBridge, Wave 5 identity packets, ERS InstructionPacket, Scene Intent, CameraShotPacket, Setup `COMPONENTS`, or video generator adapters.

## Final verdict language

Only:

`GO — CO-DIRECTOR TEMPORAL VIDEO INTELLIGENCE & CONTINUITY CERTIFIED`

or

`NO-GO — CO-DIRECTOR TEMPORAL VIDEO INTELLIGENCE & CONTINUITY NOT CERTIFIED`
