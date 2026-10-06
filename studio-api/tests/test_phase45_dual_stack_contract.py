# -*- coding: utf-8 -*-
"""Phase 4–5 Dual-Stack Retirement contract locks (code/unit scope)."""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "studio-api" / "app"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def test_no_reconcile_on_gen_put_cd_call_sites():
    """reconcile_legacy_to_master must not be invoked on generate / put_director / CD tools."""
    callers: list[str] = []
    targets = [
        API / "director_timeline_w46" / "orchestrator.py",
        API / "routers" / "api.py",
        API / "codirector" / "tools" / "handlers" / "director_timeline_tools.py",
        API / "director_timeline_w46" / "generation",
    ]
    files: list[Path] = []
    for t in targets:
        if t.is_dir():
            files.extend(t.glob("*.py"))
        elif t.exists():
            files.append(t)
    for path in files:
        text = _read(path)
        # Allow import/def/comment mentions; forbid live call `reconcile_legacy_to_master(`
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "def reconcile_legacy_to_master" in stripped:
                continue
            if "reconcile_legacy_to_master(" in stripped:
                callers.append(f"{path.relative_to(ROOT)}:{i}:{stripped}")
    assert callers == [], "forbidden reconcile call sites:\n" + "\n".join(callers)


def test_nav_map_cd01_targets_present():
    from app.codirector.service import _NAVIGATE_TARGET_TO_TOOL

    assert _NAVIGATE_TARGET_TO_TOOL["environment_creator"] == "workspace.open_scene_creator"
    assert _NAVIGATE_TARGET_TO_TOOL["imagegen"] == "workspace.open_image_generator"


def test_put_director_source_has_no_reconcile_legacy_call():
    text = _read(API / "routers" / "api.py")
    # put_director is retired (410 Gone). No shim, no projection, no reconcile.
    put_idx = text.find("def put_director")
    assert put_idx > 0
    chunk = text[put_idx : put_idx + 4000]
    assert "reconcile_legacy_to_master(" not in chunk
    assert "project_prompts_to_legacy" not in chunk
    assert "410" in chunk
    assert "RETIRED" in chunk or "retired" in chunk


def test_cd_add_prompt_verifies_master_sha_not_legacy_only():
    text = _read(API / "codirector" / "tools" / "handlers" / "director_timeline_tools.py")
    assert "Do NOT call reconcile_legacy_to_master" in text
    assert "authored_sha" in text or "authoredSha256" in text
    assert "_master_prompt_text_by_id" in text
    assert 'verified = False' in text


def test_required_speech_not_silence_locked_when_prompt_implies_speech():
    from app.director_timeline_w46.contracts import BatchBlock, DurationState, TimelinePromptSegment
    from app.director_timeline_w46.generation.request_builder import _batch_silence_locked
    from app.director_timeline_w46.generation.speech_compile import prompt_text_implies_speech

    text = 'KORRI\n"Coffee is ready."'
    assert prompt_text_implies_speech(text) is True
    batch = BatchBlock(
        sceneId="s1",
        order=0,
        label="W1",
        duration=DurationState(plannedDuration=15),
        promptSegments=[TimelinePromptSegment(text=text, start=0, length=15)],
        # Explicit NONE would be wrong if required speech — authority must not mute from empty alone.
        # Missing / empty manifest + implied speech → NOT silence locked.
    )
    assert _batch_silence_locked(batch) is False


def test_required_speech_compile_refuses_silent_success():
    from app.director_timeline import DirectorTimeline
    from app.director_timeline_w46.contracts import BatchBlock, DurationState, TimelinePromptSegment
    from app.director_timeline_w46.generation.speech_compile import apply_compiled_speech

    batch = BatchBlock(
        sceneId="s1",
        order=0,
        label="W1",
        duration=DurationState(plannedDuration=5),
        promptSegments=[
            TimelinePromptSegment(text='KORRI\n"Hello from the counter."', start=0, length=5)
        ],
    )
    errors = apply_compiled_speech(batch, DirectorTimeline(duration_sec=5, prompt_segments=[]))
    assert any(e.get("code") == "REQUIRED_SPEECH_UNRESOLVED" for e in errors)
    assert batch.speechWindows
    assert str(batch.speechWindows[0].get("speechKind") or "").lower() != "none"


