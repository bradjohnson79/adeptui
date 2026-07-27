"""M3.0 Completion Phases 9-10: drive the twelve production situations, fixtures OFF.

Two stages, deliberately separated so ComfyUI and Ollama never contend for the same VRAM:

  --stage production   project -> discovery -> storyteller -> approval -> sound concept ->
                       real audio import onto the Director timeline -> real local ImageGen ->
                       approval-gated timeline apply -> reused fal artifact -> export
  --stage intelligence M2.11 orchestration against the live Co-Director provider

No fal job is ever submitted: the only fal artifact used is the one M3.0a already paid for,
copied in by `scripts/m30_register_fal_artifact.py`. No key is read, printed, or logged here.

Results are written per situation so a partial run is still usable evidence.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
import re
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request
import wave
from io import BytesIO
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "artifacts" / "m30-situations"
API = os.environ.get("M30_SIT_API", "http://127.0.0.1:8760")

# The five Phase 9 core situations, plus the seven Phase 10 matrix situations.
CORE = (1, 3, 4, 11, 12)

SITUATIONS = [
    {
        "n": 1,
        "name": "Live-action dramatic",
        "brief": "A father and daughter finally speak after ten years of silence.",
        "shot": (
            "cinematic medium two-shot, an older father and his adult daughter at a kitchen "
            "table at dusk, window light, 35mm, film grain, held silence"
        ),
        "audio": {"kind": "music", "style": "sustained_low", "seconds": 4.0, "bpm": 60},
    },
    {
        "n": 2,
        "name": "Suspense/thriller",
        "brief": "A locksmith realises the apartment he was hired to open is his own.",
        "shot": (
            "tense wide shot of a dim apartment hallway, a locksmith kneeling at a door, "
            "long take framing, hard practical light, anamorphic, 35mm"
        ),
        "audio": {"kind": "ambience", "style": "drone", "seconds": 4.0, "bpm": 0},
    },
    {
        "n": 3,
        "name": "Music video",
        "brief": "A dancer moves through four seasons in one continuous take.",
        "shot": (
            "stylised wide shot of a dancer mid-turn in a field, seasons blending, "
            "motion blur, saturated colour, continuous camera move, 24mm"
        ),
        "audio": {"kind": "music", "style": "click", "seconds": 8.0, "bpm": 120},
    },
    {
        "n": 4,
        "name": "Animated",
        "brief": "A paper crane learns it can carry messages it cannot read.",
        "shot": (
            "non-photoreal illustrated frame, a folded paper crane on a windowsill, "
            "flat shading, painterly texture, soft rim light"
        ),
        "audio": {"kind": "music", "style": "sustained_low", "seconds": 4.0, "bpm": 90},
    },
    {
        "n": 5,
        "name": "Commercial",
        "brief": "Thirty seconds for a coffee brand built on the first sip.",
        "shot": (
            "product hero shot of a ceramic coffee cup on a marble counter, steam, "
            "brand-safe clean framing, macro detail, soft key light"
        ),
        "audio": {"kind": "music", "style": "click", "seconds": 4.0, "bpm": 110},
    },
    {
        "n": 6,
        "name": "Dialogue-heavy two-person",
        "brief": "Two negotiators discover they want the same outcome.",
        "shot": (
            "medium two-shot across a boardroom table, two negotiators, eyeline match, "
            "50mm, even key light, shallow depth"
        ),
        "audio": {"kind": "dialogue", "style": "speech_bed", "seconds": 4.0, "bpm": 0},
    },
    {
        "n": 7,
        "name": "Action/chase",
        "brief": "A courier outruns a drone through a night market.",
        "shot": (
            "kinetic low-angle shot of a courier sprinting through a neon night market, "
            "motion blur, rain sheen, handheld energy, 24mm"
        ),
        "audio": {"kind": "sfx", "style": "impact", "seconds": 3.0, "bpm": 0},
    },
    {
        "n": 8,
        "name": "Fantasy/sci-fi",
        "brief": "A cartographer maps a city that rearranges itself nightly.",
        "shot": (
            "epic wide establishing shot of an impossible city rearranging at night, "
            "vast scale, volumetric light, matte painting detail"
        ),
        "audio": {"kind": "ambience", "style": "drone", "seconds": 4.0, "bpm": 0},
    },
    {
        "n": 9,
        "name": "Documentary/interview",
        "brief": "A retired ferry captain describes the crossing he never finished.",
        "shot": (
            "static long-lens interview framing, a retired ferry captain seated by a window, "
            "natural light, documentary realism, 85mm"
        ),
        "audio": {"kind": "ambience", "style": "room_tone", "seconds": 4.0, "bpm": 0},
    },
    {
        "n": 10,
        "name": "Stylized 2D/anime",
        "brief": "A student duels her own shadow on a rooftop at dusk.",
        "shot": (
            "anime style key frame, a student facing her own shadow on a rooftop at dusk, "
            "flat cel shading, bold line art, dramatic sky"
        ),
        "audio": {"kind": "music", "style": "click", "seconds": 4.0, "bpm": 128},
    },
    {
        "n": 11,
        "name": "Product/location reconstruction",
        "brief": "Rebuild a 1970s diner from three reference photographs.",
        "shot": (
            "reference-faithful interior of a 1970s American diner, chrome stools, "
            "formica counter, warm tungsten light, wide angle, geometric accuracy"
        ),
        "audio": {"kind": "ambience", "style": "room_tone", "seconds": 4.0, "bpm": 0},
    },
    {
        "n": 12,
        "name": "Full short-form capstone",
        "brief": "A three-minute short: the crane, the diner, and the crossing.",
        "shot": (
            "opening frame of a short film, a paper crane on a diner counter at dawn, "
            "cinematic composition, 35mm, warm light"
        ),
        "audio": {"kind": "music", "style": "sustained_low", "seconds": 6.0, "bpm": 84},
    },
]

# Situations that receive the already-paid-for fal Seedance artifact as their motion handoff.
FAL_REUSE = (1, 3, 4, 11, 12)

UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{32}", re.I
)


def call(method, path, body=None, timeout=1800):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        API + path, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return {
                "status": resp.status,
                "payload": json.loads(raw) if raw else None,
                "seconds": round(time.time() - t0, 3),
            }
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"raw": raw[:600]}
        return {"status": exc.code, "payload": payload, "seconds": round(time.time() - t0, 3)}
    except Exception as exc:
        return {"status": 0, "payload": {"error": str(exc)[:300]}, "seconds": round(time.time() - t0, 3)}


def fetch_bytes(path, limit=64):
    req = urllib.request.Request(API + path)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
            return {
                "status": resp.status,
                "contentType": resp.headers.get("content-type"),
                "bytes": len(data),
                "magic": data[:limit].hex()[:32],
                "sha256": hashlib.sha256(data).hexdigest(),
            }
    except urllib.error.HTTPError as exc:
        return {"status": exc.code, "error": exc.reason}
    except Exception as exc:
        return {"status": 0, "error": str(exc)[:200]}


def make_wav(style, seconds, bpm):
    """Real PCM WAV bytes, synthesised locally with the stdlib. Not model-generated."""
    rate = 44100
    total = int(rate * seconds)
    buf = BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        frames = bytearray()
        for n in range(total):
            t = n / float(rate)
            if style == "click" and bpm:
                phase = (t * bpm / 60.0) % 1.0
                env = math.exp(-18.0 * phase)
                val = 12000 * env * math.sin(2 * math.pi * 660.0 * t)
            elif style == "sustained_low":
                env = min(1.0, t / 0.6) * min(1.0, max(0.0, (seconds - t) / 0.6))
                val = 6000 * env * (
                    math.sin(2 * math.pi * 110.0 * t) + 0.5 * math.sin(2 * math.pi * 165.0 * t)
                )
            elif style == "drone":
                val = 4500 * (
                    math.sin(2 * math.pi * 73.0 * t) + 0.4 * math.sin(2 * math.pi * 146.5 * t)
                )
            elif style == "room_tone":
                val = 900 * math.sin(2 * math.pi * 50.0 * t) + 600 * math.sin(
                    2 * math.pi * 317.0 * t
                )
            elif style == "impact":
                env = math.exp(-6.0 * t)
                val = 15000 * env * math.sin(2 * math.pi * (90.0 + 400.0 * env) * t)
            else:  # speech_bed
                env = 0.5 + 0.5 * math.sin(2 * math.pi * 4.0 * t)
                val = 7000 * env * math.sin(2 * math.pi * 210.0 * t)
            frames += struct.pack("<h", max(-32768, min(32767, int(val))))
        wav.writeframes(bytes(frames))
    return buf.getvalue()


def poll_exec_job(job_id, project_id, timeout=420, interval=3):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        res = call("GET", "/api/codirector/jobs/" + job_id + "?projectId=" + project_id)
        body = res.get("payload") or {}
        last = body.get("job") or body
        status = str((last or {}).get("status") or "").lower()
        if status and status not in ("queued", "running", "pending", "inprogress"):
            return last
        time.sleep(interval)
    return last


def poll_studio_job(job_id, timeout=900, interval=10):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        res = call("GET", "/api/jobs/" + job_id)
        last = res.get("payload")
        status = str((last or {}).get("status") or "").lower()
        if status in ("done", "failed", "cancelled"):
            return last
        time.sleep(interval)
    return last


def register_fal_artifact(project_id):
    """Reuse the M3.0a artifact. Never submits a job; the script refuses on digest mismatch."""
    env = dict(os.environ)
    env.setdefault("STUDIO_DATA_DIR", os.environ.get("STUDIO_DATA_DIR", ""))
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "m30_register_fal_artifact.py"),
         "--project-id", project_id],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=env,
    )
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip().splitlines(),
        "stderr": proc.stderr.strip().splitlines()[-3:],
    }


def normalised_digest(payload):
    text = json.dumps(payload, sort_keys=True, default=str)
    text = UUID_RE.sub("<id>", text)
    text = re.sub(r"\d{4}-\d{2}-\d{2}T[\d:.]+", "<ts>", text)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def run_production(sit):
    n = sit["n"]
    rec = {"n": n, "situation": sit["name"], "brief": sit["brief"], "steps": {}, "notes": []}
    step = rec["steps"]

    res = call("POST", "/api/projects", {"name": "M3.0 S%d %s" % (n, sit["name"])})
    step["project"] = {"status": res["status"], "id": (res["payload"] or {}).get("id")}
    pid = (res["payload"] or {}).get("id")
    rec["projectId"] = pid
    if not pid:
        rec["fatal"] = "project creation failed"
        return rec

    res = call(
        "POST",
        "/api/projects/%s/scenes" % pid,
        {"name": sit["name"], "prompt": sit["brief"], "duration_sec": 8},
    )
    sid = (res["payload"] or {}).get("id")
    rec["sceneId"] = sid
    step["scene"] = {"status": res["status"], "id": sid}

    res = call("POST", "/api/codirector/m214/idea", {"projectId": pid, "idea": sit["brief"]})
    step["m214_idea"] = {
        "status": res["status"],
        "honesty": (res["payload"] or {}).get("honesty"),
        "questions": len((res["payload"] or {}).get("questions") or []),
    }

    res = call(
        "POST",
        "/api/codirector/m214/storyteller/analyze",
        {"projectId": pid, "sceneId": sid, "idea": sit["brief"]},
    )
    story = res["payload"] or {}
    step["storyteller"] = {
        "status": res["status"],
        "profileId": story.get("id"),
        "emotionalArc": story.get("emotional_arc"),
        "tone": story.get("tone"),
        "stakes": story.get("stakes"),
        "subtext": story.get("subtext"),
        "honesty": story.get("honesty"),
        "approved": story.get("approved"),
    }

    res = call(
        "POST",
        "/api/codirector/m214/storyteller/handoff",
        {
            "projectId": pid,
            "profileId": story.get("id"),
            "sceneId": sid,
            "directionSummary": sit["brief"],
        },
    )
    handoff = res["payload"] or {}
    step["handoff"] = {
        "status": res["status"],
        "id": handoff.get("id"),
        "approvedBeforeGate": handoff.get("approved"),
    }
    res = call("POST", "/api/codirector/m214/storyteller/handoff/%s/approve" % handoff.get("id"))
    step["handoff_approve"] = {
        "status": res["status"],
        "approved": (res["payload"] or {}).get("approved"),
    }

    res = call(
        "POST",
        "/api/codirector/m214/sound/concept",
        {"projectId": pid, "sceneId": sid, "emotionalArc": story.get("emotional_arc") or ""},
    )
    sonic = res["payload"] or {}
    step["sound_concept"] = {
        "status": res["status"],
        "id": sonic.get("id"),
        "honesty": sonic.get("honesty"),
        "approvedBeforeGate": sonic.get("approved"),
    }
    res = call("POST", "/api/codirector/m214/sound/concept/%s/approve" % sonic.get("id"))
    step["sound_approve"] = {
        "status": res["status"],
        "approved": (res["payload"] or {}).get("approved"),
    }

    # Generative audio: expected to be provider-missing. Recorded, never faked.
    res = call(
        "POST",
        "/api/codirector/m29/audio/generate",
        {
            "projectId": pid,
            "sceneId": sid,
            "kind": sit["audio"]["kind"],
            "prompt": sit["brief"],
            "durationSec": sit["audio"]["seconds"],
        },
    )
    gen_audio = res["payload"] or {}
    step["audio_generate"] = {
        "status": res["status"],
        "providerMissing": gen_audio.get("providerMissing"),
        "awaitingProvider": gen_audio.get("awaitingProvider"),
        "assetId": gen_audio.get("assetId"),
        "cueStatus": gen_audio.get("status"),
        "timelinePlaced": gen_audio.get("timelinePlaced"),
    }

    # Real audio bytes on the Director timeline (blocker B4 path).
    wav = make_wav(sit["audio"]["style"], sit["audio"]["seconds"], sit["audio"]["bpm"])
    res = call(
        "POST",
        "/api/codirector/m29/audio/import",
        {
            "projectId": pid,
            "contentBase64": base64.b64encode(wav).decode("ascii"),
            "filename": "s%02d_%s.wav" % (n, sit["audio"]["style"]),
            "kind": sit["audio"]["kind"],
            "sceneId": sid,
            "startSec": 0.0,
            "tag": "m30-situation-audio",
        },
    )
    imported = res["payload"] or {}
    step["audio_import"] = {
        "status": res["status"],
        "assetId": imported.get("assetId"),
        "cueId": imported.get("cueId"),
        "timelinePlaced": imported.get("timelinePlaced"),
        "measuredDurationSec": imported.get("measuredDurationSec"),
        "bytes": imported.get("bytes"),
        "sha256": imported.get("sha256"),
        "provider": imported.get("provider"),
    }
    audio_asset = imported.get("assetId")

    # Real still image through the local ComfyUI provider.
    res = call(
        "POST",
        "/api/codirector/m29/image/generate",
        {
            "projectId": pid,
            "sceneId": sid,
            "prompt": sit["shot"],
            "width": 1024,
            "height": 1024,
        },
    )
    queued = res["payload"] or {}
    step["image_generate_queued"] = {
        "status": res["status"],
        "assetId": queued.get("assetId"),
        "versionId": queued.get("versionId"),
        "jobStatus": queued.get("status"),
        "providerMissing": queued.get("providerMissing"),
        "fixture": queued.get("fixture"),
    }
    image_asset = None
    if queued.get("jobId"):
        t0 = time.time()
        job = poll_exec_job(queued["jobId"], pid)
        result = (job or {}).get("result") or {}
        image_asset = result.get("assetId")
        step["image_job"] = {
            "jobId": queued["jobId"],
            "status": (job or {}).get("status"),
            "provider": result.get("provider"),
            "mockAdapter": result.get("mockAdapter"),
            "assetId": image_asset,
            "imageJobId": result.get("imageJobId"),
            "error": (job or {}).get("errorMessage"),
            "seconds": round(time.time() - t0, 1),
        }
    rec["imageAssetId"] = image_asset

    if image_asset:
        step["image_file"] = fetch_bytes("/api/assets/%s/file" % image_asset)
        res = call("GET", "/api/assets/%s/graph" % image_asset)
        graph = res["payload"] or {}
        step["image_graph"] = {
            "status": res["status"],
            "versions": len(graph.get("versions") or []),
            "asset": (graph.get("asset") or {}).get("id"),
            "tag": (graph.get("asset") or {}).get("tag"),
        }
        call("PATCH", "/api/projects/%s/scenes/%s" % (pid, sid), {"start_asset_id": image_asset})

    # Video department through its own endpoint (image_to_video is the only local/fal mode).
    res = call(
        "POST",
        "/api/codirector/m29/video/generate",
        {
            "projectId": pid,
            "sceneId": sid,
            "prompt": sit["shot"],
            "mode": "image_to_video",
            "firstFrameAssetId": image_asset,
            "durationSec": 4,
        },
    )
    vqueued = res["payload"] or {}
    step["video_generate_queued"] = {
        "status": res["status"],
        "providerMissing": vqueued.get("providerMissing"),
        "assetId": vqueued.get("assetId"),
    }
    if vqueued.get("jobId"):
        vjob = poll_exec_job(vqueued["jobId"], pid, timeout=120, interval=2)
        step["video_job"] = {
            "status": (vjob or {}).get("status"),
            "error": str((vjob or {}).get("errorMessage") or "").splitlines()[:1],
            "assetId": ((vjob or {}).get("result") or {}).get("assetId"),
        }

    # Reused fal artifact (already paid for in M3.0a) as the motion handoff.
    if n in FAL_REUSE:
        step["fal_reuse"] = register_fal_artifact(pid)

    # Approval-gated timeline write: apply must be refused before approval.
    clips = []
    if image_asset:
        clips.append(
            {"clipId": "s%02d-img" % n, "assetId": image_asset, "start": 0, "length": 4,
             "track": "image", "label": "key frame"}
        )
    res = call(
        "POST",
        "/api/codirector/m29/timeline/propose",
        {"projectId": pid, "sceneId": sid, "clips": clips, "notes": sit["name"]},
    )
    proposal = res["payload"] or {}
    step["timeline_propose"] = {"status": res["status"], "id": proposal.get("id"),
                                "proposalStatus": proposal.get("status")}
    if proposal.get("id"):
        res = call("POST", "/api/codirector/m29/timeline/%s/apply" % proposal["id"], {})
        step["timeline_apply_before_approval"] = {
            "status": res["status"],
            "detail": str((res["payload"] or {}).get("detail"))[:120],
        }
        res = call("POST", "/api/codirector/m29/timeline/%s/approve" % proposal["id"], {})
        step["timeline_approve"] = {"status": res["status"],
                                    "proposalStatus": (res["payload"] or {}).get("status")}
        res = call("POST", "/api/codirector/m29/timeline/%s/apply" % proposal["id"], {})
        step["timeline_apply"] = {"status": res["status"],
                                  "proposalStatus": (res["payload"] or {}).get("status"),
                                  "appliedSceneId": (res["payload"] or {}).get("appliedSceneId")}

    res = call("GET", "/api/projects/%s/scenes/%s/director" % (pid, sid))
    director = res["payload"] or {}
    step["director_timeline"] = {
        "status": res["status"],
        "audio_clips": len(director.get("audio_clips") or []),
        "sfx_clips": len(director.get("sfx_clips") or []),
        "image_clips": len(director.get("image_clips") or []),
        "video_clips": len(director.get("video_clips") or []),
        "audio_asset_ids": [c.get("asset_id") for c in (director.get("audio_clips") or [])],
        "image_asset_ids": [c.get("asset_id") for c in (director.get("image_clips") or [])],
    }

    res = call("GET", "/api/codirector/m29/audio/cues?projectId=%s" % pid)
    cues = res["payload"] or {}
    cue_rows = cues.get("cues") if isinstance(cues, dict) else cues
    step["audio_cues"] = {"status": res["status"], "count": len(cue_rows or [])}

    res = call("GET", "/api/projects/%s/library?scope=project" % pid)
    lib = res["payload"] or []
    step["library"] = {
        "status": res["status"],
        "count": len(lib),
        "kinds": sorted({a.get("kind") for a in lib}),
        "tags": sorted({a.get("tag") for a in lib}),
    }
    rec["assetCount"] = len(lib)

    res = call("GET", "/api/codirector/m214/plan/%s" % pid)
    plan = res["payload"] or {}
    step["plan"] = {
        "status": res["status"],
        "honesty": plan.get("honesty"),
        "stages": len(plan.get("stages") or []),
    }

    res = call("POST", "/api/projects/%s/export" % pid, None)
    export_job = res["payload"] or {}
    step["export_queued"] = {"status": res["status"], "jobId": export_job.get("id")}
    if export_job.get("id"):
        done = poll_studio_job(export_job["id"], timeout=240, interval=5)
        step["export_job"] = {
            "status": (done or {}).get("status"),
            "message": str((done or {}).get("message") or "").splitlines()[:1],
            "output_path": (done or {}).get("output_path"),
        }

    # Situation 1 also probes the two local video engines directly, once, for the record.
    if n == 1:
        local = {}
        for engine in ("ltx", "wan"):
            call("PATCH", "/api/projects/%s/scenes/%s" % (pid, sid),
                 {"engine": engine, "duration_sec": 3.0})
            res = call("POST", "/api/projects/%s/render" % pid,
                       {"kind": "scene", "scene_id": sid})
            job_id = (res["payload"] or {}).get("id")
            done = poll_studio_job(job_id, timeout=900, interval=10) if job_id else None
            msg = str((done or {}).get("message") or "")
            local[engine] = {
                "status": (done or {}).get("status"),
                "output_path": (done or {}).get("output_path"),
                "failure": msg[:400],
            }
        step["local_video_render"] = local

    return rec


def run_intelligence(sit, state, model_id):
    n = sit["n"]
    pid = state.get("projectId")
    sid = state.get("sceneId")
    rec = {"n": n, "situation": sit["name"], "projectId": pid, "sceneId": sid}
    if not pid:
        rec["skipped"] = "no project from the production stage"
        return rec

    t0 = time.time()
    res = call(
        "POST",
        "/api/codirector/m211/orchestrate",
        {"projectId": pid, "brief": sit["brief"], "sceneId": sid, "modelUsed": model_id},
        timeout=3600,
    )
    orch = res["payload"] or {}
    specialists = orch.get("specialists") or []
    rec.update(
        {
            "status": res["status"],
            "seconds": round(time.time() - t0, 1),
            "modelUsed": model_id,
            "analysisMode": orch.get("analysisMode"),
            "honesty": orch.get("honesty"),
            "useProvider": orch.get("useProvider"),
            "runStatus": orch.get("status"),
            "specialistCount": len(specialists),
            "specialistIds": [s.get("specialistId") for s in specialists],
            "modelIds": sorted({str(s.get("modelId")) for s in specialists}),
            "summaries": [s.get("summary") for s in specialists],
            "recommendations": [s.get("recommendation") for s in specialists],
            "substantive": sum(
                1
                for s in specialists
                if len(str(s.get("recommendation") or "")) > 40 or s.get("requirements")
            ),
            "failures": (orch.get("trace") or {}).get("failures"),
            "durations": (orch.get("trace") or {}).get("durations"),
            "conflictCount": (orch.get("conflicts") or {}).get("count"),
            "pendingApprovals": len(orch.get("pendingApprovals") or []),
            "missingAssets": orch.get("missingAssets"),
            "enriched": orch.get("enriched"),
        }
    )
    rec["analysisDigest"] = normalised_digest(
        {
            "specialists": specialists,
            "shotPlan": orch.get("shotPlan"),
            "camera": orch.get("camera"),
            "music": orch.get("music"),
            "sfx": orch.get("sfx"),
            "editingBeats": orch.get("editingBeats"),
            "continuity": orch.get("continuity"),
        }
    )
    decisions = orch.get("decisions") or []
    rec["decisionCount"] = len(decisions)
    if decisions:
        did = decisions[0].get("id")
        approve = call(
            "POST",
            "/api/codirector/m211/decisions/%s/approve" % did,
            {"projectId": pid, "status": "approved"},
        )
        rec["decisionApprove"] = {
            "status": approve["status"],
            "approvalStatus": (approve["payload"] or {}).get("approvalStatus")
            or (approve["payload"] or {}).get("approval_status"),
        }
    return rec


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("production", "intelligence"), required=True)
    parser.add_argument("--only", default="", help="comma separated situation numbers")
    parser.add_argument("--model", default="", help="model id for the intelligence stage")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    wanted = (
        {int(x) for x in args.only.split(",") if x.strip()}
        if args.only
        else {s["n"] for s in SITUATIONS}
    )

    if args.stage == "production":
        for sit in SITUATIONS:
            if sit["n"] not in wanted:
                continue
            t0 = time.time()
            rec = run_production(sit)
            rec["wallSeconds"] = round(time.time() - t0, 1)
            path = OUT_DIR / ("situation-%02d-production.json" % sit["n"])
            path.write_text(json.dumps(rec, indent=1), encoding="utf-8")
            print(
                "[S%02d] %-32s project=%s image=%s assets=%s %.1fs"
                % (
                    sit["n"],
                    sit["name"],
                    str(rec.get("projectId"))[:8],
                    str(rec.get("imageAssetId"))[:8],
                    rec.get("assetCount"),
                    rec["wallSeconds"],
                ),
                flush=True,
            )
        return 0

    model_id = args.model
    if not model_id:
        health = call("GET", "/api/health")["payload"] or {}
        model_id = ((health.get("operator") or {}).get("provider") or {}).get("selectedModel") or ""
    print("intelligence stage model:", model_id, flush=True)
    for sit in SITUATIONS:
        if sit["n"] not in wanted:
            continue
        prod_path = OUT_DIR / ("situation-%02d-production.json" % sit["n"])
        state = json.loads(prod_path.read_text(encoding="utf-8")) if prod_path.exists() else {}
        rec = run_intelligence(sit, state, model_id)
        path = OUT_DIR / ("situation-%02d-intelligence.json" % sit["n"])
        path.write_text(json.dumps(rec, indent=1), encoding="utf-8")
        print(
            "[S%02d] %-32s %ss specialists=%s substantive=%s digest=%s"
            % (
                sit["n"],
                sit["name"],
                rec.get("seconds"),
                rec.get("specialistCount"),
                rec.get("substantive"),
                rec.get("analysisDigest"),
            ),
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
