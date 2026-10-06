# 04 — Multi-Model Review Record

**Method:** independent reviewers (subagents) + live deterministic tool verification + a local
vision-capable reviewer (Ollama gemma4:12b) for image/video evidence, per mission Part 28-29.

## Reviewer roster

| Reviewer | Role | Model / identity | Verdict basis |
|---|---|---|---|
| Subagent A | Timeline architecture audit | independent LLM auditor | read-only code audit, reuse map, generator classification |
| Subagent B | Wiring / state integrity | independent LLM auditor | 32 field-chains traced, WIRED/PARTIAL/BROKEN classes |
| Subagent C | Creator UX / workflow review | independent LLM auditor | track matrix, blockers, Beta-readiness verdict |
| Vision reviewer | Visual evidence (source images) | gemma4:12b via local Ollama (vision-capable) | verified source images match prompt intent (hallway + spokesperson in navy blazer) |
| Reviewer 4 (tiebreak) | Cross-batch / continuity evidence | deterministic production-state checks + candidate re-review | batch isolation, source-image binding, prompt correspondence from persisted state |

## Disagreements and resolution

1. **Timed Prompt lane vs Batch Inspector prompt (BROKEN #1).** Subagents B and C both flagged the lane
   as disconnected from generation. Resolution: implemented the legacy↔master reconciliation
   (reconcile.py) and verified live that lane prompts reach the generator request.
2. **Retake surfaces.** Subagent B flagged the legacy Re-take drawer as a disconnected parallel system,
   while the wired w46 batch retake (inspector) is the production path. Resolution: certified the wired
   path; the legacy drawer remains (load-bearing for the Final Systems gate) and is documented as legacy.
3. **MiniMax H3 readiness.** Subagent A verified model files exist but the capability is flag-gated
   (Testing). Resolution: MiniMax is NOT used as the governing live generator — LTX (Certified) is.
4. **generatedDuration honesty.** Live evidence showed generatedDuration=5.0 while the real media is
   8.04 s. Resolution: adapter now surfaces the output-gate-measured duration (unit-tested); the earlier
   approved run's media is real (ffprobe-verified) and the metadata fix is regression-tested.

## Vision review evidence (gemma4:12b, local)

Source image shot1-establishing.png prompt: "modern hallway with a person in a navy blazer at the far
end". Reviewer reply: "YES. The image shows a woman in a navy blazer standing in a modern, wood-paneled
hallway." — source media matches authored intent.

Hosted VLM paths were probed honestly: Kie chat returns HTTP 200 with empty output in this environment
(adapter reports ok=False); fal vision endpoints are not provisioned for this key. The local gemma4:12b
vision path was used instead; this limitation is disclosed (no fake visual pass is claimed).