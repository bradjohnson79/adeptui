# 06 — Gate F Generator knowledge on the production path

**Surface:** CURRENT DEVELOPMENT  
**Date:** 2026-08-29

## Defect

Profiles existed under `studio-api/app/codirector/generator_knowledge/`. `compile_for_generator` was Inspector/API preview only. W46 generate did not call it.

## Repair

`build_timeline_generation_request` now compiles through `compile_for_generator` after assembling the authored prompt.

- If compile is `ok` and non-empty, the compiled prompt is used. Authored text is kept in `providerOptions.authoredPrompt`.
- If the profile is unavailable (hosted Kling/Seedance/Veo, unknown IDs), the authored prompt is kept. Never emptied.
- MiniMax `<subject N>` is emitted only from entity + approved asset + **wired** Route A `ref_images`. Current Route A `ref_images` is `EXIST UNWIRED`, so production MiniMax emits **no** subject tags.
- Decorative / typed tags are stripped. LTX / WAN / Hunyuan dialects never keep MiniMax tags.

## Tests

`pytest tests/test_timeline_knowledge_compile.py tests/test_generator_knowledge.py -q`

## Peer close

- Kimi K3 (`bee0819a`): **PASS WITH NON-BLOCKING** — W46 generate calls `compile_for_generator`; MiniMax `<subject N>` only from wired Route A slots; current Route A `ref_images` is EXIST UNWIRED so no decorative tags. **ACCEPTED NON-BLOCKING**.
- GLM 5.2 (`ac605263`): **PASS** — same trace; LTX/WAN/Hunyuan do not keep MiniMax syntax.

**Gate F: CLOSED**
