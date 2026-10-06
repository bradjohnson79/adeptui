---
id: adept-readiness
kind: adept
modality: platform
registry_ids: []
aliases:
  - readiness
  - available
  - on demand
  - requires setup
spoken: Ready means it can run now. On Demand means Adept will start it when you ask — that is not broken. Requires Setup means something still needs installing or connecting.
workspace_tags:
  - settings
  - production-control
version: "2026.09.04"
authority: adept-integrated
---

# Adept readiness language

## Purpose

Keep generator and runtime status honest. Never flatten every gap to “offline.”

## Identity

These words are Adept product speech. They are not HTTP codes.

## Supported modes

| Word | Creator meaning |
| --- | --- |
| **READY** | This path can run now for the mode you asked. |
| **ON DEMAND** | Adept starts this path when you ask. Waiting is normal. Not broken. |
| **MODE-SPECIFIC** | Ready for one job, not another (example: Timeline H3 ready, On Demand MiniMax not started). |
| **TESTING** | Adept exposes it, but it is not the certified default. |
| **NOT INSTALLED** | Files or a provider are missing. |
| **REQUIRES SETUP** | Keys, weights, or a setting are missing. Say what is missing if Adept knows. |

## Unsupported modes

- “Offline” as a catch-all.
- “Down” when the truth is On Demand or Requires Setup.
- Treating On Demand MiniMax as proof that Timeline H3 is unavailable.

## Runtime semantics

Report each surface separately:

- Image Runtime
- Local Video Runtime (Timeline)
- On Demand Local Video Runtime (MiniMax text-to-video / image-to-video)
- Voice Engine
- Hosted API (named provider)

A READY Timeline generator can sit next to an ON DEMAND text-to-video path.

## Selection guidance

If the creator picked a generator that is NOT INSTALLED or REQUIRES SETUP, say that. Do not silently switch models.

## What Co-Director may read

Production Control / Settings capability labels and live project selection.

## What Co-Director must never claim

- That On Demand equals failure.
- That a TESTING row is Certified.
- That a hidden catalog-only stills model is a normal picker choice.

## Failure semantics

One late health check is not death. A busy generate is not “offline.” If Adept only knows “not ready,” use MODE-SPECIFIC or REQUIRES SETUP, not a invented outage.

## Relationships

- Platform speech: `adept-platform`
- Authority: `adept-authority`
- Video rooms: `video-generation`
- Image rooms: `image-generation`
