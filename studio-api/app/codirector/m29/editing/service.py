"""M2.9 editing / SFX / music cue proposals — apply to director timeline."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from ...executive.models import JobType
from .. import fixture_mode_enabled
from ..audio.service import AudioService
from ..fixtures import fixture_edit_result
from ..providers import wants_fixture
from ..store import enqueue_executive_job


class EditingService:
    @staticmethod
    def propose_edit(
        db: Session,
        *,
        project_id: str,
        ops: list[dict[str, Any]] | None = None,
        scene_id: str | None = None,
        owner: str = "user",
    ) -> dict[str, Any]:
        """Propose edit ops for approval.

        Outside an env-gated fixture run the proposal is only ever the caller's own ops:
        there is no edit planner that can invent them, so an empty request is refused
        rather than answered with fixture ops that look like a suggestion.
        """
        del db, owner
        if wants_fixture():
            result = fixture_edit_result({"ops": ops})
            result["projectId"] = project_id
            result["requiresApproval"] = True
            result["fixture"] = fixture_mode_enabled()
            return result

        cleaned = [op for op in (ops or []) if isinstance(op, dict) and op]
        if not cleaned:
            raise ValueError(
                "edit_propose requires explicit ops: no automatic edit planner is wired, "
                "so Adept UI will not invent edit operations."
            )
        return {
            "editId": f"edit-{uuid.uuid4().hex[:10]}",
            "provider": "m29_editing",
            "fixture": False,
            "status": "proposed",
            "ops": cleaned,
            "requiresApproval": True,
            "projectId": project_id,
            "sceneId": scene_id,
            "honesty": (
                "Proposal echoes the requested ops for approval. Nothing has been applied "
                "to the director timeline."
            ),
        }

    @staticmethod
    def apply_edit(
        db: Session,
        *,
        project_id: str,
        ops: list[dict[str, Any]],
        approved: bool = False,
        scene_id: str | None = None,
        owner: str = "user",
    ) -> dict[str, Any]:
        if not approved:
            raise PermissionError("edit_apply blocked: human approval required")
        payload = {"ops": ops, "approved": True, "m29": True, "sceneId": scene_id}
        if fixture_mode_enabled():
            payload["fixtureComplete"] = True
        job = enqueue_executive_job(
            db,
            project_id=project_id,
            job_type=JobType.EDIT_APPLY,
            payload=payload,
            scene_id=scene_id,
            owner=owner,
        )
        return {
            "jobId": job.id,
            "ops": ops,
            "status": "queued" if not fixture_mode_enabled() else "applied",
            "fixture": fixture_mode_enabled(),
            "projectId": project_id,
        }

    @staticmethod
    def propose_sfx_cue(
        db: Session,
        *,
        project_id: str,
        prompt: str = "SFX cue",
        scene_id: str | None = None,
        owner: str = "user",
        **params: Any,
    ) -> dict[str, Any]:
        out = AudioService.generate(
            db,
            project_id=project_id,
            kind="sfx",
            prompt=prompt,
            scene_id=scene_id,
            owner=owner,
            **params,
        )
        out["requiresApproval"] = True
        out["proposalKind"] = "sfx_cue"
        return out

    @staticmethod
    def propose_music_cue(
        db: Session,
        *,
        project_id: str,
        prompt: str = "Music cue",
        scene_id: str | None = None,
        owner: str = "user",
        **params: Any,
    ) -> dict[str, Any]:
        out = AudioService.generate(
            db,
            project_id=project_id,
            kind="music",
            prompt=prompt,
            scene_id=scene_id,
            owner=owner,
            **params,
        )
        out["requiresApproval"] = True
        out["proposalKind"] = "music_cue"
        return out

    @staticmethod
    def execute_job(db: Session, payload: dict[str, Any], project_id: str) -> dict[str, Any]:
        if not payload.get("approved"):
            raise PermissionError("edit_apply blocked: human approval required")
        ops = list(payload.get("ops") or [])
        if wants_fixture(payload):
            return {
                "ops": ops,
                "status": "applied",
                "fixture": True,
                "projectId": project_id,
            }

        scene_id = payload.get("sceneId")
        if not scene_id:
            raise ValueError("edit_apply requires sceneId for director timeline mutation")

        from ....db import Scene
        from ....director_timeline import dumps_director_timeline, parse_director_timeline

        scene = db.get(Scene, scene_id)
        if not scene or scene.project_id != project_id:
            raise ValueError(f"Scene not found: {scene_id}")

        before = scene.director_json or ""
        tl = parse_director_timeline(
            before,
            fallback_duration=float(scene.duration_sec or 5),
            fallback_prompt=scene.prompt or "",
        )
        history = []
        try:
            cont = json.loads(scene.continuity_json or "{}")
        except json.JSONDecodeError:
            cont = {}
        undo_stack = list(cont.get("m29EditUndo") or [])
        redo_stack = list(cont.get("m29EditRedo") or [])

        for op in ops:
            name = (op.get("op") or op.get("type") or "").lower()
            if name == "undo":
                if not undo_stack:
                    continue
                redo_stack.append(scene.director_json or "")
                scene.director_json = undo_stack.pop()
                tl = parse_director_timeline(
                    scene.director_json,
                    fallback_duration=float(scene.duration_sec or 5),
                    fallback_prompt=scene.prompt or "",
                )
                history.append({"op": "undo"})
                continue
            if name == "redo":
                if not redo_stack:
                    continue
                undo_stack.append(scene.director_json or "")
                scene.director_json = redo_stack.pop()
                tl = parse_director_timeline(
                    scene.director_json,
                    fallback_duration=float(scene.duration_sec or 5),
                    fallback_prompt=scene.prompt or "",
                )
                history.append({"op": "redo"})
                continue

            undo_stack.append(dumps_director_timeline(tl))
            redo_stack.clear()

            if name in {"trim", "speed"}:
                clip_id = op.get("clipId")
                clips = tl.video_clips + tl.image_clips + tl.audio_clips + tl.sfx_clips
                for c in clips:
                    if c.id == clip_id or (not clip_id and clips):
                        if op.get("trimStart") is not None:
                            c.trim_start = float(op["trimStart"])
                        if op.get("length") is not None:
                            c.length = float(op["length"])
                        if op.get("start") is not None:
                            c.start = float(op["start"])
                        break
            elif name in {"replace", "alt_take", "clip_replace"}:
                clip_id = op.get("clipId")
                new_asset = op.get("assetId")
                for c in tl.video_clips + tl.image_clips:
                    if c.id == clip_id or (not clip_id and new_asset):
                        c.asset_id = new_asset
                        break
            elif name in {"insert", "shot_insert"}:
                from ....director_timeline import TimelineClip

                clip = TimelineClip(
                    asset_id=op.get("assetId"),
                    start=float(op.get("start") or 0),
                    length=float(op.get("length") or 4),
                    label=str(op.get("label") or "insert"),
                )
                track = (op.get("track") or "video").lower()
                if track == "audio":
                    tl.audio_clips.append(clip)
                elif track == "sfx":
                    tl.sfx_clips.append(clip)
                else:
                    tl.video_clips.append(clip)
            elif name == "ripple":
                delta = float(op.get("delta") or op.get("amount") or 0)
                after = float(op.get("after") or 0)
                for c in tl.video_clips + tl.image_clips + tl.audio_clips + tl.sfx_clips:
                    if c.start >= after:
                        c.start = max(0.0, c.start + delta)
            elif name == "transition":
                # Store transition metadata on continuity; no silent media overwrite.
                transitions = list(cont.get("transitions") or [])
                transitions.append(op)
                cont["transitions"] = transitions
            history.append({"op": name, **{k: v for k, v in op.items() if k != "op"}})

        scene.director_json = dumps_director_timeline(tl)
        cont["m29EditUndo"] = undo_stack[-50:]
        cont["m29EditRedo"] = redo_stack[-50:]
        scene.continuity_json = json.dumps(cont)
        db.commit()
        return {
            "ops": ops,
            "status": "applied",
            "fixture": False,
            "projectId": project_id,
            "sceneId": scene_id,
            "history": history,
            "beforeHash": hash(before),
            "provider": "director_timeline",
        }
