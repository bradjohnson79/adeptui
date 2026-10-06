"""Durable approval. This is not a second agent.

The chat turn has already finished with a persisted proposal. Approve later
executes that stored tool and its stored arguments once, then verifies the
record that tool owns.
"""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from ...db import SessionLocal
from .admission import master_hash
from .barrier import apply_with_barrier
from .crash import maybe_crash
from .journal import (
    append_event,
    executor_call_count,
    get_status,
    load_admission,
    load_proposal_link,
    record_executor_call,
    save_admission,
    set_status,
)
from .models import FailureState, ToolReceipt, ToolRequest


def approval_identity(originating_workflow_id: str, proposal_id: str) -> str:
    return f"approve:{originating_workflow_id}:{proposal_id}"


_STORED_PROPOSAL_TOOLS = frozenset(
    {
        "timeline.propose_add_prompt_segment",
        "create_scene",
        "timeline.generate_shot",
        "timeline.continue_shot",
        "timeline.prepend_shot",
        "timeline.publish_scene",
        "propose_image_generate",
        "character_creator.create_from_brief",
        "character_creator.propose_visual_sheet",
        "prop_creator.generate_view",
        "ers.generate",
        "character_creator.generate_voice_candidates",
        "audio.generate_sfx",
        "audio.generate_ambience",
        "audio.generate_music",
        "magi.audio.generate",
        "magi.render",
        "magi.color.apply",
        "magi.recipe.apply",
        "magi.transition.apply",
        "magi.compare",
        "voice_performance.generate_takes",
        "voice_performance.save_take_to_library",
        "voice_environment.create_preview",
        "voice_environment.render",
    }
)


def _blocks(master: Any) -> list[Any]:
    if master is None:
        return []
    if isinstance(master, dict):
        inner = master.get("master")
        if inner is not None and not isinstance(inner, (str, int, float, bool)):
            found = _blocks(inner)
            if found:
                return found
    blocks = getattr(master, "batchBlocks", None)
    if blocks is None and isinstance(master, dict):
        blocks = master.get("batchBlocks") or []
    return list(blocks or [])


def master_has_text(master: Any, text: str) -> bool:
    needle = (text or "").strip()
    if not needle or master is None:
        return False
    blocks = _blocks(master)
    for block in blocks:
        segments = getattr(block, "promptSegments", None)
        if segments is None and isinstance(block, dict):
            segments = block.get("promptSegments") or []
        for segment in segments or []:
            body = getattr(segment, "text", None)
            if body is None and isinstance(segment, dict):
                body = segment.get("text")
            if needle in str(body or ""):
                return True
    return False


def _load_master(db: Session, project_id: str, scene_id: str | None) -> Any:
    if not scene_id:
        return None
    from ...director_timeline_w46.store import load_master

    return load_master(db, project_id, scene_id)


