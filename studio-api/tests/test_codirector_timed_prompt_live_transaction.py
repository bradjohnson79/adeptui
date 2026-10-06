"""Compact Timed Prompt author → place → verify transaction tests.

Isolation: this module only. Do not edit certified probe suites.
"""

from __future__ import annotations

import hashlib
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.codirector.conversation_events import EventInput, append_events
from app.codirector.errors import CoDirectorError
from app.codirector.service import (
    AUTHORED_NOT_PLACED_COPY,
    _bind_timed_prompt_tool_arguments,
    _extract_place_existing_body,
    _maybe_platform_knowledge_reply,
    _claims_timed_prompt_placed,
    _extract_timed_prompt_body,
    _inspect_timed_prompt_in_timeline,
    _resolve_authored_timed_prompt,
    _rewrite_unverified_placement_claim,
    _strip_timed_prompt_carrier,
    _user_asks_timed_prompt_in_timeline,
    _verify_timed_prompt_destination,
)
from app.codirector.tools.definitions import ToolContext
from app.codirector.tools.handlers.director_timeline_tools import apply_propose_add_prompt_segment
from app.db import Base, Project, Scene
from app.director_timeline import PromptSegment
from app.director_timeline_w46 import store
from app.director_timeline_w46.contracts import (
    BatchBlock,
    DurationState,
    SceneTimelineMaster,
    TimelinePromptSegment,
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _project_scene(db, *, duration=15.0):
    pid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    db.add(Project(id=pid, name="Timed Prompt Transaction", description=""))
    db.add(
        Scene(
            id=sid,
            project_id=pid,
            index=0,
            name="Scene 1",
            prompt="",
            duration_sec=duration,
            director_json="",
        )
    )
    db.commit()
    # SINGLE-STORE: plant a real Master execution window. Empty scenes no
    # longer auto-mint one, and save_master persists Master + workspace only —
    # legacy director_json prompt_segments writes are dead writes.
    master = SceneTimelineMaster(
        sceneId=sid,
        batchBlocks=[
            BatchBlock(
                id="bb1",
                sceneId=sid,
                order=0,
                label="Window 1",
                duration=DurationState(plannedDuration=duration, timelineVisibleDuration=duration),
            )
        ],
    )
    store.save_master(db, pid, sid, master)
    return pid, sid


def _seed_segments(db, pid, sid, segments):
    """Seed Master promptSegments (single store). Accepts legacy PromptSegment
    doubles for compact call sites; maps to Master TimelinePromptSegment."""
    payload = store.load_master(db, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = master.batchBlocks[0]
    batch.promptSegments = [
        TimelinePromptSegment(
            id=str(getattr(s, "id", "") or ""),
            start=float(getattr(s, "start", 0.0) or 0.0),
            length=float(getattr(s, "length", 0.0) or 0.0),
            text=str(getattr(s, "text", "") or ""),
        )
        for s in segments
    ]
    store.save_master(db, pid, sid, master, bump_revision=False)


def _master_segments(db, pid, sid):
    """Read back Master promptSegments (never the legacy COW leftover array)."""
    payload = store.load_master(db, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    segs = []
    for batch in master.batchBlocks or []:
        segs.extend(batch.promptSegments or [])
    return segs


def _ctx(db, pid, sid) -> ToolContext:
    return ToolContext(db=db, project_id=pid, scene_id=sid)


AUTHORED = "[0s-8s] Medium shot of Korri behind the bar.\n[8s-15s] Pan left to Cade at the table."


def test_strip_removes_tool_fence():
    raw = AUTHORED + '\n```tool\n{"responseType":"mutation_proposal","toolId":"timeline.propose_add_prompt_segment","arguments":{"text":""}}\n```'
    cleaned = _strip_timed_prompt_carrier(raw)
    assert AUTHORED in cleaned
    assert "```tool" not in cleaned
    assert "propose_add_prompt_segment" not in cleaned


def test_place_on_timeline_uses_the_request_not_a_prior_draft():
    body = _extract_place_existing_body(
        "Place this timed prompt on the Timeline now: [0s-10s] A ceramic cup sits on a wooden counter in warm light."
    )
    assert body.startswith("[0s-10s]")
    assert "warm light" in body
    assert _maybe_platform_knowledge_reply(
        "Is that timed prompt already in the timeline? Check the timeline store."
    ) is None
    cool = _extract_place_existing_body(
        "Place this timed prompt on the Timeline now: [0s-8s] A ceramic cup sits on a wooden counter in cool shade."
    )
    assert cool.startswith("[0s-8s]")
    assert "cool shade" in cool
    assert "warm light" not in cool


def test_timed_instruction_is_admitted_on_the_durable_path_only():
    from pathlib import Path

    from app.codirector.durable.admission import exposed_tool_ids, is_timed_instruction

    text = "Place this timed prompt on the timeline: [0s-4s] a cup on the counter."
    assert is_timed_instruction(text)
    exposed = exposed_tool_ids(surface="timeline", user_text=text)
    assert "timeline.propose_add_prompt_segment" in exposed
    assert "set_scene_prompt" not in exposed
    service = Path(__file__).resolve().parents[1].joinpath("app", "codirector", "service.py").read_text(encoding="utf-8")
    for name in ("async def chat_for_project", "async def stream_for_project", "async def _stream_for_project_inner"):
        assert name not in service
    router = Path(__file__).resolve().parents[1].joinpath("app", "routers", "codirector.py").read_text(encoding="utf-8")
    chat = router[router.find("async def chat(") : router.find("async def chat_stream(")]
    assert "begin_turn(" in chat
    assert "chat_for_project(" not in chat


def test_bind_refuses_missing_scene():
    db = _db()
    bound, refusal = _bind_timed_prompt_tool_arguments(
        db, project_id="p", scene_id=None, arguments={"text": AUTHORED}
    )
    assert bound is None
    assert refusal and "No Timeline scene" in refusal


def test_bind_refuses_empty_text():
    db = _db()
    pid, sid = _project_scene(db)
    bound, refusal = _bind_timed_prompt_tool_arguments(
        db, project_id=pid, scene_id=sid, arguments={"text": "   "}
    )
    assert bound is None
    assert refusal and "authored timed prompt" in refusal


def test_bind_same_turn_display_and_overwrite_scene_id():
    db = _db()
    pid, sid = _project_scene(db)
    bound, refusal = _bind_timed_prompt_tool_arguments(
        db,
        project_id=pid,
        scene_id=sid,
        arguments={"sceneId": "fabricated-id", "text": ""},
        same_turn_display=AUTHORED,
    )
    assert refusal is None
    assert bound is not None
    assert bound["sceneId"] == sid
    assert bound["text"] == AUTHORED
    assert bound["start"] == 0.0
    assert bound["length"] == 15.0


def test_resolve_owner_timeline_edit_wins_over_stale_assistant():
    db = _db()
    pid, sid = _project_scene(db)
    stale = "[0s-15s] STALE ASSISTANT COPY"
    owner = "[0s-15s] OWNER EDITED TIMED PROMPT"
    append_events(
        db,
        pid,
        [
            EventInput(role="user", content="Create the Timed Prompt for this scene.", actor="user"),
            EventInput(role="assistant", content=stale, message_type="answer", actor="assistant"),
        ],
    )
    _seed_segments(db, pid, sid, [PromptSegment(id="ps_owner", start=0, length=15, text=owner)])
    resolved = _resolve_authored_timed_prompt(db, pid, scene_id=sid)
    assert resolved == owner
    assert resolved != stale


def test_extract_drops_leading_claim_prose():
    claimed = (
        "I've updated Scene 1 → Timed Prompt in Timeline.\n\n"
        "prompt=[0:00-0:05] Korri walks the corridor."
    )
    assert _extract_timed_prompt_body(claimed) == "[0:00-0:05] Korri walks the corridor."
    assert _extract_timed_prompt_body(AUTHORED) == AUTHORED


def test_resolve_newer_assistant_wins_over_multiple_old_clips():
    db = _db()
    pid, sid = _project_scene(db)
    old_a = "[0s-5s] OLD CLIP A"
    old_b = "[5s-10s] OLD CLIP B"
    newer = "[0s-15s] NEW AUTHORED THIS TURN"
    _seed_segments(
        db,
        pid,
        sid,
        [
            PromptSegment(id="ps_a", start=0, length=5, text=old_a),
            PromptSegment(id="ps_b", start=5, length=5, text=old_b),
        ],
    )
    append_events(
        db,
        pid,
        [EventInput(role="assistant", content=newer, message_type="answer", actor="assistant")],
    )
    resolved = _resolve_authored_timed_prompt(db, pid, scene_id=sid)
    assert resolved == newer


def test_bind_same_turn_wins_over_existing_destination_clips():
    db = _db()
    pid, sid = _project_scene(db)
    _seed_segments(
        db,
        pid,
        sid,
        [PromptSegment(id="ps_old", start=0, length=5, text="[0s-5s] OLD DESTINATION")],
    )
    bound, refusal = _bind_timed_prompt_tool_arguments(
        db,
        project_id=pid,
        scene_id=sid,
        arguments={"text": ""},
        same_turn_display="I've placed it.\n[0s-8s] NEW SAME-TURN BODY",
    )
    assert refusal is None
    assert bound is not None
    assert bound["text"] == "[0s-8s] NEW SAME-TURN BODY"


def test_resolve_latest_assistant_when_destination_empty():
    db = _db()
    pid, sid = _project_scene(db)
    older = "[0s-15s] FIRST DRAFT"
    newer = "[0s-15s] SECOND DRAFT"
    append_events(
        db,
        pid,
        [
            EventInput(role="assistant", content=older, message_type="answer", actor="assistant"),
            EventInput(role="assistant", content=newer + '\n```tool\n{"toolId":"x","arguments":{}}\n```', message_type="answer", actor="assistant"),
        ],
    )
    resolved = _resolve_authored_timed_prompt(db, pid, scene_id=sid)
    assert resolved == newer


def test_apply_appends_when_track_empty():
    db = _db()
    pid, sid = _project_scene(db)
    result = apply_propose_add_prompt_segment(_ctx(db, pid, sid), {"sceneId": sid, "text": AUTHORED, "start": 0, "length": 15})
    assert result["ok"] is True
    assert result["verified"] is True
    assert result["authoredSha256"] == _sha(AUTHORED)
    assert result["storedSha256"] == _sha(AUTHORED)
    assert result["destinationSceneId"] == sid
    segs = _master_segments(db, pid, sid)
    assert len(segs) == 1
    assert segs[0].text == AUTHORED
    assert "minimax" not in str(result).lower()
    assert "jobId" not in result


def test_apply_fills_single_empty_segment():
    db = _db()
    pid, sid = _project_scene(db)
    _seed_segments(db, pid, sid, [PromptSegment(id="ps_empty", start=0, length=15, text="   ")])
    result = apply_propose_add_prompt_segment(_ctx(db, pid, sid), {"sceneId": sid, "text": AUTHORED})
    assert result["verified"] is True
    assert result["segmentId"] == "ps_empty"
    segs = _master_segments(db, pid, sid)
    assert len(segs) == 1
    assert segs[0].id == "ps_empty"
    assert segs[0].text == AUTHORED


def test_apply_appends_when_existing_has_text():
    db = _db()
    pid, sid = _project_scene(db)
    first = "[0s-5s] Already placed."
    _seed_segments(db, pid, sid, [PromptSegment(id="ps_one", start=0, length=5, text=first)])
    second = "[5s-15s] New beat."
    result = apply_propose_add_prompt_segment(_ctx(db, pid, sid), {"sceneId": sid, "text": second, "start": 5, "length": 10})
    assert result["verified"] is True
    segs = _master_segments(db, pid, sid)
    assert len(segs) == 2
    assert segs[0].text == first
    assert any(s.text == second for s in segs)


def test_apply_idempotent_does_not_duplicate_owner_text():
    db = _db()
    pid, sid = _project_scene(db)
    _seed_segments(db, pid, sid, [PromptSegment(id="ps_owner", start=0, length=15, text=AUTHORED)])
    result = apply_propose_add_prompt_segment(_ctx(db, pid, sid), {"sceneId": sid, "text": AUTHORED})
    assert result["verified"] is True
    assert result["segmentId"] == "ps_owner"
    segs = _master_segments(db, pid, sid)
    assert len(segs) == 1
    assert segs[0].text == AUTHORED


def test_apply_refuses_two_empty_segments():
    db = _db()
    pid, sid = _project_scene(db)
    _seed_segments(
        db,
        pid,
        sid,
        [
            PromptSegment(id="ps_a", start=0, length=7, text=""),
            PromptSegment(id="ps_b", start=7, length=8, text="  "),
        ],
    )
    with pytest.raises(CoDirectorError):
        apply_propose_add_prompt_segment(_ctx(db, pid, sid), {"sceneId": sid, "text": AUTHORED})
    segs = _master_segments(db, pid, sid)
    assert len(segs) == 2
    assert all(not str(s.text or "").strip() for s in segs)


def test_apply_empty_text_refused():
    db = _db()
    pid, sid = _project_scene(db)
    with pytest.raises(CoDirectorError):
        apply_propose_add_prompt_segment(_ctx(db, pid, sid), {"sceneId": sid, "text": "  "})


def test_destination_verify_sha():
    db = _db()
    pid, sid = _project_scene(db)
    apply_propose_add_prompt_segment(_ctx(db, pid, sid), {"sceneId": sid, "text": AUTHORED, "start": 0, "length": 15})
    verify = _verify_timed_prompt_destination(db, pid, sid, AUTHORED)
    assert verify["verified"] is True
    assert verify["authoredSha256"] == verify["storedSha256"] == _sha(AUTHORED)
    assert _verify_timed_prompt_destination(db, pid, sid, "not the prompt")["verified"] is False


def test_claim_fence_catches_placed_cleanly_in_the_timeline():
    claimed = (
        "Logged. Here's your timed prompt locked in:\n\n"
        "[0s-5s] A ceramic cup sits on a wooden counter.\n\n"
        "It's placed cleanly in the timeline."
    )
    assert _claims_timed_prompt_placed(claimed) is True
    rewritten = _rewrite_unverified_placement_claim(claimed, verified=False)
    assert "placed cleanly" not in rewritten.lower()
    assert rewritten == AUTHORED_NOT_PLACED_COPY
    assert _claims_timed_prompt_placed("It was not placed in the timeline.") is False


def test_claim_fence_rewrites_unverified_residing_language():
    claimed = "Scene 1 → Timed Prompt has been updated. The exact text now residing in Scene 1 is ready."
    assert _claims_timed_prompt_placed(claimed) is True
    rewritten = _rewrite_unverified_placement_claim(claimed, verified=False)
    assert rewritten == AUTHORED_NOT_PLACED_COPY
    assert _rewrite_unverified_placement_claim(claimed, verified=True) == claimed


def test_inspect_is_not_place_language():
    assert _user_asks_timed_prompt_in_timeline("Is that prompt already in Timeline?") is True
    assert _user_asks_timed_prompt_in_timeline("Is it in Timeline?") is True
    assert _user_asks_timed_prompt_in_timeline("Place that prompt into Scene 1's Timed Prompt track.") is False


def test_inspect_timeline_empty_despite_assistant_claim():
    db = _db()
    pid, sid = _project_scene(db)
    append_events(
        db,
        pid,
        [
            EventInput(
                role="assistant",
                content="I added the Timed Prompt. It is now residing in Scene 1.\n[0s-15s] AUTHORED BODY",
                message_type="answer",
                actor="assistant",
            )
        ],
    )
    inspect = _inspect_timed_prompt_in_timeline(db, pid, sid)
    assert inspect["present"] is False
    assert inspect["verified"] is False
    assert AUTHORED_NOT_PLACED_COPY in inspect["answer"]


def test_inspect_timeline_verified_after_place():
    db = _db()
    pid, sid = _project_scene(db)
    append_events(
        db,
        pid,
        [EventInput(role="assistant", content=AUTHORED, message_type="answer", actor="assistant")],
    )
    apply_propose_add_prompt_segment(_ctx(db, pid, sid), {"sceneId": sid, "text": AUTHORED, "start": 0, "length": 15})
    inspect = _inspect_timed_prompt_in_timeline(db, pid, sid)
    assert inspect["present"] is True
    assert inspect["verified"] is True
    assert "currently contains" in inspect["answer"]
