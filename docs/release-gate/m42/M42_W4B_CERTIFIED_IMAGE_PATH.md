# M42 Wave 4B — Certified Image Path Wiring

MAGI Apply Edit calls pi.imageProduct.editEnqueue only.

Recipes load from Wave 4 /api/image-product/projects/{id}/recipes.
Masks via Wave 4 mask store + ImageMaskEditor.
Versions/approval via Wave 4 version graph.

No parallel Comfy builders in MAGI package. No product-side queue_prompt.
