"""M2.9 Director Timeline Generation propose/apply (approval-aware).

Apply persists clips to SceneTimelineMaster. Bible mutations route through ProposalService
and are never silently applied.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import ensure_m29_tables


def _now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


class TimelineService:
    @staticmethod
    def propose(
        db: Session,
        *,
        project_id: str,
        scene_id: str | None = None,
        clips: list[dict[str, Any]] | None = None,
        notes: str = "",
        bible_mutations: dict[str, Any] | None = None,
        branch: str | None = None,
    ) -> dict[str, Any]:
        ensure_m29_tables()
        pid = uuid.uuid4().hex
        proposal = {
            "clips": clips
            or [
                {"clipId": "clip-1", "assetId": None, "start": 0, "length": 4, "track": "video"},
            ],
            "notes": notes,
            "requiresApproval": True,
            "bibleMutations": bible_mutations,
            "branch": branch or "main",
        }
        now = _now()
        db.execute(
            text(
                "INSERT INTO m29_timeline_proposals "
                "(id, project_id, scene_id, status, proposal_json, created_at, updated_at) "
                "VALUES (:id, :pid, :sid, :status, :pj, :c, :u)"
            ),
            {
                "id": pid,
                "pid": project_id,
                "sid": scene_id,
                "status": "pending",
                "pj": json.dumps(proposal),
                "c": now,
                "u": now,
            },
        )
        db.commit()
        return {
            "id": pid,
            "projectId": project_id,
            "sceneId": scene_id,
            "status": "pending",
            "proposal": proposal,
            "requiresApproval": True,
        }

    @staticmethod
    def get(db: Session, proposal_id: str) -> dict[str, Any] | None:
        ensure_m29_tables()
        row = db.execute(
            text(
                "SELECT id, project_id, scene_id, status, proposal_json, created_at, updated_at "
                "FROM m29_timeline_proposals WHERE id = :id"
            ),
            {"id": proposal_id},
        ).mappings().first()
        if not row:
            return None
        return {
            "id": row["id"],
            "projectId": row["project_id"],
            "sceneId": row["scene_id"],
            "status": row["status"],
            "proposal": json.loads(row["proposal_json"] or "{}"),
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "requiresApproval": True,
        }

    @staticmethod
    def approve(db: Session, proposal_id: str, *, actor: str = "user") -> dict[str, Any]:
        prop = TimelineService.get(db, proposal_id)
        if not prop:
            raise KeyError(proposal_id)
        if prop["status"] != "pending":
            raise PermissionError(f"proposal not pending: {prop['status']}")
        db.execute(
            text(
                "UPDATE m29_timeline_proposals SET status = :s, updated_at = :u WHERE id = :id"
            ),
            {"s": "approved", "u": _now(), "id": proposal_id},
        )
        db.commit()
        prop["status"] = "approved"
        prop["approvedBy"] = actor
        return prop

    @staticmethod
    def reject(db: Session, proposal_id: str, *, actor: str = "user") -> dict[str, Any]:
        prop = TimelineService.get(db, proposal_id)
        if not prop:
            raise KeyError(proposal_id)
        db.execute(
            text(
                "UPDATE m29_timeline_proposals SET status = :s, updated_at = :u WHERE id = :id"
            ),
            {"s": "rejected", "u": _now(), "id": proposal_id},
        )
        db.commit()
        prop["status"] = "rejected"
        prop["rejectedBy"] = actor
        return prop

    @staticmethod
    def apply(db: Session, proposal_id: str, *, actor: str = "user") -> dict[str, Any]:
        """Apply only after human approval — persist Master clips; Bible via proposal bus."""
        prop = TimelineService.get(db, proposal_id)
        if not prop:
            raise KeyError(proposal_id)
        if prop["status"] != "approved":
            raise PermissionError("timeline apply blocked: human approval required")

        project_id = prop["projectId"]
        scene_id = prop.get("sceneId")
        proposal = prop.get("proposal") or {}
        clips = list(proposal.get("clips") or [])
        bible_mutations = proposal.get("bibleMutations")
        bible_proposal_id = None

        # Bible mutations must go through ProposalService — never silent apply.
        if bible_mutations:
            from ...bible.proposals import ProposalService
            from ...bible.schemas import BibleMutationSet

            if isinstance(bible_mutations, dict):
                mutation_set = BibleMutationSet.model_validate(bible_mutations)
            else:
                mutation_set = bible_mutations
            bible_prop = ProposalService.create_proposal(
                db,
                project_id=project_id,
                proposal_type="bible_mutation",
                title=f"M2.9 timeline Bible handoff ({proposal_id[:8]})",
                summary=str(proposal.get("notes") or "Timeline apply Bible mutations"),
                payload=mutation_set,
                created_by=actor,
            )
            bible_proposal_id = bible_prop.id

        applied_scene = None
        if scene_id:
            from ....db import Scene
            from ....director_timeline_w46 import store as timeline_store
            from ....director_timeline_w46.contracts import BatchClip
            from ....director_timeline_w46.master_clip_mutate import append_clip, ensure_windows, snapshot
            from ....director_timeline_w46.service import load_timeline_bundle

            scene = db.get(Scene, scene_id)
            if scene and scene.project_id == project_id:
                bundle = load_timeline_bundle(db, project_id, scene_id)
                if not bundle.get("ok"):
                    raise KeyError(scene_id)
                master = bundle["master"]
                ensure_windows(
                    master,
                    scene_id=scene_id,
                    duration_sec=float(scene.duration_sec or 5),
                )
                # Version branch metadata
                try:
                    cont = json.loads(scene.continuity_json or "{}")
                except json.JSONDecodeError:
                    cont = {}
                branches = list(cont.get("timelineBranches") or [])
                branch = proposal.get("branch") or "main"
                branches.append(
                    {
                        "branch": branch,
                        "proposalId": proposal_id,
                        "snapshot": snapshot(master),
                        "at": _now(),
                    }
                )
                cont["timelineBranches"] = branches[-20:]
                cont["activeTimelineBranch"] = branch

                for c in clips:
                    track = (c.get("track") or "video").lower()
                    start = float(c.get("start") or 0)
                    clip_id = str(c.get("clipId") or "").strip()
                    fields: dict[str, Any] = {
                        "kind": (
                            "audio"
                            if track in {"dialogue", "music", "audio"}
                            else ("sfx" if track == "sfx" else ("image" if track == "image" else "video"))
                        ),
                        "assetId": c.get("assetId"),
                        "start": start,
                        "length": float(c.get("length") or 4),
                        "label": str(c.get("label") or ""),
                    }
                    if clip_id:
                        fields["id"] = clip_id
                    clip = BatchClip.model_validate(fields)
                    attr = (
                        "audioClips"
                        if track in {"dialogue", "music", "audio"}
                        else ("sfxClips" if track == "sfx" else "visualClips")
                    )
                    append_clip(master, clip, start, attr)
                timeline_store.save_master(db, project_id, scene_id, master, bump_revision=True)
                scene.continuity_json = json.dumps(cont)
                db.commit()
                applied_scene = scene_id

        db.execute(
            text(
                "UPDATE m29_timeline_proposals SET status = :s, updated_at = :u WHERE id = :id"
            ),
            {"s": "applied", "u": _now(), "id": proposal_id},
        )
        db.commit()
        prop["status"] = "applied"
        prop["appliedBy"] = actor
        prop["applied"] = True
        prop["appliedSceneId"] = applied_scene
        prop["bibleProposalId"] = bible_proposal_id
        prop["bibleMutationsPendingApproval"] = bool(bible_proposal_id)
        return prop
