"""Timeline V2 hosted (API) video wiring — dry-run certification.

Proves the hosted provider route end to end without spending credits:
registry resolution, availability provider mapping, per-model request
assembly, capability validation, completion ingest, failure honesty, hosted
cancel honesty, and the absence of any local fallback.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from app.db import Base, Project, Scene, SessionLocal, engine
from app.director_timeline_w46.generation import registry
from app.director_timeline_w46.generation.contracts import (
    NormalizedJobStatus,
    NormalizedJobSubmission,
    TimelineGenerationResult,
)
from app.film_timeline import availability, orchestrator
from app.film_timeline.contracts import FilmTimeline, ReferenceAsset
from app.film_timeline.store import require_film, save_film


@pytest.fixture()
def scene():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    pid, sid = str(uuid.uuid4()), str(uuid.uuid4())
    db.add(Project(id=pid, name="Hosted wiring", description=""))
    db.add(
        Scene(
            id=sid,
            project_id=pid,
            index=0,
            name="Scene",
            prompt="",
            duration_sec=15.0,
            aspect_ratio="16:9",
            director_json="",
        )
    )
    db.commit()
    try:
        yield db, pid, sid
    finally:
        db.close()


class _Capture:
    """Monkeypatched adapter: records requests, returns scripted statuses."""

    def __init__(self, generator_id: str, statuses: list[NormalizedJobStatus] | None = None, assets: list[str] | None = None) -> None:
        self._gid = generator_id
        self.requests: list = []
        self.cancel_calls: list = []
        self._statuses = list(statuses or [])
        self._assets = list(assets or ["asset-out"])

    # Adapter protocol -----------------------------------------------------
    @property
    def capabilities(self):
        return registry.get_registry().capabilities(self._gid)

    def validate(self, request):
        from app.director_timeline_w46.generation.adapter import validate_against_capabilities

        caps = registry.get_registry().capabilities(request.generatorId)
        return validate_against_capabilities(caps, request)

    def submit(self, request):
        self.requests.append(request)
        return NormalizedJobSubmission(
            internalJobId=f"tgen_{uuid.uuid4().hex[:8]}",
            providerJobId=f"hosted-{len(self.requests)}",
            queueJobId=None,
            generatorId=request.generatorId,
            status="running",
            apiUsed=True,
            providerMetadata={"hosted": True},
        )

    def get_status(self, job):
        if self._statuses:
            return self._statuses.pop(0)
        return NormalizedJobStatus(
            internalJobId=job.internalJobId,
            providerJobId=job.providerJobId,
            generatorId=job.generatorId,
            status="completed",
            progress=1.0,
            apiUsed=True,
        )

    def collect_result(self, job):
        return TimelineGenerationResult(
            internalJobId=job.internalJobId,
            providerJobId=job.providerJobId,
            generatorId=job.generatorId,
            status="completed",
            outputAssetIds=self._assets,
            apiUsed=True,
        )

    def cancel(self, job):
        self.cancel_calls.append(job)


@pytest.fixture()
def capture(monkeypatch):
    box: dict[str, _Capture] = {}

    def install(generator_id: str, statuses=None, assets=None) -> _Capture:
        adapter = _Capture(generator_id, statuses=statuses, assets=assets)
        box[generator_id] = adapter
        monkeypatch.setattr(orchestrator, "_adapter", lambda gid: adapter)
        return adapter

    install.box = box
    return install


def _shot(film: FilmTimeline, shot_id: str):
    return next(item for item in film.shots if item.id == shot_id)


def _create(db, pid: str, sid: str, generator_id: str, **kwargs) -> str:
    created = orchestrator.create_shot(db, pid, sid, generator_id=generator_id, **kwargs)
    return created["shot"]["id"]


# ---------------------------------------------------------------- registry


def test_registry_resolves_every_exposed_model_and_alias():
    reg = registry.get_registry()
    for gid in (
        "minimax-h3-i2v-local",
        "ltx-2.5",
        "seedance-2.0",
        "seedance-2.5",
        "seedance-2.0-mini",
        "seedance-2.0-fast",
        "kling-api",
        "veo-api",
        "kling-fal",
        "veo-fal",
        "fal_veo",
        "seedance-mini",
        "seedance-fast",
        "fal_seedance_mini",
        "fal_seedance_fast",
    ):
        assert reg.get(gid) is not None, gid


def test_registry_refuses_unknown_and_retired_ids():
    reg = registry.get_registry()
    for gid in ("kling-2.5-turbo", "wan-api", "definitely-not-a-model"):
        with pytest.raises(Exception):
            reg.resolve_id(gid)


# ---------------------------------------------------------------- availability


def test_availability_maps_every_hosted_model_to_fal():
    providers = {row["id"]: row["provider"] for row in availability.list_generator_status()}
    for gid in ("seedance-2.0", "seedance-2.5", "seedance-2.0-mini", "seedance-2.0-fast", "kling-api", "veo-api"):
        assert providers[gid] == "fal", (gid, providers[gid])
    assert providers["minimax-h3-i2v-local"] == "comfy"


def test_availability_only_offers_executable_seedance_tiers():
    rows = {row["id"]: row for row in availability.list_generator_status()}
    for gid in ("seedance-2.0", "seedance-2.5", "seedance-2.0-fast"):
        assert rows[gid]["supportedResolutions"] == ["480p", "720p"], gid


def test_availability_labels_veo_for_fal():
    rows = {row["id"]: row for row in availability.list_generator_status()}
    assert "Kie" not in rows["veo-api"]["label"]


# ---------------------------------------------------------------- request assembly


def test_seedance_request_carries_tier_resolution_and_scene_aspect(scene, capture):
    db, pid, sid = scene
    adapter = capture("seedance-2.0-fast")
    shot_id = _create(db, pid, sid, "seedance-2.0-fast", duration_sec=4)
    result = orchestrator.generate_shot(db, pid, sid, shot_id, timed_prompt="a red kite over the sea")
    assert result["ok"] is True, result.get("message")
    request = adapter.requests[0]
    assert request.resolution == "720p"  # tier token, never WxH pixels
    assert request.aspectRatio == "16:9"
    assert request.duration == 4
    assert "a red kite over the sea" in request.prompt
    assert "<Picture" not in request.prompt  # no H3-only syntax leaks hosted


def test_seedance_quality_choice_flows_to_request(scene, capture):
    db, pid, sid = scene
    adapter = capture("seedance-2.0")
    shot_id = _create(db, pid, sid, "seedance-2.0", duration_sec=4)
    result = orchestrator.generate_shot(
        db, pid, sid, shot_id,
        timed_prompt="kite", provider_options={"seedanceResolution": "480p"},
    )
    assert result["ok"] is True, result.get("message")
    assert adapter.requests[0].resolution == "480p"
    film = require_film(db, pid, sid)
    assert _shot(film, shot_id).state.resolvedGeneration["seedanceResolution"] == "480p"


def test_kling_request_stamps_aspect_without_invented_pixels(scene, capture):
    db, pid, sid = scene
    adapter = capture("kling-api")
    shot_id = _create(db, pid, sid, "kling-api", duration_sec=5)
    film = require_film(db, pid, sid)
    _shot(film, shot_id).state.references = [ReferenceAsset(type="character", assetId="asset-char", label="Cade", tag="@Cade")]
    save_film(db, pid, sid, film)
    result = orchestrator.generate_shot(db, pid, sid, shot_id, timed_prompt="kite")
    assert result["ok"] is True, result.get("message")
    request = adapter.requests[0]
    assert request.aspectRatio == "16:9"
    segment = _shot(FilmTimeline.model_validate(result["film"]), shot_id).segments[0]
    resolved = segment.generationMetadata["resolvedGeneration"]
    assert resolved["aspect"] == "16:9"
    assert "width" not in resolved and "height" not in resolved


def test_kling_text_to_video_refused_before_any_segment(scene, capture):
    db, pid, sid = scene
    adapter = capture("kling-api")
    shot_id = _create(db, pid, sid, "kling-api", duration_sec=5)
    result = orchestrator.generate_shot(db, pid, sid, shot_id, timed_prompt="kite")
    assert result["ok"] is False
    assert result["error"] == "START_FRAME_REQUIRED"
    assert adapter.requests == []  # refused before the adapter ever saw it


def test_prompt_language_clause_reaches_hosted_request(scene, capture):
    db, pid, sid = scene
    adapter = capture("seedance-2.0-fast")
    shot_id = _create(db, pid, sid, "seedance-2.0-fast", duration_sec=4)
    result = orchestrator.generate_shot(
        db, pid, sid, shot_id, timed_prompt="kite", spoken_language="fr"
    )
    assert result["ok"] is True, result.get("message")
    assert "French" in adapter.requests[0].prompt


# ---------------------------------------------------------------- validation honesty


def test_illegal_duration_fails_closed_without_submission(scene, capture):
    db, pid, sid = scene
    adapter = capture("veo-api")
    shot_id = _create(db, pid, sid, "veo-api", duration_sec=5)
    film = require_film(db, pid, sid)
    _shot(film, shot_id).state.references = [ReferenceAsset(type="character", assetId="asset-char", label="Cade", tag="@Cade")]
    save_film(db, pid, sid, film)
    result = orchestrator.generate_shot(db, pid, sid, shot_id, timed_prompt="kite")
    assert result["ok"] is False
    assert result["error"] in {"VALIDATION_FAILED", "DURATION_UNSUPPORTED"}
    assert adapter.requests == []
    film = require_film(db, pid, sid)
    assert _shot(film, shot_id).segments == []  # refused before any segment was planned


def test_kling_refuses_unsupported_aspect(scene, capture):
    db, pid, sid = scene
    scene_row = db.get(Scene, sid)
    scene_row.aspect_ratio = "4:3"  # kling supports 16:9/9:16/1:1 only
    db.commit()
    adapter = capture("kling-api")
    shot_id = _create(db, pid, sid, "kling-api", duration_sec=5)
    film = require_film(db, pid, sid)
    _shot(film, shot_id).state.references = [ReferenceAsset(type="character", assetId="asset-char", label="Cade", tag="@Cade")]
    save_film(db, pid, sid, film)
    result = orchestrator.generate_shot(db, pid, sid, shot_id, timed_prompt="kite")
    assert result["ok"] is False
    assert adapter.requests == []


# ---------------------------------------------------------------- ingest / no local fallback


def test_completion_ingests_segment_with_no_queue_job(scene, capture):
    db, pid, sid = scene
    capture("seedance-2.0-fast", assets=["asset-out"])
    shot_id = _create(db, pid, sid, "seedance-2.0-fast", duration_sec=4)
    result = orchestrator.generate_shot(db, pid, sid, shot_id, timed_prompt="kite")
    assert result["ok"] is True, result.get("message")
    synced = orchestrator.sync_shot(db, pid, sid, shot_id)
    film = FilmTimeline.model_validate(synced["film"])
    segment = _shot(film, shot_id).segments[0]
    assert segment.status == "completed"
    assert segment.assetId == "asset-out"  # canonical Timeline segment registered
    assert not segment.generationMetadata.get("queueJobId")  # no local queue involvement
    assert segment.shotNumber == 1  # scene-local shot identity


def test_provider_failure_marks_segment_failed_without_fallback(scene, capture):
    db, pid, sid = scene
    capture(
        "seedance-2.0-fast",
        statuses=[
            NormalizedJobStatus(
                internalJobId="x", generatorId="seedance-2.0-fast",
                status="failed", errorMessage="provider refused the prompt", apiUsed=True,
            )
        ],
    )
    shot_id = _create(db, pid, sid, "seedance-2.0-fast", duration_sec=4)
    orchestrator.generate_shot(db, pid, sid, shot_id, timed_prompt="kite")
    synced = orchestrator.sync_shot(db, pid, sid, shot_id)
    film = FilmTimeline.model_validate(synced["film"])
    segment = _shot(film, shot_id).segments[0]
    assert segment.status == "failed"
    assert "provider refused the prompt" in (segment.error or "")
    assert not segment.generationMetadata.get("queueJobId")


# ---------------------------------------------------------------- cancel honesty


def test_hosted_cancel_uses_adapter_not_local_queue(scene, capture):
    db, pid, sid = scene
    adapter = capture(
        "seedance-2.0-fast",
        statuses=[
            NormalizedJobStatus(
                internalJobId="x", generatorId="seedance-2.0-fast",
                status="cancelled", apiUsed=True,
            )
        ],
    )
    shot_id = _create(db, pid, sid, "seedance-2.0-fast", duration_sec=4)
    orchestrator.generate_shot(db, pid, sid, shot_id, timed_prompt="kite")
    cancelled = asyncio.run(orchestrator.cancel_shot(db, pid, sid, shot_id))
    assert cancelled["ok"] is True, cancelled.get("message")
    assert len(adapter.cancel_calls) == 1  # adapter.cancel ran — never job_queue
    film = FilmTimeline.model_validate(cancelled["film"])
    assert _shot(film, shot_id).segments[0].status == "cancelled"


def test_hosted_cancel_rejection_is_honest(scene, capture):
    db, pid, sid = scene
    capture(
        "kling-api",
        statuses=[
            NormalizedJobStatus(
                internalJobId="x", generatorId="kling-api", status="running", apiUsed=True,
                providerMetadata={"cancelRejected": True, "cancelReason": "PROVIDER_CANCEL_UNSUPPORTED"},
            )
        ],
    )
    shot_id = _create(db, pid, sid, "kling-api", duration_sec=5)
    film = require_film(db, pid, sid)
    _shot(film, shot_id).state.references = [ReferenceAsset(type="character", assetId="asset-char", label="Cade", tag="@Cade")]
    save_film(db, pid, sid, film)
    orchestrator.generate_shot(db, pid, sid, shot_id, timed_prompt="kite")
    cancelled = asyncio.run(orchestrator.cancel_shot(db, pid, sid, shot_id))
    assert cancelled["ok"] is False
    assert "cannot cancel" in cancelled["message"]
    film = FilmTimeline.model_validate(cancelled["film"])
    assert _shot(film, shot_id).segments[0].status in {"queued", "running"}  # not falsely marked cancelled


# ---------------------------------------------------------------- coin composition


def test_fixed_slot_duration_coin_composes_same_shot_number(scene, capture):
    db, pid, sid = scene
    adapter = capture("kling-api")
    shot_id = _create(db, pid, sid, "kling-api", duration_sec=15)
    film = require_film(db, pid, sid)
    _shot(film, shot_id).state.references = [ReferenceAsset(type="character", assetId="asset-char", label="Cade", tag="@Cade")]
    save_film(db, pid, sid, film)
    result = orchestrator.generate_shot(db, pid, sid, shot_id, timed_prompt="kite")
    assert result["ok"] is True, result.get("message")
    durations = sorted(request.duration for request in adapter.requests)
    assert durations == [5]  # first piece submits now; the 10s piece follows on sync
    film = FilmTimeline.model_validate(result["film"])
    shot = _shot(film, shot_id)
    assert {segment.shotNumber for segment in shot.segments} == {1}  # one action, one shot number
    assert sorted(segment.durationSec for segment in shot.segments) == [5, 10]
