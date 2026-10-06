> **SUPERSEDED (2026.09.04).** The Qwen-default line below is stale. Environment Reference Sheets are GPT Image 2 API exclusively. Qwen local is not an ERS fallback. Canonical: `studio-api/app/codirector/knowledgebase/environment-reference-sheet/ERS_SPEC.md` and `workflows/ers-law.md`.

# Environment Reference Sheets

Authoritative Co-Director knowledgebase:

`studio-api/app/codirector/knowledgebase/environment-reference-sheet/`

- `ERS_SPEC.md` - product contract
- `ERS_REFERENCE_01.png` - GPT Image 2 layout exemplar (Venture Corridor)
- `ERS_REFERENCE_02.png` - GPT Image 2 layout exemplar (Korri's Domocile)

Deterministic loader: `studio-api/app/codirector/knowledgebase/ers_loader.py`
Dedicated compiler: `compile_environment_reference_sheet_prompt()` in `ers_compiler.py`
Layout gate: `ERS_LAYOUT_NONCOMPLIANT` in `ers_layout_gate.py`

Exemplars are layout and density only. Never copy their content into a new environment.

Runtime: purpose `environment_reference_sheet`, layout `production_ers`.
Default local generator is Qwen Image. GPT Image 2 is an explicit paid API option.
No silent cloud fallback. One prompt, one image. Not a Character Sheet.