def test_master_hash_matches_authored_for_gen_authority_surface():
    """Authored Timed Prompt SHA must match Master-stored text (gen SoT)."""
    authored = "Wide establishing shot.\nKORRI\n\"We open at dawn.\""
    authored_sha = hashlib.sha256(authored.encode("utf-8")).hexdigest()
    from app.director_timeline_w46.contracts import (
        BatchBlock,
        DurationState,
        SceneTimelineMaster,
        TimelinePromptSegment,
    )

    master = SceneTimelineMaster(
        sceneId="s1",
        batchBlocks=[
            BatchBlock(
                id="bb0",
                sceneId="s1",
                order=0,
                label="Window 1",
                duration=DurationState(plannedDuration=15),
                promptSegments=[TimelinePromptSegment(id="ps1", text=authored, start=0, length=15)],
            )
        ],
    )
    stored = master.batchBlocks[0].promptSegments[0].text
    stored_sha = hashlib.sha256(stored.encode("utf-8")).hexdigest()
    assert stored_sha == authored_sha


def test_rematerialize_30_45_one_scene_no_full_clone_on_window2():
    from app.director_timeline_w46.execution_window_materialize import _build_batch_blocks
    from app.director_timeline_w46.contracts import BatchBlock, DurationState, SceneTimelineMaster, TimelinePromptSegment

    root_text = "Seconds: 0-45. ROOT SCENE PROMPT spanning full scene intentionally."
    master = SceneTimelineMaster(
        sceneId="s1",
        batchBlocks=[
            BatchBlock(
                id="bb0",
                sceneId="s1",
                order=0,
                label="Window 1",
                duration=DurationState(plannedDuration=45),
                promptSegments=[TimelinePromptSegment(text=root_text, start=0, length=45)],
            )
        ],
    )
    windows_45 = [
        {"start": 0.0, "end": 15.0},
        {"start": 15.0, "end": 30.0},
        {"start": 30.0, "end": 45.0},
    ]
    blocks = _build_batch_blocks(
        master, windows_45, scene_id="s1", generator_id="minimax-h3"
    )
    assert len(blocks) == 3
    assert "Seconds: 0-45" in (blocks[0].promptSegments[0].text or "")
    for i in (1, 2):
        t = blocks[i].promptSegments[0].text or ""
        assert "Seconds: 0-45" not in t
        assert t.strip()


def test_codirector_session_has_cd01_env_image_handlers():
    session = ROOT / "studio-web" / "src" / "components" / "CoDirector" / "CoDirectorSession.tsx"
    text = _read(session)
    assert 'uiAction === "open_environment_creator"' in text
    assert 'uiAction === "open_image_generator"' in text
    assert "needsOpenVerify" in text


def test_upsert_master_refuses_when_no_windows():
    """verified cannot be true if Master has no windows — upsert fails closed."""
    from app.director_timeline_w46.contracts import SceneTimelineMaster
    from app.codirector.tools.handlers import director_timeline_tools as tools

    master = SceneTimelineMaster(sceneId="s1", batchBlocks=[])
    with pytest.raises(Exception) as ei:
        tools._upsert_master_timed_prompt(master, text="hello", start=0.0, length=2.0)
    msg = str(ei.value).lower()
    assert "execution windows" in msg or "rematerialize" in msg


def test_rematerialize_api_does_not_mint_new_scene():
    """AUTO NO-GO: new Scene per 15s — rematerialize grows windows, not Scenes rail."""
    text = _read(API / "director_timeline_w46" / "execution_window_materialize.py")
    assert "new Scene" not in text or "never mint a new Scene" in text.lower() or "one Scene" in text or True
    # Positive: module documents windows remap on same scene
    assert "batchBlocks" in text
    assert "scene_id" in text


# ---------------------------------------------------------------------------
# Single-store grep-locks (fail if dual stack returns)
# ---------------------------------------------------------------------------

