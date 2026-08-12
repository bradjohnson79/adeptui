# M42 Wave 2 — Image Provenance

QueueWorker writes `ImageProvenance` into asset `prompt_meta_json` on successful registration.

Required fields include workflow, version, provider, prompt, seed, references, parentImages, validation/gate result, and checksum settings.

For `zimage.ref_edit`, reference content hash and parent/reference graph edges are recorded.
