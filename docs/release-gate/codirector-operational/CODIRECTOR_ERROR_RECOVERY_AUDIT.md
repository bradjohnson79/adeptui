# Co-Director Operational Integrity Audit — Error Recovery & Truthful Reporting

**Milestone:** Co-Director Operational Integrity Audit
**Date:** 2026-08-07
**Status:** AUDIT COMPLETE — repairs tracked in milestone phases c6/c7
**Repo:** `C:\AdeptFilmWorks\AIVideoStudio`
**Audit scope:** Co-Director error model, error propagation paths (tool -> service -> SSE/sync -> creator), result normalization/scrubbing, and truthful-reporting guarantees across the `INTENT -> TOOL ROUTING` pathway.
**Audit mode:** READ-ONLY. No files modified; no non-readonly commands run during source investigation.
**Governing instrument:** Governing audit for the error-recovery and truthful-reporting surface under Build Law 30. Complements `CODIRECTOR_ROUTING_AUDIT.md` (phases c2/c3) and `CODIRECTOR_APPROVAL_PERSISTENCE_AUDIT.md` (phase c7). Supersedes prior informal error-propagation notes for this milestone.
**Sources of truth:** `data/tmp/codirector-audit-sources/routing-report.md`, `tool-registry-report.md`, `state-isolation-report.md`, `native-systems-report.md`, plus direct verification against the current tree (see Section 8).

---

## 1. Executive Summary

Co-Director's error model is a single structured exception (`CoDirectorError`) carrying a stable `code`, a creator-facing `message`, bounded/redacted `details`, a `recoverable` flag, and a `recommended_action`. Every code maps to an HTTP status and a UI category, so a provider timeout, a capability block, a stale proposal, and a handler crash all surface as typed envelopes rather than tracebacks. The error boundary is enforced at two trust borders in `studio-api/app/codirector/tools/sanitize.py`: model-supplied arguments are validated against the declared schema (unknown keys dropped, types coerced, limits enforced), and handler results are scrubbed of secret-shaped strings and absolute filesystem paths, depth/breadth-capped, and truncated to a per-tool character budget with an explicit `_truncated` signal rather than a silent cut.

The propagation chain is sound at its core: tool failures raise `CoDirectorError`, which is caught in `_run_read_tool` / `_propose_tool_call` / the audited-write branch and re-emitted as `tool_failed` / `capability_blocked` SSE events with the error envelope attached; the model is then instructed via `follow_up_prompt` to admit the failure plainly. Every attempt (succeeded, failed, or capability-blocked) is written to `codirector_tool_invocations` by `_log_invocation`, so the database alone answers "what did Co-Director actually do, and what was it prevented from doing."

The audit identified **five defects** in the truthful-reporting surface. None defeat the unforgeability invariant, but each allows the model to make truthful-sounding claims the pipeline cannot automatically retract or verify:

1. Streamed false-success tokens cannot be retracted (grounding can only substitute when the reply is empty).
2. Silent JSON repair in `_validate_or_repair` fabricates specialist findings without surfacing an error.
3. Synthesis `confidence` is a hardcoded constant (0.88 / 0.62), overstating confidence for heuristic-only syntheses.
4. Generic-error collapse: handler `Exception` branches flatten structured upstream errors into one `TOOL_EXECUTION_FAILED` envelope, losing recoverability classification.
5. No post-tool state-diff verification reconciles model prose against `invocation.result`.

Repairs for defects 1-5 are mapped to milestone phase c6 in Section 7.

## 2. Error Model

### 2.1 `CoDirectorError` structure

Defined in `studio-api/app/codirector/errors.py:103-136`:

```103:136:studio-api/app/codirector/errors.py
@dataclass
class CoDirectorError(Exception):
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    recoverable: bool = True
    recommended_action: str = "retry"

    def __str__(self) -> str:
        return self.message

    def to_dict(self) -> dict[str, Any]:
        explicit_key = self.details.get("messageKey") if isinstance(self.details, dict) else None
        details = dict(self.details) if isinstance(self.details, dict) else {}
        partial = bool(details.get("partialWorkCreated") or details.get("partial_work_created") or False)
        return {
            "code": self.code, "error_code": self.code,
            "category": category_for_code(self.code), "message": self.message,
            "messageKey": explicit_key or f"errors.code.{self.code}", "details": details,
            "recoverable": self.recoverable, "retryable": self.recoverable,
            "project_id": details.get("projectId") or details.get("project_id"),
            "provider": details.get("provider"), "model": details.get("model"),
            "technical_evidence": _safe_evidence(details), "partial_work_created": partial,
            "recommendedAction": self.recommended_action, "recommended_action": self.recommended_action,
        }
```

