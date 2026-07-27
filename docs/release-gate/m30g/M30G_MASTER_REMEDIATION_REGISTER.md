# M30G Master Remediation Register

| Field | Value |
|-------|-------|
| Branch | `phase2/codirector-m2-9-production-suite` |
| Starting SHA | `77c664c77a5a3caf6347ea32080f8b6a346a35cd` |
| Provider Manifest SHA | `cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc` **LOCKED** |
| Date | 2026-07-27 |

Historical packs preserved (not overwritten):
- `docs/release-gate/production-certification/`
- `docs/release-gate/model-intelligence/`
- `docs/release-gate/multilingual/`

## Inherited open items

| ID | Source | Requirement | Blocks M3.0g YES? | Blocks Brad beta? | Disposition target |
|----|--------|-------------|-------------------|-------------------|--------------------|
| A11Y | M3.0d/f | Accessibility GREEN (axe archive + keyboard + SR) | Yes | Yes | Close with archived evidence |
| B16 | M3.0d | Live multi-specialist diversity | Yes unless CLAIM NARROWED | Yes if claim kept | VERIFIED or CLAIM NARROWED |
| PW-S4 | M3.0d | Local-live Playwright | Env | Partial | Document env gate |
| PW-S5 | M3.0d | Local-live artifact | Env | Partial | Document env gate |
| PW-S6 | M3.0d | fal-live Playwright | Partial | Partial | Superseded by MI-LIVE for music-off |
| MI-LIVE | M3.0e | Live fal `generate_audio=false` + audio class | Yes | Yes | Live proof or BLOCKED→NO |
| LTX-AUDIO | M3.0e | BEST_EFFORT_EXTERNAL_AUDIO honesty | Disclose | No | Preserve |
| LI-LING | M3.0f | Non-en MACHINE_DRAFT honesty | No if disclosed | No | Dual verdict |
| LI-TECH | M3.0f | Multilingual technical integration | Yes | Yes | GREEN/NOT GREEN |
| RTL | M3.0f | ar/ur RTL certification | Yes | Yes | GREEN evidence |
| CANON | M3.0f | Glossary/canon protection | Yes | Yes | Automated suite |
| ML | M3.0f | Mixed-language workflows | Yes | Yes | ML-01..06 |
| EN-REG | M3.0f | English regression after LI | Yes if broken | Yes | E2E-01 |
| LOC-ISO | M3.0f | UI locale isolation | Yes if broken | Yes | LOC-ISO tests |

## Scenario ID families

A11Y-01..20 · MI-LIVE-01..05 · LI-01..20 · RTL-01..12 · CANON-01..12 · ML-01..10 · E2E-01..08 · SMOKE-01..25 · REC-01..08 · SEC-01..15 · EN-REG · LOC-ISO · B16
