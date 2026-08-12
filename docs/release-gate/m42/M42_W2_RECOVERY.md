# M42 Wave 2 — Recovery

## Retry without duplicate registration

When registration/provenance fails after Output Gate PASS:

- Job status detail: `output_valid_but_unregistered`
- `validated_output_path` retained
- Retry reuses the validated file — does not regenerate unless explicitly requested

Evidence: `artifacts/m42/w2/retry_without_duplicate.json`

## Cancellation

Confirmed cancel must not yield late `completed` jobs or registered assets. Runtime reservation released via existing `cancel_and_halt` path.