The five fields the task requires verified are all present and authoritative:

| Field | Source | Notes |
|---|---|---|
| `code` | `errors.py:105` | Stable string constant (e.g. `PROVIDER_UNAVAILABLE`, `TOOL_EXECUTION_FAILED`, `PROPOSAL_STALE`). Constants at `errors.py:139-243`. |
| `message` | `errors.py:106` | Creator-facing prose, authored at the raise site; never constructed by parsing provider output. |
| `details` | `errors.py:107` | Free-form dict, scrubbed at emission by `_safe_evidence` (`errors.py:69-100`): skips `token`/`apiKey`/`raw`/`arguments`/`stack`, caps strings to 400 chars, lists to 20 items, dicts to 12 keys, 24 top-level entries. |
| `recoverable` | `errors.py:108` | Default `True`. Set `False` for `PROJECT_NOT_FOUND`, `PROPOSAL_NOT_FOUND`, `TOOL_KIND_MISMATCH`, schema-version mismatch, terminal-state guards. |
| `recommended_action` | `errors.py:109` | Default `retry`. Other values: `retry_or_check_service`, `revise_arguments`, `select_project`, `unlock_project_in_ui`, `preview_again`, `none`. |

### 2.2 Code -> status -> category

`status_code_for_error` (`errors.py:338-339`) resolves a code to an HTTP status via `_STATUS_BY_CODE` (`errors.py:246-335`). `category_for_code` (`errors.py:30-66`) resolves a code to `model | project | tool | validation | provider | runtime`. Both are exhaustive over declared constants; an unknown code falls back to HTTP 500 and category `runtime`. A provider outage (503), a stale proposal (409), a capability block (409/503), and a handler crash (502) are distinguishable by the client without parsing prose.

### 2.3 Secret redaction

`redact_secrets` (`errors.py:20-27`) strips Bearer tokens, `key=value`-shaped secrets, `sk-` prefixes, and 16+ hex blobs before they reach `details` or logs. `_safe_evidence` applies it again at emission. This is the second trust border (the first is `sanitize.scrub_text` on results; see Section 4).

## 3. Error Propagation Paths

### 3.1 Tool failure -> service -> SSE event

The chat-stream tool loop lives in `_interpret_reply` (`studio-api/app/codirector/service.py:684`). It dispatches to three branches; each wraps its `ToolExecutionService` call in `try/except CoDirectorError` that re-emits a typed SSE event and stores the error on the shared `outcome` so the sync path can also surface it.

**Read tools** (`_run_read_tool`, `service.py:534-622`). On `CoDirectorError` it distinguishes capability blocks from handler failures:

```568:594:studio-api/app/codirector/service.py
    except CoDirectorError as err:
        outcome.error = err
        if _capability_error(err):
            yield {"type": "capability_blocked", "requestId": request_id, "toolId": tool_call.tool_id,
                   "kind": "read", "arguments": dict(tool_call.arguments),
                   "capability": err.details.get("capability"), "error": err.to_dict()}
        else:
            yield {"type": "tool_failed", "requestId": request_id, "toolId": tool_call.tool_id,
                   "kind": "read", "arguments": dict(tool_call.arguments), "error": err.to_dict()}
        outcome.follow_up_prompt = (
            f"The `{tool_call.tool_id}` tool could not run: {err.message} "
            "Tell the user plainly what you cannot check right now, and help them with what you "
            "do know. Do not request another tool.")
        return
```

The `follow_up_prompt` is the truthful-reporting lever: the model is instructed to admit the failure in plain prose and is forbidden from requesting another tool. A failed read cannot be dressed up as a success because the model never sees a success-shaped result.

**Mutating tools (proposal path)** (`_propose_tool_call`, `service.py:625-681`). On `CoDirectorError` it emits `capability_blocked` or `tool_failed` with the same envelope and returns without creating a proposal. Because `propose` never applies anything, a proposal-creation failure is itself a no-op on authoritative state; there is nothing to retract.

**Audited writes (`production_plan.create_draft` only)** (`service.py:749-798`). Structurally identical: `execute_audited` raises `CoDirectorError`, the branch emits `tool_failed` and returns. The `tool_completed` receipt with `unapprovedDraft: True` (`service.py:791-797`) is emitted only on success.

