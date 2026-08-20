"""Inspect the combined MAGI finishing render and write artifacts/magi-finalization/combined-proof.json."""

from __future__ import annotations

import json
import struct
import subprocess
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "artifacts" / "magi-finalization"
OUT.mkdir(parents=True, exist_ok=True)
API = "http://127.0.0.1:8758"
PROJECT_ID = "61fe0ac2-4cc4-4855-8219-5600aef4057b"
FINAL_ID = "bdf29126-d960-4599-b459-2251f66e4718"
SOURCE_ID = "075f44f2-bf22-4d9d-8e76-32d30494f8c8"
CLIP_ID = "clip_magi_final_1787251554329"


def _get(path: str) -> dict:
    with urllib.request.urlopen(API + path, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _probe(path: Path) -> dict:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return json.loads(proc.stdout or "{}") if proc.returncode == 0 else {"error": proc.stderr[-400:]}


def _wav_stats(path: Path) -> dict:
    with wave.open(str(path), "rb") as handle:
        channels, sampwidth, rate, nframes, *_ = handle.getparams()
        raw = handle.readframes(nframes)
    samples = struct.unpack("<" + "h" * (len(raw) // 2), raw) if sampwidth == 2 else ()
    return {
        "bytes": path.stat().st_size,
        "channels": channels,
        "sampleRate": rate,
        "nframes": nframes,
        "durationSec": round(nframes / rate, 3) if rate else 0,
        "maxabs": max((abs(sample) for sample in samples), default=0),
        "nonzero": sum(1 for sample in samples if sample != 0),
        "nsamples": len(samples),
    }


def main() -> int:
    library = _get(f"/api/projects/{PROJECT_ID}/library")
    items = {item["id"]: item for item in (library.get("items") or [])}
    final = items.get(FINAL_ID) or {}
    final_path = Path(final.get("path") or "")
    source_path = Path(
        r"C:\AdeptFilmWorks\AIVideoStudio\data\assets\61fe0ac2-4cc4-4855-8219-5600aef4057b\075f44f2-bf22-4d9d-8e76-32d30494f8c8.mp4"
    )
    wav = OUT / "final-render-audio.wav"
    if final_path.is_file():
        subprocess.run(["ffmpeg", "-y", "-i", str(final_path), str(wav)], capture_output=True, check=False)
    sequence = _get(f"/api/magi/projects/{PROJECT_ID}/sequence")
    finishing = (sequence.get("sequence") or {}).get("finishing") or {}
    evidence = {
        "projectId": PROJECT_ID,
        "finalAssetId": FINAL_ID,
        "sourceAssetId": SOURCE_ID,
        "finalPath": str(final_path),
        "sourcePath": str(source_path),
        "finalExists": final_path.is_file(),
        "sourceExists": source_path.is_file(),
        "finalSize": final_path.stat().st_size if final_path.is_file() else 0,
        "sourceSize": source_path.stat().st_size if source_path.is_file() else 0,
        "sourceProbe": _probe(source_path) if source_path.is_file() else {},
        "finalProbe": _probe(final_path) if final_path.is_file() else {},
        "audioExtract": _wav_stats(wav) if wav.is_file() else {},
        "promptMeta": json.loads(final.get("prompt_meta_json") or "{}") if final.get("prompt_meta_json") else {},
        "finishingRender": finishing.get("render"),
        "finishingAudio": finishing.get("audio"),
        "gradeForCurrentClip": (finishing.get("clipGrades") or {}).get(CLIP_ID),
        "parentAssetId": final.get("parent_asset_id"),
        "tag": final.get("tag"),
    }
    (OUT / "combined-proof.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps({
        "finalExists": evidence["finalExists"],
        "finalSize": evidence["finalSize"],
        "sourceSize": evidence["sourceSize"],
        "audioExtract": evidence["audioExtract"],
        "finishingRender": evidence["finishingRender"],
        "grade": evidence["gradeForCurrentClip"],
        "upscale": evidence["promptMeta"].get("upscale"),
        "audio": evidence["promptMeta"].get("audio"),
        "gradeMeta": evidence["promptMeta"].get("grade"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
