# M42 Wave 2 — Output Gate

Atomic sequence:

1. Runtime output produced (temp path)
2. Temporary inspection (exists, nonzero, decodable, min dimensions, aspect)
3. Validation PASS
4. Thumbnail / preview generated
5. Checksum calculated
6. Asset registration committed
7. Provenance committed
8. Job completed

Failure after valid output but before registration → `output_valid_but_unregistered` (not `completed`).
Retry reuses `validated_output_path` unless the user explicitly regenerates.
