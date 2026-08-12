# M42 Wave 2 — Consumer Contract

Authoritative rule: product creates a valid `ImageIntent`; QueueWorker receives or resolves a certified contract; no product surface builds or executes graphs.

## Surface classes

| Class | Requirement |
|---|---|
| execution | Intent + certified contract path |
| enqueue-only | Valid ImageIntent; worker pins contract |
| planning-only | No graph build/execute |
| display-only | No execution |

Harness: `scripts/m42_w2_consumer_contract.py` → `artifacts/m42/w2/consumer_contract_results.json`.

Legacy callers listed in `artifacts/m42/w2/legacy_callers.json` for Wave 3 elimination.
