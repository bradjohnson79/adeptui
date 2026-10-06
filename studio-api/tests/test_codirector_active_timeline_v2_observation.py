"""Timeline V2 <-> Co-Director observation convergence (item 17).

The active Timeline scene snapshot must observe the live Timeline V2 owner
(director_json.filmTimeline). Non-V2 scenes keep the existing W46 path; the V2
data is additive so certified grounding answers are unchanged for them.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from app.codirector.active_timeline_scene_snapshot import (
    _film_document_exists,
    build_active_timeline_scene_snapshot,
)
from app.codirector.project_grounding import grounding_reply
from app.db import Base, Project, Scene, SessionLocal, engine
from app.film_timeline.contracts import (
    FilmTimeline,
    ReferenceAsset,
    Segment,
    Shot,
    ShotState,
)
from app.film_timeline.store import save_film
from app.runtime_session import current_runtime_session_id

LEGAL_CANVAS = {
    "productId": "minimax-h3",
    "width": 1728,
    "height": 736,
    "megapixels": 1.2,
    "source": "table",
    "label": "1.2 MP 21:9",
    "aspect": "21:9",
    "projectCanvasIgnored": None,
}


@pytest.fixture()
def db_project():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    pid = str(uuid.uuid4())
    db.add(Project(id=pid, name="V2 Observation", description=""))
    db.commit()
    try:
        yield db, pid
    finally:
        db.close()


def _scene(db, pid, *, director_json="", aspect="21:9", name="V2 Scene"):
    sid = str(uuid.uuid4())
    db.add(
        Scene(
            id=sid,
            project_id=pid,
            index=0,
            name=name,
            prompt="Scene prompt",
            summary="Scene summary",
            duration_sec=10.0,
            aspect_ratio=aspect,
            director_json=director_json,
        )
    )
    db.commit()
    return sid


def _v2_film(pid, sid):
    shot = Shot(
        id="shot_1",
        sceneId=sid,
        name="Shot 01",
        order=0,
        durationSec=10.0,
        timedPrompt="Cade walks the corridor.",
        status="generating",
        state=ShotState(
            shotId="shot_1",
            sceneId=sid,
            modelId="minimax-h3",
            references=[
                ReferenceAsset(
                    id="ref_char",
                    type="character",
                    assetId="asset-cade",
                    label="Cade",
                    tag="@Cade",
                )
            ],
            promptHistory=["Cade walks the corridor.", "Cade walks the corridor, wind."],
            modelPrompt="compiled: Cade walks the corridor.",
            stitchAssetId="stitch-asset-1",
            stitchStatus="ready",
            resolvedGeneration={"h3Resolution": {"mode": "manual", "megapixels": 1.2}},
        ),
        segments=[
            Segment(
                id="seg_1",
                order=0,
                durationSec=5.0,
                requestedDurationSec=5.0,
                status="completed",
                assetId="asset-seg-1",
                timedPrompt="Cade walks.",
                generatorId="minimax-h3",
                generationMetadata={
                    "legalCanvas": dict(LEGAL_CANVAS),
                    "resolvedGeneration": dict(LEGAL_CANVAS),
                },
            ),
            Segment(
                id="seg_2",
                order=1,
                durationSec=5.0,
                requestedDurationSec=5.0,
                status="queued",
                assetId=None,
                timedPrompt="Cade stops.",
                generatorId="minimax-h3",
                generationMetadata={},
            ),
        ],
    )
    return FilmTimeline(
        version=1,
        projectId=pid,
        sceneId=sid,
        name="V2 Scene",
        generatorId="minimax-h3",
        references=[
            ReferenceAsset(
                id="ref_env",
                type="environment",
                assetId="asset-env",
                label="Venture Corridor",
                tag="#VentureCorridorScene",
            )
        ],
        shots=[shot],
        renderSessionId=current_runtime_session_id(),
    )


# ---------------------------------------------------------------------------
# (a) A scene WITH a filmTimeline document exposes live V2 truth.
# ---------------------------------------------------------------------------


def test_v2_scene_snapshot_exposes_live_v2_fields(db_project):
    db, pid = db_project
    sid = _scene(db, pid)
    save_film(db, pid, sid, _v2_film(pid, sid))

    assert _film_document_exists(db, pid, sid) is True
    snap = build_active_timeline_scene_snapshot(db, pid, sid, playhead_sec=2.0)

    assert snap["hasTimelineSnapshot"] is True
    assert snap["activeSceneId"] == sid

    v2 = snap["timelineV2"]
    assert v2["source"] == "filmTimeline"
    assert v2["sceneId"] == sid
    assert v2["activeShotId"] == "shot_1"
    assert v2["activeShotName"] == "Shot 01"

    # selected generator, aspect, megapixel tier, legal canvas, duration.
    assert v2["generatorId"] == "minimax-h3"
    assert v2["aspectRatio"] == "21:9"
    assert v2["resolvedAspect"] == "21:9"
    assert v2["megapixelTier"] == 1.2
    assert v2["h3Resolution"] == {"mode": "manual", "megapixels": 1.2}
    assert v2["legalCanvas"] == {
        "width": 1728,
        "height": 736,
        "resolution": "1728x736",
        "megapixels": 1.2,
        "aspect": "21:9",
        "label": "1.2 MP 21:9",
        "source": "table",
        "productId": "minimax-h3",
    }
    assert v2["durationSec"] == 10.0
    assert v2["segmentDurationsSec"] == [5.0, 5.0]

    # references (scene + shot).
    ref_tuples = {(r["type"], r["tag"], r["assetId"], r["source"]) for r in v2["references"]}
    assert ("environment", "#VentureCorridorScene", "asset-env", "scene") in ref_tuples
    assert ("character", "@Cade", "asset-cade", "shot") in ref_tuples

    # prompt (timed prompt / history / segment prompts).
    assert v2["prompt"]["timedPrompt"] == "Cade walks the corridor."
    assert "Cade walks the corridor, wind." in v2["prompt"]["promptHistory"]
    assert v2["prompt"]["modelPrompt"] == "compiled: Cade walks the corridor."
    assert v2["prompt"]["activeSegmentPrompt"] == "Cade walks."
    assert [s["timedPrompt"] for s in v2["prompt"]["segments"]] == ["Cade walks.", "Cade stops."]

    # generation status (shot + per-segment).
    assert v2["status"]["shotStatus"] == "generating"
    assert v2["status"]["segments"][0] == {
        "id": "seg_1",
        "order": 0,
        "status": "completed",
        "assetId": "asset-seg-1",
        "error": None,
    }
    assert v2["status"]["segments"][1]["status"] == "queued"

    # shots summary.
    assert len(v2["shots"]) == 1
    assert v2["shots"][0]["id"] == "shot_1"
    assert v2["shots"][0]["segmentCount"] == 2
    assert v2["shots"][0]["segmentStatuses"] == ["completed", "queued"]
    assert v2["shots"][0]["active"] is True

    # currentTake / stitch.
    assert v2["currentTake"]["stitchAssetId"] == "stitch-asset-1"
    assert v2["currentTake"]["stitchStatus"] == "ready"
    assert v2["currentTake"]["takeId"] == "stitch-asset-1"

    # mirrored existing keys stay populated for certified grounding consumers.
    assert snap["generatorId"] == "minimax-h3"
    assert snap["environment"]["tag"] == "#VentureCorridorScene"
    assert snap["currentTimedPrompt"]["text"] == "Cade walks."
    assert snap["currentTimedPrompt"]["start"] == 0.0
    assert snap["currentTimedPrompt"]["length"] == 5.0
    assert snap["currentTake"]["takeId"] == "stitch-asset-1"
    assert any(r["tag"] == "@Cade" for r in snap["referencedInShot"])


def test_v2_grounding_answers_use_v2_truth(db_project):
    db, pid = db_project
    sid = _scene(db, pid)
    save_film(db, pid, sid, _v2_film(pid, sid))
    snap = build_active_timeline_scene_snapshot(db, pid, sid)
    inspect = {
        "bound": True,
        "activeScene": snap["activeScene"],
        "characters": [],
        "timelineSnapshot": snap,
    }
    gen = grounding_reply(inspect, "What generator is this scene using?") or ""
    assert "minimax-h3" in gen
    env = grounding_reply(inspect, "What environment is assigned?") or ""
    assert "Venture Corridor" in env
    refs = grounding_reply(inspect, "Who is referenced in this shot?") or ""
    assert "Cade" in refs
    happens = grounding_reply(inspect, "What happens in this scene?") or ""
    assert "Scene summary" in happens


# ---------------------------------------------------------------------------
# (b) A scene WITHOUT a filmTimeline document keeps the W46 fallback path.
# ---------------------------------------------------------------------------


def test_non_v2_scene_uses_unchanged_w46_fallback(db_project):
    db, pid = db_project
    sid = _scene(db, pid)
    assert _film_document_exists(db, pid, sid) is False

    snap = build_active_timeline_scene_snapshot(db, pid, sid)

    assert snap["hasTimelineSnapshot"] is True
    # The W46 join shape is untouched: its keys are present and the V2-only
    # keys are absent.
    assert "timelineV2" not in snap
    assert "activeSceneId" not in snap
    assert set(["batches", "batchApproval", "promptSegments", "sceneTakes"]).issubset(snap.keys())
    assert isinstance(snap["batches"], list)
    assert snap["batchApproval"]["total"] == len(snap["batches"])
    assert snap["scenePrompt"] == "Scene prompt"
    assert snap["activeScene"]["id"] == sid
    # The W46 join must never co-create a V2 document.
    assert _film_document_exists(db, pid, sid) is False


# ---------------------------------------------------------------------------
# (c) Unbound / empty / malformed scenes never raise.
# ---------------------------------------------------------------------------


def test_unbound_and_empty_scenes_never_raise(db_project):
    db, pid = db_project

    unbound = build_active_timeline_scene_snapshot(db, None, None)
    assert unbound["hasTimelineSnapshot"] is False
    assert unbound["bound"] is False

    no_scene = build_active_timeline_scene_snapshot(db, pid, None)
    assert no_scene["hasTimelineSnapshot"] is False

    missing = build_active_timeline_scene_snapshot(db, pid, str(uuid.uuid4()))
    assert missing["hasTimelineSnapshot"] is False
    assert "timelineV2" not in missing

    # A malformed filmTimeline is detected, then safely falls back to W46.
    bad = _scene(db, pid, director_json='{"filmTimeline": {"version": 1, "shots": "not-a-list"}}')
    assert _film_document_exists(db, pid, bad) is True
    snap_bad = build_active_timeline_scene_snapshot(db, pid, bad)
    assert "timelineV2" not in snap_bad

    # A V2 document with zero shots is still observable without raising.
    empty = _scene(db, pid)
    save_film(db, pid, empty, FilmTimeline(version=1, projectId=pid, sceneId=empty, name="Empty"))
    snap_empty = build_active_timeline_scene_snapshot(db, pid, empty)
    assert snap_empty["hasTimelineSnapshot"] is True
    assert snap_empty["timelineV2"]["activeShotId"] is None
    assert snap_empty["timelineV2"]["shots"] == []
    assert snap_empty["timelineV2"]["legalCanvas"] is None


# ---------------------------------------------------------------------------
# Additional: the timeline.* read tools expose the same V2 block additively.
# ---------------------------------------------------------------------------


def _tool_ctx(db, pid, sid):
    from app.codirector.tools.definitions import ToolContext

    return ToolContext(db=db, project_id=pid, scene_id=sid)


def test_v2_read_tools_expose_v2_block_without_dropping_w46_keys(db_project):
    from app.codirector.tools.handlers.director_timeline_tools import (
        get_workspace,
        inspect_batches,
    )

    db, pid = db_project
    sid = _scene(db, pid)
    save_film(db, pid, sid, _v2_film(pid, sid))
    ctx = _tool_ctx(db, pid, sid)

    ws = asyncio.run(get_workspace(ctx, {"sceneId": sid}))
    assert ws["timelineV2"]["generatorId"] == "minimax-h3"
    assert ws["timelineV2"]["legalCanvas"]["resolution"] == "1728x736"
    assert ws["timelineV2"]["status"]["shotStatus"] == "generating"
    # The W46 master block is still present (additive only).
    assert "master" in ws
    assert "batchesSummary" in ws and "batchCount" in ws

    ib = asyncio.run(inspect_batches(ctx, {"sceneId": sid}))
    assert ib["timelineV2"]["activeShotId"] == "shot_1"
    assert "batches" in ib and "batchCount" in ib


def test_non_v2_read_tools_keep_payload_without_v2_key(db_project):
    from app.codirector.tools.handlers.director_timeline_tools import (
        get_workspace,
        inspect_batches,
    )

    db, pid = db_project
    sid = _scene(db, pid)
    ctx = _tool_ctx(db, pid, sid)

    ws = asyncio.run(get_workspace(ctx, {"sceneId": sid}))
    assert "timelineV2" not in ws
    assert "master" in ws

    ib = asyncio.run(inspect_batches(ctx, {"sceneId": sid}))
    assert "timelineV2" not in ib
    assert "batches" in ib
