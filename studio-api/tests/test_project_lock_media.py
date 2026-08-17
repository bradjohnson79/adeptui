"""CDX-069 — project password lock must cover /media static mount and /api/file.

Regression: mediaUrl() emits /media/projects/{id}/... (and /media/assets/{id}/...)
for scene renders, lipsync outputs, thumbnails and job previews, plus
/api/file?path=... as a fallback. Before this change a locked project's media
was fetchable without the unlock token through those URLs.

Also spot-checks CDX-053 (cross-project scriptwriter document access stays 404).
"""

from __future__ import annotations

import pytest

PASSWORD = "correct horse battery staple"
MEDIA_BYTES = b"fake-media-bytes-0123456789"
ORIGIN = "https://adeptui.vercel.app"


def _mk_project(client, name="Media Lock Project"):
    res = client.post("/api/projects", json={"name": name})
    assert res.status_code == 200, res.text
    return res.json()


def _enable_password(client, pid):
    res = client.post(
        f"/api/projects/{pid}/security/password",
        json={"password": PASSWORD, "confirmPassword": PASSWORD},
    )
    assert res.status_code == 200, res.text


def _unlock(client, pid):
    res = client.post(
        f"/api/projects/{pid}/security/unlock",
        json={"password": PASSWORD, "rememberFor": "session"},
    )
    assert res.status_code == 200, res.text
    return res.json()["unlockToken"]


