# Qwen2512PromptIntelligence Handoff

## Completed
- Added `studio-api/app/image_prompting/qwen_2512/` with a structured Qwen-Image-2512 prompt compiler and helpers.
- Added Korri identity lock enforcement, negative constraints, validation, and correction prompt compilation.
- Added owned unit tests and generated evidence artifacts under `artifacts/m42/w43-qwen-2512/prompts/`.

## Key Contracts
- Main entry point: `app.image_prompting.qwen_2512.compile_character_image_prompt`
- Correction entry point: `app.image_prompting.qwen_2512.compile_correction_prompt`
- Compiler returns a `CharacterImagePromptPackage` with:
  - fixed 13-block order
  - full prompt text
  - negative prompt text
  - block map
  - identity lock payload
  - validation result
  - normalized blueprint

## Korri Guarantees
- Preserves pale skin, purple eyes, black twin ponytails, elongated Sun Sprite Elf ears, petite athletic build, handmade black clothing, wooden accessories, and light-circuitry markings `(not tattoos)`.
- Rejects blonde hair, blue/aqua eyes, human/rounded ears, Anadriya resemblance, and wardrobe drift.

## Test Status
- `pytest tests/test_qwen_2512_prompt_compiler.py tests/test_character_identity_lock.py tests/test_character_correction_compiler.py`
- Result: `4 passed in 0.12s`

## Evidence Paths
- `artifacts/m42/w43-qwen-2512/prompts/korri_compiled_prompt.txt`
- `artifacts/m42/w43-qwen-2512/prompts/korri_compiled_prompt.json`
- `artifacts/m42/w43-qwen-2512/prompts/korri_rejection_sample.json`
- `artifacts/m42/w43-qwen-2512/prompts/korri_correction_sample.json`

## Expected Next Step
Integrate this package from the owning Co-Director/runtime layer without changing the block order or weakening the Korri lock semantics.
