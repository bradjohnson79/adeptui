# Co-Director / Platform — WAN Residue Removal

**Governing document for removing WAN as a current Adept UI v1.1 product.**

Predecessor (historical, not current WAN-canary authority):

- `docs/release-gate/codirector/CODIRECTOR_100_OPERATIONAL_CONVERGENCE.md` (100% Status still governs score weights; WAN spoken-card canary does not)

---

## Law

WAN is not a current Adept UI v1.1 generator. Co-Director must not teach First and Last Frame WAN as a live product. Status must not use “What is WAN?” as the knowledge-routing canary.

Archival compile, Comfy adapters, and historical release-gate reports stay. Do not delete implementations. Do not restore WAN to fill 3 Frame.

## Replacement canary

| Field | Value |
| --- | --- |
| Query | `What is Timeline?` |
| Spoken | Timeline turns this project's pictures and Prompt Names into video. |
| Status details | `timelineSpokenCard` · `r2vContentNotReimplemented` · `probeQuery` |
| Retired WAN | “WAN is retired in Adept UI v1.1. Timeline uses MiniMax H3 and LTX 2.5 for Reference-to-Video. Do not restore WAN.” |
| Networking | Still Wide Area Network when the creator is clearly talking about networks |

## Inventory

`.runtime/_wan_residue_inventory.json`

## Live proof (2026-09-14)

Project: Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`  
Scene: `d774a22f-2b02-4eb2-b5ab-a98af9ff8f85`  
Evidence: `.runtime/_wan_residue_e2e.json`

| Surface | Result |
| --- | --- |
| `POST /api/codirector/chat` “What is Timeline?” | Timeline spoken card. `fallbackUsed=false` |
| `POST /api/codirector/chat` “What is WAN?” | Retired spoken card. Not Wide Area Network. `fallbackUsed=false` |
| Networking WAN | Wide Area Network |
| `/chat/stream` Timeline + WAN | Same spoken cards |
| Status probe | `routed=true` `landed=true` `timelineSpokenCard=true` `probeQuery=What is Timeline?` retrieved `timeline` |
| Status after warmup | **100 / 0 warnings / 0 blocked** · Operational · 18 healthy |

API recycle: `oldPid=25564` `newPid=30248` `comfyPid=45624` `unchanged=True`

### Tests (observed)

- `test_codirector_platform_knowledge.py` + targeted availability / R2V knowledge tests: **26 passed**
- `engineSurfacePolicy.test.ts`: **11 passed**

### E2E TRACE

| Stage | Verdict |
| --- | --- |
| User action | PASS — “What is Timeline?” / “What is WAN?” |
| Frontend | PASS — source + unit tests; Vite `:5173` was down at handoff start |
| API | PASS — `/chat` `/chat/stream` `/status/check` HTTP 200 |
| Backend | PASS — knowledge hook + Status Timeline canary |
| Persistence | N/A — no project mutation |
| Runtime | PASS — Comfy `:8188` 200, PID **45624** unchanged |
| Result | PASS — retired WAN + Timeline R2V spoken cards |
| Reload | PASS — Status 100 after recycle warmup |
| Downstream | PASS — routing receipt `timeline` |

## COMFY

| | |
| --- | --- |
| COMFY BEFORE | PID **45624** · `GET :8188/system_stats` 200 |
| COMFY AFTER | PID **45624** · `GET :8188/system_stats` 200 |
| COMFY RESTARTED? | **NO** |
| WHY? | Ordinary knowledge/Status/API work. API-only recycle. |

## Limitations

- Comfy Desktop still owns `:8188` (`EXTERNAL` leave-alone). Not adopted, not killed.
- WAN compile files and adapters remain for old-project readability. They are not creator destinations.
- Historical release-gate reports still mention WAN as a then-current canary. Those stay historical.
- Local Vite `:5173` was started for review after it was down. Studio API remains the proven chat/Status surface.

## Verdict

**GO — WAN residue removed from Co-Director knowledge, Status canary, and current creator teaching.**
