from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    engine_default: Mapped[str] = mapped_column(String(16), default="ltx")
    global_prompt: Mapped[str] = mapped_column(Text, default="")
    negative_prompt: Mapped[str] = mapped_column(Text, default="blurry, low quality, watermark")
    width: Mapped[int] = mapped_column(Integer, default=1280)
    height: Mapped[int] = mapped_column(Integer, default=720)
    fps: Mapped[int] = mapped_column(Integer, default=24)
    seed: Mapped[int] = mapped_column(Integer, default=-1)
    preset: Mapped[str] = mapped_column(String(32), default="quality")
    vram_gb: Mapped[int] = mapped_column(Integer, default=32)
    spatial_map_json: Mapped[str] = mapped_column(Text, default="{}")
    render_safety_json: Mapped[str] = mapped_column(Text, default="")
    learning_json: Mapped[str] = mapped_column(Text, default="")
    learning_enabled_json: Mapped[str] = mapped_column(Text, default="")
    preview_settings_json: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    company: Mapped[str] = mapped_column(String(200), default="")
    director_name: Mapped[str] = mapped_column(String(200), default="")
    version: Mapped[str] = mapped_column(String(64), default="1.0")
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    archived: Mapped[int] = mapped_column(Integer, default=0)
    defaults_json: Mapped[str] = mapped_column(Text, default="")
    settings_json: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    scenes: Mapped[list["Scene"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    assets: Mapped[list["Asset"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    jobs: Mapped[list["Job"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Scene(Base):
    __tablename__ = "scenes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    index: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String(200), default="Scene")
    engine: Mapped[str] = mapped_column(String(16), default="ltx")
    prompt: Mapped[str] = mapped_column(Text, default="")
    duration_sec: Mapped[float] = mapped_column(Float, default=5.0)
    start_asset_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    middle_asset_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    end_asset_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    audio_asset_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    output_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    lipsync_enabled: Mapped[int] = mapped_column(Integer, default=0)
    lipsync_audio_asset_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    lipsync_output_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    lipsync_tracks_json: Mapped[str] = mapped_column(Text, default="")
    director_json: Mapped[str] = mapped_column(Text, default="")
    continuity_json: Mapped[str] = mapped_column(Text, default="")
    camera_note: Mapped[str] = mapped_column(Text, default="")
    seed: Mapped[int] = mapped_column(Integer, default=-1)
    aspect_ratio: Mapped[str] = mapped_column(String(16), default="16:9")
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    fps_mode: Mapped[str] = mapped_column(String(16), default="auto")
    fps: Mapped[int] = mapped_column(Integer, default=0)

    project: Mapped["Project"] = relationship(back_populates="scenes")


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    tag: Mapped[str] = mapped_column(String(64), default="")
    kind: Mapped[str] = mapped_column(String(32), default="image")
    filename: Mapped[str] = mapped_column(String(260))
    path: Mapped[str] = mapped_column(Text)
    comfy_name: Mapped[str] = mapped_column(String(260), default="")
    scope: Mapped[str] = mapped_column(String(32), default="project")  # project | shared | global
    shared_project_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    labels_json: Mapped[str] = mapped_column(Text, default="[]")
    prompt_meta_json: Mapped[str] = mapped_column(Text, default="{}")
    parent_asset_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="assets")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    scene_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    kind: Mapped[str] = mapped_column(String(32), default="render")
    status: Mapped[str] = mapped_column(String(32), default="queued")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    message: Mapped[str] = mapped_column(Text, default="")
    stage: Mapped[str] = mapped_column(String(64), default="")
    preview_json: Mapped[str] = mapped_column(Text, default="")
    params_json: Mapped[str] = mapped_column(Text, default="")
    history_json: Mapped[str] = mapped_column(Text, default="")
    comfy_prompt_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    output_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="jobs")


class CoDirectorConversation(Base):
    __tablename__ = "codirector_conversations"

    project_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    messages_json: Mapped[str] = mapped_column(Text, default="[]")
    model_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    provider_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# --------------------------------------------------------------------------
# Co-Director M2.1: Production Bible + durable proposals/approvals.
#
# The model never writes these tables directly — every mutation flows through a
# `codirector_proposals` row, an explicit `codirector_approvals` decision, and (on approval)
# a new immutable `production_bible_versions` row plus a `codirector_execution_receipts`
# row for idempotency. See docs/CODIRECTOR_PRODUCTION_BIBLE.md.
# --------------------------------------------------------------------------


class ProductionBible(Base):
    __tablename__ = "production_bibles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), unique=True, index=True)
    current_version_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProductionBibleVersion(Base):
    """Immutable snapshot metadata. Content lives in entities/facts rows for this version."""

    __tablename__ = "production_bible_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    bible_id: Mapped[str] = mapped_column(ForeignKey("production_bibles.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    parent_version_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    change_reason: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(64), default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProductionBibleEntity(Base):
    __tablename__ = "production_bible_entities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    bible_version_id: Mapped[str] = mapped_column(ForeignKey("production_bible_versions.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(32), index=True)
    entity_key: Mapped[str] = mapped_column(String(160), index=True)
    display_name: Mapped[str] = mapped_column(String(200), default="")
    data_json: Mapped[str] = mapped_column(Text, default="{}")
    stable_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    slug: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    lifecycle_status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    content_revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BibleAuditEvent(Base):
    __tablename__ = "bible_audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(48), index=True)
    entity_stable_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    entity_key: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    entity_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    bible_version_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    bible_version_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    proposal_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    receipt_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    actor: Mapped[str] = mapped_column(String(64), default="user")
    summary: Mapped[str] = mapped_column(Text, default="")
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProductionBibleFact(Base):
    __tablename__ = "production_bible_facts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    bible_version_id: Mapped[str] = mapped_column(ForeignKey("production_bible_versions.id"), index=True)
    entity_key: Mapped[Optional[str]] = mapped_column(String(160), nullable=True, index=True)
    fact_type: Mapped[str] = mapped_column(String(32), default="continuity")
    statement: Mapped[str] = mapped_column(Text, default="")
    data_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CoDirectorProposal(Base):
    __tablename__ = "codirector_proposals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    bible_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    based_on_version_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    proposal_type: Mapped[str] = mapped_column(String(48), default="bible_update")
    title: Mapped[str] = mapped_column(String(200), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), default="assistant")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CoDirectorApproval(Base):
    __tablename__ = "codirector_approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("codirector_proposals.id"), index=True)
    decision: Mapped[str] = mapped_column(String(24))
    note: Mapped[str] = mapped_column(Text, default="")
    decided_by: Mapped[str] = mapped_column(String(64), default="user")
    decided_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CoDirectorExecutionReceipt(Base):
    __tablename__ = "codirector_execution_receipts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("codirector_proposals.id"), index=True)
    input_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(24), default="success")
    resulting_version_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    error_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# --------------------------------------------------------------------------
# Co-Director M2.2: bounded tool registry. One row per tool invocation — read tools log the
# result they returned, mutating tools log the approved execution (linked to its proposal), and
# capability-blocked attempts are logged too so "why didn't it use that tool" is answerable.
# See docs/architecture/CODIRECTOR_TOOL_REGISTRY.md.
# --------------------------------------------------------------------------


class CoDirectorToolInvocation(Base):
    __tablename__ = "codirector_tool_invocations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    tool_id: Mapped[str] = mapped_column(String(64), index=True)
    tool_schema_version: Mapped[int] = mapped_column(Integer, default=1)
    kind: Mapped[str] = mapped_column(String(16), default="read")
    status: Mapped[str] = mapped_column(String(16), default="succeeded", index=True)
    arguments_json: Mapped[str] = mapped_column(Text, default="{}")
    result_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    result_truncated: Mapped[int] = mapped_column(Integer, default=0)
    capability_snapshot_json: Mapped[str] = mapped_column(Text, default="{}")
    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    proposal_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str] = mapped_column(String(64), default="assistant")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# --------------------------------------------------------------------------
