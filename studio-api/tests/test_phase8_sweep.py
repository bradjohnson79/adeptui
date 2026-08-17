'Phase 8 sweep tests: bounded P2/P3 remediation (CDX-005/011/016/023/025/026/033/040/047/048/049/050).'

from __future__ import annotations

import json
import uuid


def _session():
    from app.db import SessionLocal, init_db

    init_db()
    return SessionLocal()


def _create_project(client, name: str = 'Phase8 Sweep') -> str:
    res = client.post('/api/projects', json={'name': name})
    assert res.status_code == 200
    return res.json()['id']


def _seed_character(project_id: str, character_id: str) -> None:
    from app.character_identity.models import CharacterProfileRow

    db = _session()
    try:
        existing = db.get(CharacterProfileRow, character_id)
        if existing is not None:
            db.delete(existing)
            db.commit()
        db.add(CharacterProfileRow(id=character_id, project_id=project_id, name=character_id))
        db.commit()
    finally:
        db.close()


def _make_document() -> object:
    from app.spatial_map.schemas import SpatialMapDocument, SpatialCharacterPlacement, SpatialCamera

    return SpatialMapDocument(
        id=str(uuid.uuid4()),
        projectId='p1',
        title='Stage',
        masterEnvironmentPrompt='One master environment.',
        cameras=[SpatialCamera(label='Hero Cam', x=0.0, z=2.0, hero=True)],
        characters=[
            # CDX-025: never placed on the grid - defaults x=0/z=0, no normalized coords.
            SpatialCharacterPlacement(characterId='unplaced-1', label='Unplaced Char', x=0.0, z=0.0),
            # Explicitly placed in front of the hero camera (z=2.0) at yaw 0.
            SpatialCharacterPlacement(characterId='placed-1', label='Placed Char', x=0.0, z=4.0),
        ],
    )


def test_cdx023_camera_limit_copy_says_four() -> None:
    from app.spatial_map.errors import ERROR_DETAILS, SpatialMapErrorCode

    detail = ERROR_DETAILS[SpatialMapErrorCode.CAMERA_LIMIT_REACHED]
    assert 'four cameras' in detail['explanation']
    assert 'eight' not in detail['explanation']


def test_cdx025_unplaced_character_not_reported_at_origin() -> None:
    from app.spatial_map.capture_intelligence import _spatial_visibility_clause
    from app.spatial_map.reference_bundle import compile_reference_bundle, summarize_reference_bundle

    doc = _make_document()
    db = _session()
    try:
        clause = _spatial_visibility_clause(doc, yaw_degrees=0, include_characters=True)
        # The unplaced character must not be described as standing at the world
        # origin (0,0). The placed character at x=-2,z=-2.5 is foreground-left.
        assert 'Unplaced Char' not in clause
        assert 'Placed Char' in clause

        bundle = compile_reference_bundle(db, document=doc, target='image')
        labels = bundle.creatorPositionLabels
        placed_id = [c.id for c in doc.characters if c.characterId == 'placed-1'][0]
        unplaced_id = [c.id for c in doc.characters if c.characterId == 'unplaced-1'][0]
        assert labels.get(placed_id) == 'background center'
        assert unplaced_id not in labels
        summary = summarize_reference_bundle(bundle)
        chars = '; '.join(summary['characters'])
        assert 'not placed on the grid yet' in chars
        assert 'center midground' not in chars
    finally:
        db.close()


def test_cdx033_legacy_ers_mutation_tools_not_exposed() -> None:
    from app.codirector.tools.exposure import _LEGACY_ERS_MUTATION_TOOL_IDS, expose

    ids = expose(workspace_surface='environment', intent='generate the ers')
    for tool_id in _LEGACY_ERS_MUTATION_TOOL_IDS:
        assert tool_id not in ids
    # Read-only ERS tools remain reachable.
    assert 'ers.list_sheets' in ids
    assert 'ers.get_sheet' in ids


def test_cdx040_reference_packet_discloses_unsupported_environment() -> None:
    from app.scene_creator.reference_packet import apply_reference_packet

    body = {'creativeContext': {'ers_composite_asset_id': 'ers-composite-1'}}
    out = apply_reference_packet(body, family='qwen2512', profile_grounded=False, production_loaded=False)
    pkt = out['creativeContext']['referencePacket']
    assert pkt['pixelSlots'] == 0
    assert pkt['environment']['consumption'] == 'unsupported'
    assert pkt['blocking'] is False
    assert any(i['code'] == 'provider_slot' and i['type'] == 'advisory' for i in pkt['issues'])

    # zimage (1 slot): in a normal shot the slot goes to characters/props, so the
    # environment rides as semantic_only; in ers_only mode it is consumed.
    body2 = {'creativeContext': {'ers_composite_asset_id': 'ers-composite-1'}}
    out2 = apply_reference_packet(body2, family='zimage', profile_grounded=False, production_loaded=False)
    pkt2 = out2['creativeContext']['referencePacket']
    assert pkt2['environment']['consumption'] == 'semantic_only'
    body3 = {'creativeContext': {'ers_composite_asset_id': 'ers-composite-1'}}
    out3 = apply_reference_packet(body3, family='zimage', profile_grounded=False, production_loaded=False, diagnostic_mode='ers_only')
    pkt3 = out3['creativeContext']['referencePacket']
    assert pkt3['environment']['consumption'] == 'consumed'


