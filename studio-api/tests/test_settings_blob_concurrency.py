"""CDX-057 probe — Project.settings_json single-blob concurrency.

Audit claim (docs/release-gate/codirector-express-audit/CO_DIRECTOR_EXPRESS_MASTER_AUDIT.md,
"fragile seams" #6): knowledgeEntries / workingNotes / compiledWiki, the project
intelligence cache and the creative-operating bundles all live in ONE
Project.settings_json blob that is rewritten whole via load-mutate-save
(snapshot.save_snapshot / project_cache.save_project_cache /
creative_operating.save_bundle). Concurrent writers may clobber unrelated
fields, and the blob may grow without bound.

This file is a VERIFICATION-ONLY probe (subagent 1D). It measures the current
behavior on disk with fresh line numbers and does NOT redesign persistence.

Method:
  1. CONCURRENCY / FIELD-LOSS — deterministic two-session interleaving
     (load A, load B, save A, save B), exactly the read-modify-write pattern of
     two concurrent API requests, plus a threaded N-writer variant.
  2. BLOB GROWTH — 50 compiledWiki writes with distinct payloads (constant vs
     unbounded curve) and a 60-turn knowledgeEntries accumulation probe.
  3. MONOTONIC REVISION — sequential (must be 1..N) and interleaved (must
     advance +1 per save) saves.

Contract assertions are marked xfail with reason=CDX-057 where the probe
reproduces a defect; the xfail markers are the regression canary for the
architecture decision.
"""

from __future__ import annotations

import json
import threading
import uuid

import pytest

from app.codirector.conversation.knowledge import apply_wiki_candidates
from app.codirector.conversation.project_cache import load_project_cache, save_project_cache
from app.codirector.conversation.schemas import WikiCandidate
from app.codirector.conversation.snapshot import load_snapshot, save_snapshot
from app.codirector.creative_operating.persistence import load_bundle, save_bundle
from app.db import Project, SessionLocal, init_db

PROBE_TAG = "CDX-057"


def _baseline_settings(pid: str) -> dict:
    """Mimic a production settings_json blob: several Co-Director sub-blobs plus
    unrelated keys written by other subsystems (library, voice, ...)."""
    return {
        "projectIntelligence": {
            "projectId": pid,
            "revision": 0,
            "title": "CDX057 Probe",
            "workingNotes": [{"id": "wn-0", "text": "baseline note", "kind": "note"}],
            "knowledgeEntries": [
                {"id": "ke-0", "text": "Baseline fact", "state": "confirmed", "section": "knownDetails"}
            ],
            "compiledWiki": {"projection": "compiled_bible_v1", "compiledRevision": 0, "pages": []},
            "director": {"currentGoal": "", "currentTask": "", "creativeStage": "Project Creation", "revision": 0},
        },
        "projectIntelligenceCache": {"projectId": pid, "cacheVersion": 1, "projectSummary": "baseline"},
        "creativeOperating": {"projectId": pid, "revision": 1, "creativeStage": "EMERGING"},
        "libraryState": {"folders": [], "revision": 1},
        "voice": {"active": False},
    }


def _seed_project(db, pid: str, *, settings: dict | None = None) -> None:
    project = Project(
        id=pid,
        name="CDX057 Probe",
        settings_json=json.dumps(settings if settings is not None else _baseline_settings(pid)),
    )
    db.add(project)
    db.commit()


def _fresh_session():
    return SessionLocal()


def _read_blob(pid: str) -> dict:
    """Read the raw settings_json blob from disk through a fresh session."""
    with SessionLocal() as s:
        p = s.get(Project, pid)
        return json.loads(p.settings_json or "{}")


@pytest.fixture()
def db():
    init_db()
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture()
def cleanup_project():
    pids: list[str] = []
    yield pids
    with SessionLocal() as s:
        for pid in pids:
            p = s.get(Project, pid)
            if p is not None:
                s.delete(p)
        s.commit()


def _new_pid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


# --------------------------------------------------------------------------
# 1. CONTROL — single session, sequential read-modify-write must be lossless
# --------------------------------------------------------------------------