def execute_approval(payload: dict[str, Any]) -> dict[str, Any]:
    """Run the persisted proposal through ProposalService and the replay barrier."""

    approval_id = str(payload["approval_id"])
    origin = str(payload["originating_workflow_id"])
    proposal_id = str(payload["proposal_id"])
    project_id = str(payload["project_id"])
    scene_id = payload.get("scene_id")
    tool_id = str(payload["tool_id"])
    intended = str(payload.get("intended_text") or "")
    arguments = dict(payload.get("arguments") or {})
    arguments["proposalId"] = proposal_id
    if intended and not arguments.get("text"):
        arguments["text"] = intended
    crash_at = payload.get("crash_at")
    from .journal import get_mutation

    stored = get_mutation(approval_id)
    before = (stored or {}).get("before_hash") or payload.get("master_hash_before")

    request = ToolRequest(
        workflow_id=approval_id,
        tool_call_id=proposal_id,
        mutation_id=approval_id,
        project_id=project_id,
        scene_id=scene_id,
        tool_id=tool_id,
        arguments=arguments,
        action=f"approve:{tool_id}",
    )

    def _read() -> str | None:
        with SessionLocal() as db:
            return master_hash(db, project_id, scene_id)

    def _executor() -> dict[str, Any]:
        record_executor_call(approval_id)
        from ..bible.proposals import ProposalService

        with SessionLocal() as db:
            receipt = ProposalService.approve(
                db,
                project_id,
                proposal_id,
                note=payload.get("note"),
                decided_by=str(payload.get("decided_by") or "user"),
            )
        if tool_id == "timeline.propose_add_prompt_segment":
            _apply_stored_scene(project_id, scene_id, arguments)
        dumped = receipt.model_dump(mode="json") if hasattr(receipt, "model_dump") else dict(receipt)
        dumped.setdefault("ok", True)
        return dumped

    def _verify(raw: dict[str, Any], after: str | None) -> bool:
        if raw.get("proposedOnly"):
            return False
        if tool_id == "timeline.propose_add_prompt_segment":
            if not after or after == before:
                return False
            if not _scene_contract_matches(project_id, scene_id, arguments):
                return False
            with SessionLocal() as db:
                master = _load_master(db, project_id, scene_id)
            return master_has_text(master, intended or str(arguments.get("text") or ""))
        if tool_id == "character_creator.create_from_brief":
            return _character_contract_matches(project_id, arguments)
        if tool_id == "character_creator.propose_visual_sheet":
            return _sheet_contract_matches(raw, arguments)
        if tool_id == "propose_image_generate":
            return _image_contract_matches(raw, arguments)
        if tool_id == "create_scene":
            return _scene_contract_matches(project_id, scene_id, arguments)
        if tool_id == "timeline.publish_scene":
            blob = json.dumps(raw, default=str)
            return "publishedAssetId" in blob
        if tool_id in {"timeline.generate_shot", "timeline.continue_shot", "timeline.prepend_shot"}:
            blob = json.dumps(raw, default=str)
            return bool(re.search(r'"(?:queueJobId|internalJobId|jobId)"\s*:\s*"[^"]+"', blob))
        if tool_id == "prop_creator.generate_view":
            return _prop_job_submitted(raw)
        if tool_id == "ers.generate":
            return _prop_job_submitted(raw) or bool(raw.get("job_ids"))
        if tool_id in {
            "character_creator.generate_voice_candidates",
            "audio.generate_sfx",
            "audio.generate_ambience",
            "audio.generate_music",
            "magi.audio.generate",
            "magi.render",
        }:
            return _studio_job_started(raw)
        if tool_id == "magi.recipe.apply":
            from ...magi.recipes import canonical_recipe_id
            from ...magi.sequence.store import get_sequence

            saved = get_sequence(project_id)
            return str(saved.get("recipeId") or "") == canonical_recipe_id(str(arguments.get("recipeId") or ""))
        if tool_id == "magi.transition.apply":
            from ...magi.sequence.store import get_sequence
            from ...magi.transitions import canonical_transition

            kind = canonical_transition(str(arguments.get("kind") or ""))
            saved = get_sequence(project_id)
            clips = list(saved.get("clips") or [])
            clip_id = str(arguments.get("clipId") or "")
            if clip_id:
                clips = [clip for clip in clips if str(clip.get("id") or "") == clip_id]
            if kind == "none":
                return bool(clips) and all(not clip.get("transitionOutId") for clip in clips)
            return any(canonical_transition(str(clip.get("transitionOutId") or "")) == kind for clip in clips)
        if tool_id == "magi.compare":
            from ...magi.sequence.store import get_sequence

            finishing = (get_sequence(project_id).get("finishing") or {})
            mode = str(arguments.get("mode") or "compare")
            return bool(finishing.get("compareAssetId")) and str(finishing.get("viewerMode") or "") == mode
        if tool_id == "magi.color.apply":
            nested = raw.get("toolResult") if isinstance(raw.get("toolResult"), dict) else {}
            if raw.get("ok") is False or nested.get("ok") is False:
                return False
            if raw.get("liveOnly") or nested.get("liveOnly"):
                from ...magi.sequence.store import get_sequence

                grades = (get_sequence(project_id).get("finishing") or {}).get("clipGrades") or {}
                return bool(grades)
            return bool(
                raw.get("output_asset_id")
                or raw.get("assetId")
                or raw.get("verifyOk")
                or nested.get("output_asset_id")
                or nested.get("assetId")
                or nested.get("verifyOk")
            )
        if tool_id in {
            "voice_performance.generate_takes",
            "voice_performance.save_take_to_library",
            "voice_environment.create_preview",
            "voice_environment.render",
        }:
            return _voice_workflow_ready(raw)
        return False

    def _crash(checkpoint: str) -> None:
        maybe_crash(checkpoint, approval_id, crash_at if crash_at == checkpoint else None)

    outcome = apply_with_barrier(
        request,
        before_hash=before,
        read_hash=_read,
        executor=_executor,
        verify=_verify,
        on_before_execute=lambda: _crash("before_execute"),
        on_after_executor=lambda _raw: _crash("after_executor_return"),
        on_after_observed=lambda _after: _crash("after_master_observed"),
        on_after_receipt=lambda _receipt: _crash("after_verified_receipt"),
    )
    handler: dict[str, Any] = {}
    if isinstance(outcome, ToolReceipt):
        evidence = outcome.evidence or {}
        found = evidence.get("handler")
        handler = found if isinstance(found, dict) else {}
    if tool_id == "prop_creator.generate_view":
        verified = _prop_image_ready(handler)
    else:
        verified = isinstance(outcome, ToolReceipt) and outcome.verification_status == "verified"
    body: dict[str, Any] = {
        "approvalId": approval_id,
        "originatingWorkflowId": origin,
        "proposalId": proposal_id,
        "projectId": project_id,
        "sceneId": scene_id,
        "toolId": tool_id,
        "intendedText": intended,
        "verified": verified,
        "executorCalls": executor_call_count(approval_id),
        "receipt": outcome.model_dump(),
    }
    if verified:
        reply = _verified_wording(tool_id, arguments)
        _project_approval_result(project_id, origin, approval_id, reply, outcome="verified")
    else:
        if tool_id == "prop_creator.generate_view" and not isinstance(outcome, FailureState):
            reply = "The prop image is generating. It is not in the Library yet."
        elif isinstance(outcome, FailureState):
            reply = outcome.message
        else:
            reply = "The change could not be verified against project state."
        # Stable identity projection so reconnect / journal replay cannot double the bubble.
        _project_approval_result(
            project_id,
            origin,
            approval_id,
            f"Couldn't approve that proposal: {reply}",
            outcome="failed",
        )
    body["reply"] = reply
    finished = verified or (
        tool_id == "prop_creator.generate_view" and not isinstance(outcome, FailureState)
    )
    append_event(
        approval_id,
        {
            "type": "completed" if finished else "error",
            "requestId": approval_id,
            "workflowId": approval_id,
            "content": reply,
            "verified": verified,
            "receipt": body["receipt"],
            "approvalId": approval_id,
            "proposalId": proposal_id,
            "toolId": tool_id,
        },
    )
    set_status(approval_id, "SUCCESS" if finished else "ERROR", body)
    return body


