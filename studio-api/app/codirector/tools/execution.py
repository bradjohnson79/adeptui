"""ToolExecutionService: run read tools, propose mutating tools, execute approved proposals.

Entry points and the asymmetry between them is the whole security model:

- `execute_read` runs immediately, because read handlers have no write path.
- `execute_audited` runs immediate audited writes that opt out of human proposal
  (Wave 4 `production_plan.create_draft` only — drafts stay non-authoritative).
- `propose` never executes anything. It validates arguments, computes a server-side preview,
  pins the resource versions it was built against, and hands a durable `tool_call` proposal to
  `ProposalService`.
- `execute_approved_proposal` is called *only* by `ProposalService.approve` — after a human
  decision has been recorded — and replays the arguments stored on the proposal, not anything
  the model says at approve time.

Every attempt (including a capability-blocked one) is written to `codirector_tool_invocations`,
so "what did Co-Director actually do, and what was it prevented from doing" is answerable from
the database alone.
"""

from __future__ import annotations

import contextvars
import json
import os
import time
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from ...db import CoDirectorProposal, CoDirectorToolInvocation, Project
from ..errors import (
    PROJECT_NOT_FOUND,
    TOOL_EXECUTION_FAILED,
    TOOL_PAYLOAD_INVALID,
    TOOL_VERSION_UNSUPPORTED,
    CoDirectorError,
)
from . import sanitize
from . import registry as tool_registry
from .capabilities import CapabilityAdapter, CapabilityState
from .definitions import (
    TOOL_SCHEMA_VERSION,
    ToolAvailability,
    ToolCallPayload,
    ToolContext,
    ToolDefinition,
    ToolInvocationOut,
    ToolPreview,
)
from .read_cache import clear_project, get_cached, put_cached
from .read_envelope import wrap_handler_result

MAX_INVOCATION_PAGE = 100


def _e2e_execution_fault() -> bool:
    """E2E-only: force an approved tool to fail at apply time.

    A proposal that validates at creation time can't be made to fail on approval by choosing
    bad arguments — the registry rejects those up front. Playwright still needs to see the
    failed-receipt path, so it is injected here, gated on `STUDIO_E2E` and the existing
    mock-scenario variable, exactly like the capability overrides in `capabilities.py`.
    """

    from ..service import e2e_enabled

    if not e2e_enabled():
        return False
    return (os.environ.get("ADEPT_CODIRECTOR_MOCK_SCENARIO") or "").strip().lower() == "mutation_tool_execution_failure"


# Ambient unlock grant token for the current Co-Director request (never a password).
_UNLOCK_TOKEN: contextvars.ContextVar[str] = contextvars.ContextVar("adept_project_unlock_token", default="")


def set_request_unlock_token(token: str | None) -> contextvars.Token:
    return _UNLOCK_TOKEN.set((token or "").strip())


def reset_request_unlock_token(tok: contextvars.Token) -> None:
    _UNLOCK_TOKEN.reset(tok)


def _require_project(db: Session, project_id: str, *, unlock_token: str | None = None) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise CoDirectorError(
            PROJECT_NOT_FOUND,
            "Project not found.",
            details={"projectId": project_id},
            recoverable=False,
            recommended_action="none",
        )
    try:
        from ...project_security import service as project_security

        if project_security.is_protected(db, project_id):
            token = (unlock_token if unlock_token is not None else _UNLOCK_TOKEN.get()).strip()
            if not project_security.is_unlocked(db, project_id, token):
                raise CoDirectorError(
                    "PROJECT_LOCKED",
                    "This project is password protected. Unlock it before I access its production data.",
                    details={"projectId": project_id, "messageKey": "PROJECT_LOCKED"},
                    recoverable=True,
                    recommended_action="unlock_project_in_ui",
                )
    except CoDirectorError:
        raise
    except Exception:
        pass
    return project


def _row_to_out(row: CoDirectorToolInvocation) -> ToolInvocationOut:
    def _load(raw: Optional[str], fallback: Any) -> Any:
        if not raw:
            return fallback
        try:
            return json.loads(raw)
        except Exception:
            return fallback

    return ToolInvocationOut(
        id=row.id,
        projectId=row.project_id,
        toolId=row.tool_id,
        toolSchemaVersion=row.tool_schema_version,
        kind=row.kind,  # type: ignore[arg-type]
        status=row.status,
        arguments=_load(row.arguments_json, {}),
        result=_load(row.result_json, None),
        resultTruncated=bool(row.result_truncated),
        resultHash=row.result_hash,
        errorCode=row.error_code,
        errorMessage=row.error_message,
        proposalId=row.proposal_id,
        requestId=row.request_id,
        durationMs=row.duration_ms,
        createdBy=row.created_by,
        createdAt=row.created_at.isoformat() if row.created_at else "",
    )