> Routing note (verified, not in source reports): The chat-stream audited-write branch is hardcoded to `{"production_plan.create_draft"}` (`service.py:753`). The three other `requires_approval=False` tools (`audio.cancel_batch`, `minimax_h3.offer_ltx_fallback`, `minimax_h3.cancel`) are declared no-approval in the registry but are NOT special-cased here, so via the chat stream they fall through to `_propose_tool_call` (`service.py:800`) and become approval-gated proposals. They can still execute immediately through the direct `/projects/{project_id}/tools/audited` endpoint (`routers/codirector.py:1884`), which honors `requires_approval` generically. This drift is tracked in the Approval/Persistence audit (phase c7); it does not affect error propagation, which is identical on both paths.

### 3.2 Sync response path

On the sync path, `outcome.errors` is filtered for fatal codes (`STRUCTURED_OUTPUT_INVALID`, `TOOL_LOOP_LIMIT_REACHED`) at `service.py:1006-1009`; a fatal error short-circuits the response with the error envelope. Non-fatal tool errors are still surfaced as events but do not abort the turn; the model is expected to address them in prose via `follow_up_prompt`.

### 3.3 Invocation audit logging (success AND failure)

`_log_invocation` (`studio-api/app/codirector/tools/execution.py:146-185`) is the single ledger writer. It is called on every terminal state:

- **Blocked** (`execution.py:287-298` read; `:488-499` audited; `:591-602` propose): logged with `status="blocked"` and the capability error *before* the error is raised, so a blocked tool leaves the same audit trail as a successful one.
- **Failed - CoDirectorError** (`execution.py:329-342` read; `:514-527` audited; `:724-738` approved): logged with `status="failed"`, `error_code`, `error_message`, then re-raised.
- **Failed - generic Exception** (`execution.py:343-363` read; `:528-548` audited; `:739-760` approved): wrapped into `TOOL_EXECUTION_FAILED` with a 200-char scrubbed `reason`, logged, then raised `from exc` (preserves the chain for server logs without leaking the traceback to the client).
- **Succeeded** (`execution.py:374-386` read; `:551-563` audited; `:763-776` approved): logged with `status="succeeded"`, the sanitized/truncated `result`, `result_hash`, and `result_truncated`.

The ledger row (`CoDirectorToolInvocation`) records `project_id`, `tool_id`, `tool_schema_version`, `kind`, `status`, `arguments_json`, `result_json`, `result_hash`, `result_truncated`, `capability_snapshot_json`, `error_code`, `error_message`, `proposal_id`, `request_id`, `duration_ms`, `created_by`, `created_at`. This is the durable evidence trail required by Build Law 31.

## 4. Result Normalization

### 4.1 Argument sanitization (first trust border)

`sanitize_arguments` (`studio-api/app/codirector/tools/sanitize.py:90-110`) validates model-supplied arguments against the tool's declared `ToolDefinition.parameters`:

```90:110:studio-api/app/codirector/tools/sanitize.py
def sanitize_arguments(definition: ToolDefinition, raw: Any) -> dict[str, Any]:
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise _invalid(definition.tool_id, "Tool arguments must be a JSON object.")
    declared = {p.name: p for p in definition.parameters}
    out: dict[str, Any] = {}
    for name, param in declared.items():
        if name not in raw or raw[name] is None or raw[name] == "":
            if param.required:
                raise _invalid(definition.tool_id, f"'{name}' is required.", parameter=name)
            continue
        out[name] = _coerce(param, raw[name], definition.tool_id)
    return out
```

Unknown keys are **dropped, not rejected** (comment `:93-94`): a model inventing an extra field must not fail an otherwise valid call, but that field can never reach a handler. The sanitized dict is what gets stored on a proposal, so approving a proposal can only replay what the registry would accept today. This is the foundation of the argument-pinned replay guarantee (see Approval/Persistence audit).

### 4.2 Result scrubbing (second trust border)

`scrub_text` (`sanitize.py:140-143`) applies `_ABS_PATH_RE` (strips Windows `C:\..` and POSIX `/usr/..` paths to `<path>`) over `redact_secrets`. `_scrub` (`sanitize.py:146-169`) enforces structural caps: `MAX_STRING_CHARS=1200`, `MAX_LIST_ITEMS=50`, `MAX_DICT_KEYS=60`, `MAX_DEPTH=6` (returns `<nested>` past depth, appends `<N more omitted>` past list cap, sets `_omittedKeys` past dict cap).

