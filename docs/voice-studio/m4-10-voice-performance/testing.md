# Testing

## Backend coverage

The focused automated coverage for M4.10 lives in:

- `studio-api/tests/test_m410_voice_performance.py`

That suite covers:

- preset mapping
- emotion-vector validation
- direction-mode persistence
- approved voice identity enforcement
- single approved-take exclusivity
- timeline payload shape
- Lip Sync linkage payload shape
- capability honesty when the runtime is not ready

## Frontend and workflow coverage

The most aligned existing browser test called out by the M4.10 release-gate audit is:

- `tests/e2e/m43/m43-voice-studio.spec.ts`

The repository also still contains older voice-performance browser suites under `tests/e2e/m42/`, but the M4.10 audit notes that some earlier M42 test IDs are partially stale relative to the current Voice Studio shell.

## Runtime verification

For live local runtime verification, M4.10 also provides:

- `POST /api/voice-performance/m410/runtime/verify`
- `scripts/voice_studio/index_tts2_benchmark.py`

Those checks confirm runtime readiness separately from the persistence/unit test coverage.