def _log_invocation(
    db: Session,
    *,
    project_id: str,
    definition: ToolDefinition,
    status: str,
    arguments: dict[str, Any],
    capability_snapshot: dict[str, Any],
    result: Optional[dict[str, Any]] = None,
    result_truncated: bool = False,
    error: Optional[CoDirectorError] = None,
    proposal_id: Optional[str] = None,
    request_id: Optional[str] = None,
    duration_ms: int = 0,
    created_by: str = "assistant",
) -> ToolInvocationOut:
    row = CoDirectorToolInvocation(
        id=str(uuid.uuid4()),
        project_id=project_id,
        tool_id=definition.tool_id,
        tool_schema_version=definition.schema_version,
        kind=definition.kind,
        status=status,
        arguments_json=json.dumps(arguments, default=str),
        result_json=json.dumps(result, default=str) if result is not None else None,
        result_hash=sanitize.result_hash(result) if result is not None else None,
        result_truncated=1 if result_truncated else 0,
        capability_snapshot_json=json.dumps(capability_snapshot, default=str),
        error_code=error.code if error else None,
        error_message=error.message if error else None,
        proposal_id=proposal_id,
        request_id=request_id,
        duration_ms=duration_ms,
        created_by=created_by,
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _row_to_out(row)


class ToolExecutionService:
    # ---------------- availability ----------------

    @staticmethod
    async def availability(db: Session, project_id: str) -> tuple[list[ToolAvailability], dict[str, Any]]:
        adapter = CapabilityAdapter(db, project_id)
        states = await adapter.snapshot()
        out: list[ToolAvailability] = []
        for definition in tool_registry.all_definitions():
            readiness = await adapter.readiness_for_tool(definition.tool_id)
            state = states.get(definition.capability)
            available = bool(readiness.get("callable"))
            status = str(readiness.get("status") or (state.status if state else "unknown"))
            reason = None
            if not available:
                if readiness.get("proposalReady"):
                    missing = ", ".join(readiness.get("missingCapabilities") or [])
                    reason = f"Proposal may be created, but execution is blocked: {missing}"
                else:
                    reason = state.reason if state else "Unknown capability."
            # Read tools require callable. Mutating tools may still be offered when
            # proposalReady even if execution dependencies are blocked.
            offered = available or (definition.kind == "mutating" and bool(readiness.get("proposalReady")))
            out.append(
                ToolAvailability(
                    toolId=definition.tool_id,
                    available=offered,
                    capability=definition.capability,
                    capabilityStatus=status,
                    reason=reason,
                    errorCode=None if offered else (state.error_code() if state else None),
                )
            )
        return out, {k: v.to_dict() for k, v in states.items()}

    # ---------------- read ----------------

    @staticmethod
    async def execute_read(
        db: Session,
        *,
        project_id: str,
        tool_id: str,
        arguments: Any,
        scene_id: Optional[str] = None,
        request_id: Optional[str] = None,
        created_by: str = "assistant",
        adapter: Optional[CapabilityAdapter] = None,
        tool_schema_version: Optional[int] = None,
    ) -> ToolInvocationOut:
        """Run a read tool now. Raises `CoDirectorError` for anything the caller must surface.

        A capability block and a handler failure are both logged as invocations before the error
        propagates, so a blocked tool leaves the same audit trail as a successful one.

        Handler return values stay typed domain dicts; this boundary wraps the canonical
        retrieval envelope for conversational + Project Content consumers.
        """

        _require_project(db, project_id)
        definition = tool_registry.require_kind(tool_id, "read")

        if tool_schema_version is not None and int(tool_schema_version) != int(definition.schema_version):
            raise CoDirectorError(
                TOOL_VERSION_UNSUPPORTED,
                f"Tool schema version {tool_schema_version} is unsupported for '{definition.tool_id}'.",
                details={
                    "toolId": definition.tool_id,
                    "requestedVersion": tool_schema_version,
                    "supportedVersion": definition.schema_version,
                    "registrySchemaVersion": TOOL_SCHEMA_VERSION,
                },
                recoverable=False,
                recommended_action="none",
            )

        # Reconnect / client retry: same requestId must not re-execute a successful read.
        if request_id:
            prior = (
                db.query(CoDirectorToolInvocation)
                .filter(
                    CoDirectorToolInvocation.project_id == project_id,
                    CoDirectorToolInvocation.tool_id == definition.tool_id,
                    CoDirectorToolInvocation.request_id == request_id,
                    CoDirectorToolInvocation.status == "succeeded",
                    CoDirectorToolInvocation.kind == "read",
                )
                .order_by(CoDirectorToolInvocation.created_at.desc())
                .first()
            )
            if prior is not None:
                return _row_to_out(prior)

        adapter = adapter or CapabilityAdapter(db, project_id)

        state = await adapter.state_for(definition.capability)
        snapshot = {definition.capability: state.to_dict()}
        if not state.available:
            error = state.as_error(definition.tool_id)
            _log_invocation(
                db,
                project_id=project_id,
                definition=definition,
                status="blocked",
                arguments={},
                capability_snapshot=snapshot,
                error=error,
                request_id=request_id,
                created_by=created_by,
            )
            raise error

        clean_args = sanitize.sanitize_arguments(definition, arguments)
        ctx = ToolContext(
            db=db,
            project_id=project_id,
            scene_id=scene_id,
            request_id=request_id,
            capabilities=adapter.cached_states(),
        )

        started = time.monotonic()
        cached = get_cached(project_id, definition.tool_id, clean_args)
        if cached is not None:
            result, truncated = sanitize.sanitize_result(cached, char_budget=definition.result_char_budget)
            return _log_invocation(
                db,
                project_id=project_id,
                definition=definition,
                status="succeeded",
                arguments=clean_args,
                capability_snapshot=snapshot,
                result=result,
                result_truncated=truncated,
                request_id=request_id,
                created_by=created_by,
                duration_ms=int((time.monotonic() - started) * 1000),
            )

        try:
            raw = await tool_registry.read_handler(definition.tool_id)(ctx, clean_args)
        except CoDirectorError as err:
            _log_invocation(
                db,
                project_id=project_id,
                definition=definition,
                status="failed",
                arguments=clean_args,
                capability_snapshot=snapshot,
                error=err,
                request_id=request_id,
                created_by=created_by,
                duration_ms=int((time.monotonic() - started) * 1000),
            )
            raise
        except Exception as exc:  # noqa: BLE001 - a handler bug must not leak a traceback
            err = CoDirectorError(
                TOOL_EXECUTION_FAILED,
                f"The '{definition.tool_id}' tool couldn't complete.",
                details={"toolId": definition.tool_id, "reason": sanitize.scrub_text(str(exc))[:200]},
                recoverable=True,
                recommended_action="retry",
            )
            _log_invocation(
                db,
                project_id=project_id,
                definition=definition,
                status="failed",
                arguments=clean_args,
                capability_snapshot=snapshot,
                error=err,
                request_id=request_id,
                created_by=created_by,
                duration_ms=int((time.monotonic() - started) * 1000),
            )
            raise err from exc

        enveloped = wrap_handler_result(
            tool_id=definition.tool_id,
            tool_version=definition.schema_version,
            project_id=project_id,
            request_id=request_id,
            raw=raw,
        )
        put_cached(project_id, definition.tool_id, clean_args, enveloped)
        result, truncated = sanitize.sanitize_result(enveloped, char_budget=definition.result_char_budget)
        return _log_invocation(
            db,
            project_id=project_id,
            definition=definition,
            status="succeeded",
            arguments=clean_args,
            capability_snapshot=snapshot,
            result=result,
            result_truncated=truncated,
            request_id=request_id,
            created_by=created_by,
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    # ---------------- propose ----------------

    @staticmethod
    def base_resource_versions(
        db: Session, *, project_id: str, definition: ToolDefinition, arguments: dict[str, Any]
    ) -> dict[str, Optional[str]]:
        """Pin the state a mutating proposal was built against.

        Only the resources the tool actually depends on are pinned, so an unrelated Bible edit
        doesn't invalidate a pending scene rename (and vice versa).
        """

        from ... import project_service, scene_service as scene_helpers
        from ...services.scene_service import SceneService
        from ...capabilities.errors import CapabilityError
        from ..bible import operations as ops

        versions: dict[str, Optional[str]] = {}
        for resource in definition.pinned_resources:
            if resource == "bible":
                bible = ops.get_bible(db, project_id)
                versions["bible"] = bible.current_version_id if bible else None
            elif resource == "project":
                versions[f"project:{project_id}"] = project_service.project_version_token(
                    db.get(Project, project_id)
                )
            elif resource == "scene":
                scene_id = str(arguments.get("sceneId") or "")
                scene = None
                if scene_id:
                    try:
                        scene = SceneService.get(db, project_id, scene_id)
                    except CapabilityError:
                        scene = None
                versions[f"scene:{scene_id}"] = scene_helpers.scene_fingerprint(scene) if scene else None
            elif resource == "plan":
                plan_id = str(arguments.get("planId") or "")
                token = None
                if plan_id:
                    try:
                        from ..plans.service import PlanService

                        plan = PlanService.get(db, project_id, plan_id)
                        token = str(plan.version)
                    except CoDirectorError:
                        token = None
                versions[f"plan:{plan_id}"] = token
        return versions

    @staticmethod
    async def execute_audited(
        db: Session,
        *,
        project_id: str,
        tool_id: str,
        arguments: Any,
        scene_id: Optional[str] = None,
        request_id: Optional[str] = None,
        created_by: str = "assistant",
        adapter: Optional[CapabilityAdapter] = None,
    ) -> ToolInvocationOut:
        """Run an audited mutating tool that does not require human proposal approval.

        Only tools with `requires_approval=False` are accepted. Wave 4 uses this for
        `production_plan.create_draft` so conversational drafting stays fluid while remaining
        durable, idempotent, and non-authoritative.
        """

        _require_project(db, project_id)
        definition = tool_registry.require_kind(tool_id, "mutating")
        if definition.requires_approval:
            raise CoDirectorError(
                TOOL_EXECUTION_FAILED,
                f"'{definition.tool_id}' requires an approved proposal.",
                details={"toolId": definition.tool_id},
                recoverable=False,
                recommended_action="none",
            )

        if request_id:
            prior = (
                db.query(CoDirectorToolInvocation)
                .filter(
                    CoDirectorToolInvocation.project_id == project_id,
                    CoDirectorToolInvocation.tool_id == definition.tool_id,
                    CoDirectorToolInvocation.request_id == request_id,
                    CoDirectorToolInvocation.status == "succeeded",
                    CoDirectorToolInvocation.kind == "mutating",
                )
                .order_by(CoDirectorToolInvocation.created_at.desc())
                .first()
            )
            if prior is not None:
                return _row_to_out(prior)

        adapter = adapter or CapabilityAdapter(db, project_id)
        state = await adapter.state_for(definition.capability)
        snapshot = {definition.capability: state.to_dict()}
        if not state.available:
            error = state.as_error(definition.tool_id)
            _log_invocation(
                db,
                project_id=project_id,
                definition=definition,
                status="blocked",
                arguments={},
                capability_snapshot=snapshot,
                error=error,
                request_id=request_id,
                created_by=created_by,
            )
            raise error

        clean_args = sanitize.sanitize_arguments(definition, arguments)
        if request_id and "requestId" not in clean_args:
            clean_args["requestId"] = request_id
        ctx = ToolContext(
            db=db,
            project_id=project_id,
            scene_id=scene_id,
            request_id=request_id,
            capabilities=adapter.cached_states(),
        )
        started = time.monotonic()
        try:
            raw = tool_registry.mutation_handler(definition.tool_id).apply(ctx, clean_args)
        except CoDirectorError as err:
            _log_invocation(
                db,
                project_id=project_id,
                definition=definition,
                status="failed",
                arguments=clean_args,
                capability_snapshot=snapshot,
                error=err,
                request_id=request_id,
                created_by=created_by,
                duration_ms=int((time.monotonic() - started) * 1000),
            )
            raise
        except Exception as exc:  # noqa: BLE001
            err = CoDirectorError(
                TOOL_EXECUTION_FAILED,
                f"The '{definition.tool_id}' tool couldn't complete.",
                details={"toolId": definition.tool_id, "reason": sanitize.scrub_text(str(exc))[:200]},
                recoverable=True,
                recommended_action="retry",
            )
            _log_invocation(
                db,
                project_id=project_id,
                definition=definition,
                status="failed",
                arguments=clean_args,
                capability_snapshot=snapshot,
                error=err,
                request_id=request_id,
                created_by=created_by,
                duration_ms=int((time.monotonic() - started) * 1000),
            )
            raise err from exc

        # A successful write invalidates the project's short-lived read cache so the model's
        # next read reflects authoritative post-mutation state, not a pre-write snapshot.
        clear_project(project_id)
        result, truncated = sanitize.sanitize_result(raw, char_budget=definition.result_char_budget)
        return _log_invocation(
            db,
            project_id=project_id,
            definition=definition,
            status="succeeded",
            arguments=clean_args,
            capability_snapshot=snapshot,
            result=result,
            result_truncated=truncated,
            request_id=request_id,
            created_by=created_by,
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    @staticmethod
    async def propose(
        db: Session,
        *,
        project_id: str,
        tool_id: str,
        arguments: Any,
        scene_id: Optional[str] = None,
        request_id: Optional[str] = None,
        created_by: str = "assistant",
        adapter: Optional[CapabilityAdapter] = None,
    ):
        """Build and persist a `tool_call` proposal. Nothing is applied here."""

        from ..bible.proposals import ProposalService

        _require_project(db, project_id)
        definition = tool_registry.require_kind(tool_id, "mutating")
        adapter = adapter or CapabilityAdapter(db, project_id)

        state = await adapter.state_for(definition.capability)
        readiness = await adapter.readiness_for_tool(definition.tool_id)
        # Mutating tools may still create a proposal when execution dependencies are down
        # (proposal_ready). Hard-block only when neither callable nor proposal-ready.
        if not state.available and not readiness.get("proposalReady"):
            error = state.as_error(definition.tool_id)
            _log_invocation(
                db,
                project_id=project_id,
                definition=definition,
                status="blocked",
                arguments={},
                capability_snapshot={definition.capability: state.to_dict()},
                error=error,
                request_id=request_id,
                created_by=created_by,
            )
            raise error

        clean_args = sanitize.sanitize_arguments(definition, arguments)
        ctx = ToolContext(
            db=db,
            project_id=project_id,
            scene_id=scene_id,
            request_id=request_id,
            capabilities=adapter.cached_states(),
        )
        preview = ToolExecutionService._build_preview(ctx, definition, clean_args)
        base_versions = ToolExecutionService.base_resource_versions(
            db, project_id=project_id, definition=definition, arguments=clean_args
        )
        capability_snapshot = {
            definition.capability: {
                **state.to_dict(),
                "toolReadiness": readiness,
            }
        }
        payload = ToolCallPayload(
            toolId=definition.tool_id,
            toolSchemaVersion=definition.schema_version,
            arguments=clean_args,
            capabilitySnapshot=capability_snapshot,
            preview=preview,
            inputHash=sanitize.compute_input_hash(
                tool_id=definition.tool_id,
                schema_version=definition.schema_version,
                arguments=clean_args,
                base_resource_versions=base_versions,
            ),
            baseResourceVersions=base_versions,
        )
        return ProposalService.create_tool_proposal(
            db,
            project_id=project_id,
            payload=payload,
            title=definition.title,
            summary=preview.summary,
            request_id=request_id,
            created_by=created_by,
        )

    @staticmethod
    def _build_preview(ctx: ToolContext, definition: ToolDefinition, arguments: dict[str, Any]) -> ToolPreview:
        try:
            return tool_registry.mutation_handler(definition.tool_id).preview(ctx, arguments)
        except CoDirectorError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise CoDirectorError(
                TOOL_EXECUTION_FAILED,
                f"Couldn't build a preview for '{definition.tool_id}'.",
                details={"toolId": definition.tool_id, "reason": sanitize.scrub_text(str(exc))[:200]},
                recoverable=True,
                recommended_action="retry",
            ) from exc

    # ---------------- approved execution ----------------

    @staticmethod
    def parse_payload(raw: Optional[str]) -> ToolCallPayload:
        try:
            data = json.loads(raw or "{}")
        except Exception as exc:
            raise CoDirectorError(
                TOOL_PAYLOAD_INVALID,
                "This tool proposal's stored payload could not be read.",
                recoverable=False,
                recommended_action="none",
            ) from exc
        try:
            return ToolCallPayload.model_validate(data)
        except Exception as exc:
            raise CoDirectorError(
                TOOL_PAYLOAD_INVALID,
                "This tool proposal's stored payload doesn't match the current tool contract.",
                recoverable=False,
                recommended_action="none",
            ) from exc

    @staticmethod
    def is_stale(db: Session, *, project_id: str, payload: ToolCallPayload) -> bool:
        """Compare the pinned resource versions against the world as it is now."""

        definition = tool_registry.find(payload.toolId)
        if definition is None:
            return True
        current = ToolExecutionService.base_resource_versions(
            db, project_id=project_id, definition=definition, arguments=payload.arguments
        )
        return current != dict(payload.baseResourceVersions)

    @staticmethod
    def execute_approved_proposal(
        db: Session,
        *,
        proposal: CoDirectorProposal,
        payload: ToolCallPayload,
        decided_by: str = "user",
    ) -> dict[str, Any]:
        """Apply an approved tool proposal. Called only from `ProposalService.approve`.

        The arguments replayed here are the sanitized ones recorded at proposal time — the model
        gets no second say at approval, which is what makes the approval meaningful.
        """

        definition = tool_registry.require_kind(payload.toolId, "mutating")
        tool_registry.check_schema_version(definition, payload.toolSchemaVersion)

        ctx = ToolContext(
            db=db,
            project_id=proposal.project_id,
            scene_id=str(payload.arguments.get("sceneId") or "") or None,
            request_id=proposal.request_id,
        )
        started = time.monotonic()
        try:
            if _e2e_execution_fault():
                raise RuntimeError("Simulated tool execution failure (E2E).")
            raw = tool_registry.mutation_handler(definition.tool_id).apply(ctx, dict(payload.arguments))
        except CoDirectorError as err:
            _log_invocation(
                db,
                project_id=proposal.project_id,
                definition=definition,
                status="failed",
                arguments=dict(payload.arguments),
                capability_snapshot=dict(payload.capabilitySnapshot),
                error=err,
                proposal_id=proposal.id,
                request_id=proposal.request_id,
                created_by=decided_by,
                duration_ms=int((time.monotonic() - started) * 1000),
            )
            raise
        except Exception as exc:  # noqa: BLE001
            err = CoDirectorError(
                TOOL_EXECUTION_FAILED,
                f"Applying '{definition.tool_id}' failed.",
                details={"toolId": definition.tool_id, "reason": sanitize.scrub_text(str(exc))[:200]},
                recoverable=True,
                recommended_action="retry",
            )
            _log_invocation(
                db,
                project_id=proposal.project_id,
                definition=definition,
                status="failed",
                arguments=dict(payload.arguments),
                capability_snapshot=dict(payload.capabilitySnapshot),
                error=err,
                proposal_id=proposal.id,
                request_id=proposal.request_id,
                created_by=decided_by,
                duration_ms=int((time.monotonic() - started) * 1000),
            )
            raise err from exc

        # A successful write invalidates the project's short-lived read cache so the model's
        # next read reflects authoritative post-mutation state, not a pre-write snapshot.
        clear_project(proposal.project_id)
        result, truncated = sanitize.sanitize_result(raw, char_budget=definition.result_char_budget)
        invocation = _log_invocation(
            db,
            project_id=proposal.project_id,
            definition=definition,
            status="succeeded",
            arguments=dict(payload.arguments),
            capability_snapshot=dict(payload.capabilitySnapshot),
            result=result,
            result_truncated=truncated,
            proposal_id=proposal.id,
            request_id=proposal.request_id,
            created_by=decided_by,
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        # A tool that writes the Bible produces a version id the receipt should point at, so the
        # existing "which Bible version did this create" question keeps its single answer.
        resulting_version_id = None
        if isinstance(raw, dict):
            candidate = raw.get("bibleVersionId")
            if isinstance(candidate, str):
                resulting_version_id = candidate
        return {
            "invocation": invocation,
            "resultingVersionId": resulting_version_id,
            "result": result,
            "resultTruncated": truncated,
        }

    # ---------------- ledger ----------------

    @staticmethod
    def list_invocations(
        db: Session, project_id: str, *, tool_id: Optional[str] = None, limit: int = 50
    ) -> list[ToolInvocationOut]:
        query = db.query(CoDirectorToolInvocation).filter(CoDirectorToolInvocation.project_id == project_id)
        if tool_id:
            query = query.filter(CoDirectorToolInvocation.tool_id == tool_id)
        rows = (
            query.order_by(CoDirectorToolInvocation.created_at.desc())
            .limit(max(1, min(limit, MAX_INVOCATION_PAGE)))
            .all()
        )
        return [_row_to_out(r) for r in rows]


__all__ = ["ToolExecutionService", "CapabilityState"]