### 4.3 Char budget and `_truncated` signalling

`sanitize_result` (`sanitize.py:172-202`) is the size-cap the task asks to verify. It returns `(payload, truncated)`:

```172:202:studio-api/app/codirector/tools/sanitize.py
def sanitize_result(value: Any, *, char_budget: int) -> tuple[dict[str, Any], bool]:
    scrubbed = _scrub(value if isinstance(value, dict) else {"value": value}, 0)
    serialized = json.dumps(scrubbed, default=str)
    if len(serialized) <= char_budget:
        return scrubbed, False
    kept = dict(scrubbed)
    dropped: list[str] = []
    by_size = sorted(kept.items(), key=lambda kv: len(json.dumps(kv[1], default=str)), reverse=True)
    for key, _ in by_size:
        if len(json.dumps(kept, default=str)) <= char_budget:
            break
        if len(kept) <= 1:
            break
        kept.pop(key, None)
        dropped.append(key)
    kept["_truncated"] = True
    if dropped:
        kept["_omittedFields"] = dropped
    if len(json.dumps(kept, default=str)) > char_budget:
        return {"_truncated": True, "_reason": "Result exceeded this tool's size budget."}, True
    return kept, True
```

Per-tool budgets are declared in `definitions.py` (e.g. `result_char_budget=20000` for the wide readers, `=12000` for narrow ones; `DEFAULT_RESULT_CHAR_BUDGET=4000` at `definitions.py:38`). The `_truncated` flag is surfaced to the caller as a `tool_result_truncated` SSE event (`service.py:605-611`) and to the model via `render_result_for_model` (`sanitize.py:209-213`), which appends "(Result was truncated to fit its size budget.)". Neither the model nor the user is silently handed a partial answer they think is complete — this is the explicit truncation signal required by Build Law 8 (no silent behavior).

### 4.4 Result hash and idempotency

`result_hash` (`sanitize.py:205-206`) is a SHA-256 over the sorted-key JSON of the sanitized payload, stored on the invocation row. `compute_input_hash` (`sanitize.py:113-132`) is the idempotency key for tool proposals: same `toolId + toolSchemaVersion + arguments + baseResourceVersions` = same execution. Both are stored server-side; the model cannot influence them.

## 5. Defects (root cause + file:line)

### 5.1 Defect 1 — Streamed false-success claims cannot be retracted

**Root cause:** `evaluate_grounding` (`studio-api/app/codirector/conversation/foundation/grounding.py:103`) runs *after* the stream has already emitted tokens to the creator. The post-stream handler at `service.py:1790-1793` can only substitute the fallback reply when the streamed `reply` is empty:

```1790:1793:studio-api/app/codirector/service.py
            if not grounding.ok and (core.fallbackReply or "").strip():
                # Prefer streamed reply; only substitute when empty.
                if not reply.strip():
                    reply = (core.fallbackReply or "").strip()
```

If the model already streamed "Done — I added the scene," the grounding gate can flag a violation (`NO_FAKE_WIKI_CLAIMS` at `grounding.py:202-203`, `EXPLORATION_NOT_CANONIZED` at `:186`, claimed tool use under `tool_policy=NONE` at `:98`) but **cannot retract the tokens**. The user sees the false claim. For wiki claims specifically, a downstream `wiki_status.prematureClaim` flag (`service.py:1957-1988`) is emitted, but for non-wiki false-success claims (e.g. "I created the scene") there is no automatic correction — only the `STRUCTURED_OUTPUT_INVALID` path is fatal. This is a truthful-reporting gap, not an unforgeability gap.

### 5.2 Defect 2 — Silent JSON repair in `_validate_or_repair`

**Root cause:** `SpecialistRunner._validate_or_repair` (`studio-api/app/codirector/intelligence/specialist_runner.py:344-364`) catches `ValidationError`, fabricates defaults for every missing field, sets `contentDropped` from `_has_substantive_content`, and re-validates:

