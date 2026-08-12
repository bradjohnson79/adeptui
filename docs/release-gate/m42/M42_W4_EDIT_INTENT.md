# M42 Wave 4 — ImageEditIntent

ImageEditIntent is the product edit contract: operation taxonomy, source asset, optional mask/control/reference IDs, EditLayer stack, recipeId, preserve toggles, and CreativeContext digest.

Compiler: compile_edit_request() applies recipe defaults → validates taxonomy → recommends → maps to ImageIntent → resolves with llow_draft=False → pins. No silent family/workflow substitution after pin.

API: /api/image-product/edit/* (recommend, compile, enqueue, batch).

Artifact: rtifacts/m42/w4/edit_intent_results.json.
