"""SQLAlchemy persistence models for M4.10 voice performance records and takes."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class VoicePerformanceRecordRow(Base):
    __tablename__ = "voice_performance_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column("projectId", String(36), index=True)
    scene_id: Mapped[str | None] = mapped_column("sceneId", String(36), nullable=True, index=True)
    script_document_id: Mapped[str | None] = mapped_column("scriptDocumentId", String(36), nullable=True, index=True)
    script_element_id: Mapped[str | None] = mapped_column("scriptElementId", String(36), nullable=True, index=True)
    character_id: Mapped[str] = mapped_column("characterId", String(36), index=True)
    voice_identity_id: Mapped[str] = mapped_column("voiceIdentityId", String(36), index=True)
    voice_identity_version: Mapped[str] = mapped_column("voiceIdentityVersion", String(64), default="")
    dialogue_text: Mapped[str] = mapped_column("dialogueText", Text, default="")
    language: Mapped[str] = mapped_column(String(32), default="en")
    direction_mode: Mapped[str] = mapped_column("directionMode", String(32), default="codirector")
    performance_plan_json: Mapped[dict] = mapped_column("performancePlan", JSON, default=dict)
    emotion_source: Mapped[str | None] = mapped_column("emotionSource", String(64), nullable=True)
    emotion_vector_json: Mapped[dict] = mapped_column("emotionVector", JSON, default=dict)
    emotional_reference_asset_id: Mapped[str | None] = mapped_column(
        "emotionalReferenceAssetId", String(36), nullable=True
    )
    emotional_reference_strength: Mapped[float | None] = mapped_column(
        "emotionalReferenceStrength", Float, nullable=True
    )
    provider_id: Mapped[str] = mapped_column("providerId", String(64), default="index-tts2-local")
    provider_version: Mapped[str | None] = mapped_column("providerVersion", String(64), nullable=True)
    model_revision: Mapped[str | None] = mapped_column("modelRevision", String(128), nullable=True)
    approved_take_id: Mapped[str | None] = mapped_column("approvedTakeId", String(36), nullable=True, index=True)
    manual_plan_json: Mapped[dict] = mapped_column("manualPlan", JSON, default=dict)
    codirector_plan_json: Mapped[dict] = mapped_column("codirectorPlan", JSON, default=dict)
    scene_arc_id: Mapped[str | None] = mapped_column("sceneArcId", String(64), nullable=True)
    timeline_linkage_json: Mapped[dict] = mapped_column("timelineLinkage", JSON, default=dict)
    lipsync_linkage_json: Mapped[dict] = mapped_column("lipsyncLinkage", JSON, default=dict)
    consent_ack_json: Mapped[dict] = mapped_column("consentAck", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column("updatedAt", DateTime, default=datetime.utcnow)


class VoicePerformanceTakeRow(Base):
    __tablename__ = "voice_performance_takes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    record_id: Mapped[str] = mapped_column("recordId", String(36), index=True)
    take_number: Mapped[int] = mapped_column("takeNumber", Integer, default=1)
    label: Mapped[str] = mapped_column(String(120), default="")
    job_id: Mapped[str | None] = mapped_column("jobId", String(36), nullable=True, index=True)
    audio_asset_id: Mapped[str | None] = mapped_column("audioAssetId", String(36), nullable=True, index=True)
    duration_ms: Mapped[int | None] = mapped_column("durationMs", Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    direction_snapshot_json: Mapped[dict] = mapped_column("directionSnapshot", JSON, default=dict)
    generated_at: Mapped[datetime | None] = mapped_column("generatedAt", DateTime, nullable=True)
    error_code: Mapped[str | None] = mapped_column("errorCode", String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column("errorMessage", Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column("updatedAt", DateTime, default=datetime.utcnow)


M410_TABLES = [VoicePerformanceRecordRow.__table__, VoicePerformanceTakeRow.__table__]
