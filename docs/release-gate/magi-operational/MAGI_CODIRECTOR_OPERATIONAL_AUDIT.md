# MAGI Co-Director Operational Audit

**Status:** Read-only Phase 0 audit — **superseded by m6 implementation (2026-08-08).**
**Date:** 2026-08-08

> **Law 30 supersede notice:** §1 and §3 below describe the pre-m6 "not-operational"
> state. As of the m6 repair, MAGI is **operational (READ-only)** via Co-Director:
> `magi.inspect_sequence`, `magi.inspect_clip`, `magi.readiness` are registered,
> project-ownership-isolated read tools; `UNSUPPORTED_SYSTEMS` no longer contains
> `magi`. WRITE/PERSIST/VERIFY remain **N/A** (MAGI mutations live inside Adept UI).
> Verified by `tests/test_codirector_native_systems_matrix.py::test_magi_operational_read_only_tools`.

## 1. Current state — MAGI is hard-blocked for Co-Director

- **No `magi_*` tools exist.** `studio-api/app/codirector/tools/handlers/` contains 33 handlers, none MAGI.
- **Hard enforcement:** `codirector/tools/exposure.py:235` `UNSUPPORTED_SYSTEMS: frozenset = frozenset({"magi"})`, plus `assert_unsupported_systems_have_no_tools()` (`:238-255`) which raises at import/call time if any tool derives to the `magi` domain. Enforced by `tests/test_codirector_native_systems_matrix.py:807-823`.

## 2. What does exist

- **Read-only health probe:** `codirector/status/registry.py:729-740` `_probe_magi` → `readiness_payload()`; registered `HealthCheckDefinition(id="magi.readiness", …)` (`:938`, mapped `:962`); deep probe 6.0s (`probe_context.py:38`).
- **Navigation only:** `codirector/tools/handlers/continuity_w5.py:119-129` — `open_workspace` accepts `"magi"` as a deep-link target, "no mutation performed".
- **Lifecycle label:** `codirector/production_lifecycle/service.py:69,108` computes `magiReady` from post status.

## 3. Documented status (consensus across milestones)

- `docs/release-gate/codirector-operational/CODIRECTOR_NATIVE_SYSTEM_OPERATIONS_AUDIT.md` §2.7: "Tools exist: NO. READ/WRITE/PERSIST/VERIFY/UI-SYNC: GAP across all five."
- §4: "MAGI is documented as not-operational via Co-Director. No fictional magi_* tools may be exposed to creators. Capability label: 'Unavailable' or 'Requires Setup'."
- `CODIRECTOR_OPERATIONAL_INTEGRITY_FINAL_CERTIFICATION.md` (2026-08-08, GO): "MAGI ... Not operational — documented and no fictional tools exposed."

## 4. Tool Law (certified Co-Director operational law)

Any new tool must follow: READ → authoritative state; WRITE → proposal where appropriate; APPROVE → native mutation; PERSIST → authoritative save; VERIFY → independent read; UI SYNC → event-driven refresh. No "Done" without verification.

## 5. Mission scope (decision)

**Build real read tools only.**
- Remove `"magi"` from `UNSUPPORTED_SYSTEMS` — ONLY after the native MAGI sequence API is verified (m1-m5 green).
- Add capability-scoped READ-only `magi.*` tools:
  - `magi.inspect_sequence` — authoritative sequence read (projectId-scoped).
  - `magi.inspect_clip` — single clip by immutable `clipId` + projectId.
  - `magi.readiness` — surface readiness (already probed; expose as tool).
- Ownership isolation: every call requires `projectId`; no selection-only targeting; immutable IDs only.
- **No writes/proposals in this milestone** (documented as N/A — do not fabricate).
- Update `test_codirector_native_systems_matrix.py` (replace zero-tools assertion with ownership tests).
- Update Co-Director docs: flip "Not operational" → "Operational (read-only)" with superseded marking per Law 30.

## 6. Required repairs (m6)

1. `exposure.py`: remove `magi` from `UNSUPPORTED_SYSTEMS`.
2. New handler module `codirector/tools/handlers/magi.py` with READ-only tools.
3. Register tool definitions (`definitions.py`) + `registry`.
4. Ownership tests (project isolation, immutable IDs).
5. Docs: Law 30 supersede-marking on `CODIRECTOR_OPERATIONAL_INTEGRITY_FINAL_CERTIFICATION.md` MAGI row.
6. Capability gating: expose only in workspaces/intents that support MAGI; no global fictional exposure.
