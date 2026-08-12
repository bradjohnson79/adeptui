# AI-Guided Setup Architecture

## Purpose

AI-Guided Setup adds a creator-facing Provider Lifecycle Manager on top of existing trusted setup systems. Co-Director recommends and proposes. Source Manager and setup services execute.

## Runtime shape

1. `setup/catalog.py` remains the canonical setup component inventory.
2. `setup/status.py` remains the canonical creator-facing readiness surface.
3. `setup/lifecycle/` adds lifecycle contracts, certified recipe loading, certification persistence, calibration defaults, and monitor views.
4. `source_manager/install_jobs/service.py` remains the trusted installer entrypoint.
5. `codirector/tools/handlers/setup_guided.py` exposes discovery and proposal-gated setup tools.
6. `production_control/model_registry.py` reads setup-driven posture so Production Dock reflects install/certification state honestly.

## Trust boundary

- Co-Director may search, compare, explain, and propose.
- Source verification goes through Source Manager.
- Install/repair/verify actions go through existing setup/install-job services.
- Certification records document the result; they do not replace live verification.

## Frontend shape

- `SetupWizard.tsx` now persists a mode preference: `Guided`, `AI-Guided`, `Manual`.
- `AiGuidedSetupPanel.tsx` renders:
  - creator brief input
  - recommended setup cards
  - install plan review
  - grouped lifecycle catalog
  - cloud provider separation
  - calibration/certification actions
  - monitor warnings

## Data flow

1. Setup status fetch returns component posture plus lifecycle metadata.
2. AI-Guided panel reads lifecycle APIs for plans, cloud providers, monitoring, calibration, and certification.
3. Install progress continues to come from `useInstallJobsPoll`.
4. Production Dock maps model IDs back to setup components and upgrades labels from setup status.
