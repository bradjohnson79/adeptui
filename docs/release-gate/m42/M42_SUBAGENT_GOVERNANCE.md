# M42 Subagent Governance & End-to-End Double-Check Protocol

**Status:** Binding for all M42 subagent work  
**Authority:** Primary agent only for architecture, integration, final evidence, and binary GO/NO-GO  
**Conditional GO:** Forbidden  

---

## Objective

Use subagents to accelerate M42 implementation while preserving strict ownership, professional integration, full end-to-end wiring, and binary certification.

Subagents may investigate, implement, test, or document only within their assigned scope.

They must not broaden their mandate, edit unrelated systems, redefine architecture, or certify their own work.

The primary agent remains the sole owner of:

* architecture
* task decomposition
* shared contracts
* integration
* conflict resolution
* end-to-end execution
* final evidence
* binary GO/NO-GO certification

---

## 1. Mandatory Role Contract

Every subagent must receive a written assignment containing:

```text
Role
Owned scope
Allowed files
Forbidden files
Inputs
Required outputs
Tests owned
Dependencies
Completion evidence
Escalation conditions
```

No subagent begins work without this contract.

Assignment templates live under `docs/release-gate/m42/subagent-assignments/`.

Ownership matrix: `docs/release-gate/m42/M42_SUBAGENT_OWNERSHIP_MATRIX.md`  
Frozen contracts: `docs/release-gate/m42/M42_SUBAGENT_SHARED_CONTRACTS.md`

---

## 2. Strict Scope Enforcement

```text
Do not edit outside assigned ownership.
Do not silently change shared contracts.
Do not refactor unrelated code.
Do not rename shared APIs without approval.
Do not alter certification gates.
Do not declare milestone completion.
Do not conceal test failures.
Do not replace real execution with mocks.
Do not modify another subagent's files while that task is active.
```

When blocked, a subagent must stop and report:

```text
BLOCKED

Reason:
Required dependency:
Affected owner:
Recommended resolution:
```

The primary agent decides the next action.

---

## 3. Non-Overlapping Ownership

Before launching subagents, consult the ownership matrix. Only one subagent may be the active implementation owner of a file or subsystem.

---

## 4. Shared Contract Freeze

Before parallel work begins, contracts in `M42_SUBAGENT_SHARED_CONTRACTS.md` are frozen.

Subagents may not change these contracts independently.

Any necessary change requires:

```text
Change request
→ impact analysis
→ primary-agent approval
→ contract update
→ notification to all affected subagents
```

---

## 5. Required Subagent Handoff

Each subagent must return a structured handoff (store under `docs/release-gate/m42/subagent-handoffs/`):

```markdown
# Subagent Handoff

## Assignment
## Scope completed
## Files changed
## APIs consumed
## APIs changed
## Tests run
## Test results
## Manual checks
## Evidence
## Known issues
## Risks
## Dependencies still pending
## Recommended integration checks
```

A statement such as “done” is insufficient.

---

## 6. First-Level Double-Check — Peer Review

Every implemented area must be reviewed by a second agent that did not author the change.

The reviewer checks: scope compliance, architecture compliance, code quality, error handling, persistence, accessibility, security, test sufficiency, mock leakage, regression risk.

Verdict:

```text
PASS
or
RETURN FOR CORRECTION
```

The reviewer cannot edit the implementation unless specifically reassigned.

---

## 7. Second-Level Double-Check — Integration Review

After peer review, the primary agent performs integration checks across all touched boundaries (upstream and downstream). A component-level pass is not enough.

---

## 8. Area-Based End-to-End Checklists

### UI work

Route opens; loading / empty / populated / error / disabled states; tooltips; keyboard access; responsive layout; persistence after reload; no hidden broken controls.

### API work

Valid / invalid / unauthorized / locked project; provider failure; timeout; retry; idempotency; response schema; audit logging.

### Provider work