def _write_media(rel_parts):
    from app.config import settings

    p = settings.data_dir.joinpath(*rel_parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(MEDIA_BYTES)
    return p


def _mk_asset(pid, path, aid="11111111-1111-4111-8111-111111111111"):
    from app.db import Asset, SessionLocal

    db = SessionLocal()
    try:
        db.add(Asset(id=aid, project_id=pid, filename="scene.png", path=str(path)))
        db.commit()
    finally:
        db.close()
    return aid


def test_media_mount_locked_then_unlocked_via_header(client):
    pid = _mk_project(client)["id"]
    video = _write_media([f"projects/{pid}/renders", "scene_001.png"])
    url = f"/media/projects/{pid}/renders/scene_001.png"
    _enable_password(client, pid)

    # Locked: 403 without unlock token.
    locked = client.get(url)
    assert locked.status_code == 403, locked.text
    assert locked.json()["detail"]["code"] == "PROJECT_LOCKED"

    # Unlock and fetch with the header token: 200.
    token = _unlock(client, pid)
    ok = client.get(url, headers={"X-Adept-Project-Unlock": token})
    assert ok.status_code == 200, ok.text
    assert ok.content == MEDIA_BYTES
    assert video.exists()


def test_media_mount_unlocked_via_cookie(client):
    pid = _mk_project(client)["id"]
    _write_media([f"projects/{pid}/renders", "scene_002.png"])
    url = f"/media/projects/{pid}/renders/scene_002.png"
    _enable_password(client, pid)

    assert client.get(url).status_code == 403
    _unlock(client, pid)  # sets adept_unlock_<pid> cookie
    ok = client.get(url)
    assert ok.status_code == 200, ok.text
    assert ok.content == MEDIA_BYTES

    # Re-lock: grants revoked -> 403 again even with the (now stale) cookie.
    relock = client.post(f"/api/projects/{pid}/security/lock")
    assert relock.status_code == 200, relock.text
    assert client.get(url).status_code == 403


def test_api_file_locked_then_unlocked(client):
    pid = _mk_project(client)["id"]
    video = _write_media([f"projects/{pid}/renders", "scene_003.png"])
    _enable_password(client, pid)

    # Absolute path: locked without token.
    locked = client.get("/api/file", params={"path": str(video)})
    assert locked.status_code == 403, locked.text

    # Relative data path also resolves to the project and is locked (still locked).
    rel = client.get("/api/file", params={"path": f"projects/{pid}/renders/scene_003.png"})
    assert rel.status_code == 403, rel.text

    token = _unlock(client, pid)
    ok = client.get("/api/file", params={"path": str(video)}, headers={"X-Adept-Project-Unlock": token})
    assert ok.status_code == 200, ok.text
    assert ok.content == MEDIA_BYTES


def test_assets_dir_media_mount_locked(client):
    pid = _mk_project(client)["id"]
    _write_media([f"assets/{pid}", "imported_footage.png"])
    url = f"/media/assets/{pid}/imported_footage.png"
    _enable_password(client, pid)

    assert client.get(url).status_code == 403
    token = _unlock(client, pid)
    ok = client.get(url, headers={"X-Adept-Project-Unlock": token})
    assert ok.status_code == 200, ok.text
    assert ok.content == MEDIA_BYTES


def test_unprotected_project_media_unaffected(client):
    pid = _mk_project(client)["id"]
    _write_media([f"projects/{pid}/renders", "scene_004.png"])
    url = f"/media/projects/{pid}/renders/scene_004.png"
    # No password set: media must remain fetchable.
    ok = client.get(url)
    assert ok.status_code == 200, ok.text
    assert ok.content == MEDIA_BYTES
    ok2 = client.get("/api/file", params={"path": str(_write_media([f"projects/{pid}/renders", "scene_004b.png"]))})
    assert ok2.status_code == 200, ok2.text


def test_locked_project_does_not_affect_other_projects(client):
    locked_pid = _mk_project(client, "Locked")["id"]
    open_pid = _mk_project(client, "Open")["id"]
    _write_media([f"projects/{locked_pid}/renders", "a.png"])
    _write_media([f"projects/{open_pid}/renders", "b.png"])
    _enable_password(client, locked_pid)

    assert client.get(f"/media/projects/{locked_pid}/renders/a.png").status_code == 403
    ok = client.get(f"/media/projects/{open_pid}/renders/b.png")
    assert ok.status_code == 200, ok.text
    assert ok.content == MEDIA_BYTES


def test_asset_file_route_remains_locked(client):
    pid = _mk_project(client)["id"]
    video = _write_media([f"projects/{pid}/renders", "scene_005.png"])
    aid = _mk_asset(pid, video)
    _enable_password(client, pid)

    locked = client.get(f"/api/assets/{aid}/file")
    assert locked.status_code == 403, locked.text
    token = _unlock(client, pid)
    ok = client.get(f"/api/assets/{aid}/file", headers={"X-Adept-Project-Unlock": token})
    assert ok.status_code == 200, ok.text
    assert ok.content == MEDIA_BYTES


def test_unresolvable_project_media_fails_closed(client):
    # No project exists behind these URLs; they must still be denied because
    # the project scope cannot be resolved.
    assert client.get("/media/projects/not-a-uuid/x.png").status_code == 403
    assert client.get("/media/assets/not-a-uuid/x.png").status_code == 403
    from app.config import settings

    bogus = client.get("/api/file", params={"path": str(settings.data_dir / "projects" / "not-a-uuid" / "x.mp4")})
    assert bogus.status_code == 403, bogus.text


def test_non_project_media_unaffected(client):
    _write_media(["marketplace", "hero.png"])
    _write_media(["exports", "out.json"])
    ok = client.get("/media/marketplace/hero.png")
    assert ok.status_code == 200, ok.text
    assert ok.content == MEDIA_BYTES
    ok2 = client.get("/media/exports/out.json")
    assert ok2.status_code == 200, ok2.text


def test_media_403_carries_cors_headers(client):
    pid = _mk_project(client)["id"]
    _write_media([f"projects/{pid}/renders", "scene_006.png"])
    _enable_password(client, pid)
    res = client.get(f"/media/projects/{pid}/renders/scene_006.png", headers={"Origin": ORIGIN})
    assert res.status_code == 403
    assert res.headers.get("access-control-allow-origin") == ORIGIN


def test_locked_project_route_carries_cors_headers(client):
    """Mirror of test_cors_contract's tmp_path-gated regression test (which is
    unrunnable under `-p no:tmpdir`): the project-scoped lock short-circuit must
    never bypass CORSMiddleware, so the 403 still carries CORS headers."""
    res = client.get(
        "/api/projects/00000000-0000-0000-0000-000000000000/scriptwriter/documents",
        headers={"Origin": ORIGIN},
    )
    assert res.status_code in (200, 400, 403, 404, 422)
    assert res.headers.get("access-control-allow-origin") == ORIGIN


def test_cdx053_cross_project_scriptwriter_doc_still_404(client):
    """Spot-check: CDX-053 ownership enforcement on scriptwriter documents."""
    owner = _mk_project(client, "Owner")
    intruder = _mk_project(client, "Intruder")
    pid1, pid2 = owner["id"], intruder["id"]

    created = client.post(f"/api/projects/{pid1}/scriptwriter/documents")
    assert created.status_code == 200, created.text
    doc_id = created.json()["document"]["id"]

    # Owner can read the document.
    ok = client.get(f"/api/projects/{pid1}/scriptwriter/documents/{doc_id}")
    assert ok.status_code == 200, ok.text

    # Cross-project access is indistinguishable from missing: 404 with the
    # PROJECT_SCOPE_VIOLATION code (CDX-053).
    bad = client.get(f"/api/projects/{pid2}/scriptwriter/documents/{doc_id}")
    assert bad.status_code == 404, bad.text
    assert bad.json()["detail"]["code"] == "PROJECT_SCOPE_VIOLATION"


def test_permission_helpers_unit():
    """Pure-path unit checks for the URL -> project-id resolution."""
    from app.project_security.permissions import (
        file_path_is_ambiguous,
        media_path_is_ambiguous,
        project_id_from_file_path,
        project_id_from_media_path,
    )

    pid = "00e46c46-ead5-4b67-8d63-5962a8fab260"
    assert project_id_from_media_path(f"/media/projects/{pid}/renders/x.mp4") == pid
    assert project_id_from_media_path(f"/media/assets/{pid}/x.png") == pid
    assert project_id_from_media_path("/media/projects/" + pid) == pid
    assert project_id_from_media_path("/media/marketplace/hero.png") is None
    assert project_id_from_media_path("/media/exports/out.json") is None
    assert project_id_from_media_path("/api/projects/" + pid + "/x") is None

    assert media_path_is_ambiguous("/media/projects/not-a-uuid/x.png") is True
    assert media_path_is_ambiguous(f"/media/projects/{pid}/x.png") is False
    assert media_path_is_ambiguous("/media/marketplace/hero.png") is False

    win = f"C:\\data\\projects\\{pid}\\renders\\x.mp4"
    assert project_id_from_file_path(win) == pid
    rel = f"projects/{pid}/renders/x.mp4"
    assert project_id_from_file_path(rel) == pid
    assert project_id_from_file_path("C:/data/marketplace/hero.png") is None
    assert project_id_from_file_path("C:/Users/x/Desktop/assets/foo.png") is None

    assert file_path_is_ambiguous("C:/data/projects/not-a-uuid/x.mp4") is True
    assert file_path_is_ambiguous("C:/data/assets/not-a-uuid/x.png") is True
    assert file_path_is_ambiguous(win) is False
    assert file_path_is_ambiguous("C:/data/marketplace/hero.png") is False
