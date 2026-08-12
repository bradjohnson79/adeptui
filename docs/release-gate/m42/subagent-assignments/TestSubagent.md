# Assignment — TestSubagent

```yaml
role: TestSubagent

owned_scope:
  - Playwright M42 voice/character specs
  - honest reporting of soft-skips as incomplete evidence

allowed_files:
  - tests/e2e/m42/m42-w43-korri-voice-creator.spec.ts
  - tests/e2e/m42/m42-w44-voice-performance.spec.ts
  - tests/e2e/m42/** (read; edit only assigned specs)

forbidden_files:
  - product feature implementation (except adding testids via owner)
  - certification binary verdict docs

inputs:
  - governance protocol §12
  - shared contracts

required_outputs:
  - Subagent Handoff with pass/fail/skip counts
  - list of soft-skips

tests_owned:
  - the two specs above

dependencies:
  - beta runtime READY

completion_evidence:
  - docs/release-gate/m42/subagent-handoffs/TestSubagent.md
  - artifacts/m42/governance/voice-ux/playwright-* if run

escalation_conditions:
  - tests require API contract change
```
