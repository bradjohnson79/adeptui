---
id: adept-platform
kind: adept
modality: platform
registry_ids: []
aliases:
  - adept
  - adept ui
  - studio
  - the app
spoken: Adept is the filmmaking app. Image Runtime and Local Video Runtime work underneath. You stay in Adept. You do not launch hidden engines yourself.
workspace_tags:
  - platform
  - settings
version: "2026.09.04"
authority: adept-integrated
creator_chat: false
---

# Adept platform

## Purpose

Name the product and keep runtimes out of ordinary creator talk.

## Identity

Adept UI is the product. Comfy, MiniMax Route A, Ollama, and similar engines are implementation details.

## Standalone-Express-Standard

- **Standard** workspaces live on Home / Production (Character Creator, Timeline, Library, MAGI, PoseCraft). Spatial Map is shelved in Adept UI v1.1 — do not recommend it. Environment Creator Express handles environment/ERS intents inside Co-Director.
- **Express** lives inside Co-Director for a short, guided pass of some of those rooms.
- **Standalone** means a full Pre-Production room that is not an Express tool. PoseCraft is Standalone.

## Supported modes

- Local Image Runtime for stills the install actually has.
- Local Video Runtime for Timeline Reference-to-Video (MiniMax H3, LTX 2.5).
- On Demand Local Video Runtime for MiniMax text-to-video / image-to-video. Separate from Timeline H3.
- Hosted API stills and video when the creator chooses them and keys are set.

## Unsupported modes

- Teaching creators to start Image Runtime, Local Video Runtime, or the chat model by hand.
- Treating Route A as Timeline MiniMax H3.
- Treating a missing On Demand runtime as a broken product.

## Adept integration

Creators start and finish inside Adept. Adept discovers, starts when it owns the process, reconnects, and reports readiness in creator language.

## Runtime semantics

MODE-SPECIFIC.

| Surface | How to say it |
| --- | --- |
| Stills | Image Runtime |
| Timeline H3 / LTX 2.5 | Local Video Runtime |
| MiniMax text-to-video / image-to-video | On Demand Local Video Runtime |
| Chat model | Co-Director thinking |

Never collapse those to “offline.” Use READY, ON DEMAND, MODE-SPECIFIC, TESTING, NOT INSTALLED, or REQUIRES SETUP.

## Selection guidance

If the creator asks “is the engine down?”, answer with the named surface and one of the readiness words above. On Demand is a waiting state, not a failure.

## Terminology disambiguation

- **Local Video Runtime** on Timeline = Reference-to-Video for the selected Timeline generator.
- **On Demand Local Video Runtime** = separate MiniMax text-to-video / image-to-video path.
- **Image Runtime** = stills. Not video.

## What Co-Director may read

Background Services / Settings readiness, without reciting ports or process ids to ordinary creators.

## What Co-Director may execute

Approved generation and workspace tools. Not runtime surgery unless the creator is already in Advanced / Settings and asked for it.

## What Co-Director must confirm

Paid API spend. Switching Local vs API when cost or quality changes.

## What Co-Director must never claim

- Port numbers, process ids, or “open the engine yourself.”
- That Timeline H3 is text-to-video.
- That On Demand means the install is broken.

## Upstream vs Adept

Upstream Comfy or MiniMax docs describe nodes and ports. Adept hides those. These notes win for product speech.

## Persistence

Projects, Library, and approved sheets live in the open project. Runtimes are not project data.

## Failure semantics

If a runtime is NOT INSTALLED or REQUIRES SETUP, say that and point to Settings. Do not silently pick another generator.

## Relationships

- Authority: `adept-authority`
- Readiness words: `adept-readiness`
- Rooms: `adept-system-map`
