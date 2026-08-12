# Assignment — HelpSystemSubagent

```yaml
role: HelpSystemSubagent

owned_scope:
  - (?) HelpTip component positioning, portal, z-index
  - ensure captions fully visible above UI layers

allowed_files:
  - studio-web/src/components/HelpTip.tsx
  - studio-web/src/styles.css  # .help-tip* / .panel-heading help only

forbidden_files:
  - provider / queue / DB
  - voice/character business logic beyond consuming HelpTip

inputs:
  - creator-first UI rule
  - reported left-clip / z-index issues

required_outputs:
  - Subagent Handoff
  - manual check notes

tests_owned: []

dependencies: []

completion_evidence:
  - docs/release-gate/m42/subagent-handoffs/HelpSystemSubagent.md

escalation_conditions:
  - overflow clipping requires shell layout contract change
```
