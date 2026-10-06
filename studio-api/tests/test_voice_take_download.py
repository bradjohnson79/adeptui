"""Takes download route: exact generated file, attachment disposition, sane name."""
from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from app.character_identity.models import CharacterProfileRow
from app.db import Asset, Project, SessionLocal
from app.voice_performance.m410_models import VoicePerformanceRecordRow, VoicePerformanceTakeRow


def _seed_take(isolated_data_dir: Path, *, character_name: str = "Renkoka", suffix: str = ".mp3"):
    db = SessionLocal()
    try:
        project_id = f"proj-{uuid.uuid4().hex[:8]}"
        character_id = f"char-{uuid.uuid4().hex[:8]}"
        record_id = str(uuid.uuid4())
        take_id = str(uuid.uuid4())
        asset_id = str(uuid.uuid4())

        audio = isolated_data_dir / f"{take_id}{suffix}"
        audio.write_bytes(b"ID3\x03\x00\x00\x00\x00\x00\x21")

        db.add(Project(id=project_id, name="Takes Download", settings_json="{}"))
        db.add(
            CharacterProfileRow(
                id=character_id,
                project_id=project_id,
                name=character_name,
                status="APPROVED",
                approval_status="approved",
            )
        )
        db.add(
            VoicePerformanceRecordRow(
                id=record_id,
                project_id=project_id,
                character_id=character_id,
                voice_identity_id=f"voice-{uuid.uuid4().hex[:8]}",
                dialogue_text="[Warmly] Hello, my name is Renkoka.",
            )
        )
        db.add(
            Asset(
                id=asset_id,
                project_id=project_id,
                kind="audio",
                tag="dialogue",
                filename=audio.name,
                path=str(audio),
            )
        )
        db.add(
            VoicePerformanceTakeRow(
                id=take_id,
                record_id=record_id,
                take_number=2,
                label="Take 2",
                audio_asset_id=asset_id,
                duration_ms=2100,
                status="completed",
                direction_snapshot_json={},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )
        db.commit()
        return record_id, take_id, audio.read_bytes()
    finally:
        db.close()


def test_take_download_route_streams_attachment(client, isolated_data_dir):
    record_id, take_id, expected = _seed_take(isolated_data_dir)

    response = client.get(f"/api/voice-performance/m410/records/{record_id}/takes/{take_id}/download")
    assert response.status_code == 200, response.text
    assert response.content == expected
    disposition = response.headers.get("content-disposition", "")
    assert "attachment" in disposition
    assert "Renkoka_Take_2.mp3" in disposition
    assert response.headers.get("content-type", "").startswith("audio/mpeg")


def test_take_download_route_rejects_unfinished_take(client, isolated_data_dir):
    record_id, take_id, _ = _seed_take(isolated_data_dir)
    db = SessionLocal()
    try:
        take = db.get(VoicePerformanceTakeRow, take_id)
        take.status = "generating"
        db.commit()
    finally:
        db.close()

    response = client.get(f"/api/voice-performance/m410/records/{record_id}/takes/{take_id}/download")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "TAKE_NOT_READY"


def test_take_download_route_404_for_unknown_take(client):
    response = client.get(
        f"/api/voice-performance/m410/records/{uuid.uuid4()}/takes/{uuid.uuid4()}/download"
    )
    assert response.status_code == 404
