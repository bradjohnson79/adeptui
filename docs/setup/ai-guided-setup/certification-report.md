# AI-Guided Setup Certification Report

## Scope completed in this branch

- repository audit hard gate
- lifecycle contracts and service layer
- certified recipe registry
- Co-Director lifecycle tools
- setup mode chooser and AI-Guided panel
- expanded certified image catalog
- Production Dock mapping for new image models
- backend regression tests
- frontend production build

## Evidence captured

- audit: `docs/setup/ai-guided-setup/repository-audit.md`
- recipes: `config/setup/certified-recipes/*.json`
- backend tests: `studio-api/tests/test_setup_lifecycle.py`
- frontend UI: `studio-web/src/setup/lifecycle/AiGuidedSetupPanel.tsx`
- dock mapping: `studio-api/app/production_control/model_registry.py`

## Honest limitations

- The new Playwright spec was added but not executed in this subagent run.
- The AI-Guided UI currently leans on setup/install-job status rather than a separate conversational backend session.
- Some image entries are catalogued as experimental/path-link posture rather than fully automated installers.

## Subagent verdict

READY FOR PRIMARY REVIEW
