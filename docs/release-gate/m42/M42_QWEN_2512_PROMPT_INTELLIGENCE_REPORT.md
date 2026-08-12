# M42 Qwen-Image-2512 Prompt Intelligence Report

## Scope
Implemented a new structured compiler package at `studio-api/app/image_prompting/qwen_2512/` for Qwen-Image-2512 character image prompting, with Korri-specific identity locking, negative constraints, prompt validation, and correction prompt compilation.

No forbidden areas were edited.

## Delivered Files
- `studio-api/app/image_prompting/__init__.py`
- `studio-api/app/image_prompting/qwen_2512/__init__.py`
- `studio-api/app/image_prompting/qwen_2512/compiler.py`
- `studio-api/app/image_prompting/qwen_2512/identity_lock.py`
- `studio-api/app/image_prompting/qwen_2512/style_grammar.py`
- `studio-api/app/image_prompting/qwen_2512/composition_grammar.py`
- `studio-api/app/image_prompting/qwen_2512/character_sheet_grammar.py`
- `studio-api/app/image_prompting/qwen_2512/continuity_rules.py`
- `studio-api/app/image_prompting/qwen_2512/negative_constraints.py`
- `studio-api/app/image_prompting/qwen_2512/prompt_validator.py`
- `studio-api/app/image_prompting/qwen_2512/deviation_corrector.py`
- `studio-api/tests/test_qwen_2512_prompt_compiler.py`
- `studio-api/tests/test_character_identity_lock.py`
- `studio-api/tests/test_character_correction_compiler.py`

## Stable 13-Block Order
The compiler emits this fixed block order for every package:

1. `request_intent`
2. `subject_identity`
3. `identity_lock`
4. `face_features`
5. `wardrobe_materials`
6. `pose_expression`
7. `composition_camera`
8. `environment_lighting`
9. `style_profile`
10. `continuity_references`
11. `character_sheet`
12. `negative_constraints`
13. `output_guardrails`

## Identity Lock Notes
- Compiler input is normalized from canon/profile dictionaries into a structured blueprint.
- The identity compiler does not free-form rewrite Korri's identity from prose. It composes from canonical fields and locked trait lists.
- Korri lock is enforced around:
  - pale skin
  - purple eyes
  - black twin ponytails
  - elongated Sun Sprite Elf ears
  - petite athletic build
  - handmade black clothing
  - wooden accessories
  - light-circuitry markings `(not tattoos)`
- Rejection/negative constraints explicitly cover blonde hair, blue/aqua eyes, human/rounded ears, Anadriya resemblance, and wardrobe drift.

## Validation and Correction
- `prompt_validator.py` checks stable block order, required Korri identity terms, forbidden positive leakage, and correct markings language.
- `deviation_corrector.py` produces a correction prompt that restores identity drift without rebuilding the approved scene/style context.

## Evidence
- Sample compiled prompt: `artifacts/m42/w43-qwen-2512/prompts/korri_compiled_prompt.txt`
- Structured package dump: `artifacts/m42/w43-qwen-2512/prompts/korri_compiled_prompt.json`
- Rejection sample: `artifacts/m42/w43-qwen-2512/prompts/korri_rejection_sample.json`
- Correction sample: `artifacts/m42/w43-qwen-2512/prompts/korri_correction_sample.json`

## Test Result
Executed from `studio-api`:

```text
pytest tests/test_qwen_2512_prompt_compiler.py tests/test_character_identity_lock.py tests/test_character_correction_compiler.py
```

Result: `4 passed in 0.12s`

## Notes For Integration
- `style_grammar.py` intentionally accepts a style profile dictionary only and does not invent a registry.
- The package is isolated and ready for integration by the owning runtime / Co-Director layers.
