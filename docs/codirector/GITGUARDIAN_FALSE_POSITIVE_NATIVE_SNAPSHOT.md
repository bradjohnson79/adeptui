# GitGuardian false positive - `adept-ui-v1.0-native-snapshot.json`

**Date:** 2026-07-26
**Detector:** High-entropy / `apikey`
**Repo:** `bradjohnson79/adeptui`
**Path:** `config/capabilities/adept-ui-v1.0-native-snapshot.json`
**Commit:** `eaf15e4` (`chore(capabilities): freeze native capability snapshot`)
**Severity shown:** High

## Verdict

**FALSE POSITIVE - no secret leaked. No rotation required.**

## What was flagged

GitGuardian's entropy / `apikey` detector matched high-entropy hexadecimal strings in the frozen Native Capability Snapshot. Those strings are:

| Field | Meaning |
| --- | --- |
| `nativeBaselineSha256` | SHA-256 of `adept-ui-v1.0-native.json` |
| `frozenFromTip` | Git commit SHA at freeze time |
| Digests quoted in `freezeNote` | Same baseline / tip hashes for human audit |

Example (not a credential):

```text
630069ff4abe79348f5632236f12796da03e6e79cbb6209198f636f29ac42b57
916c3651e25a6dfab42768a1332b50cfb143dbe4
```

There is no API key, OAuth token, password, or private key in this file. Capability snapshot JSON is intentional public/repo metadata for M2.10 readiness.

## Actions taken in repo

1. Added [`.gitguardian.yaml`](../../.gitguardian.yaml) to ignore `config/capabilities/**` JSON / `.sha256` / schema paths (capability IDs, hashes, and commit tips only).
2. Recorded this disposition note.

## Actions for the operator (GitGuardian UI)

1. Open the incident -> mark as **False positive** (reason: SHA-256 / git tip, not an API key).
2. Optionally attach this doc path as justification.
3. Do **not** rotate Ollama, Comfy, fal, or other credentials on the basis of this alert alone.
4. Confirm no real `.env` / credential files were committed (`.env` remains gitignored).

## Policy reminder

- Secrets stay in local env / secret stores - never in `config/capabilities/`.
- Capability freeze artifacts may contain content hashes and commit SHAs by design.
- Real secret exposures still require rotate -> revoke -> audit.