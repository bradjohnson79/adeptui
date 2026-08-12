"""Multi-Shot Image Planning — provider-agnostic scene-to-shots decomposition.

A Multi-Shot Plan decomposes a scene into an ordered collection of shots, each
with its own image-planning context (prompt, framing, references, seed strategy),
a history of generated candidates, and one approved asset. The model layer is
deliberately provider-agnostic: `provider_id` / `model_id` are plain strings, so
Krea 2, Flux, Z-Image, or any future provider can back a plan without schema
changes. Approved outputs reference the shared `Asset` system — generated images
are never stored only inside provider runtime folders.
"""
