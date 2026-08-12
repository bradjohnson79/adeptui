# M42 Wave 4 — Masking

Mask asset store persists project masks with role, feather, opacity, invert. ImageMaskEditor provides canvas painting for regional edits. QueueWorker stages include PreparingMasks; builders receive mask_image via leaf graph.

EditLayer stack includes a dedicated mask layer for visibility/lock in the workspace.

Artifact: masking_results.json. Gate: MaskingOperational.
