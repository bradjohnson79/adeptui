# Session Memory: 2026-09-24 through 2026-09-25

Completed work from the last 48 hours. Branch `feat/character-creator-final-closure`. HEAD `ca8f3c0cc25cf09e665047363cfb4ebecc2bb89b`. These repairs are in the working tree and were not committed. Comfy `:8188` stayed PID 27852 and was not restarted.

A bulk file-time touch at 2026-09-24 10:11 on older Timeline reports is not new completion. Those reports stay historical.

Not completed: the fitted movable ERS legend insert (header, slots, footnote, drag, real Save). Do not treat that as certified.

---

## 1. Co-Director durable single-owner architecture

**GO — CODIRECTOR DURABLE SINGLE-OWNER ARCHITECTURE CERTIFIED**

Chat turns run through one durable owner: admission, one model call, tool authorization, approval, execution, and verification. Fresh closure projects were used. Studio API and Vite were healthy. Comfy was left running.

Evidence: `reports/CODIRECTOR_INFRASTRUCTURE_REBUILD_CERT.md`

## 2. Co-Director 6-test command acceptance

**GO — CODIRECTOR 6-TEST COMMAND ACCEPTANCE CERTIFIED**

Conversation turns that discuss a character beat do not call a tool. A Timeline request prepares a timed prompt and does not place it. An approved Prop Creator identity stays in its owning project and is visible to search without copying the asset. The image tool receipt carries the job id. `legacy_invocation` was 0.

Evidence: `reports/CODIRECTOR_6_TEST_COMMAND_ACCEPTANCE.md`

## 3. Character Creator and reference sheet

**GO — CODIRECTOR CHARACTER CREATOR + CRS ACCEPTANCE CERTIFIED**

A verified character create tells the creator to refresh Character Creator. A reference-sheet request uses `character_creator.propose_visual_sheet`. The server binds one persisted character id before the proposal is stored. The approval card stays in plain language. Ids stay behind Technical details.

Evidence: `reports/CODIRECTOR_CHARACTER_CREATOR_CRS_ACCEPTANCE.md`

## 4. Creator tool completeness

**GO — CODIRECTOR CREATOR TOOL COMPLETENESS CERTIFIED**

Missing side and back views are notes, not a reason to block the front reference. With no approved reference, Character, Prop, and Environment proposals use the existing Qwen Image path. An approved reference is not replaced. A compound Timeline request stores one ordered plan of existing tools.

The tool capability matrix records which routes were admitted after a targeted test. Registry presence alone is not admission.

Evidence: `reports/CODIRECTOR_CREATOR_TOOL_COMPLETENESS_ACCEPTANCE.md`, `reports/CODIRECTOR_TOOL_CAPABILITY_MATRIX.md`

## 5. ERS legend layout and navigation

**GO — ERS EDIT/INPAINT LEGEND + NAVIGATION CERTIFIED**

The editor paints the 2048×1536 sheet. Middle row: Spatial Map, Legend, Structuring. Legend has four character slots and four prop slots. Hand pans. Draw annotates. Zoomed scroll reaches the sheet edges.

Evidence: `reports/ERS_EDIT_INPAINT_LEGEND_NAVIGATION_ACCEPTANCE.md`

## 6. ERS zoom, legend colors, and environment scope

**GO — ERS ZOOM + LEGEND COLORS + ENVIRONMENT SCOPE FIX CERTIFIED**

Zoom max is 12×. Fit returns to 1×. Legend defaults are red, orange, yellow, green, then aqua, blue, purple, gray. A new environment name starts a new sheet. An exact duplicate name stays blocked with: “An environment with this name already exists in this project. Open the existing one or choose a different name.”

Evidence: `reports/ERS_ZOOM_LEGEND_SCOPE_ACCEPTANCE.md`

## 7. Environment Creator provider binding

**GO — ENVIRONMENT CREATOR PROVIDER BINDING CERTIFIED**

The provider dropdown always lists kie.ai, wavespeed.ai, and fal.ai. A provider Setup Wizard has not configured stays visible and disabled. The selected provider is the provider that generates. There is no silent fallback. GPT Image 2.5 is removed from Environment Creator only. GPT Image 2 on fal uses `gpt-image-2-fal` / `openai/gpt-image-2`.

## 8. Character name auto-resolution and approval copy

**GO — CHARACTER AUTO-RESOLUTION + FRONTEND BUILD REPAIR CERTIFIED**

A Timeline scene that names a character uses the existing profile lookup: the current project first, then one exact global match. One match stores the persisted id on the proposal. Zero matches and two exact matches stay in plain language and do not ask for an id. The approval card uses the stored scene, character, prop, and environment names. Technical details stay collapsed.

Evidence: `reports/CHARACTER_AUTO_RESOLUTION_ACCEPTANCE.md`

## 9. Semantic intent authority

**GO — CODIRECTOR SEMANTIC INTENT AUTHORITY CERTIFIED**

The model is the primary reader of what the creator means. The server still decides tool admission, permissions, argument checks, approval, execution, replay, and verified success. Modes are conversation, read, navigate, propose, and mutate. Generic words alone do not mutate. Low confidence cannot mutate. “Don’t apply” cannot stay a mutation. Naming a studio does not by itself select a tool.

Evidence: `reports/CODIRECTOR_SEMANTIC_INTENT_ACCEPTANCE.md`

## 10. Entity resolution and receipt projection

**GO — CODIRECTOR ENTITY RESOLUTION + RECEIPT PROJECTION CERTIFIED**

A unique visible character, including a global profile, binds internally. Incidental words such as “with green” do not discard that match. A search receipt is not shown as chat JSON. The same receipt is not shown twice. The original Timeline request continues into the approval card. Law 39: normal chat is a sentence. Technical details stay collapsed.

Evidence: `reports/CODIRECTOR_ENTITY_RESOLUTION_ACCEPTANCE.md`

## 11. Approval lifetime

**GO — CODIRECTOR APPROVAL LIFETIME CERTIFIED**

The card was not expiring on a three-second timer. It went stale because `project.updated_at` moved a few seconds after the proposal was saved. A project clock change inside the window no longer invalidates the card. The card stays actionable for 60 minutes unless a scene, bible, or plan pin moves, or the proposal is rejected or already completed. After that hour the sentence is: “This approval is no longer current. Ask Co-Director to prepare it again.”

Evidence: `reports/CODIRECTOR_APPROVAL_LIFETIME_ACCEPTANCE.md`
