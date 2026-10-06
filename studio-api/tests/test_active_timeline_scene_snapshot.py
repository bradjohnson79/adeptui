"""ACTIVE TIMELINE SCENE SNAPSHOT — approval and shot refs."""

from __future__ import annotations

from app.codirector.active_timeline_scene_snapshot import render_timeline_snapshot_block
from app.codirector.project_grounding import grounding_reply


def test_grounding_shot_questions_use_timeline_snapshot() -> None:
    inspect = {
        "bound": True,
        "characters": [{"name": "Korri"}, {"name": "Anadriya"}],
        "activeScene": {"name": "Venture Corridor Walk"},
        "timelineSnapshot": {
            "hasTimelineSnapshot": True,
            "generatorId": "minimax-h3",
            "generatorReadiness": "Ready",
            "referencedInShot": [
                {"promptName": "Korri", "type": "character", "tag": "@Korri"},
                {"promptName": "Anadriya", "type": "character", "tag": "@Anadriya"},
            ],
            "environment": {"promptName": "Venture corridor", "tag": "#VentureCorridorScene"},
            "batchApproval": {"approved": 3, "draft": 0, "total": 3},
        },
    }
    assert "Korri" in (grounding_reply(inspect, "Who is referenced in this shot?") or "")
    assert "Anadriya" in (grounding_reply(inspect, "Who is referenced in this shot?") or "")
    assert "Venture corridor" in (grounding_reply(inspect, "What environment is assigned?") or "")
    assert "minimax-h3" in (grounding_reply(inspect, "What generator is this scene using?") or "")
    approval = grounding_reply(inspect, "How many Timeline batches are approved?") or ""
    assert "3 Approved" in approval
    assert "0 Draft" in approval
    assert "lifecycle" in approval.lower()
    production = grounding_reply(
        {
            **inspect,
            "productionLifecycle": {
                "projectStage": "TIMELINE_ASSEMBLY",
                "productionStatus": "IN_PROGRESS",
                "sceneReadyStatus": "READY",
            },
        },
        "What is the production status of this scene?",
    ) or ""
    assert "READY" in production
    assert "batch approval" in production.lower()
    assert "3 Approved" not in production
    happens = grounding_reply(
        {
            **inspect,
            "timelineSnapshot": {
                **inspect["timelineSnapshot"],
                "sceneSummary": "Anadriya presses Korri on the missing crew.",
                "scenePrompt": "Korri sits for the interview.",
            },
        },
        "What happens in this scene?",
    ) or ""
    assert "Anadriya presses Korri" in happens
    take = grounding_reply(
        {
            **inspect,
            "timelineSnapshot": {
                **inspect["timelineSnapshot"],
                "currentTake": {"takeId": "take_12b", "batchLabel": "Batch 1"},
            },
        },
        "What is the current take?",
    ) or ""
    assert "take_12b" in take
    assert "Batch 1" in take


def test_grounding_without_snapshot_does_not_invent_shot_refs() -> None:
    inspect = {
        "bound": True,
        "characters": [{"name": "Korri"}],
        "activeScene": {"name": "Scene 1"},
    }
    reply = grounding_reply(inspect, "Who is referenced in this shot?") or ""
    assert "no active Timeline shot" in reply or "cannot list" in reply.lower()


def test_timeline_snapshot_block_includes_bounded_prompts() -> None:
    block = render_timeline_snapshot_block(
        {
            "hasTimelineSnapshot": True,
            "activeScene": {"name": "12B — Quarters Interview"},
            "generatorId": "minimax-h3",
            "generatorReadiness": "Ready",
            "batchApproval": {"approved": 1, "draft": 0, "total": 1},
            "referencedInShot": [{"promptName": "Korri", "type": "character", "tag": "@Korri"}],
            "environment": {"promptName": "Quarters", "tag": "#Quarters"},
            "scenePrompt": "Korri sits for the interview in tight quarters.",
            "sceneSummary": "Anadriya presses Korri on the missing crew.",
            "currentTimedPrompt": {"start": 2.0, "text": "Korri looks down, then answers."},
            "currentTake": {"takeId": "take_12b", "batchLabel": "Batch 1"},
        }
    )
    assert "12B — Quarters Interview" in block
    assert "minimax-h3" in block
    assert "Scene Prompt: Korri sits for the interview" in block
    assert "What happens: Anadriya presses Korri" in block
    assert "Timed Prompt @ 2.0s: Korri looks down" in block
    assert "Current take: take_12b (Batch 1)" in block
    assert render_timeline_snapshot_block({"hasTimelineSnapshot": False}) == ""
