---
id: gpt-image-2
kind: generator
modality: image
registry_ids:
  - gpt-image-2-fal
  - gpt-image-2-kie
aliases:
  - gpt image
  - gpt image 2
  - openai image
spoken: GPT Image 2 is the hosted stills engine Adept uses for Environment Reference Sheets. If it is not set up, Adept stops and tells you. It does not switch to Qwen.
workspace_tags:
  - spatial-map
  - image-generation
version: "2026.09.04"
authority: adept-integrated
---

# GPT Image 2

## Purpose

Hosted stills. Exclusive engine for Environment Reference Sheets.

## Identity

Prefer `gpt-image-2-fal` when that row is Available. `gpt-image-2-kie` may be Testing. Not Qwen. Not Flux.

## Supported modes

- One-prompt ERS (`purpose=environment_reference_sheet`).
- General hosted stills / edits when the creator picks this engine.
- Layout exemplars attach only as shape/density, never as content to copy.

## Unsupported modes

- Local Qwen / Flux / Z-Image / Krea / Auto Select as ERS fallback.
- Four beauty POVs as an ERS.
- Character Front / Side / Back as an ERS.

## Inputs

Scene intent, Spatial Map / Atlas facts, ERS spec sections. Exemplars are structure only.

## Reference semantics

Exemplars teach page shape. Venture corridor and Korri's room must not be copied into a new place.

## Prompting semantics

Ask for the required ERS sections in one image. Do not invent dimensions or IDs the map does not have.

## Strengths

Unified production ERS page. Strong layout following when the spec is attached.

## Weaknesses

Paid API. REQUIRES SETUP without keys. Not a local offline stills engine.

## Output contract

One image. ERS must pass layout rules or it is non-compliant. Library on this project.

## Adept integration

Spatial Map ERS button. Co-Director ERS tools. Never Scene Creator Mini's Qwen path.

## Runtime semantics

READY / Available when the hosted key works. REQUIRES SETUP when missing. Never “use Qwen instead” without an explicit creator choice to abandon ERS.

## Selection guidance

If the job is ERS, this is the only engine. For ordinary stills, the creator may still pick GPT Image 2, but local engines are fine.

## What Co-Director must confirm

Every ERS generate (paid).

## What Co-Director must never claim

That a local engine made the ERS. That setup failure is “offline Qwen.”

## Upstream vs Adept

Upstream GPT Image can do many picture types. Adept ERS law is narrower: one production sheet, required sections.

## Persistence

ERS asset on this project.

## Relationships

- Law: `ers-law`
- Spec: `ers-spec`
- Map: `spatial-map`