```344:364:studio-api/app/codirector/intelligence/specialist_runner.py
    def _validate_or_repair(self, definition, raw):
        normalized = self._normalize_provider_payload(raw)
        normalized.setdefault("specialistId", definition.id)
        try:
            return SpecialistFinding.model_validate(normalized)
        except ValidationError:
            repaired = dict(normalized)
            content_dropped = not self._has_substantive_content(normalized)
            repaired["summary"] = str(repaired.get("summary") or definition.display_name)
            repaired["recommendation"] = str(repaired.get("recommendation") or repaired["summary"])
            repaired["requirements"] = list(repaired.get("requirements") or [])
            # ... all list fields defaulted to [] ...
            repaired["contentDropped"] = content_dropped
            return SpecialistFinding.model_validate(repaired)
```

When a specialist's raw payload fails validation, the runner silently substitutes the specialist's `display_name` as both `summary` and `recommendation`, empties every structured list, and returns a "valid" finding. The only signal is the internal `contentDropped` boolean; no error is raised, no warning is surfaced to the creator, and the fabricated finding flows into `synthesize` (Section 5.3) as if it were real evidence. This violates Build Law 8 (no silent behavior) and Law 11 (failure recovery): a malformed specialist output is presented as a substantive finding.

### 5.3 Defect 3 — Synthesis confidence overstatement

**Root cause:** `Synthesizer.synthesize` (`studio-api/app/codirector/intelligence/synthesis.py:23-87`) assigns a fixed confidence regardless of evidence quality:

```86:86:studio-api/app/codirector/intelligence/synthesis.py
            confidence=0.88 if not blockers else 0.62,
```

`confidence` is `0.88` whenever no specialist reported a blocker and `0.62` otherwise. It does not factor whether the findings came from real provider calls or from `_heuristic_finding` (`specialist_runner.py:438`), which is the fallback when no provider is available and which labels its output with `LIMITED_ANALYSIS_ASSUMPTION` (`specialist_runner.py:102`). A heuristic-only synthesis — where every finding is a fabricated default (Defect 5.2) — still reports `0.88` confidence if no blocker was raised. This overstates the reliability of the recommendation and violates Law 32 (Co-Director intelligence must be transparent and evidence-backed, not conversation history alone).

### 5.4 Defect 4 — Generic-error collapse risk

**Root cause:** Every `execute_read` / `execute_audited` / `execute_approved_proposal` handler wraps non-`CoDirectorError` exceptions in a single envelope, e.g. `execution.py:343-350`:

```343:350:studio-api/app/codirector/tools/execution.py
        except Exception as exc:  # noqa: BLE001 - a handler bug must not leak a traceback
            err = CoDirectorError(
                TOOL_EXECUTION_FAILED,
                f"The '{definition.tool_id}' tool couldn't complete.",
                details={"toolId": definition.tool_id, "reason": sanitize.scrub_text(str(exc))[:200]},
                recoverable=True,
                recommended_action="retry",
            )
```

