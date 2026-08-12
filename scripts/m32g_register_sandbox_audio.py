"""Copy sandbox music/SFX into project library assets and refresh Editor clips."""
from __future__ import annotations

import json
import shutil
import uuid
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8758"
PID = "d1683511-1cc7-4d3d-8cb7-00f48cc36aa9"
MUSIC = Path(r"C:\AdeptFilmWorks\AIVideoStudio\data\m210b-sandbox\providers\m2101-music-045\output\ace_step_f2c1b2135f.wav")
SFX = Path(r"C:\AdeptFilmWorks\AIVideoStudio\data\m210b-sandbox\providers\m2101-sfx-031\output\mmaudio_f3d98fb93b.wav")
OUT = Path("artifacts/m32g/hitchhiker-test-2/09-music")


def call(method: str, url: str, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if body is not None else {},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def upload(path: Path, kind: str, tag: str) -> dict:
    boundary = f"----m32g{uuid.uuid4().hex}"
    body = b""
    for name, value in (("kind", kind), ("tag", tag)):
        body += f"--{boundary}\r\n".encode()
        body += f'Content-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
    body += f"--{boundary}\r\n".encode()
    body += f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'.encode()
    body += b"Content-Type: audio/wav\r\n\r\n"
    body += path.read_bytes()
    body += f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"{API}/api/projects/{PID}/assets",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    music = upload(MUSIC, "audio", "test2_music")
    sfx = upload(SFX, "audio", "test2_sfx")
    editor = call("GET", f"{API}/api/projects/{PID}/editor")
    data = editor.get("data") or editor
    tracks = data.setdefault("tracks", {})
    tracks["music"] = [
        {
            "id": f"music-{music['id'][:8]}",
            "asset_id": music["id"],
            "start": 0.0,
            "length": 8.0,
            "label": "Test2 music",
            "gain": 0.35,
        }
    ]
    tracks["sfx"] = [
        {
            "id": f"sfx-{sfx['id'][:8]}",
            "asset_id": sfx["id"],
            "start": 1.2,
            "length": 2.5,
            "label": "Test2 passing vehicle",
            "gain": 0.55,
        }
    ]
    data["tracks"] = tracks
    saved = call("PUT", f"{API}/api/projects/{PID}/editor", data)
    result = {"music": music, "sfx": sfx, "editorTracks": {k: len(v or []) for k, v in (saved.get("data") or saved).get("tracks", {}).items()}}
    OUT.joinpath("registered-library-audio.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"musicId": music["id"], "sfxId": sfx["id"]}, indent=2))


if __name__ == "__main__":
    main()
