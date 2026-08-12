# M42 W1-8 — Output Validation Strategy

| Field | Value |
|---|---|
| **Date** | 2026-07-29 |
| **Module** | `studio-api/app/image_runtime/output_gate.py` |

## Required checks

- Output existence
- Non-zero file size
- Decodable image (PIL)
- Minimum dimensions
- Optional aspect-ratio match
- Metadata capture
- Preview / thumbnail generation (Wave 2 wiring)
- Asset registration only after gate pass

## Rule

**No optimistic success.** Wave 1 ships `validate_image_output()` for architecture proof. Wave 2 enforces it in QueueWorker before job `done`.
