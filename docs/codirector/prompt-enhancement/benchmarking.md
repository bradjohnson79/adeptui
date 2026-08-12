# Benchmarking

Offline harness: `scripts/codirector/prompt_intelligence_benchmark.py`

Compares Original / Refined EN / EN+subtle ZH / EN+balanced ZH without generating media.

Outputs: `docs/codirector/prompt-enhancement/benchmarks/offline-prompt-matrix.json`

**Certification rule:** do not set `bilingualCertified: true` without recorded generation evidence.