def _project_approval_result(
    project_id: str,
    origin: str,
    approval_id: str,
    reply: str,
    *,
    outcome: str = "verified",
) -> None:
    """Project one approval result into conversation with a stable message id."""
    from ..conversation_events import EventInput, append_events

    suffix = "verified" if outcome == "verified" else "failed"
    message_id = f"{approval_id}:{suffix}"
    with SessionLocal() as db:
        append_events(
            db,
            project_id,
            [
                EventInput(
                    role="assistant",
                    content=reply,
                    request_id=origin,
                    client_request_id=message_id,
                    message_id=message_id,
                    actor="assistant",
                )
            ],
        )
        db.commit()


def _project_verified(project_id: str, origin: str, approval_id: str, reply: str) -> None:
    _project_approval_result(project_id, origin, approval_id, reply, outcome="verified")


def _proposal_payload(db: Session, project_id: str, proposal_id: str) -> dict[str, Any]:
    from ...db import CoDirectorProposal

    row = db.get(CoDirectorProposal, proposal_id)
    if row is None or row.project_id != project_id:
        raise ValueError("That proposal is not in this project.")
    link = load_proposal_link(proposal_id)
    try:
        stored = json.loads(row.payload_json or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("The stored proposal could not be read.") from exc
    tool_id = str((link or {}).get("tool_id") or stored.get("toolId") or "")
    arguments = stored.get("arguments") if isinstance(stored.get("arguments"), dict) else {}
    if tool_id not in _STORED_PROPOSAL_TOOLS:
        raise ValueError("Approval can only execute the proposal that was already authorized.")
    origin = str((link or {}).get("originating_workflow_id") or row.request_id or proposal_id)
    scene_id = (link or {}).get("scene_id") or arguments.get("sceneId")
    intended = str((link or {}).get("intended_text") or arguments.get("text") or "")
    if tool_id == "timeline.propose_add_prompt_segment" and not intended.strip():
        raise ValueError("The stored proposal has no timed-prompt text.")
    return {
        "approval_id": approval_identity(origin, proposal_id),
        "originating_workflow_id": origin,
        "proposal_id": proposal_id,
        "project_id": project_id,
        "scene_id": scene_id,
        "tool_id": tool_id,
        "intended_text": intended,
        "arguments": arguments,
        "master_hash_before": master_hash(db, project_id, scene_id),
    }


def _apply_stored_scene(project_id: str, scene_id: str | None, arguments: dict[str, Any]) -> None:
    fields: dict[str, Any] = {}
    if arguments.get("sceneDurationSec") is not None:
        fields["duration_sec"] = float(arguments["sceneDurationSec"])
    if arguments.get("aspectRatio"):
        fields["aspect_ratio"] = str(arguments["aspectRatio"])
    if not fields or not scene_id:
        return
    from ...services.scene_service import SceneService

    with SessionLocal() as db:
        SceneService.update(db, project_id, str(scene_id), fields)


def _scene_contract_matches(project_id: str, scene_id: str | None, arguments: dict[str, Any]) -> bool:
    want_duration = arguments.get("sceneDurationSec")
    if want_duration is None:
        want_duration = arguments.get("durationSec")
    want_ratio = arguments.get("aspectRatio")
    if want_duration is None and not want_ratio:
        return True
    if not scene_id:
        return False
    from ...services.scene_service import SceneService

    with SessionLocal() as db:
        scene = SceneService.get(db, project_id, str(scene_id))
    if want_duration is not None and abs(float(scene.duration_sec or 0) - float(want_duration)) > 0.05:
        return False
    if want_ratio and str(getattr(scene, "aspect_ratio", "") or "") != str(want_ratio):
        return False
    return True


def _character_contract_matches(project_id: str, arguments: dict[str, Any]) -> bool:
    name = str(arguments.get("name") or "").strip()
    brief = str(arguments.get("brief") or "").strip()
    if not name or not brief:
        return False
    from ...character_identity import service as ci

    with SessionLocal() as db:
        profiles = [
            profile
            for profile in ci.list_profiles(db, project_id)
            if getattr(profile, "name", "") == name and str(getattr(profile, "project_id", "") or getattr(profile, "projectId", "")) == project_id
        ]
        if len(profiles) != 1:
            return False
        profile = profiles[0]
        description = str(getattr(profile, "description", "") or "")
        if brief[:4000] not in description and description not in brief:
            return False
        traits = ci.list_traits(db, project_id, str(profile.id))
    source = next((item.get("value") for item in traits if item.get("key") == "source_brief"), "")
    return str(source or "") == brief or brief.startswith(str(source or "")) and bool(source)


def _sheet_contract_matches(raw: dict[str, Any], arguments: dict[str, Any]) -> bool:
    """The stored character id was the one the existing sheet tool used, and a job exists."""

    character_id = str(arguments.get("characterId") or "").strip()
    if not character_id:
        return False
    tool_result = raw.get("toolResult") if isinstance(raw.get("toolResult"), dict) else {}
    if raw.get("ok") is False or tool_result.get("ok") is False:
        return False
    if str(tool_result.get("status") or "") == "missing_description":
        return False
    if tool_result.get("errorCode") or tool_result.get("errorMessage"):
        return False
    blob = json.dumps(raw, default=str)
    if character_id not in blob:
        return False
    return bool(re.search(r'"(?:jobId|job_id)"\s*:\s*"([^"]+)"', blob))


def _image_contract_matches(raw: dict[str, Any], arguments: dict[str, Any]) -> bool:
    if not arguments.get("prompt") or not arguments.get("aspectRatio") or not arguments.get("referenceAssetId"):
        return False
    tool_result = raw.get("toolResult") if isinstance(raw.get("toolResult"), dict) else {}
    if raw.get("ok") is False or tool_result.get("ok") is False:
        return False
    if tool_result.get("errorCode") or tool_result.get("errorMessage"):
        return False
    blob = json.dumps(raw, default=str)
    if not re.search(r'"jobId"\s*:\s*"([^"]+)"', blob):
        return False
    folded = blob.lower()
    if "video.generate" in folded or "propose_video" in folded:
        return False
    return "image" in folded or "job" in folded or "intent" in folded


def _prop_job_submitted(raw: dict[str, Any]) -> bool:
    """The Prop Creator button accepted the request. The picture may still be running."""

    tool_result = raw.get("toolResult")
    if isinstance(tool_result, dict) and tool_result.get("ok") and str(tool_result.get("jobId") or "").strip():
        return True
    if raw.get("ok") and str(raw.get("jobId") or "").strip():
        return True
    return bool(re.search(r'"jobId"\s*:\s*"([^"]+)"', json.dumps(raw, default=str)))


def _prop_image_ready(raw: dict[str, Any]) -> bool:
    """Success only after the Prop Creator job has a library picture."""

    blob = json.dumps(raw, default=str)
    asset_id = str(raw.get("assetId") or "")
    if not asset_id:
        match = re.search(r'"assetId"\s*:\s*"([^"]+)"', blob)
        asset_id = match.group(1) if match else ""
    if not asset_id:
        return False
    status = str(raw.get("status") or "").lower()
    if status and status not in {"complete", "completed", "done", "success"}:
        return False
    return "library" in blob.lower() or bool(asset_id)


def _voice_workflow_ready(raw: dict[str, Any]) -> bool:
    """A voice take, Library save, or environment render finished through the shared service."""
    blob = json.dumps(raw, default=str)
    if re.search(r'"mock"\s*:\s*true', blob):
        return False
    if re.search(r'"recordId"\s*:\s*"[^"]+"', blob) and re.search(r'"audioAssetId"\s*:\s*"[^"]+"', blob):
        return True
    if re.search(r'"assetId"\s*:\s*"[^"]+"', blob):
        return True
    if re.search(r'"processedAudioAssetId"\s*:\s*"[^"]+"', blob):
        return True
    return False


def _studio_job_started(raw: dict[str, Any]) -> bool:
    """A Voice or Audio handler accepted the work. The clip may still be rendering."""

    blob = json.dumps(raw, default=str)
    if re.search(r'"(?:batchId|voiceId|candidateId|jobId)"\s*:\s*"[^"]+"', blob):
        return True
    return bool(re.search(r'"candidateCount"\s*:\s*[1-9]', blob) and re.search(r'"mock"\s*:\s*false', blob))


def _verified_wording(tool_id: str, arguments: dict[str, Any]) -> str:
    if tool_id == "timeline.propose_add_prompt_segment":
        duration = arguments.get("sceneDurationSec")
        ratio = arguments.get("aspectRatio")
        extra = ""
        if duration is not None or ratio:
            extra = f" The scene is {duration:g}s" if duration is not None else " The scene"
            if ratio:
                extra += f" at {ratio}" if duration is not None else f" is {ratio}"
            extra += "."
        return f"The timed prompt was added.{extra}"
    if tool_id == "propose_image_generate":
        return (
            "The still image request was accepted"
            f" at {arguments.get('aspectRatio')} using the existing reference."
            " The picture is not finished until it is in the Library."
        )
    if tool_id == "character_creator.create_from_brief":
        name = str(arguments.get("name") or "").strip() or "the new character"
        return (
            f"The new character {name} was created from the brief. "
            "Refresh the page to see the new character in Character Creator."
        )
    if tool_id == "character_creator.propose_visual_sheet":
        name = str(arguments.get("characterName") or arguments.get("name") or "").strip() or "that character"
        if str(arguments.get("heroAssetId") or "").strip():
            return f"The front reference for {name} is using the existing image."
        return (
            f"The front reference for {name} was started. "
            "There isn’t an existing character image, so I’ll create the front reference first "
            "and use that as the character’s visual identity."
        )
    if tool_id == "timeline.publish_scene":
        return "The scene is published. The master is the finished picture of this scene."
    if tool_id == "timeline.prepend_shot":
        return "Timeline started the opening shot. It is placed before the first picture when the take is finished."
    if tool_id == "timeline.continue_shot":
        return "Timeline continued that shot from the finished picture."
    if tool_id == "timeline.generate_shot":
        return "Timeline started that shot. The picture is not finished until the take is in the Library."
    if tool_id == "create_scene":
        name = str(arguments.get("characterName") or "").strip()
        if name:
            return f"The scene was created with {name}."
        return "The scene was created."
    if tool_id == "prop_creator.generate_view":
        return "The prop image is in the Library."
    if tool_id == "character_creator.generate_voice_candidates":
        name = str(arguments.get("name") or arguments.get("characterName") or "that character").strip()
        if str(arguments.get("testLine") or "").strip():
            return (
                f"Voice Studio started a performance for {name}. "
                "The clip is not assigned until you keep a take."
            )
        return f"Voice Studio started a voice for {name}. It is not assigned until you keep a take."
    if tool_id == "audio.generate_ambience":
        return "Audio Studio started that ambience. The clip is not ready yet."
    if tool_id == "voice_performance.generate_takes":
        return "The takes were generated with the character's saved voice."
    if tool_id == "voice_performance.save_take_to_library":
        return "The take was saved to the Library. The original recording is unchanged."
    if tool_id == "voice_environment.render":
        return "The final take was saved. The original recording is unchanged."
    if tool_id == "voice_environment.create_preview":
        return "The environment preview is ready. The original recording is unchanged."
    if tool_id == "audio.generate_sfx":
        return "Audio Studio started that sound effect. The clip is not ready yet."
    if tool_id == "audio.generate_music":
        return "Audio Studio started that music cue. The clip is not ready yet."
    if tool_id == "magi.render":
        return "MAGI started the final render. The file is not in the Library until the render finishes."
    if tool_id == "magi.recipe.apply":
        return "The MAGI recipe is applied. The clips and their timing are unchanged."
    if tool_id == "magi.transition.apply":
        return "The transition is set on the cut between those clips."
    if tool_id == "magi.compare":
        return "Compare is pointed at the original picture."
    if tool_id == "magi.color.apply":
        return "The lighting look is on the viewer. Final Render commits it."
    if tool_id == "magi.audio.generate":
        kind = str(arguments.get("kind") or "audio").strip().lower()
        if kind == "sfx":
            return "MAGI started that sound effect. It is not on the scene until the clip is ready."
        return "MAGI started that music. It is not on the scene until the clip is ready."
    if tool_id == "ers.generate":
        if str(arguments.get("sourceAssetId") or "").strip():
            return "The environment image is using the existing reference."
        return (
            "There isn’t an existing environment image, so Qwen Image will create the first view "
            "and use that as the environment’s visual identity."
        )
    return "The approved change was verified."


codirector_approve = None


def register_approval_workflow():
    """Register after DBOS() exists. Importing this module must not launch DBOS."""

    global codirector_approve
    if codirector_approve is not None:
        return codirector_approve
    from dbos import DBOS

    @DBOS.step()
    def _approval_step(payload: dict[str, Any]) -> dict[str, Any]:
        return execute_approval(payload)

    @DBOS.workflow()
    def _codirector_approve(payload: dict[str, Any]) -> dict[str, Any]:
        return _approval_step(payload)

    codirector_approve = _codirector_approve
    return codirector_approve


async def begin_approval(
    db: Session,
    *,
    project_id: str,
    proposal_id: str,
    note: str | None,
    decided_by: str,
    crash_at: str | None = None,
) -> str:
    from .runtime import ensure_started

    ensure_started()
    payload = _proposal_payload(db, project_id, proposal_id)
    payload["note"] = note
    payload["decided_by"] = decided_by
    payload["crash_at"] = crash_at
    approval_id = str(payload["approval_id"])
    existing = get_status(approval_id)
    if existing == "SUCCESS":
        return approval_id
    if existing is not None or load_admission(approval_id) is not None:
        # The proposal was not verified. Re-enter the barrier. Do not execute again
        # when Master already contains the change.
        execute_approval(payload)
        return approval_id
    save_admission(approval_id, payload)
    await _start(payload)
    return approval_id


async def _start(payload: dict[str, Any]) -> None:
    from dbos import DBOS, SetWorkflowID

    with SetWorkflowID(str(payload["approval_id"])):
        await DBOS.start_workflow_async(codirector_approve, payload)


async def observe_prop_image(project_id: str, result: dict[str, Any]) -> dict[str, Any]:
    """Watch the job the Prop Creator tool already started. Do not start another."""

    import asyncio
    import time

    if result.get("toolId") != "prop_creator.generate_view" or result.get("verified"):
        return result
    blob = json.dumps(result.get("receipt") or {}, default=str)
    job_match = re.search(r'"jobId"\s*:\s*"([^"]+)"', blob)
    prop_match = re.search(r'"propId"\s*:\s*"([^"]+)"', blob)
    job_id = job_match.group(1) if job_match else ""
    prop_id = prop_match.group(1) if prop_match else ""
    if not job_id:
        return result
    from ...db import Job

    deadline = time.time() + 600
    last_message = ""
    while time.time() < deadline:
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job is None or job.project_id != project_id:
                result["reply"] = f"Prop image job {job_id} was not found."
                result["verified"] = False
                return result
            status = (job.status or "").lower()
            last_message = job.message or last_message
            if status in {"failed", "error", "cancelled"}:
                result["verified"] = False
                result["reply"] = last_message or f"Prop image job {job_id} {status}."
                return result
            if status in {"done", "completed", "complete", "success"}:
                asset_id = ""
                if prop_id:
                    from ...prop_creator.service import get_prop

                    prop = get_prop(db, project_id, prop_id)
                    candidate = next((item for item in prop.candidates if item.job_id == job_id), None)
                    asset_id = str(getattr(candidate, "asset_id", "") or "")
                if not asset_id:
                    try:
                        params = json.loads(job.params_json or "{}")
                    except Exception:
                        params = {}
                    asset_id = str(params.get("output_asset_id") or "")
                if asset_id:
                    result["verified"] = True
                    result["reply"] = "The prop image is in the Library."
                    result["assetId"] = asset_id
                    result["jobId"] = job_id
                    _project_verified(
                        project_id,
                        str(result.get("approvalId") or job_id),
                        str(result.get("approvalId") or job_id),
                        result["reply"],
                    )
                    return result
        await asyncio.sleep(2)
    result["verified"] = False
    result["reply"] = last_message or "The prop image job did not finish."
    return result


async def wait_approval(approval_id: str) -> dict[str, Any]:
    from .turn import iter_projection

    completed: dict[str, Any] | None = None
    async for event in iter_projection(approval_id):
        if event.get("type") in {"completed", "error"}:
            completed = event
    if completed is None:
        return {"verified": False, "approvalId": approval_id, "reply": "Approval did not finish."}
    return {
        "verified": bool(completed.get("verified")),
        "approvalId": approval_id,
        "reply": completed.get("content") or "",
        "receipt": completed.get("receipt") or {},
        "proposalId": completed.get("proposalId"),
        "toolId": completed.get("toolId"),
    }