def test_single_session_sequential_saves_preserve_all_fields(db, cleanup_project):
    """Same-session sequential load-mutate-save must keep unrelated fields.

    This is the control case: within ONE session the identity-mapped Project
    carries the latest settings_json, so no unrelated field should be dropped.
    """
    pid = _new_pid("cdx057-seq")
    cleanup_project.append(pid)
    _seed_project(db, pid)

    snap = load_snapshot(db, pid)
    snap.workingNotes = [{"id": "wn-a", "text": "A note", "kind": "note"}]
    save_snapshot(db, snap)

    snap2 = load_snapshot(db, pid)
    snap2.knowledgeEntries = [
        WikiCandidate(id="ke-a", text="A fact", state="confirmed", section="knownDetails")
    ]
    save_snapshot(db, snap2)

    settings = _read_blob(pid)
    pi = settings["projectIntelligence"]
    assert pi["workingNotes"] == [{"id": "wn-a", "text": "A note", "kind": "note"}], pi["workingNotes"]
    assert [e["id"] for e in pi["knowledgeEntries"]] == ["ke-a"], pi["knowledgeEntries"]
    for key in ("projectIntelligenceCache", "creativeOperating", "libraryState", "voice"):
        assert key in settings, f"unrelated top-level key {key} was dropped"
    assert pi["revision"] == 2, pi["revision"]
    print(f"[{PROBE_TAG}][control] single-session sequential saves: all fields preserved, revision={pi['revision']}")


# --------------------------------------------------------------------------
# 2. FIELD-LOSS — deterministic two-session read-modify-write interleaving
# --------------------------------------------------------------------------

@pytest.mark.xfail(
    reason=(
        "CDX-057 CONFIRMED BY PROBE: session B's save_snapshot replaces the whole "
        "projectIntelligence key with its stale model dump (snapshot.py:165), dropping "
        "session A's unrelated workingNotes change. Fix requires optimistic concurrency "
        "or per-writer storage (ARCHITECTURAL DECISION REQUIRED)."
    ),
    strict=False,
)
def test_two_sessions_interleaved_saves_drop_unrelated_snapshot_fields(db, cleanup_project):
    """Deterministic race: session A and B both load (T0), A saves (T1), B
    saves (T2) from its stale snapshot model. B's whole-key replacement of
    projectIntelligence must NOT drop A's workingNotes change.

    Contract: A's workingNotes and B's knowledgeEntries both survive.
    """
    pid = _new_pid("cdx057-il")
    cleanup_project.append(pid)
    _seed_project(db, pid)

    session_a = _fresh_session()
    session_b = _fresh_session()
    try:
        snap_a = load_snapshot(session_a, pid)  # T0
        snap_b = load_snapshot(session_b, pid)  # T0 (same baseline)
        snap_a.workingNotes = [{"id": "wn-a", "text": "A note from session A", "kind": "note"}]
        save_snapshot(session_a, snap_a)        # T1 commit
        snap_b.knowledgeEntries = [
            WikiCandidate(id="ke-b", text="B fact from session B", state="confirmed", section="knownDetails")
        ]
        save_snapshot(session_b, snap_b)        # T2 commit (stale baseline + B change)
    finally:
        session_a.close()
        session_b.close()

    settings = _read_blob(pid)
    pi = settings["projectIntelligence"]
    a_note_survived = any(n.get("text") == "A note from session A" for n in pi.get("workingNotes") or [])
    b_fact_survived = any(e.get("id") == "ke-b" for e in pi.get("knowledgeEntries") or [])
    print(
        f"[{PROBE_TAG}][field-loss] interleaved A(notes)/B(knowledge): "
        f"A survived={a_note_survived} B survived={b_fact_survived} "
        f"workingNotes={[n.get('id') for n in pi.get('workingNotes') or []]} "
        f"revision={pi.get('revision')}"
    )
    assert a_note_survived, (
        f"[{PROBE_TAG} CONFIRMED] session A's workingNotes change was dropped by session B's save "
        f"(save_snapshot replaces the whole projectIntelligence key with a stale model dump)"
    )
    assert b_fact_survived