Credential test; model resolution; capability honesty; queue submission; status polling; success / failure / cancellation; no silent provider switch; provenance.

### Asset work

Asset creation; metadata; identity / project / version link; reload; deletion; duplicates; missing-file handling.

### Timeline work

Insert / replace / trim / move; reload; playback; version replacement; undo/redo where applicable; render handoff.

### Co-Director work

Read access; proposal; approval boundary; execution; error explanation; no silent mutation; project authorization; locked-project denial.

---

## 9. Cross-Subsystem Double-Check Matrix

Every row must have evidence under `artifacts/m42/<phase>/<area>/`.

| Source | Destination | Verification |
|---|---|---|
| UI | API | Request shape and errors |
| API | Provider resolver | Canonical intent preserved |
| Resolver | Provider adapter | Correct certified mapping |
| Provider | Queue | Status normalized |
| Queue | Asset Library | Output registered |
| Asset Library | VersionGraph / Identity | Lineage / role links recorded |
| Asset Library | Timeline | Correct asset inserted |
| Timeline | Preview | Playback succeeds |
| Co-Director | Workflow | Approval respected |
| Reload | Persistence | State restored |

---

## 10. Mandatory Real Execution

For any production workflow, the primary agent must run at least one real end-to-end execution.

Character Creator hard-stop path:

```text
Open Korri profile
→ submit generation through Adept UI
→ Adept UI builds ComfyUI workflow
→ ComfyUI executes
→ images return
→ character sheet is assembled
→ assets register
→ Identity Registry links
→ VersionGraph records
→ project reloads
→ generated sheets remain visible
→ visual review confirms acceptable Korri identity
```

No subagent report can replace this execution.

---

## 11. Correction Loop

```text
Identify owner
→ reopen only affected scope
→ issue correction assignment
→ implement fix
→ rerun owned tests
→ rerun peer review
→ rerun affected integration path
→ rerun final end-to-end flow
```

Do not proceed with known unresolved defects.

---

## 12. Test Layer Requirements

Every completed area must pass applicable layers among: static checks, unit, integration, API, UI component, Playwright, manual workflow, persistence reload, security, end-to-end production execution.

A phase may not rely solely on Playwright or solely on unit tests.

---

## 13. Evidence Requirements

Store evidence under:

```text
artifacts/m42/<phase>/<area>/
```

Include where applicable: screenshots, logs, request/response payloads, workflow JSON, generated assets, test output, queue records, provenance, reload evidence, failure/recovery evidence.

Redact secrets and API keys.

---

## 14. Final Primary-Agent Review

Before certification, the primary agent must answer:

```text
Were all subagents confined to scope?
Were all changed areas independently reviewed?
Were shared contracts preserved?
Were all upstream and downstream boundaries tested?
Were real providers or runtimes exercised where required?
Were all outputs persisted and reopened?
Were security boundaries checked?
Were failures handled honestly?
Were all mocks excluded from certification?
Was a complete end-to-end workflow demonstrated?
```

Any `No` means **NO-GO**.

---

## 15. Certification Authority

Subagents may report:

```text
Scope complete
Tests passed
Ready for integration review
```

They may not report:

```text
Phase GO
Milestone certified
Production ready
Blocker resolved
```

Only the primary agent may issue final certification.

---

## 16. Binary Verdict

```text
GO — All assigned areas were completed under enforced ownership, independently reviewed, integrated across subsystem boundaries, tested end-to-end with real execution, persisted, reopened, and professionally certified.
```

or:

```text
NO-GO — One or more ownership, review, integration, security, persistence, testing, evidence, or end-to-end execution requirements remain incomplete. Continue correction and do not advance.
```

No Conditional GO.

---

## Hard-stop priority

Korri Character Creator → ComfyUI real generation remains the hard stop. Voice / Voice Performance work may proceed in parallel only under frozen UI scope and must not distract the primary agent from Korri integration proof.
