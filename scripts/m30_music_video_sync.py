"""Situation 3 follow-up: how far tempo-locked cutting actually gets today.

Places bar-line cues by hand on the Director timeline at 120 BPM and records exactly which
part of that the system did and which part the caller had to compute. Also shows what
`syncEvent` does and does not do.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8760"
OUT = Path(__file__).resolve().parents[1] / "artifacts" / "m30-situations"

BPM = 120.0
BEATS_PER_BAR = 4
BAR_SECONDS = 60.0 / BPM * BEATS_PER_BAR  # 2.0 s


def call(method, path, body=None, timeout=300):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        API + path, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return {"status": resp.status, "payload": json.loads(raw) if raw else None}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"raw": raw[:400]}
        return {"status": exc.code, "payload": payload}


state = json.loads((OUT / "situation-03-production.json").read_text(encoding="utf-8"))
pid = state["projectId"]
sid = state["sceneId"]
audio_asset = state["steps"]["audio_import"]["assetId"]
image_asset = state["imageAssetId"]

rec = {
    "projectId": pid,
    "sceneId": sid,
    "bpm": BPM,
    "barSeconds": BAR_SECONDS,
    "audioAssetId": audio_asset,
    "imageAssetId": image_asset,
    "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}

# 1. Does the placement API accept a tempo or a sync event at all?
rec["placeCueAcceptsSyncEvent"] = call(
    "POST",
    "/api/codirector/m29/audio/place-cue",
    {
        "projectId": pid,
        "sceneId": sid,
        "kind": "sfx",
        "assetId": audio_asset,
        "startSec": 0.5,
        "durationSec": 0.25,
        "syncEvent": "bar-1",
    },
)

# 2. The plan surface does carry syncEvent - check whether validation does anything with it.
rec["planProposeWithSyncEvent"] = call(
    "POST",
    "/api/codirector/m29/audio/plan/propose",
    {
        "projectId": pid,
        "sceneId": sid,
        "music": [
            {"prompt": "four-on-the-floor bed", "startSec": 0.0, "durationSec": 8.0,
             "syncEvent": "downbeat"},
        ],
        "sfx": [
            {"prompt": "transition riser", "startSec": 2.0, "durationSec": 0.5,
             "syncEvent": "bar-2"},
        ],
    },
)

# 3. Bar-line cues the caller computes itself.
placements = []
for bar in range(4):
    start = round(bar * BAR_SECONDS, 3)
    res = call(
        "POST",
        "/api/codirector/m29/audio/place-cue",
        {
            "projectId": pid,
            "sceneId": sid,
            "kind": "sfx",
            "assetId": audio_asset,
            "startSec": start,
            "durationSec": 0.25,
            "volume": 0.8,
        },
    )
    placements.append(
        {
            "bar": bar + 1,
            "startSec": start,
            "status": res["status"],
            "timelinePlaced": (res["payload"] or {}).get("timelinePlaced"),
            "cueId": (res["payload"] or {}).get("cueId"),
        }
    )
rec["barLineCues"] = placements

director = call("GET", "/api/projects/%s/scenes/%s/director" % (pid, sid))
tl = director["payload"] or {}
rec["directorAfter"] = {
    "sfx_clips": [
        {"start": c.get("start"), "length": c.get("length"), "asset_id": c.get("asset_id"),
         "volume": c.get("volume"), "label": c.get("label")}
        for c in (tl.get("sfx_clips") or [])
    ],
    "audio_clips": [
        {"start": c.get("start"), "length": c.get("length"), "asset_id": c.get("asset_id")}
        for c in (tl.get("audio_clips") or [])
    ],
    "image_clips": [
        {"start": c.get("start"), "length": c.get("length"), "asset_id": c.get("asset_id")}
        for c in (tl.get("image_clips") or [])
    ],
}

# 4. Cut the visual on bar lines: four image clips, one per bar, through the approval gate.
clips = [
    {
        "clipId": "s03-bar%d" % (bar + 1),
        "assetId": image_asset,
        "start": round(bar * BAR_SECONDS, 3),
        "length": BAR_SECONDS,
        "track": "image",
        "label": "bar %d" % (bar + 1),
    }
    for bar in range(4)
]
prop = call(
    "POST",
    "/api/codirector/m29/timeline/propose",
    {"projectId": pid, "sceneId": sid, "clips": clips, "notes": "tempo-locked cuts at 120 BPM"},
)
pid_prop = (prop["payload"] or {}).get("id")
rec["tempoCutProposal"] = {"status": prop["status"], "id": pid_prop}
if pid_prop:
    rec["tempoCutApprove"] = call(
        "POST", "/api/codirector/m29/timeline/%s/approve" % pid_prop, {}
    )["status"]
    applied = call("POST", "/api/codirector/m29/timeline/%s/apply" % pid_prop, {})
    rec["tempoCutApply"] = {
        "status": applied["status"],
        "proposalStatus": (applied["payload"] or {}).get("status"),
    }

final = call("GET", "/api/projects/%s/scenes/%s/director" % (pid, sid))["payload"] or {}
rec["imageClipStarts"] = [c.get("start") for c in (final.get("image_clips") or [])]
rec["sfxClipStarts"] = [c.get("start") for c in (final.get("sfx_clips") or [])]

(OUT / "situation-03-music-sync.json").write_text(json.dumps(rec, indent=1), encoding="utf-8")
print(json.dumps(rec, indent=1)[:3000])