def test_cdx048_sync_candidate_jobs_falls_back_to_failed(client) -> None:
    from app.db import Job, Scene
    from app.scene_creator.service import _sync_candidate_jobs
    from app.spatial_map.ers_contracts import SceneShot, SceneShotCandidate

    project_id = _create_project(client)
    db = _session()
    try:
        scene_id = str(uuid.uuid4())
        db.add(Scene(id=scene_id, project_id=project_id, name='S1'))
        db.commit()

        # 1) job_id references a job that no longer exists -> failed.
        missing_job_id = str(uuid.uuid4())
        # 2) job done but no parseable output asset -> failed.
        done_no_asset = Job(
            id=str(uuid.uuid4()), project_id=project_id, status='done',
            params_json='{}', preview_json='{}',
        )
        # 3) job done with a real output asset -> complete.
        done_with_asset = Job(
            id=str(uuid.uuid4()), project_id=project_id, status='done',
            params_json=json.dumps({'output_asset_id': 'asset-ok'}), preview_json='{}',
        )
        db.add_all([done_no_asset, done_with_asset])
        db.commit()

        shot = SceneShot(
            project_id=project_id, scene_id=scene_id, sheet_id='sheet-1',
            candidates=[
                SceneShotCandidate(id='c1', job_id=missing_job_id, status='generating'),
                SceneShotCandidate(id='c2', job_id=done_no_asset.id, status='generating'),
                SceneShotCandidate(id='c3', job_id=done_with_asset.id, status='generating'),
            ],
        )
        _sync_candidate_jobs(db, project_id, shot)
        by_id = {c.id: c for c in shot.candidates}
        assert by_id['c1'].status == 'failed'
        assert by_id['c1'].error
        assert by_id['c2'].status == 'failed'
        assert by_id['c2'].error
        assert by_id['c3'].status == 'complete'
        assert by_id['c3'].asset_id == 'asset-ok'
    finally:
        db.close()


def test_cdx049_workspace_hydrate_is_read_only(client) -> None:
    from app.environment_reference_sheet import orchestrator, store
    from app.scene_creator.production_handoff import (
        SpatialProfilePointers, load_selection, save_profile, save_selection,
        ProfileSelection, stable_handoff_id,
    )
    from app.spatial_map.ers_persistence import list_ers_packages

    project_id = _create_project(client)
    from app.db import Scene

    db0 = _session()
    try:
        db0.add(Scene(id='scene-1', project_id=project_id, name='Scene 1'))
        db0.commit()
    finally:
        db0.close()
    sheet = orchestrator.create_sheet(
        project_id=project_id, name='Helios', description='Glass atrium.', scene_id='scene-1',
    )
    store.save_sheet(sheet)

    db = _session()
    try:
        # Persist a selection for profile A, then GET with profile B: the GET
        # must hydrate read-only and leave the persisted selection at A.
        handoff_a = stable_handoff_id(project_id, 'map-a', 'scene-1')
        handoff_b = stable_handoff_id(project_id, 'map-b', 'scene-1')
        save_profile(db, project_id, SpatialProfilePointers(
            handoffId=handoff_a, projectId=project_id, sceneId='scene-1',
            sheetId=sheet.sheetId, spatialMapId='map-a', name='A',
        ))
        save_profile(db, project_id, SpatialProfilePointers(
            handoffId=handoff_b, projectId=project_id, sceneId='scene-1',
            sheetId=sheet.sheetId, spatialMapId='map-b', name='B',
        ))
        save_selection(db, project_id, ProfileSelection(selectedProfileId=handoff_a))

        res = client.get(
            f'/api/scene-creator/projects/{project_id}/workspace',
            params={'spatial_profile_id': handoff_b, 'scene_id': 'scene-1', 'sheet_id': sheet.sheetId},
        )
        assert res.status_code == 200
        # Selection must NOT have moved to profile B - GET never persists.
        assert load_selection(db, project_id).selectedProfileId == handoff_a
        # No runtime-* ERS package may be persisted by hydration.
        packages = list_ers_packages(db, project_id)
        assert not any(str(p.id).startswith('runtime-') for p in packages)
    finally:
        db.close()


def test_cdx016_upsert_identity_is_atomic() -> None:
    from app.prop_creator.service import create_or_update_prop

    project_id = str(uuid.uuid4())
    db = _session()
    try:
        from app.db import Asset, Project

        db.add(Project(id=project_id, name='Props'))
        db.add(Asset(id='ref-1', project_id=project_id, kind='image', tag='ref', filename='ref.png', path='ref.png'))
        db.commit()
        prop = create_or_update_prop(
            db, project_id, name='Coffee Cup',
            reference_asset_id='ref-1', use_as_identity=True, identity_asset_id='ref-1',
        )
        assert prop.approved_asset_id == 'ref-1'
        assert prop.library_asset_id == 'ref-1'
    finally:
        db.close()