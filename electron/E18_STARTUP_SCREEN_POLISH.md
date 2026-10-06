# Adept UI 1.1 Electron — Startup Screen Polish

Presentation and status-display correction for the packaged startup screen. Boot ownership, ports, and the GO rule for required checks are unchanged. Cloud 1.2 is removed from the Adept UI 1.1 boot inventory.

## What was wrong

The screen drew two inventories at once: the runtime snapshot and every boot check, labeled only by system name. That produced repeated Studio API and Creator UI rows.

The GO line came from Boot. The sentence “A few essentials are still missing.” came from the Setup catalog. On this machine the only Setup item marked required and not ready is VideoChat3 4B. Boot does not require it, and Boot’s verdict is GO. Those two statements were being shown together.

Cloud 1.2 was inserted in `evaluate()` as a non-required check. It did not decide GO, but it was still in the boot inventory.

## What changed

- One visible row per system. Distinct checks stay in the certification report.
- Sections: Core Runtime, Production Systems, Optional / On Demand.
- Completed startup says “Startup Complete” and “ALL REQUIRED SYSTEMS ONLINE”.
- GO and a required failure cannot be shown together. A required failure says “ADEPT UI SETUP REQUIRED” and names the check.
- Setup items that Boot does not require are named under “Optional setup available”. They are not called essentials.
- `http://127.0.0.1:8760` is a footer line.
- The Cloud 1.2 check is gone from the 1.1 boot contract. Cloud provider source remains in the repo.

## Live packaged result

Unpacked `Adept UI.exe` launched with a temporary profile. Boot on `http://127.0.0.1:8760`:

- verdict GO
- progress 100
- runtime mode electron-packaged
- 19 checks, 0 failed, 0 Cloud 1.2
- the screen names VideoChat3 4B as optional setup and still shows ADEPT UI READY — GO

Screenshots:

- `electron/evidence/startup-screen/default-1440x900.png`
- `electron/evidence/startup-screen/maximized.png`

A 760px-wide window collapses the cards to one column. Labels and badges do not overlap.

## Tests

- `studio-web` vitest `startupDisplay.test.ts` + `startupSnapshot.test.ts`: 18 passed
- `studio-api/tests/test_boot_certification.py`: 15 passed

## Boundaries

- BOOT VERDICT RULE CHANGED = NO. GO still means every required boot check passed.
- PORT ARCHITECTURE CHANGED = NO. Packaged Studio API 8760. Dev API 8758. Comfy 8188.
- COMFY BEFORE: PID 31048, HTTP 200
- COMFY AFTER: PID 31048, HTTP 200
- COMFY RESTARTED = NO
- Live `data/studio.db` SHA-256 unchanged: `275953ec5e485d8f50967b9c7522a55a75073a0a862c0230ae01ded429ba4326`
- The long-running dev API on 8758 was not recycled.

## Matrix

| Check | Result |
| --- | --- |
| STARTUP SCREEN LOAD | PASS |
| DEFAULT WINDOW LAYOUT | PASS |
| MAXIMIZED LAYOUT | PASS |
| OUTER MARGINS | PASS |
| CARD PADDING | PASS |
| SECTION SPACING | PASS |
| AMBIGUOUS DUPLICATE LABELS | 0 |
| REQUIRED VS OPTIONAL CLASSIFICATION | PASS |
| GO + MISSING REQUIRED CONTRADICTION | 0 |
| OPTIONAL ITEMS BLOCK GO | 0 |
| MISSING ITEMS NAMED | PASS |
| FINAL STATUS COPY | PASS |
| ALL REQUIRED SYSTEMS ONLINE COPY | PASS |
| ENDPOINT DISPLAY | PASS |
| STUDIO API :8760 | PASS |
| BOOT VERDICT | GO |
| FUNCTIONAL REGRESSIONS | 0 |
| COMFY RESTARTED | NO |
| ADEPT UI 1.1 BOOT INVENTORY | PASS |
| CLOUD 1.2 PRESENT IN BOOT INVENTORY | NO |
| CLOUD 1.2 PRESENT ON STARTUP SCREEN | NO |
| CLOUD 1.2 AFFECTS READINESS | NO |
| CLOUD 1.2 AFFECTS PROGRESS | NO |
| CLOUD 1.2 AFFECTS WARNINGS | NO |
| CLOUD 1.2 SOURCE ACCIDENTALLY DELETED | NO |

ADEPT UI ELECTRON STARTUP SCREEN POLISH — FULL GO
