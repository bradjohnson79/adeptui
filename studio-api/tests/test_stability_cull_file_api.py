from pathlib import Path

from app.config import settings
from app.project_security.permissions import SCHNICK_PROJECT_ID


def test_file_api_rejects_non_project_path(client):
    data = Path(settings.data_dir)
    stray = data / "runtime" / "stability-cull-file-api.txt"
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_text("nope", encoding="utf-8")
    res = client.get("/api/file", params={"path": str(stray)})
    assert res.status_code == 403
    assert res.json()["detail"]["error"] == "FILE_API_RESTRICTED"


def test_file_api_rejects_dotdot_traversal(client):
    data = Path(settings.data_dir)
    open_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    locked_id = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    secret = data / "projects" / locked_id / "secret.txt"
    secret.parent.mkdir(parents=True, exist_ok=True)
    secret.write_text("secret", encoding="utf-8")
    (data / "projects" / open_id).mkdir(parents=True, exist_ok=True)
    traversal = str(data / "projects" / open_id / ".." / ".." / "projects" / locked_id / "secret.txt")
    res = client.get("/api/file", params={"path": traversal})
    assert res.status_code == 403
    detail = res.json().get("detail")
    if isinstance(detail, dict):
        assert detail.get("error") == "FILE_API_RESTRICTED" or detail.get("code") == "FILE_API_RESTRICTED"
    else:
        assert "FILE_API_RESTRICTED" in str(detail)


def test_owner_fixture_writes_denied_by_header(client):
    res = client.post(
        f"/api/projects/{SCHNICK_PROJECT_ID}/characters",
        json={"name": "Should Fail"},
        headers={"X-Adept-Deny-Owner-Writes": "1"},
    )
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "OWNER_FIXTURE_WRITE_DENIED"