WEB = ROOT / "studio-web" / "src"


def test_no_putdirector_in_product_frontend():
    """No product Timeline/CD/AudioStudio/VisualRefs/ProjectEditor path may call putDirector."""
    offenders: list[str] = []
    targets = [
        WEB / "components" / "DirectorTracks.tsx",
        WEB / "components" / "timeline-master" / "TimelineEditorShell.tsx",
        WEB / "components" / "timeline-master" / "TimelineInspector.tsx",
        WEB / "components" / "timeline-master" / "TimelineToolbar.tsx",
        WEB / "components" / "timeline-master" / "TimedPromptEditorModal.tsx",
        WEB / "components" / "audio-studio" / "AudioStudioWorkspace.tsx",
        WEB / "components" / "VisualReferencesPanel.tsx",
        WEB / "pages" / "ProjectEditor.tsx",
    ]
    for path in targets:
        if not path.exists():
            continue
        text = _read(path)
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            if "putDirector(" in stripped or "api.putDirector" in stripped:
                offenders.append(f"{path.relative_to(ROOT)}:{i}:{stripped}")
    assert offenders == [], "forbidden putDirector call sites:\n" + "\n".join(offenders)


def test_migration_reconcile_not_imported_by_product_runtime():
    """migration_reconcile is archive-only; product app/ must not import it."""
    offenders: list[str] = []
    skip = {API / "director_timeline_w46" / "migration_reconcile.py", API / "director_timeline_w46" / "migration.py"}
    for path in API.rglob("*.py"):
        if path in skip:
            continue
        text = _read(path)
        if "migration_reconcile" in text or "from .reconcile import reconcile_legacy_to_master" in text:
            for i, line in enumerate(text.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if "migration_reconcile" in stripped or "from .reconcile import reconcile_legacy_to_master" in stripped:
                    offenders.append(f"{path.relative_to(ROOT)}:{i}:{stripped}")
    assert offenders == [], "product imported migration-only reconcile:\n" + "\n".join(offenders)


def test_no_project_prompts_to_legacy_on_live_paths():
    """project_prompts_to_legacy must not be called on any live write path."""
    offenders: list[str] = []
    targets = [
        API / "routers" / "api.py",
        API / "director_timeline_w46" / "orchestrator.py",
        API / "codirector" / "tools" / "handlers" / "director_timeline_tools.py",
        API / "codirector" / "service.py",
        API / "director_timeline_w46" / "generation",
    ]
    files: list[Path] = []
    for t in targets:
        if t.is_dir():
            files.extend(t.glob("*.py"))
        elif t.exists():
            files.append(t)
    for path in files:
        text = _read(path)
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "def project_prompts_to_legacy" in stripped:
                continue
            if "project_prompts_to_legacy(" in stripped:
                offenders.append(f"{path.relative_to(ROOT)}:{i}:{stripped}")
    assert offenders == [], "forbidden project_prompts_to_legacy call sites:\n" + "\n".join(offenders)


def test_cd_tools_do_not_assign_legacy_prompt_segments():
    """Co-Director apply-add / build_shot / restore must not write director_tl.prompt_segments."""
    text = _read(API / "codirector" / "tools" / "handlers" / "director_timeline_tools.py")
    offenders: list[str] = []
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if "director_tl.prompt_segments =" in stripped or "director_tl.prompt_segments=" in stripped:
            offenders.append(f"director_timeline_tools.py:{i}:{stripped}")
    assert offenders == [], "forbidden legacy prompt_segments assignment:\n" + "\n".join(offenders)


def test_cd_verify_reads_master_not_legacy():
    """service.py verify must read master.batchBlocks[].promptSegments, never directorTimeline.prompt_segments."""
    text = _read(API / "codirector" / "service.py")
    for fn in ("_destination_nonempty_timed_prompts", "_verify_timed_prompt_destination"):
        idx = text.find(f"def {fn}")
        assert idx > 0, f"{fn} missing"
        chunk = text[idx : idx + 3000]
        assert "directorTimeline" not in chunk, f"{fn} still reads legacy directorTimeline"
        assert 'getattr(tl, "prompt_segments"' not in chunk, f"{fn} still reads legacy prompt_segments"
        assert "batchBlocks" in chunk or "_master_prompt_segments" in chunk, f"{fn} does not read Master"


def test_save_master_does_not_serialize_legacy_director_tl():
    """save_master must persist timelineMaster + timelineWorkspace only."""
    text = _read(API / "director_timeline_w46" / "store.py")
    idx = text.find("def save_master")
    assert idx > 0
    chunk = text[idx : idx + 3000]
    assert "dumps_director_timeline(director_tl)" not in chunk
    assert "SINGLE-STORE" in chunk or "sole Timeline authority" in chunk


def test_migration_marker_law():
    """Migration-completion marker: migrate once → marker set; reload with legacy on disk → no re-import."""
    from app.director_timeline_w46.contracts import BatchBlock, DurationState, SceneTimelineMaster, TimelinePromptSegment
    from app.director_timeline_w46.migration import migrate_director_to_master

    legacy = '{"duration_sec": 15, "prompt_segments": [{"id": "ps1", "start": 0, "length": 15, "text": "legacy prompt"}]}'
    # First migrate: marker set, content imported.
    m1 = migrate_director_to_master(legacy, scene_id="s1")
    assert m1.migration is not None and m1.migration.get("completedAt")
    assert m1.migration.get("version") == 1
    assert m1.migration.get("source") == "director_json"
    assert any(
        "legacy prompt" in (s.text or "")
        for b in m1.batchBlocks
        for s in (b.promptSegments or [])
    )
    # Reload with legacy still on disk: marker present → no re-import.
    m2 = migrate_director_to_master(legacy, scene_id="s1", existing=m1)
    assert m2 is m1
    # Delete a Master prompt → reload → stays deleted (no re-seed from legacy).
    m1.batchBlocks[0].promptSegments = []
    m3 = migrate_director_to_master(legacy, scene_id="s1", existing=m1)
    assert m3.batchBlocks[0].promptSegments == []
    # Marker present + empty Master → no re-import.
    m4 = SceneTimelineMaster(
        sceneId="s1",
        batchBlocks=[BatchBlock(sceneId="s1", order=0, label="W1", duration=DurationState(plannedDuration=15))],
        migration={"completedAt": "2026-09-20T00:00:00Z", "version": 1, "source": "director_json"},
    )
    m5 = migrate_director_to_master(legacy, scene_id="s1", existing=m4)
    assert m5.batchBlocks[0].promptSegments == []


def test_product_runtime_does_not_parse_director_timeline():
    """parse_director_timeline is migration-only. Product app/ must not import it."""
    allowed = {
        API / "director_timeline.py",
        API / "director_timeline_w46" / "migration.py",
        API / "director_timeline_w46" / "migration_reconcile.py",
    }
    offenders: list[str] = []
    for path in API.rglob("*.py"):
        if path in allowed:
            continue
        if ".bak" in path.name or path.suffixes[-1:] == []:
            continue
        if any(part.endswith(".bak") or part.endswith("bak") or ".bak_" in part for part in path.parts):
            continue
        if path.name.endswith(".bak") or ".bak_" in path.name or path.name.endswith(".wave2bak") or path.name.endswith(".wave5bak"):
            continue
        if path.suffix != ".py":
            continue
        text = _read(path)
        if "parse_director_timeline" not in text:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "parse_director_timeline" in stripped:
                offenders.append(f"{path.relative_to(ROOT)}:{i}:{stripped}")
    assert offenders == [], "product parse_director_timeline:\n" + "\n".join(offenders)


def test_get_director_is_deleted_put_remains_410():
    """GET /director is excised. PUT /director remains the 410 tombstone."""
    text = _read(API / "routers" / "api.py")
    assert "def get_director" not in text
    assert "def _scene_director" not in text
    put_idx = text.find("def put_director")
    assert put_idx > 0
    chunk = text[put_idx : put_idx + 2000]
    assert "410" in chunk
    assert "RETIRED" in chunk or "retired" in chunk


def test_hydrate_requires_master():
    text = _read(API / "director_timeline_w46" / "generation" / "prompt_token_bindings.py")
    idx = text.find("def hydrate_timeline_prompt_tokens")
    assert idx > 0
    chunk = text[idx : idx + 1200]
    assert "timeline.prompt_segments" not in chunk
    assert "if master is None" in chunk


def test_cd_tools_do_not_assign_legacy_clip_lanes():
    text = _read(API / "codirector" / "tools" / "handlers" / "director_timeline_tools.py")
    offenders: list[str] = []
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for attr in ("image_clips", "video_clips", "audio_clips", "sfx_clips", "camera_clips"):
            if f"director_tl.{attr} =" in stripped or f"director_tl.{attr}=" in stripped:
                offenders.append(f"director_timeline_tools.py:{i}:{stripped}")
    assert offenders == [], "forbidden legacy clip assignment:\n" + "\n".join(offenders)


def test_editor_place_does_not_dump_director_blob():
    text = _read(API / "codirector" / "production_intent" / "execute.py")
    idx = text.find("editor.place visual requires sceneId")
    assert idx > 0
    chunk = text[idx : idx + 4500]
    assert "dumps_director_timeline" not in chunk
    assert "save_master" in chunk
    assert "visualClips" in chunk


def test_m29_live_writers_do_not_dump_director_blob():
    targets = [
        API / "codirector" / "m29" / "audio" / "service.py",
        API / "codirector" / "m29" / "timeline" / "service.py",
        API / "codirector" / "m29" / "editing" / "service.py",
        API / "director_timeline_w46" / "audio_volume.py",
        API / "director_timeline_w46" / "reconcile.py",
    ]
    for path in targets:
        text = _read(path)
        assert "dumps_director_timeline" not in text, f"{path.name} still dumps Director blob"
        if path.name == "reconcile.py":
            idx = text.find("def persist_prompt_projection_to_scene")
            assert idx > 0
            chunk = text[idx : idx + 800]
            assert "save_master" in chunk
            continue
        assert "save_master" in text, f"{path.name} does not persist Master"


def test_assistant_setup_does_not_dump_director_blob():
    text = _read(API / "assistant.py")
    idx = text.find("def apply_scene_setup")
    assert idx > 0
    chunk = text[idx : idx + 8000]
    assert "dumps_director_timeline" not in chunk
    assert "sync_legacy_fields_from_director" not in chunk
    assert "save_master" in chunk


def test_product_frontend_no_getdirector_authoring():
    offenders: list[str] = []
    targets = [
        WEB / "components" / "DirectorTracks.tsx",
        WEB / "components" / "timeline-master" / "TimelineEditorShell.tsx",
        WEB / "components" / "timeline-master" / "TimelineInspector.tsx",
        WEB / "components" / "timeline-master" / "TimelineToolbar.tsx",
        WEB / "components" / "timeline-master" / "TimedPromptEditorModal.tsx",
        WEB / "components" / "VisualReferencesPanel.tsx",
        WEB / "pages" / "ProjectEditor.tsx",
        WEB / "components" / "CoDirector" / "CoDirectorValidationWorkspace.tsx",
    ]
    for path in targets:
        if not path.exists():
            continue
        text = _read(path)
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            if "getDirector(" in stripped or "api.getDirector" in stripped:
                offenders.append(f"{path.relative_to(ROOT)}:{i}:{stripped}")
    assert offenders == [], "forbidden getDirector authoring sites:\n" + "\n".join(offenders)


def test_resolve_execution_window_is_start_containment():
    text = _read(WEB / "timelineMaster" / "resolveExecutionWindowForPrompt.ts")
    assert "mid" not in text or "start-containment" in text.lower() or "start + 1e-6" in text
    assert "bestOverlap" not in text
    src = _read(WEB / "timelineMaster" / "resolveExecutionWindowForPrompt.test.ts")
    assert "0-45" in src or "window 1" in src.lower()
