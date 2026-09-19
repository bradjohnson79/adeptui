"""Asset file GET/HEAD/Range — Voice Performance <audio> media probe.

Browsers (especially Safari) often HEAD a media URL before GET. A 405 JSON
response leaves the HTML audio element at 0:00/0:00 even when durationMs on
the take record is correct and GET/Range would succeed.
"""

from __future__ import annotations

MINIMAL_WAV = (
    b"RIFF"
    + (36 + 160).to_bytes(4, "little")
    + b"WAVEfmt "
    + (16).to_bytes(4, "little")
    + (1).to_bytes(2, "little")
    + (1).to_bytes(2, "little")
    + (8000).to_bytes(4, "little")
    + (16000).to_bytes(4, "little")
    + (2).to_bytes(2, "little")
    + (16).to_bytes(2, "little")
    + b"data"
    + (160).to_bytes(4, "little")
    + (b"\x00" * 160)
)


def _mk_project(client, name="Voice Asset File"):
    res = client.post("/api/projects", json={"name": name})
    assert res.status_code == 200, res.text
    return res.json()


def _mk_wav_asset(client, pid, aid="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1"):
    from app.config import settings
    from app.db import Asset, SessionLocal

    path = settings.data_dir / f"projects/{pid}" / "takes" / "take.wav"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(MINIMAL_WAV)

    db = SessionLocal()
    try:
        db.add(Asset(id=aid, project_id=pid, filename="take.wav", path=str(path), kind="audio"))
        db.commit()
    finally:
        db.close()
    return aid, path


def test_global_asset_file_head_returns_type_and_length_without_body(client):
    pid = _mk_project(client)["id"]
    aid, path = _mk_wav_asset(client, pid)

    head = client.head(f"/api/assets/{aid}/file")
    assert head.status_code == 200, head.text
    assert "audio" in (head.headers.get("content-type") or "").lower()
    assert head.headers.get("content-length") == str(path.stat().st_size)
    assert head.content == b""

    get = client.get(f"/api/assets/{aid}/file")
    assert get.status_code == 200, get.text
    assert get.content[:12] == MINIMAL_WAV[:12]
    assert get.content == MINIMAL_WAV


def test_project_asset_file_head_and_range(client):
    pid = _mk_project(client)["id"]
    aid, path = _mk_wav_asset(client, pid, aid="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2")
    url = f"/api/projects/{pid}/assets/{aid}/file"

    head = client.head(url)
    assert head.status_code == 200, head.text
    assert "audio" in (head.headers.get("content-type") or "").lower()
    assert head.headers.get("content-length") == str(path.stat().st_size)
    assert head.content == b""

    ranged = client.get(url, headers={"Range": "bytes=0-3"})
    assert ranged.status_code == 206, ranged.text
    assert ranged.content == b"RIFF"

    full = client.get(url)
    assert full.status_code == 200, full.text
    assert full.content == MINIMAL_WAV


def test_project_asset_file_rejects_cross_project(client):
    owner = _mk_project(client, "Owner")["id"]
    other = _mk_project(client, "Other")["id"]
    aid, _path = _mk_wav_asset(client, owner, aid="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa3")

    res = client.get(f"/api/projects/{other}/assets/{aid}/file")
    assert res.status_code == 404, res.text