# Co-Director M2.4: production intelligence persistence (findings, synthesis, plans).
# --------------------------------------------------------------------------


class CoDirectorSpecialistFinding(Base):
    __tablename__ = "codirector_specialist_findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    specialist_id: Mapped[str] = mapped_column(String(64), index=True)
    prompt_version: Mapped[str] = mapped_column(String(32), default="")
    model_id: Mapped[str] = mapped_column(String(128), default="")
    context_hash: Mapped[str] = mapped_column(String(64), default="")
    output_json: Mapped[str] = mapped_column(Text, default="{}")
    validation_status: Mapped[str] = mapped_column(String(24), default="generated", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CoDirectorSynthesisRecord(Base):
    __tablename__ = "codirector_synthesis_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    specialist_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    synthesis_json: Mapped[str] = mapped_column(Text, default="{}")
    prompt_versions_json: Mapped[str] = mapped_column(Text, default="{}")
    plan_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    model_id: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CoDirectorProductionPlan(Base):
    __tablename__ = "codirector_production_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    playbook_id: Mapped[str] = mapped_column(String(64), default="")
    title: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    plan_json: Mapped[str] = mapped_column(Text, default="{}")
    visual_validation_pending: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


engine = create_engine(f"sqlite:///{settings.data_dir / 'studio.db'}", future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _add_col(conn, table: str, col: str, ddl: str, existing: set[str]) -> None:
    if col not in existing:
        conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    try:
        from .profiles import ensure_profile_tables

        ensure_profile_tables()
    except Exception:
        pass
    try:
        from .asset_graph import ensure_graph_tables

        ensure_graph_tables()
    except Exception:
        pass
    try:
        from .spatial_scene import ensure_spatial_tables

        ensure_spatial_tables()
    except Exception:
        pass
    try:
        from .script_storyboard import ensure_script_tables

        ensure_script_tables()
    except Exception:
        pass
    with engine.begin() as conn:
        scene_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(scenes)").fetchall()}
        _add_col(conn, "scenes", "lipsync_tracks_json", "lipsync_tracks_json TEXT DEFAULT ''", scene_cols)
        _add_col(conn, "scenes", "director_json", "director_json TEXT DEFAULT ''", scene_cols)
        _add_col(conn, "scenes", "continuity_json", "continuity_json TEXT DEFAULT ''", scene_cols)
        _add_col(conn, "scenes", "aspect_ratio", "aspect_ratio TEXT DEFAULT '16:9'", scene_cols)
        _add_col(conn, "scenes", "width", "width INTEGER DEFAULT 0", scene_cols)
        _add_col(conn, "scenes", "height", "height INTEGER DEFAULT 0", scene_cols)
        _add_col(conn, "scenes", "fps_mode", "fps_mode TEXT DEFAULT 'auto'", scene_cols)
        _add_col(conn, "scenes", "fps", "fps INTEGER DEFAULT 0", scene_cols)

        project_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(projects)").fetchall()}
        _add_col(conn, "projects", "vram_gb", "vram_gb INTEGER DEFAULT 32", project_cols)
        _add_col(conn, "projects", "render_safety_json", "render_safety_json TEXT DEFAULT ''", project_cols)
        _add_col(conn, "projects", "learning_json", "learning_json TEXT DEFAULT ''", project_cols)
        _add_col(conn, "projects", "learning_enabled_json", "learning_enabled_json TEXT DEFAULT ''", project_cols)
        _add_col(conn, "projects", "preview_settings_json", "preview_settings_json TEXT DEFAULT ''", project_cols)
        _add_col(conn, "projects", "description", "description TEXT DEFAULT ''", project_cols)
        _add_col(conn, "projects", "company", "company TEXT DEFAULT ''", project_cols)
        _add_col(conn, "projects", "director_name", "director_name TEXT DEFAULT ''", project_cols)
        _add_col(conn, "projects", "version", "version TEXT DEFAULT '1.0'", project_cols)
        _add_col(conn, "projects", "tags_json", "tags_json TEXT DEFAULT '[]'", project_cols)
        _add_col(conn, "projects", "archived", "archived INTEGER DEFAULT 0", project_cols)
        _add_col(conn, "projects", "defaults_json", "defaults_json TEXT DEFAULT ''", project_cols)
        _add_col(conn, "projects", "settings_json", "settings_json TEXT DEFAULT ''", project_cols)

        job_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(jobs)").fetchall()}
        _add_col(conn, "jobs", "stage", "stage TEXT DEFAULT ''", job_cols)
        _add_col(conn, "jobs", "preview_json", "preview_json TEXT DEFAULT ''", job_cols)
        _add_col(conn, "jobs", "params_json", "params_json TEXT DEFAULT ''", job_cols)
        _add_col(conn, "jobs", "history_json", "history_json TEXT DEFAULT ''", job_cols)

        asset_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(assets)").fetchall()}
        _add_col(conn, "assets", "scope", "scope TEXT DEFAULT 'project'", asset_cols)
        _add_col(conn, "assets", "shared_project_ids_json", "shared_project_ids_json TEXT DEFAULT '[]'", asset_cols)
        _add_col(conn, "assets", "labels_json", "labels_json TEXT DEFAULT '[]'", asset_cols)
        _add_col(conn, "assets", "prompt_meta_json", "prompt_meta_json TEXT DEFAULT '{}'", asset_cols)
        _add_col(conn, "assets", "parent_asset_id", "parent_asset_id TEXT", asset_cols)

    try:
        from .preview_bus import preview_bus

        preview_bus.purge_abandoned()
        preview_bus.enforce_cache_limit()
    except Exception:
        pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
