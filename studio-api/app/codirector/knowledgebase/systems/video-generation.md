---
id: video-generation
kind: system
modality: video
registry_ids:
  - minimax-h3
  - ltx-2.5-distilled
  - ltx-2.5-full
  - ltx-2.5-comfy
aliases:
  - video studio
  - r2v overview
  - movie generators
spoken: Adept local video in v1.1 is MiniMax H3 and LTX 2.5. Text to Video is real local T2V. 1 Frame is Image-to-Video. Timeline is Reference-to-Video. Seedance 2.0 and 2.5 are separate hosted versions. Retired LTX 2.3, WAN, and Hunyuan are not active choices.
workspace_tags:
  - timeline
  - video-generation
version: "2026.09.04"
authority: adept-integrated
---

# Video Generation

## Purpose

Choose a video path and honor its Adept contract. Do not flatten every engine into text-to-video.

## Identity

CREATE Text to Video uses local MiniMax H3 T2V and LTX 2.5 T2V when those workflows are installed. 1 Frame is Image-to-Video. Timeline is Reference-to-Video. Do not say there is no local T2V. Do not send the creator to Seedance because locals are “reference-only.”

## Supported modes

Current per-engine notes (do not rewrite here):

- MiniMax H3 — `video-generators/minimax-h3.md` (local T2V / I2V / Timeline R2V)
- LTX 2.5 — `video-generators/ltx-2.5.md` (local T2V / I2V / Timeline R2V)
- Seedance 2.0 — `video-generators/seedance-2.0.md` (hosted, not local Ready)
- Seedance 2.5 — `video-generators/seedance-2.5.md` (hosted, distinct from 2.0)

## Unsupported modes

- WAN 2.6 / WAN 3.0 as Adept product rows.
- WAN text-to-video.
- LTX Timeline as text-to-video.
- Mixing Timeline H3 with On Demand MiniMax.
- Teaching ports or “start the video engine yourself.”

## Inputs

Sheets, Prompt Names, selected product id.

## Reference semantics

Delegated to the selected `video-generators/*.md` compile block. Those files are current.

## Output contract

Video take in Library with the selected generator in provenance.

## Adept integration

Timeline is the production surface. MAGI finishes. This page is the overview only.

## Runtime semantics

MODE-SPECIFIC.

- Timeline generators: READY / TESTING / NOT INSTALLED / REQUIRES SETUP on Local Video Runtime.
- MiniMax text-to-video / image-to-video: ON DEMAND Local Video Runtime. On Demand ≠ broken.
- Hosted: REQUIRES SETUP without keys.

## Selection guidance

See `timeline` plus the selected generator file. If the creator says “WAN,” say WAN is retired in v1.1 — do not restore it and do not substitute Seedance.

## Terminology disambiguation

- LTX 2.3 ≠ LTX 2.5.
- Route A = On Demand MiniMax T2V/I2V, not Timeline H3.
- WAN / `optional-wan` are not Timeline paths.

## What Co-Director may read

The selected generator's Markdown and live registry row.

## What Co-Director may execute

Compile using that file. Generate after confirm.

## What Co-Director must confirm

Generate. Switching engines.

## What Co-Director must never claim

Upstream cloud modes Adept did not wire. Silent T2V fallback.

## Persistence

Takes stay on this project.

## Failure semantics

Mode limits are not runtime death. Do not restore WAN to explain a missing frame.

## Relationships

- Timeline: `timeline`
- Current contracts: `ltx-2.5`, `minimax-h3`
- Readiness: `adept-readiness`