@pytest.mark.xfail(
    reason=(
        "CDX-057 CONFIRMED BY PROBE: session B's save_bundle rewrites the whole "
        "settings_json from a stale copy (persistence.py:56), dropping session A's "
        "projectIntelligenceCache update. A re-read-merge-before-save guard would fix "
        "this mode but not the intra-projectIntelligence mode."
    ),
    strict=False,
)
def test_two_sessions_cross_writer_key_clobber(db, cleanup_project):
    """Deterministic cross-writer race: session A updates the project
    intelligence cache; session B updates the creative-operating bundle. Both
    loaded settings_json at T0; B's save rewrites the whole blob from its stale
    copy and must NOT drop A's cache key.

    Contract: A's cache projectSummary and B's creativeStage both survive.
    """
    pid = _new_pid("cdx057-cw")
    cleanup_project.append(pid)
    _seed_project(db, pid)

    session_a = _fresh_session()
    session_b = _fresh_session()
    # Hold strong references to the Project instances, as production request
    # handlers typically do (existence check at request start, session-scoped
    # locals). The SQLAlchemy identity map holds objects weakly; without a
    # strong reference the stale copy can be GC-evicted and the save would
    # accidentally re-read fresh settings. Holding the reference makes the
    # read-modify-write interleaving deterministic (stale settings at save).
    proj_a = session_a.get(Project, pid)  # noqa: F841 - strong ref
    proj_b = session_b.get(Project, pid)  # noqa: F841 - strong ref
    try:
        cache_a = load_project_cache(session_a, pid)  # T0
        bundle_b = load_bundle(session_b, pid)        # T0
        cache_a.projectSummary = "A cache summary v2"
        save_project_cache(session_a, cache_a)        # T1 commit
        bundle_b.creativeStage = "STRUCTURING"
        save_bundle(session_b, bundle_b)              # T2 commit (stale blob + B key)
    finally:
        session_a.close()
        session_b.close()

    settings = _read_blob(pid)
    cache_survived = settings["projectIntelligenceCache"].get("projectSummary") == "A cache summary v2"
    bundle_survived = settings["creativeOperating"].get("creativeStage") == "STRUCTURING"
    print(
        f"[{PROBE_TAG}][cross-key] A(cache)/B(creative): "
        f"cache survived={cache_survived} creative survived={bundle_survived}"
    )
    assert cache_survived, (
        f"[{PROBE_TAG} CONFIRMED] session A's projectIntelligenceCache update was dropped by "
        f"session B's save_bundle (whole-blob rewrite from a stale settings_json copy)"
    )
    assert bundle_survived


# --------------------------------------------------------------------------
# 3. THREADED N-writer concurrency
# --------------------------------------------------------------------------

@pytest.mark.xfail(
    reason=(
        "CDX-057 CONFIRMED BY PROBE: 6 concurrent writers (barrier-synchronized loads) "
        "left only 1 of 6 distinct workingNotes updates (last committer wins). Fix "
        "requires optimistic concurrency or per-writer key isolation."
    ),
    strict=False,
)
def test_threaded_concurrent_writers_lose_fields(db, cleanup_project):
    """N threads each open their own session, load the snapshot, wait on a
    barrier (so all loads precede every save), then mutate a DISTINCT field and
    save. A correct design would merge every thread's field; the current
    load-mutate-save-whole-blob design must lose all but the last committer.

    Contract: all N fields survive (no unrelated-field loss).
    """
    pid = _new_pid("cdx057-th")
    cleanup_project.append(pid)
    _seed_project(db, pid)
    n = 6
    barrier = threading.Barrier(n)

    def worker(i: int) -> None:
        s = _fresh_session()
        try:
            snap = load_snapshot(s, pid)  # T0 read per thread
            barrier.wait(timeout=30)
            snap.workingNotes = [{"id": f"wn-t{i}", "text": f"thread {i} note", "kind": "note"}]
            save_snapshot(s, snap)
        finally:
            s.close()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    settings = _read_blob(pid)
    notes = settings["projectIntelligence"].get("workingNotes") or []
    survived = [n for n in notes if (n.get("id") or "").startswith("wn-t")]
    print(f"[{PROBE_TAG}][threaded] threads={n} survived_fields={len(survived)} ids={[n.get('id') for n in survived]}")
    assert len(survived) == n, (
        f"[{PROBE_TAG} CONFIRMED] threaded writers: only {len(survived)} of {n} distinct-field "
        f"updates survived (lost updates under concurrency)"
    )


# --------------------------------------------------------------------------
# 4. BLOB GROWTH
# --------------------------------------------------------------------------

def test_blob_growth_compiled_wiki_replacement_is_bounded(db, cleanup_project):
    """50 compiledWiki writes with DISTINCT payloads. Each write replaces the
    compiledWiki key (page_compiler.compile_wiki_bundle -> snapshot.compiledWiki
    -> save_snapshot). If the blob accumulated history it would grow linearly;
    a replacement write must stay ~constant.

    Contract: blob size does not grow with iteration count.
    """
    pid = _new_pid("cdx057-grow")
    cleanup_project.append(pid)
    _seed_project(db, pid)

    sizes: list[int] = []
    for i in range(50):
        snap = load_snapshot(db, pid)
        snap.compiledWiki = {
            "projection": "compiled_bible_v1",
            "compiledRevision": i + 1,
            "pages": [{"pageId": f"page-{i:03d}", "title": "Page", "body": ("x" * 300) + f"{i:04d}"}],
            "toc": [{"key": "k", "label": "L", "count": 1}],
        }
        save_snapshot(db, snap)
        sizes.append(len(json.dumps(_read_blob(pid))))

    growth = sizes[-1] - sizes[0]
    print(
        f"[{PROBE_TAG}][growth] compiledWiki 50 writes: start={sizes[0]}B end={sizes[-1]}B "
        f"growth={growth}B min={min(sizes)}B max={max(sizes)}B"
    )
    assert growth < 2000, (
        f"[{PROBE_TAG} CONFIRMED] compiledWiki writes grow the settings blob unboundedly: "
        f"{growth}B over 50 writes"
    )


