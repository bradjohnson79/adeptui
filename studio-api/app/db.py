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
