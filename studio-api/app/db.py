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
    camera_note: Mapped[str] = mapped_column(Text, default="")
    seed: Mapped[int] = mapped_column(Integer, default=-1)

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
    comfy_prompt_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    output_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="jobs")


engine = create_engine(f"sqlite:///{settings.data_dir / 'studio.db'}", future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    # Lightweight SQLite column migrate for older studio.db files
    with engine.begin() as conn:
        scene_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(scenes)").fetchall()}
        if "lipsync_tracks_json" not in scene_cols:
            conn.exec_driver_sql("ALTER TABLE scenes ADD COLUMN lipsync_tracks_json TEXT DEFAULT ''")
        if "director_json" not in scene_cols:
            conn.exec_driver_sql("ALTER TABLE scenes ADD COLUMN director_json TEXT DEFAULT ''")
        project_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(projects)").fetchall()}
        if "vram_gb" not in project_cols:
            conn.exec_driver_sql("ALTER TABLE projects ADD COLUMN vram_gb INTEGER DEFAULT 32")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
