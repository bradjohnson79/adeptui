# M2.10b Installation Report — `open-mmlab/Amphion`

**Status:** STUB — not installed in this documentation pass.
**Branch:** `phase2/codirector-m2-9-production-suite`
**Start SHA:** `c805d0c5b0b9a535b386ea38d09198460996d828`
**Date:** 2026-07-26
**Provider Manifest sha256 (must remain unchanged):** `cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc`
**Gate 6 product lock sha256:** `7f26170dafccae376ec6227211efd3450338b4c22cb95f5a4fc47c43d7a3419b` (install/execute/weight **false**)
**Phase 0:** `READY FOR M2.10b SANDBOX` — `docs/codirector/m2.10b-phase0-preflight-checkpoint.md`

## Identity

| Field | Value |
| --- | --- |
| Registry ID | `m2101-sfx-030` |
| Source key | `open-mmlab/Amphion` |
| Capability | `audio.sfx.generate` |
| License (discovery) | `MIT` |
| Repository / model URL | `https://github.com/open-mmlab/Amphion` |
| Gate 6 install/execute/weight | **false** (`7f26170dafccae376ec6227211efd3450338b4c22cb95f5a4fc47c43d7a3419b`) |
| Execution-lock scope | Authorized as one of nine audio candidates (M2.10b prompt provenance); lock file fill **pending** |
| Production authorized | **false** |
| Sandbox only | **true** |

## Pinning (pending)

| Field | Value |
| --- | --- |
| Git commit / revision | TBD |
| Model revision | TBD |
| Downloaded file hashes | TBD |
| Environment identifier | TBD |
| Sandbox path | TBD (planned under `data/m210b-sandbox/`) |

## Dependency / security notes

| Item | Value |
| --- | --- |
| Dependencies recorded | PENDING |
| `trust_remote_code` / custom CUDA / Triton / xFormers / FlashAttention / ffmpeg | PENDING |
| Unsafe binary rejection | PENDING |
| License change at install | PENDING — do not auto-accept |

## Runtime

| Check | Result |
| --- | --- |
| Isolated install | PENDING |
| Health check | PENDING |
| Real generation | PENDING |
| VRAM / latency | PENDING |

## Notes

SFX alternate.

## Install run (2026-07-26T21:40:30+00:00)

**Disposition:** not installed.

**Reason:** deferred — heavy deps; Kokoro prioritized for real-generation path

Sandbox dirs scaffolded under `data/m210b-sandbox/providers/` with `install-manifest.json` `installed=false`. No weights downloaded.

---

INSTALLATION FAILED