@pytest.mark.xfail(
    reason=(
        "CDX-057 CONFIRMED BY PROBE: knowledgeEntries grow ~187.6B/turn (11KB over 60 "
        "turns) because apply_wiki_candidates appends without a cap (knowledge.py:102). "
        "The compiledWiki replacement path is bounded (separate passing test)."
    ),
    strict=False,
)
def test_blob_growth_knowledge_entries_accumulate(db, cleanup_project):
    """60 conversation turns each persisting a distinct confirmed fact through
    the production path (apply_wiki_candidates -> save_snapshot). knowledge.py
    appends candidates with no cap (line 102); this probe measures the curve.

    Contract: blob size must stay bounded across turns.
    """
    pid = _new_pid("cdx057-growke")
    cleanup_project.append(pid)
    _seed_project(db, pid)

    sizes: list[int] = []
    for i in range(60):
        snap = load_snapshot(db, pid)
        cand = WikiCandidate(
            id=f"ke-g{i}",
            text=f"Distinct confirmed fact number {i} from turn {i}",
            state="confirmed",
            section="knownDetails",
        )
        updated = apply_wiki_candidates(snap, [cand], user_message=f"creator says fact {i}")
        save_snapshot(db, updated)
        sizes.append(len(json.dumps(_read_blob(pid))))

    growth = sizes[-1] - sizes[0]
    per_turn = growth / max(len(sizes) - 1, 1)
    print(
        f"[{PROBE_TAG}][growth] knowledgeEntries 60 turns: start={sizes[0]}B end={sizes[-1]}B "
        f"growth={growth}B per_turn={per_turn:.1f}B"
    )
    assert growth < 2000, (
        f"[{PROBE_TAG} CONFIRMED] knowledgeEntries accumulate unboundedly in the settings blob: "
        f"{growth}B over 60 turns ({per_turn:.1f}B/turn)"
    )


# --------------------------------------------------------------------------
# 5. MONOTONIC REVISION
# --------------------------------------------------------------------------

def test_revision_monotonic_sequential(db, cleanup_project):
    """Sequential saves must advance revision exactly +1 per save."""
    pid = _new_pid("cdx057-revseq")
    cleanup_project.append(pid)
    _seed_project(db, pid)

    revisions: list[int] = []
    for i in range(10):
        snap = load_snapshot(db, pid)
        snap.currentObjective = f"objective {i}"
        save_snapshot(db, snap)
        revisions.append(snap.revision)

    print(f"[{PROBE_TAG}][revision] sequential revisions: {revisions}")
    assert revisions == list(range(1, 11)), revisions


@pytest.mark.xfail(
    reason=(
        "CDX-057 CONFIRMED BY PROBE: 2 interleaved saves from revision 0 left stored "
        "revision 1 (both writers incremented the same stale value; snapshot.py:163). "
        "Counter stalls under concurrency - lost increments, not strictly monotonic."
    ),
    strict=False,
)
def test_revision_monotonic_concurrent_saves(db, cleanup_project):
    """Two interleaved saves must still advance the stored revision +1 per
    save. With the current load-mutate-save both writers compute their new
    revision from the same stale value, so the counter stalls.

    Contract: stored revision == 2 after 2 interleaved saves from rev 0.
    """
    pid = _new_pid("cdx057-revconc")
    cleanup_project.append(pid)
    _seed_project(db, pid)

    session_a = _fresh_session()
    session_b = _fresh_session()
    try:
        snap_a = load_snapshot(session_a, pid)
        snap_b = load_snapshot(session_b, pid)
        save_snapshot(session_a, snap_a)
        save_snapshot(session_b, snap_b)
        rev_a = snap_a.revision
        rev_b = snap_b.revision
    finally:
        session_a.close()
        session_b.close()

    stored = _read_blob(pid)["projectIntelligence"]["revision"]
    print(
        f"[{PROBE_TAG}][revision] interleaved saves: rev_a={rev_a} rev_b={rev_b} "
        f"stored_after_2_saves={stored} (contract: 2)"
    )
    assert stored == 2, (
        f"[{PROBE_TAG} CONFIRMED] revision counter stalls under interleaved saves: "
        f"2 saves from rev 0 left stored revision={stored} (expected 2)"
    )
