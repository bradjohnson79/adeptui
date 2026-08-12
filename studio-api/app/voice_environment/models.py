"""SQLAlchemy persistence for Voice Environment profiles and renders."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, String, Text, text

from ..db import Base, SessionLocal, engine


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class VoiceEnvironmentProfileRow(Base):
    __tablename__ = "voice_environment_profiles"

    id = Column(String, primary_key=True)
    project_id = Column(String, nullable=False, index=True)
    character_id = Column(String, nullable=True, index=True)
    scene_id = Column(String, nullable=True, index=True)
    location_id = Column(String, nullable=True)
    name = Column(String, nullable=False, default="Untitled Environment")
    space_preset = Column(String, nullable=False, default="small_room")
    custom_space_prompt = Column(Text, nullable=True)
    distance_preset = Column(String, nullable=False, default="medium_close_up")
    custom_distance_prompt = Column(Text, nullable=True)
    direction_preset = Column(String, nullable=False, default="center")
    custom_direction_prompt = Column(Text, nullable=True)
    tone_preset = Column(String, nullable=False, default="natural")
    custom_tone_prompt = Column(Text, nullable=True)
    device_preset = Column(String, nullable=False, default="direct")
    custom_device_prompt = Column(Text, nullable=True)
    walla_preset = Column(String, nullable=False, default="none")
    walla_level = Column(String, nullable=True)
    walla_distance = Column(String, nullable=True)
    walla_behavior = Column(String, nullable=True)
    custom_walla_prompt = Column(Text, nullable=True)
    source = Column(String, nullable=False, default="manual")
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow)


class VoiceEnvironmentRenderRow(Base):
    __tablename__ = "voice_environment_renders"

    id = Column(String, primary_key=True)
    project_id = Column(String, nullable=False, index=True)
    character_id = Column(String, nullable=False, index=True)
    performance_record_id = Column(String, nullable=False, index=True)
    performance_take_id = Column(String, nullable=False, index=True)
    environment_profile_id = Column(String, nullable=False, index=True)
    dry_audio_asset_id = Column(String, nullable=False)
    processed_audio_asset_id = Column(String, nullable=True)
    room_tone_asset_id = Column(String, nullable=True)
    walla_asset_id = Column(String, nullable=True)
    speech_start_offset_ms = Column(Float, nullable=False, default=0.0)
    processing_latency_ms = Column(Float, nullable=False, default=0.0)
    tail_duration_ms = Column(Float, nullable=False, default=0.0)
    dry_duration_ms = Column(Float, nullable=False, default=0.0)
    processed_duration_ms = Column(Float, nullable=False, default=0.0)
    status = Column(String, nullable=False, default="queued")
    approved = Column(Boolean, nullable=False, default=False)
    error_code = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    dsp_plan_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow)


def ensure_tables() -> None:
    Base.metadata.create_all(
        bind=engine,
        tables=[
            VoiceEnvironmentProfileRow.__table__,
            VoiceEnvironmentRenderRow.__table__,
        ],
    )
    # Lightweight migration for older DBs that already have Base metadata.
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS voice_environment_profiles ("
                "id VARCHAR PRIMARY KEY, project_id VARCHAR NOT NULL, character_id VARCHAR, "
                "scene_id VARCHAR, location_id VARCHAR, name VARCHAR NOT NULL, "
                "space_preset VARCHAR NOT NULL, custom_space_prompt TEXT, "
                "distance_preset VARCHAR NOT NULL, custom_distance_prompt TEXT, "
                "direction_preset VARCHAR NOT NULL, custom_direction_prompt TEXT, "
                "tone_preset VARCHAR NOT NULL, custom_tone_prompt TEXT, "
                "device_preset VARCHAR NOT NULL, custom_device_prompt TEXT, "
                "walla_preset VARCHAR NOT NULL, walla_level VARCHAR, walla_distance VARCHAR, "
                "walla_behavior VARCHAR, custom_walla_prompt TEXT, source VARCHAR NOT NULL, "
                "created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL)"
            )
        )


def session_scope():
    return SessionLocal()