The same pattern appears at `execution.py:528-535` (audited) and `:739-746` (approved). Any structured error raised by a downstream service that is not a `CoDirectorError` (e.g. a `pydantic.ValidationError`, a DB integrity error, a provider's own typed exception) is flattened into `TOOL_EXECUTION_FAILED` with a 200-char scrubbed `reason` string. The original `code`, `recoverable`, and `recommended_action` are lost; the envelope always says `recoverable=True, recommended_action="retry"` even when the underlying failure is non-retryable (e.g. a uniqueness violation). This collapses distinct failure modes into one opaque bucket, degrading the creator's ability to choose the right recovery action.

### 5.5 Defect 5 — No post-tool state-diff verification

**Root cause:** After `execute_read` (`execution.py:226`) or `execute_audited` (`execution.py:438`) completes, the pipeline logs the invocation receipt and feeds `invocation.result` back to the model, but it does **not** re-read native state to confirm the model's prose ("I added X") matches the actual change. The only verification is the wiki-specific `WikiWriteVerification` (`conversation/wiki_verification.py`), which is deferred and explicitly never blocks TTFT (`WIKI_VERIFICATION_NEVER_BLOCKS_TTFT = True` at `conversation/wiki_verification.py:10`). For all non-wiki tools, the model's prose is not reconciled against `invocation.result`; the invocation ledger records what happened, but nothing checks that what the model *said* happened matches. Combined with Defect 5.1, a model can stream a false-success claim and have nothing in the pipeline contradict it for non-wiki, non-structured-output cases.

## 6. Truthful-Reporting Assessment

### 6.1 Where the system never claims success before verification

The architecture enforces truthful reporting at four structural points:

1. **Mutating tools never auto-execute via the model.** `_propose_tool_call` (`service.py:625`) creates a durable proposal; the model cannot claim "done" because nothing happened. The `tool_proposal_created` event (`service.py:676-681`) is what the creator sees. The model gets no second say at approval — `execute_approved_proposal` replays `payload.arguments` stored at proposal time (`execution.py:697-723`), and the schema version is guarded (`execution.py:711`, `registry.py:1243-1257`).
2. **Read-tool failure is fed back as a constraint.** `outcome.follow_up_prompt` (`service.py:589-593`) instructs the model to admit the failure and forbids another tool request. The model never receives a success-shaped result for a failed read.
3. **The `responseType` is unforgeable.** `extract_tool_block` (`structured_output.py:161-169`) derives `response_type` from `definition.kind`, not from the model's claimed `responseType`. A model claiming `read_tool_call` for a mutating tool is not honored.
4. **Wiki success claims are gated.** `orchestrate.py` detects premature wiki-success language and flags `fake_wiki` when `documentation.candidate_count == 0`; the grounding gate emits `NO_FAKE_WIKI_CLAIMS` (`grounding.py:202-203`); the streaming path separately emits `wiki_status.prematureClaim` (`service.py:1957-1988`).

### 6.2 Where the system can claim success before verification

| Surface | What can slip through | Why |
|---|---|---|
| Streamed non-wiki false-success prose | "I created the scene" cannot be retracted once streamed | Defect 5.1: grounding can only substitute when reply is empty |
| Specialist findings from heuristic fallback | Fabricated `summary`/`recommendation` presented as evidence | Defect 5.2: `_validate_or_repair` silently defaults |
| Synthesis confidence on heuristic-only runs | `0.88` reported regardless of evidence quality | Defect 5.3: hardcoded constant |
| Handler crashes from structured upstream errors | Recoverability classification lost | Defect 5.4: generic `TOOL_EXECUTION_FAILED` collapse |
| Model prose vs. actual state for non-wiki tools | No reconciliation after `execute_read`/`execute_audited` | Defect 5.5: no post-tool state-diff |
| `production_plan.create_draft` audited write | Model can truthfully say "I created a plan"; no gate prevents implying it is approved | `service.py:791-797` receipt carries `unapprovedDraft: True` but nothing forces the model to mention it |

The net assessment: the **unforgeability invariant holds** — the model cannot cause a mutating write without a human-approved proposal, and cannot pass a read failure as a read success. The **truthful-reporting invariant is partial** — it holds for proposal creation, read failures, and wiki claims, but does not hold for streamed non-wiki prose, heuristic specialist output, synthesis confidence, or post-tool prose reconciliation.

## 7. Repair Recommendations (mapped to milestone phase c6)

Phase c6 owns error-recovery and truthful-reporting repairs. Each repair references the defect it closes.

| ID | Defect | Repair | Files touched | Acceptance |
|---|---|---|---|---|
| c6.1 | 5.1 Streamed false-success cannot be retracted | Emit a `correction` SSE event when grounding flags a violation on a non-empty streamed reply; render the correction inline in the chat transcript so the creator sees the retraction adjacent to the false claim. Do not attempt token rewriting (infeasible over SSE); make the correction the authoritative follow-up. | `service.py` (post-stream grounding branch ~:1790), `conversation/foundation/grounding.py`, frontend `CoDirectorSession.tsx` event handler | A Playwright scenario where the mock model streams a false "I created the scene" claim produces a visible `correction` event in the transcript; the creator is not left with the uncorrected claim. |
| c6.2 | 5.2 Silent JSON repair | When `_validate_or_repair` catches `ValidationError` and `content_dropped` is true, raise a `SPECIALIST_OUTPUT_INVALID` `CoDirectorError` (recoverable, `recommended_action=retry`) instead of returning a fabricated finding. Only fall back to defaults when `content_dropped` is false (cosmetic repair). Surface the drop in the synthesis `conflictsResolved` list. | `intelligence/specialist_runner.py:344-364`, `errors.py` (add `SPECIALIST_OUTPUT_INVALID`) | A unit test feeding a malformed specialist payload produces a `SPECIALIST_OUTPUT_INVALID` error, not a silent finding. |
| c6.3 | 5.3 Synthesis confidence overstatement | Derive `confidence` from evidence quality: weight each finding by whether it came from a real provider call vs. `_heuristic_finding` (track an `evidenceTier` on `SpecialistFinding`). Cap heuristic-only syntheses at `0.45` and mixed at `0.7`; reserve `0.88` for all-real-provider syntheses with no blockers. Include the tier breakdown in `SynthesisResult.conflictsResolved`. | `intelligence/synthesis.py:86`, `intelligence/specialist_runner.py` (add `evidenceTier`), `intelligence/contracts.py` (`SpecialistFinding`) | A test with only heuristic findings reports confidence <= 0.45; a test with all-real-provider findings and no blockers reports 0.88. |
| c6.4 | 5.4 Generic-error collapse | In the `except Exception` branches, if `exc` is a `pydantic.ValidationError` or carries a structured `code`, preserve the original `code`/`recoverable`/`recommended_action` on the wrapped `CoDirectorError` instead of forcing `TOOL_EXECUTION_FAILED`/`recoverable=True`/`retry`. Only collapse truly unknown exceptions to `TOOL_EXECUTION_FAILED`. | `tools/execution.py:343-363, 528-548, 739-760` | A test where a handler raises a `pydantic.ValidationError` produces an error envelope whose `code` reflects validation, not `TOOL_EXECUTION_FAILED`. |
| c6.5 | 5.5 No post-tool state-diff | For audited writes and approved proposals, after `apply` succeeds, re-read the affected resource (per `definition.pinned_resources`) and include a `stateDiff` summary in the invocation result. The model's `follow_up_prompt` should be augmented with the verified state so it cannot claim something the diff contradicts. | `tools/execution.py` (post-apply in `execute_audited`/`execute_approved_proposal`), `service.py` (`follow_up_prompt` construction) | A test where the model claims "I added field X" but the diff shows X absent surfaces a contradiction event; the creator sees the verified state. |

### 7.1 Out-of-phase note (tracked in c7)

The chat-stream audited-write routing drift (Section 3.1 note) — where `audio.cancel_batch`, `minimax_h3.offer_ltx_fallback`, and `minimax_h3.cancel` are declared `requires_approval=False` but routed as proposals via chat — is an approval/persistence concern and is tracked under phase c7 in `CODIRECTOR_APPROVAL_PERSISTENCE_AUDIT.md`. It is noted here only because it touches the same `_interpret_reply` dispatch.

## 8. Verification log

Every citation in this document was spot-verified against the current tree on 2026-08-07. The table records each verified citation and any correction from the source reports.

| # | Citation (as used in this doc) | Verified at | Source report claim | Correction |
|---|---|---|---|---|
| 1 | `errors.py:103-136` `CoDirectorError` | errors.py:103-136 | routing-report: CoDirectorError structure | None. |
| 2 | `errors.py:69-100` `_safe_evidence` | errors.py:69-100 | routing-report: redaction | None. |
| 3 | `errors.py:246-335` `_STATUS_BY_CODE` | errors.py:246-335 | routing-report: status mapping | None. |
| 4 | `errors.py:20-27` `redact_secrets` | errors.py:20-27 | routing-report: secret redaction | None. |
| 5 | `sanitize.py:90-110` `sanitize_arguments` | sanitize.py:90-110 | tool-registry-report §5.1 | None. |
| 6 | `sanitize.py:140-143` `scrub_text` | sanitize.py:140-143 | routing-report: scrubbing | None. |
| 7 | `sanitize.py:172-202` `sanitize_result` + `_truncated` | sanitize.py:172-202 | routing-report: char budgets | None. |
| 8 | `execution.py:146-185` `_log_invocation` | execution.py:146-185 | routing-report: invocation logging | None. |
| 9 | `execution.py:226` `execute_read` | execution.py:226 | routing-report: read path | None. |
| 10 | `execution.py:438` `execute_audited` | execution.py:438 | routing-report: audited writes | None. |
| 11 | `execution.py:566` `propose` | execution.py:566 | routing-report: propose | None. |
| 12 | `execution.py:685` `is_stale` | execution.py:685 | routing-report: staleness | None. |
| 13 | `execution.py:697-723` `execute_approved_proposal` (argument-pinned replay) | execution.py:697-723 | routing-report: replay | None. |
| 14 | `execution.py:711` schema-version check | execution.py:711 (`check_schema_version` call) | routing-report: schema guard | None. |
| 15 | `execution.py:343-363` generic Exception collapse (read) | execution.py:343-363 | Defect 5.4 root cause | None. |
| 16 | `service.py:684` `_interpret_reply` | service.py:684 | routing-report: tool loop | None. |
| 17 | `service.py:534-622` `_run_read_tool` | service.py:534-622 | routing-report: read tool | None. |
| 18 | `service.py:568-594` capability/tool_failed + follow_up_prompt | service.py:568-594 | routing-report: read failure feedback | None. |
| 19 | `service.py:625-681` `_propose_tool_call` | service.py:625-681 | routing-report: propose path | None. |
| 20 | `service.py:749-798` audited-write branch | service.py:749-798 | routing-report: audited writes | None. |
| 21 | `service.py:753` hardcoded `{"production_plan.create_draft"}` | service.py:753 | Not in source reports | **New finding**: 3 of 4 no-approval tools not routed via chat audited branch. Tracked in c7. |
| 22 | `service.py:1790-1793` empty-reply fallback only | service.py:1790-1793 | routing-report §(d) gap 1 | None. |
| 23 | `service.py:1957-1988` `wiki_status.prematureClaim` | service.py:1957-1988 | routing-report §(d) gap 1 | None. |
| 24 | `service.py:1006-1009` fatal error filter (sync) | service.py:1006-1009 | routing-report: malformed tool calls | None. |
| 25 | `structured_output.py:161-169` `responseType` unforgeable | structured_output.py:161-169 | routing-report §(b) | None. |
| 26 | `grounding.py:103` `evaluate_grounding` | grounding.py:103 | routing-report §(d) gap 6 | None. |
| 27 | `grounding.py:202-203` `NO_FAKE_WIKI_CLAIMS` | grounding.py:202-203 | routing-report §(d) gap 6 | None. |
| 28 | `specialist_runner.py:344-364` `_validate_or_repair` | specialist_runner.py:344-364 | routing-report §(d) gap 5 | None. |
| 29 | `specialist_runner.py:438` `_heuristic_finding` | specialist_runner.py:438 | routing-report §(d) gap 5 | None. |
| 30 | `specialist_runner.py:102` `LIMITED_ANALYSIS_ASSUMPTION` | specialist_runner.py:102 | routing-report §(d) gap 5 | None. |
| 31 | `synthesis.py:23-87` `synthesize` | synthesis.py:23-87 | routing-report §(d) gap 5 | None. |
| 32 | `synthesis.py:86` `confidence=0.88 if not blockers else 0.62` | synthesis.py:86 | routing-report §(d) gap 5 | None. |
| 33 | `conversation/wiki_verification.py:10` `WIKI_VERIFICATION_NEVER_BLOCKS_TTFT` | conversation/wiki_verification.py:10 | routing-report said `wiki_verification.py:10` | **Correction**: actual path is `conversation/wiki_verification.py:10` (the routing-report omitted the `conversation/` parent). The existing `CODIRECTOR_ROUTING_AUDIT.md` already uses the corrected path; this doc follows suit. |
| 34 | `registry.py:1243-1257` `check_schema_version` | registry.py:1243-1257 | routing-report: schema guard | None. |
| 35 | `definitions.py:38` `DEFAULT_RESULT_CHAR_BUDGET=4000` | definitions.py:38 | tool-registry-report: budgets | None. |
| 36 | `routers/codirector.py:1884` `/tools/audited` endpoint | routers/codirector.py:1884 | Not in source reports | **New finding**: direct audited endpoint honors `requires_approval` generically; confirms c7 drift. |

### 8.1 Summary of corrections

- One path correction: `wiki_verification.py:10` -> `conversation/wiki_verification.py:10` (citation 33). The source `routing-report.md` omitted the `conversation/` package parent; the canonical `CODIRECTOR_ROUTING_AUDIT.md` already uses the corrected path.
- Two new findings not present in the source reports: (a) the chat-stream audited-write branch is hardcoded to `production_plan.create_draft` only (citation 21), and (b) the direct `/tools/audited` endpoint honors `requires_approval` generically (citation 36). Both are routed to phase c7 in the Approval/Persistence audit; neither changes the error-propagation conclusions in this document.

---

## 9. Verdict

**AUDIT COMPLETE.** The error model and propagation chain are structurally sound: the unforgeability invariant holds, every attempt is durably logged, and read failures cannot be presented as successes. The truthful-reporting surface has five defects (Section 5), all preserved for phase c6 repair. No defect in this document is a release blocker on its own, but Defects 5.1 and 5.2 should be closed before any Co-Director capability that streams non-wiki success claims or relies on specialist evidence is certified GO under Law 31.

