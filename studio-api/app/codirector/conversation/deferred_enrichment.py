"""Background Wiki / Living Brief enrichment after response streaming begins.

Law: WIKI_VERIFICATION_NEVER_BLOCKS_TTFT — this module runs only after stream begins.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from .wiki_verification import WIKI_VERIFICATION_NEVER_BLOCKS_TTFT, build_verification

logger = logging.getLogger(__name__)

assert WIKI_VERIFICATION_NEVER_BLOCKS_TTFT is True


def run_deferred_enrichment(
    db: Session,
    *,
    project_id: str,
    user_message: str,
    messages: list[dict] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Extract → classify → persist → full read-back → invalidate cache.

    Safe after first tokens. Failures must not invalidate the chat reply.
    Persistence success is separate from presentation/UI success.
    """
    from .discovery.brief import update_living_brief
    from .discovery.documentation import extract_documentation
    from .discovery.persistence import load_discovery_bundle, save_discovery_bundle
    from .knowledge import apply_wiki_candidates
    from .project_cache import invalidate_cache_sections, warm_project_cache
    from .relationship import load_relationship_profile
    from .schemas import WikiCandidate
    from .snapshot import load_snapshot, save_snapshot

    rid = request_id or f"deferred-{(hash(user_message) & 0xFFFF):x}"
    try:
        relationship = load_relationship_profile(db, project_id)
        discovery = load_discovery_bundle(db, project_id)
        snapshot = load_snapshot(db, project_id)
        source_id = f"deferred:{rid}"
        documentation = extract_documentation(
            user_message,
            project_id=project_id,
            source_id=source_id,
            relationship=relationship,
        )
        discovery.last_documentation = documentation
        mapped: list[WikiCandidate] = []
        persisted_ids: list[str] = []
        confirmed_count = 0
        inferred_count = 0
        if documentation.candidate_count > 0:
            seen: set[str] = set()
            unique_candidates = []
            for c in documentation.candidates:
                key = f"{c.title}|{(c.content or '')[:80]}".lower()
                if key in seen:
                    continue
                seen.add(key)
                unique_candidates.append(c)
                status = str(getattr(c, "status", "") or "")
                if status == "CONFIRMED":
                    confirmed_count += 1
                elif status in {"EMERGING", "INFERRED"}:
                    inferred_count += 1
            discovery.wiki_candidates = [
                *unique_candidates,
                *list(discovery.wiki_candidates or [])[:80],
            ]
            state_map = {
                "CONFIRMED": "confirmed",
                "EMERGING": "proposed",
                "INFERRED": "proposed",
                "DISPUTED": "unresolved",
                "SUPERSEDED": "superseded",
            }
            section_map = {
                "CHARACTER": "characters",
                "LOCATION": "worldAndSetting",
                "EVENT": "storyAndEpisodes",
                "TIMELINE": "storyAndEpisodes",
                "WORLD_RULE": "worldAndSetting",
                "THEME": "creativeFoundation",
                "STORY_PRINCIPLE": "creativeFoundation",
                "ENTITY": "worldAndSetting",
                "PROJECT": "knownDetails",
                "ORGANIZATION": "worldAndSetting",
            }
            for c in unique_candidates:
                persisted_ids.append(str(c.id))
                mapped.append(
                    WikiCandidate(
                        id=c.id,
                        text=f"{c.title}: {c.content}"[:400],
                        state=state_map.get(c.status, "proposed"),  # type: ignore[arg-type]
                        section=section_map.get(c.category.value, "creativeFoundation"),
                        provenance=c.status,
                        sourceTurn=source_id,
                    )
                )
            if mapped and snapshot is not None:
                snapshot = apply_wiki_candidates(snapshot, mapped, user_message)
                save_snapshot(db, snapshot)
            # Professional Wiki Intelligence: specialists refine regex seeds (background only).
            try:
                from ..wiki_intelligence.orchestrator import process_wiki_intelligence_turn

                seeds = [
                    {"id": c.id, "text": f"{c.title}: {c.content}"[:400], "section": c.category.value}
                    for c in unique_candidates[:12]
                ]
                process_wiki_intelligence_turn(db, project_id, seeds, use_specialists=True)
            except Exception:  # noqa: BLE001
                logger.debug("wiki_intelligence_orchestrator_skipped", exc_info=True)
        # Creative Operating Intelligence — background only; never blocks TTFT.
        creative_operating_result: dict[str, Any] | None = None
        try:
            from ..creative_operating.service import process_creative_operating_turn

            primary_type = None
            snap_fmt = None
            try:
                from app.db import Project

                proj = db.get(Project, project_id)
                primary_type = getattr(proj, "primary_project_type", None) if proj else None
            except Exception:  # noqa: BLE001
                primary_type = None
            if snapshot is not None:
                snap_fmt = getattr(snapshot, "format", None)
            creative_operating_result = process_creative_operating_turn(
                db,
                project_id=project_id,
                user_message=user_message,
                discovery_stage=str(getattr(getattr(discovery, "creative_stage", None), "value", "") or "")
                or None,
                primary_project_type=primary_type,
                snapshot_format=snap_fmt,
                candidate_count=int(documentation.candidate_count or 0),
            )
        except Exception:  # noqa: BLE001
            logger.debug("creative_operating_skipped", exc_info=True)
        # Notes bridge + compiled Wiki refresh (background-only; never blocks TTFT).
        try:
            from ..notes.service import upsert_notes_from_texts
            from ..wiki_intelligence.compiled.page_compiler import compile_wiki_bundle
            from ..wiki_intelligence.compiled.promotion import detect_explicit_wiki_write, promote_explicit_wiki_text

            if mapped:
                upsert_notes_from_texts(
                    db,
                    project_id,
                    [c.text for c in mapped[:10]],
                    source="conversation",
                )
            if detect_explicit_wiki_write(user_message):
                promote_explicit_wiki_text(db, project_id, text=user_message, destination="story")
            else:
                compile_wiki_bundle(db, project_id, force_full=False)
        except Exception:  # noqa: BLE001
            logger.debug("compiled_wiki_background_skipped", exc_info=True)
        discovery.brief = update_living_brief(
            discovery.brief,
            project_id=project_id,
            user_message=user_message,
            candidates=documentation.candidates,
        )
        save_discovery_bundle(db, project_id, discovery)

        # Full read-after-write: every persisted id must verify (background only).
        verify = load_discovery_bundle(db, project_id)
        verified_ids = [
            str(c.id)
            for c in list(getattr(verify, "wiki_candidates", None) or [])
            if str(c.id) in set(persisted_ids)
        ]
        binding_ok = True
        if getattr(verify, "project_id", None) and str(verify.project_id) != str(project_id):
            binding_ok = False
        read_back_ok = (documentation.candidate_count == 0) or (
            len(persisted_ids) > 0 and set(persisted_ids).issubset(set(verified_ids)) and binding_ok
        )

        wiki_visible = False
        if documentation.candidate_count > 0 and read_back_ok:
            try:
                from ..wiki import build_project_wiki

                wiki = build_project_wiki(db, project_id)
                if isinstance(wiki, dict):
                    wiki_visible = bool(wiki.get("hasContent"))
                    if not wiki_visible:
                        for sec in (wiki.get("sections") or {}).values():
                            entries = (sec or {}).get("entries") if isinstance(sec, dict) else []
                            if entries:
                                wiki_visible = True
                                break
                else:
                    wiki_visible = len(verified_ids) > 0
            except Exception:  # noqa: BLE001
                wiki_visible = len(verified_ids) > 0

        cache_invalidated = False
        if documentation.candidate_count > 0 and read_back_ok:
            invalidate_cache_sections(db, project_id, ["wiki", "characters", "locations", "summary"])
            warm_project_cache(db, project_id, force=True, persist=True)
            cache_invalidated = True

        verification = build_verification(
            request_id=rid,
            project_id=project_id,
            source_message_id=source_id,
            candidate_count=int(documentation.candidate_count or 0),
            confirmed_count=confirmed_count,
            inferred_count=inferred_count,
            persisted_ids=persisted_ids,
            verified_ids=verified_ids,
            write_succeeded=True,
            read_back_succeeded=read_back_ok,
            project_binding_verified=binding_ok,
            cache_invalidated=cache_invalidated,
            wiki_visible=wiki_visible,
            failure_stage=None if read_back_ok else "read_back",
            error=None if read_back_ok else "Wiki write could not be fully verified on read-back.",
        )
        # Mark event pending emission by service layer
        if verification.finalState != "FAILED" or verification.persistenceState == "PERSISTED":
            verification.presentationState = "NOT_EMITTED"

        result = {
            "ok": verification.persistenceState in {"PERSISTED", "VERIFIED"}
            and (verification.finalState in {"NO_CANDIDATES", "VERIFIED", "PERSISTED"}),
            "readBackOk": verification.readBackSucceeded,
            "reason": getattr(documentation.reason, "value", str(documentation.reason)),
            "candidateCount": verification.candidateCount,
            "confirmedWrites": int(getattr(documentation, "confirmed_writes", 0) or confirmed_count),
            "persistedIds": persisted_ids,
            "verifiedIds": verified_ids,
            "summaryLines": list(documentation.summary_lines or [])[:6],
            "verification": verification.to_public_dict(),
            "neverBlocksTtft": True,
            "creativeOperating": creative_operating_result,
        }
        # Strict success for COMPLETE status: verified (or no candidates)
        if verification.finalState == "FAILED" and verification.persistenceState == "FAILED":
            result["ok"] = False
        elif verification.finalState == "PERSISTED" and not verification.readBackSucceeded:
            result["ok"] = False  # incomplete verification → job FAILED for claim purposes
            result["reason"] = "READ_BACK_FAILED"
        return result
    except Exception as exc:  # noqa: BLE001
        logger.warning("deferred enrichment failed for project %s: %s", project_id, exc)
        verification = build_verification(
            request_id=rid,
            project_id=project_id,
            write_succeeded=False,
            error=str(exc)[:300],
            failure_stage="exception",
        )
        return {
            "ok": False,
            "error": str(exc)[:300],
            "readBackOk": False,
            "verification": verification.to_public_dict(),
            "neverBlocksTtft": True,
        }
