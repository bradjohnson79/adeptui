"""Wiki write verification — persistence vs presentation (never blocks TTFT)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# Law: full read-back/verification runs only inside deferred enrichment.
WIKI_VERIFICATION_NEVER_BLOCKS_TTFT = True

PersistenceState = Literal["FAILED", "PERSISTED", "VERIFIED"]
PresentationState = Literal["NOT_EMITTED", "EVENT_EMITTED", "REFETCHED", "VISIBLE", "UI_FAILED"]
FinalState = Literal["NO_CANDIDATES", "QUEUED", "PERSISTED", "VERIFIED", "VISIBLE", "FAILED"]


class WikiWriteVerification(BaseModel):
    requestId: str = ""
    projectId: str = ""
    sourceMessageId: str = ""
    candidateCount: int = 0
    confirmedCount: int = 0
    inferredCount: int = 0
    persistedRecordIds: list[str] = Field(default_factory=list)
    readBackRecordIds: list[str] = Field(default_factory=list)
    writeSucceeded: bool = False
    readBackSucceeded: bool = False
    projectBindingVerified: bool = False
    cacheInvalidated: bool = False
    wikiEventEmitted: bool = False
    frontendRefetched: bool = False
    visibleInUi: bool = False
    persistenceState: PersistenceState = "FAILED"
    presentationState: PresentationState = "NOT_EMITTED"
    finalState: FinalState = "FAILED"
    failureStage: str | None = None
    error: str | None = None

    def to_public_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def build_verification(
    *,
    request_id: str,
    project_id: str,
    source_message_id: str = "",
    candidate_count: int = 0,
    confirmed_count: int = 0,
    inferred_count: int = 0,
    persisted_ids: list[str] | None = None,
    verified_ids: list[str] | None = None,
    write_succeeded: bool = False,
    read_back_succeeded: bool = False,
    project_binding_verified: bool = False,
    cache_invalidated: bool = False,
    wiki_visible: bool = False,
    error: str | None = None,
    failure_stage: str | None = None,
) -> WikiWriteVerification:
    persisted = list(persisted_ids or [])
    verified = list(verified_ids or [])
    if candidate_count == 0 and not error:
        return WikiWriteVerification(
            requestId=request_id,
            projectId=project_id,
            sourceMessageId=source_message_id,
            candidateCount=0,
            persistenceState="VERIFIED",
            presentationState="NOT_EMITTED",
            finalState="NO_CANDIDATES",
            writeSucceeded=True,
            readBackSucceeded=True,
            projectBindingVerified=project_binding_verified,
        )

    if error or not write_succeeded:
        return WikiWriteVerification(
            requestId=request_id,
            projectId=project_id,
            sourceMessageId=source_message_id,
            candidateCount=candidate_count,
            confirmedCount=confirmed_count,
            inferredCount=inferred_count,
            persistedRecordIds=persisted,
            readBackRecordIds=verified,
            writeSucceeded=False,
            readBackSucceeded=False,
            projectBindingVerified=project_binding_verified,
            persistenceState="FAILED",
            presentationState="NOT_EMITTED",
            finalState="FAILED",
            failureStage=failure_stage or "persist",
            error=(error or "Wiki write failed")[:300],
        )

    if not read_back_succeeded:
        # Persisted but not fully verified — still distinct from UI failure.
        return WikiWriteVerification(
            requestId=request_id,
            projectId=project_id,
            sourceMessageId=source_message_id,
            candidateCount=candidate_count,
            confirmedCount=confirmed_count,
            inferredCount=inferred_count,
            persistedRecordIds=persisted,
            readBackRecordIds=verified,
            writeSucceeded=True,
            readBackSucceeded=False,
            projectBindingVerified=project_binding_verified,
            cacheInvalidated=cache_invalidated,
            persistenceState="PERSISTED",
            presentationState="NOT_EMITTED",
            finalState="PERSISTED",
            failureStage=failure_stage or "read_back",
            error=error,
        )

    return WikiWriteVerification(
        requestId=request_id,
        projectId=project_id,
        sourceMessageId=source_message_id,
        candidateCount=candidate_count,
        confirmedCount=confirmed_count,
        inferredCount=inferred_count,
        persistedRecordIds=persisted,
        readBackRecordIds=verified,
        writeSucceeded=True,
        readBackSucceeded=True,
        projectBindingVerified=project_binding_verified,
        cacheInvalidated=cache_invalidated,
        wikiEventEmitted=False,
        persistenceState="VERIFIED",
        presentationState="NOT_EMITTED",
        finalState="VERIFIED",
        visibleInUi=wiki_visible,
    )
