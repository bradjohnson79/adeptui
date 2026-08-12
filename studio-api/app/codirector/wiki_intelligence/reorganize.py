"""Reorganize Wiki — specialist-driven professional cleanup with undo snapshots."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from ...db import Project
from ..conversation.knowledge import apply_wiki_candidates
from ..conversation.project_cache import invalidate_cache_sections, warm_project_cache
from ..conversation.schemas import WikiCandidate
from ..conversation.snapshot import load_snapshot, save_snapshot
from ..wiki import build_project_wiki
from .assignment import assign_specialists_for_domains
from .classification import (
    classify_entity_type,
    extract_display_name,
    is_false_character_name,
    is_user_preference_not_canon,
    names_are_aliases,
    target_section_for_entity,
)
from .contracts import (
    REORGANIZE_DOMAINS,
    WikiChangeRecord,
    WikiOrganizationProblem,
    WikiReorganizationJob,
    WikiReorganizationRevision,
)
from .finding_adapter import heuristic_department_finding

logger = logging.getLogger("adept.codirector.wiki_reorganize")

# In-process job store (project-scoped; also persisted on project settings for reload).
_JOBS: dict[str, WikiReorganizationJob] = {}


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds") + "Z"


def _settings(project: Project) -> dict[str, Any]:
    try:
        raw = json.loads(getattr(project, "settings_json", "") or "{}")
    except Exception:
        raw = {}
    return raw if isinstance(raw, dict) else {}


def _save_settings(db: Session, project: Project, settings: dict[str, Any]) -> None:
    project.settings_json = json.dumps(settings)
    db.add(project)
    db.commit()


def _legacy_section_for_professional(section: str) -> str:
    """Map professional TOC roots onto legacy knowledgeEntry section keys."""
    mapping = {
        "projectOverview": "knownDetails",
        "story": "creativeFoundation",
        "characters": "characters",
        "episodesAndScenes": "storyAndEpisodes",
        "worldAndLore": "worldAndSetting",
        "locationsAndSets": "worldAndSetting",
        "timelineAndContinuity": "storyAndEpisodes",
        "visualDevelopment": "visualIdentity",
        "audioAndPerformance": "creativeFoundation",
        "scriptsAndDevelopment": "productionDecisions",
        "production": "productionDecisions",
        "references": "references",
    }
    return mapping.get(section, section if section else "creativeFoundation")


def _detect_problems(
    entries: list[WikiCandidate],
    entity_type_overrides: dict[str, str] | None = None,
) -> list[WikiOrganizationProblem]:
    problems: list[WikiOrganizationProblem] = []
    names: list[tuple[str, WikiCandidate]] = []
    for e in entries:
        text = e.text or ""
        name = extract_display_name(text)
        et = classify_entity_type(
            text, hinted_section=e.section, entity_type_overrides=entity_type_overrides
        )
        if e.section == "characters" or et == "character":
            if is_false_character_name(name) or is_user_preference_not_canon(text):
                problems.append(
                    WikiOrganizationProblem(
                        problemType="false_character",
                        description=f"Invalid or non-cast entry in Characters: {name}",
                        domain="characters",
                        recordIds=[e.id],
                        severity="warning",
                    )
                )
            else:
                names.append((name, e))
            # Misplaced location/org under characters
            if et == "location":
                problems.append(
                    WikiOrganizationProblem(
                        problemType="misplaced_location",
                        description=f"Location under Characters: {name}",
                        domain="locations",
                        recordIds=[e.id],
                        severity="warning",
                    )
                )
            if et == "organization":
                problems.append(
                    WikiOrganizationProblem(
                        problemType="misplaced_organization",
                        description=f"Organization under Characters: {name}",
                        domain="world",
                        recordIds=[e.id],
                        severity="warning",
                    )
                )
        if is_user_preference_not_canon(text) and e.section in {"knownDetails", "creativeFoundation", "characters"}:
            problems.append(
                WikiOrganizationProblem(
                    problemType="preference_leak",
                    description="Working preference leaked into project material",
                    domain="canon",
                    recordIds=[e.id],
                    severity="error",
                )
            )

    # Duplicate / alias clusters
    for i, (na, ea) in enumerate(names):
        for nb, eb in names[i + 1 :]:
            if names_are_aliases(na, nb) and ea.id != eb.id:
                problems.append(
                    WikiOrganizationProblem(
                        problemType="duplicate_character",
                        description=f"Possible alias merge: {na} ↔ {nb}",
                        domain="characters",
                        recordIds=[ea.id, eb.id],
                        severity="warning",
                    )
                )
                break

    # Clipped fragments
    for e in entries:
        t = (e.text or "").strip()
        if len(t) < 12 or t.endswith("…") or re.match(r"^[A-Z][a-z]{0,3}$", t):
            if e.section == "characters":
                problems.append(
                    WikiOrganizationProblem(
                        problemType="fragment",
                        description=f"Clipped/meaningless fragment: {t[:40]}",
                        domain="characters",
                        recordIds=[e.id],
                        severity="info",
                    )
                )
    return problems


def _persist_job(db: Session, project: Project, job: WikiReorganizationJob) -> None:
    _JOBS[job.id] = job
    settings = _settings(project)
    jobs = settings.get("wikiReorganizationJobs")
    if not isinstance(jobs, dict):
        jobs = {}
    jobs[job.id] = job.model_dump(mode="json")
    # Keep last 20
    if len(jobs) > 20:
        for k in list(jobs.keys())[:-20]:
            jobs.pop(k, None)
    settings["wikiReorganizationJobs"] = jobs
    _save_settings(db, project, settings)


def get_reorganization_job(db: Session, project_id: str, job_id: str) -> dict[str, Any]:
    if job_id in _JOBS and _JOBS[job_id].projectId == project_id:
        return _JOBS[job_id].model_dump(mode="json")
    project = db.get(Project, project_id)
    if not project:
        return {"ok": False, "error": "project_not_found"}
    settings = _settings(project)
    jobs = settings.get("wikiReorganizationJobs") or {}
    raw = jobs.get(job_id) if isinstance(jobs, dict) else None
    if not raw:
        return {"ok": False, "error": "job_not_found"}
    return {"ok": True, **raw}


def list_reorganization_history(db: Session, project_id: str) -> dict[str, Any]:
    project = db.get(Project, project_id)
    if not project:
        return {"ok": False, "error": "project_not_found", "revisions": []}
    settings = _settings(project)
    revisions = settings.get("wikiReorganizationRevisions") or []
    if not isinstance(revisions, list):
        revisions = []
    return {"ok": True, "projectId": project_id, "revisions": revisions[-30:]}


def undo_wiki_reorganization(db: Session, project_id: str, job_id: str) -> dict[str, Any]:
    project = db.get(Project, project_id)
    if not project:
        return {"ok": False, "error": "project_not_found"}
    settings = _settings(project)
    revisions = settings.get("wikiReorganizationRevisions") or []
    match = None
    for rev in reversed(revisions if isinstance(revisions, list) else []):
        if isinstance(rev, dict) and rev.get("jobId") == job_id:
            match = rev
            break
    if not match or not match.get("reversible"):
        return {"ok": False, "error": "revision_not_reversible"}
    snapshot = match.get("snapshot") or {}
    intel = snapshot.get("projectIntelligence")
    if not isinstance(intel, dict):
        return {"ok": False, "error": "snapshot_missing"}
    settings["projectIntelligence"] = intel
    settings["wikiRevision"] = int(match.get("previousWikiRevision") or 0)
    _save_settings(db, project, settings)
    try:
        invalidate_cache_sections(db, project_id, sections=["wiki", "knowledge"])
        warm_project_cache(db, project_id)
    except Exception:
        pass
    return {
        "ok": True,
        "projectId": project_id,
        "jobId": job_id,
        "restoredRevision": match.get("previousWikiRevision"),
        "wiki": build_project_wiki(db, project_id),
    }


def start_wiki_reorganization(
    db: Session,
    project_id: str,
    *,
    domains: list[str] | None = None,
    use_specialists: bool = True,
    preserve_locked_canon: bool = True,
    create_undo_snapshot: bool = True,
    requested_by: str = "creator",
) -> dict[str, Any]:
    project = db.get(Project, project_id)
    if not project:
        return {"ok": False, "error": "project_not_found"}

    selected = [d for d in (domains or list(REORGANIZE_DOMAINS)) if d in REORGANIZE_DOMAINS]
    if not selected:
        selected = list(REORGANIZE_DOMAINS)

    job = WikiReorganizationJob(
        id=f"wiki_reorg_{uuid4().hex[:12]}",
        projectId=project_id,
        requestedBy=requested_by,
        selectedDomains=selected,
        status="QUEUED",
        stage="Queued",
        startedAt=_utcnow(),
    )
    _persist_job(db, project, job)

    try:
        return _run_reorganization(
            db,
            project,
            job,
            use_specialists=use_specialists,
            preserve_locked_canon=preserve_locked_canon,
            create_undo_snapshot=create_undo_snapshot,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("wiki_reorganization_failed projectId=%s", project_id)
        job.status = "FAILED"
        job.error = str(exc)[:300]
        job.completedAt = _utcnow()
        _persist_job(db, project, job)
        return {"ok": False, "error": str(exc)[:300], "job": job.model_dump(mode="json")}


def _run_reorganization(
    db: Session,
    project: Project,
    job: WikiReorganizationJob,
    *,
    use_specialists: bool,
    preserve_locked_canon: bool,
    create_undo_snapshot: bool,
) -> dict[str, Any]:
    project_id = project.id
    stages_emitted: list[str] = []

    def stage(name: str) -> None:
        job.stage = name
        job.status = "ANALYZING" if "Reviewing" in name or "Finding" in name else job.status
        if "Resolving" in name or "Organizing" in name or "Linking" in name or "Checking" in name:
            job.status = "REORGANIZING"
        if "Verifying" in name or "Rebuilding" in name:
            job.status = "VERIFYING"
        stages_emitted.append(name)
        _persist_job(db, project, job)

    stage("Reviewing Wiki structure")
    snapshot = load_snapshot(db, project_id)
    entries = list(snapshot.knowledgeEntries or [])
    job.recordsReviewed = len(entries)

    # Creator-learned correction memory: Reorganize must respect creator
    # corrections (CREATOR_CORRECTION_PRIORITY / _SURVIVES_RECOMPILE). Load
    # entity-type overrides + aliases once and thread them through classification
    # and the character resolver.
    entity_overrides: dict[str, str] = {}
    try:
        from .correction import memory as correction_memory

        entity_overrides = correction_memory.entity_type_overrides(db, project_id)
    except Exception:  # noqa: BLE001
        entity_overrides = {}

    settings = _settings(project)
    prev_rev = int(settings.get("wikiRevision") or 0)
    undo_snapshot = {
        "projectIntelligence": json.loads(json.dumps(snapshot.model_dump(mode="json"))),
    }

    stage("Finding misplaced records")
    problems = _detect_problems(entries, entity_type_overrides=entity_overrides)
    # Filter problems to selected domains
    problems = [p for p in problems if p.domain in job.selectedDomains or p.domain == "canon"]
    job.detectedProblems = problems

    assignment = assign_specialists_for_domains(
        project_id=project_id,
        domains=job.selectedDomains,
        problems=problems,
        source_id=job.id,
    )
    if not use_specialists:
        assignment.selectedSpecialists = []
        assignment.requiredSpecialists = []
    job.specialistAssignments = [assignment]

    # Collect specialist findings (heuristic department pass — structured, not keyword-only)
    findings = []
    if use_specialists:
        for prob in problems:
            for sid in assignment.selectedSpecialists[:6]:
                for rid in prob.recordIds[:2]:
                    entry = next((e for e in entries if e.id == rid), None)
                    if not entry:
                        continue
                    findings.append(
                        heuristic_department_finding(
                            specialist_id=sid,
                            source_id=rid,
                            text=entry.text,
                            problem_type=prob.problemType,
                        )
                    )

    stage("Resolving character identities")
    changes: list[WikiChangeRecord] = []
    kept: list[WikiCandidate] = []
    rejected_ids: set[str] = set()
    merged_into: dict[str, str] = {}

    # Build alias clusters among character-like entries
    char_entries = [
        e
        for e in entries
        if (
            e.section == "characters"
            or classify_entity_type(
                e.text, hinted_section=e.section, entity_type_overrides=entity_overrides
            )
            == "character"
        )
        and not is_false_character_name(extract_display_name(e.text))
        and not is_user_preference_not_canon(e.text)
    ]
    clusters: list[list[WikiCandidate]] = []
    used: set[str] = set()
    for e in char_entries:
        if e.id in used:
            continue
        cluster = [e]
        used.add(e.id)
        ename = extract_display_name(e.text)
        for other in char_entries:
            if other.id in used:
                continue
            if names_are_aliases(ename, extract_display_name(other.text)):
                cluster.append(other)
                used.add(other.id)
        clusters.append(cluster)

    for cluster in clusters:
        if len(cluster) == 1:
            continue
        # Canonical = longest display name
        canonical = max(cluster, key=lambda c: len(extract_display_name(c.text)))
        aliases = [extract_display_name(c.text) for c in cluster if c.id != canonical.id]
        merged_text = canonical.text
        if aliases:
            merged_text = f"{extract_display_name(canonical.text)}: " + (
                canonical.text.split(":", 1)[-1].strip()
                if ":" in canonical.text
                else canonical.text
            )
            merged_text += f" (also known as: {', '.join(aliases)})"
        for c in cluster:
            if c.id == canonical.id:
                continue
            rejected_ids.add(c.id)
            merged_into[c.id] = canonical.id
            job.recordsMerged += 1
            changes.append(
                WikiChangeRecord(
                    changeType="merge",
                    recordId=c.id,
                    before=c.text[:200],
                    after=f"merged→{canonical.id}",
                    sectionFrom=c.section,
                    sectionTo=canonical.section,
                    specialistIds=assignment.selectedSpecialists[:3],
                )
            )
        canonical.text = merged_text[:400]
        job.recordsUpdated += 1

    stage("Organizing locations and sets")
    for e in entries:
        if e.id in rejected_ids:
            job.recordsRejected += 1
            continue

        # Locked / approved protection
        provenance_upper = str(getattr(e, "provenance", "") or "").upper()
        if preserve_locked_canon and str(e.state) in {"approved", "confirmed"} and (
            provenance_upper in {"LOCKED", "CANON_LOCKED"}
            # Explicit creator corrections are protected from being reorganized away.
            or "USER_EXPLICIT_WIKI_WRITE" in provenance_upper
        ):
            kept.append(e)
            continue

        text = e.text or ""
        name = extract_display_name(text)
        et = classify_entity_type(
            text, hinted_section=e.section, entity_type_overrides=entity_overrides
        )

        # Reject false characters
        if (e.section == "characters" or et == "character") and (
            is_false_character_name(name) or is_user_preference_not_canon(text)
        ):
            job.recordsRejected += 1
            changes.append(
                WikiChangeRecord(
                    changeType="reject",
                    recordId=e.id,
                    before=text[:200],
                    after=None,
                    sectionFrom=e.section,
                    specialistIds=assignment.selectedSpecialists[:2],
                )
            )
            continue

        # Preference leak → quarantine as reference-only note (not overview)
        if is_user_preference_not_canon(text):
            new_section = "references"
            legacy = _legacy_section_for_professional(new_section)
            if e.section != legacy:
                job.recordsReclassified += 1
                changes.append(
                    WikiChangeRecord(
                        changeType="reclassify",
                        recordId=e.id,
                        before=text[:200],
                        after="Moved to references (preference, not project canon)",
                        sectionFrom=e.section,
                        sectionTo=legacy,
                        specialistIds=["bible-manager", "qa-reviewer"],
                    )
                )
            e.section = legacy
            e.state = "reference-only"  # type: ignore[assignment]
            kept.append(e)
            continue

        # Reclassify by entity type
        pro_section = target_section_for_entity(et)
        legacy = _legacy_section_for_professional(pro_section)
        # Organizations stay in worldAndSetting but tagged in text if needed
        if et == "organization" and not text.lower().startswith("organization"):
            e.text = f"Organization: {text}"[:400]
            job.recordsUpdated += 1
        if et == "location" and e.section == "characters":
            legacy = "worldAndSetting"
        if e.section != legacy and et not in {"note", "preference"}:
            job.recordsReclassified += 1
            changes.append(
                WikiChangeRecord(
                    changeType="reclassify",
                    recordId=e.id,
                    before=text[:200],
                    after=f"{et} → {legacy}",
                    sectionFrom=e.section,
                    sectionTo=legacy,
                    specialistIds=assignment.selectedSpecialists[:3],
                )
            )
            e.section = legacy
        kept.append(e)

    stage("Checking canon and continuity")
    # Do not promote proposed → confirmed
    conflicts = 0
    for e in kept:
        if str(e.state) == "proposed" and "confirmed" in (e.text or "").lower():
            conflicts += 1
    job.conflictsFound = conflicts + sum(1 for p in problems if p.severity == "error")

    stage("Linking production references")
    # Ensure reference entries for assets already handled by build_project_wiki; count presence
    wiki_before = build_project_wiki(db, project_id)
    ref_count = len((wiki_before.get("sections") or {}).get("references", {}).get("entries") or [])

    stage("Rebuilding the Table of Contents")
    # Deduplicate kept by normalized text
    deduped: list[WikiCandidate] = []
    seen_text: set[str] = set()
    for e in kept:
        key = re.sub(r"\s+", " ", (e.text or "").strip().lower())[:160]
        if key in seen_text:
            job.recordsMerged += 1
            continue
        seen_text.add(key)
        deduped.append(e)

    snapshot.knowledgeEntries = deduped
    # Apply as no-op pass through apply_wiki_candidates identity
    snapshot = apply_wiki_candidates(snapshot, [], "wiki_reorganize")
    snapshot.knowledgeEntries = deduped
    save_snapshot(db, snapshot)

    new_rev = prev_rev + 1
    settings = _settings(project)
    settings["wikiRevision"] = new_rev
    revision_id = f"wrev_{uuid4().hex[:12]}"
    revision = WikiReorganizationRevision(
        revisionId=revision_id,
        projectId=project_id,
        jobId=job.id,
        previousWikiRevision=prev_rev,
        newWikiRevision=new_rev,
        changes=changes[:200],
        specialistIds=assignment.selectedSpecialists,
        createdAt=_utcnow(),
        reversible=bool(create_undo_snapshot),
        snapshot=undo_snapshot if create_undo_snapshot else {},
    )
    revs = settings.get("wikiReorganizationRevisions")
    if not isinstance(revs, list):
        revs = []
    revs.append(revision.model_dump(mode="json"))
    settings["wikiReorganizationRevisions"] = revs[-30:]
    _save_settings(db, project, settings)

    stage("Compiling professional Wiki pages")
    compiled = {}
    readability_issues: list[str] = []
    try:
        from .compiled.page_compiler import compile_wiki_bundle

        compiled = compile_wiki_bundle(db, project_id, force_full=True)
        readability_issues = list(compiled.get("readabilityIssues") or [])
    except Exception as exc:  # noqa: BLE001
        readability_issues = [f"compile_error:{exc}"]

    stage("Verifying the reorganized Wiki")
    try:
        invalidate_cache_sections(db, project_id, sections=["wiki", "knowledge"])
        warm_project_cache(db, project_id)
    except Exception:
        pass
    wiki = build_project_wiki(db, project_id)
    pages = wiki.get("compiledPages") or compiled.get("pages") or []
    compiled_toc = wiki.get("compiledToc") or compiled.get("toc") or []
    job.tocRebuilt = bool(compiled_toc or wiki.get("toc") or wiki.get("hasContent"))
    job.readBackVerified = bool(pages) or bool(wiki.get("hasContent"))
    # Mandatory: compiled presentation must improve — fail soft into PARTIAL if Theme×N remains
    visible_fail = any("repeated_theme" in i or "character_pollution" in i for i in readability_issues)
    job.changes = changes[:200]
    job.revisionId = revision_id
    job.recordsCreated = 0
    char_pages = len([p for p in pages if p.get("pageType") == "CHARACTER"])
    episode_pages = len([p for p in pages if p.get("pageType") == "EPISODE"])
    job.summaryLines = [
        f"Records reviewed: {job.recordsReviewed}",
        f"Duplicates merged: {job.recordsMerged}",
        f"Misplaced records corrected: {job.recordsReclassified}",
        f"Pages rebuilt: {len(pages)}",
        f"Character pages: {char_pages}",
        f"Episode pages: {episode_pages}",
        f"Open questions added: {len((wiki.get('compiledStorySummary') or {}).get('unresolvedQuestions') or [])}",
        f"References linked: {ref_count}",
        "Story summary updated",
        "Table of Contents rebuilt" if job.tocRebuilt else "TOC rebuild pending",
    ]
    if visible_fail:
        job.summaryLines.insert(0, "Compilation found remaining presentation issues — review recommended.")
        job.status = "PARTIAL"
    elif not problems and job.recordsMerged == 0 and job.recordsReclassified == 0 and job.recordsRejected == 0:
        job.summaryLines.insert(0, "Wiki reorganized and pages recompiled.")
        job.status = "COMPLETE"
    else:
        job.status = "COMPLETE" if job.readBackVerified else "PARTIAL"
    job.completedAt = _utcnow()
    job.stage = "Complete"
    _persist_job(db, project, job)

    return {
        "ok": True,
        "job": job.model_dump(mode="json"),
        "stages": stages_emitted,
        "wiki": {
            "hasContent": wiki.get("hasContent"),
            "toc": compiled_toc or wiki.get("toc"),
            "compiledPages": pages,
            "compiledRevision": wiki.get("compiledRevision") or compiled.get("compiledRevision"),
            "readabilityOk": not visible_fail,
            "readabilityIssues": readability_issues,
            "sourceOfTruth": "compiled_bible_v1",
            "projection": "compiled_bible_v1",
        },
        "specialistsActivated": assignment.selectedSpecialists,
        "findingsCount": len(findings),
    }
