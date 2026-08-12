#!/usr/bin/env python3
"""Isolated Qwen Voice Design / Clone smoke (M3.3i). Writes evidence under artifacts/m33/.../real-local-smoke/."""

from __future__ import annotations

import json
import sys
import wave
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio-api"))

from app.codirector.m210b.qwen_voice_install import runtime_ready  # noqa: E402
from app.codirector.m210b.schemas import AudioGenerateRequest  # noqa: E402
from app.codirector.m210b import registry as m210b_registry  # noqa: E402

OUT = ROOT / "artifacts" / "m33" / "character-profile" / "real-local-smoke"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _wav_info(path: Path) -> dict:
    info = {"path": str(path), "exists": path.is_file(), "size": path.stat().st_size if path.is_file() else 0}
    if not path.is_file():
        return info
    try:
        with wave.open(str(path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            info.update(
                {
                    "channels": wf.getnchannels(),
                    "sampleRate": rate,
                    "durationSec": frames / float(rate or 1),
                    "decodable": True,
                }
            )
    except Exception as exc:
        info["decodable"] = False
        info["error"] = str(exc)
    return info


def _non_silent(path: Path, min_rms: float = 50.0) -> bool:
    try:
        import numpy as np
        import soundfile as sf

        data, _ = sf.read(str(path))
        arr = np.asarray(data, dtype=float)
        if arr.ndim > 1:
            arr = arr.mean(axis=1)
        rms = float(np.sqrt(np.mean(np.square(arr)))) if arr.size else 0.0
        return rms * 32768.0 > min_rms if abs(arr).max() <= 1.0 else rms > min_rms
    except Exception:
        return path.is_file() and path.stat().st_size > 2000


def smoke_design() -> dict:
    ready, detail = runtime_ready("qwen_voice_design_17b")
    result = {"kind": "voice_design", "startedAt": _now(), "readiness": detail}
    if not ready:
        result.update({"ok": False, "error": "MODEL_NOT_INSTALLED"})
        return result
    adapter = m210b_registry.get_adapter("m2101-voice-design-021")
    assert adapter
    req = AudioGenerateRequest(
        capabilityId="audio.character_voice.design",
        projectId="m33i-smoke",
        prompt="We should leave before the storm reaches the valley.",
        format="wav",
        kind="dialogue",
        registryId="m2101-voice-design-021",
    )
    setattr(
        req,
        "voiceDescription",
        "Warm adult female voice with gentle authority, clear articulation, "
        "moderate pace, soft breath, calm confidence, and subtle emotional depth.",
    )
    gen = adapter.generate(req)
    payload = gen.to_dict() if hasattr(gen, "to_dict") else {}
    out = Path(str(payload.get("assetPath") or payload.get("path") or ""))
    dest = OUT / "design_smoke.wav"
    if out.is_file():
        dest.write_bytes(out.read_bytes())
    info = _wav_info(dest)
    result.update(
        {
            "ok": bool(info.get("decodable") and _non_silent(dest)),
            "wav": info,
            "nonSilent": _non_silent(dest),
            "lineage": payload,
            "finishedAt": _now(),
        }
    )
    return result


def smoke_clone() -> dict:
    ready, detail = runtime_ready("qwen_voice_clone_17b")
    result = {"kind": "voice_clone", "startedAt": _now(), "readiness": detail}
    if not ready:
        result.update({"ok": False, "error": "MODEL_NOT_INSTALLED"})
        return result
    # Build a disposable ≥10s reference from design smoke or synthesize tone burst via design adapter
    ref = OUT / "clone_reference.wav"
    if not ref.is_file() or ref.stat().st_size < 1000:
        design_ready, _ = runtime_ready("qwen_voice_design_17b")
        if design_ready:
            adapter_d = m210b_registry.get_adapter("m2101-voice-design-021")
            assert adapter_d
            req = AudioGenerateRequest(
                capabilityId="audio.character_voice.design",
                projectId="m33i-smoke",
                prompt=(
                    "This is a disposable certification reference. "
                    "Speak clearly for more than ten seconds about walking through a quiet forest at dawn, "
                    "noticing birds, light through the trees, and the sound of water nearby."
                ),
                format="wav",
                kind="dialogue",
                registryId="m2101-voice-design-021",
            )
            setattr(req, "voiceDescription", "Clear adult female narrator, moderate pace.")
            gen = adapter_d.generate(req)
            payload = gen.to_dict() if hasattr(gen, "to_dict") else {}
            src = Path(str(payload.get("assetPath") or payload.get("path") or ""))
            if src.is_file():
                ref.write_bytes(src.read_bytes())
    if not ref.is_file():
        result.update({"ok": False, "error": "NO_REFERENCE"})
        return result

    adapter = m210b_registry.get_adapter("m2101-voice-clone-022")
    assert adapter
    new_text = "Wait. Someone is still inside that building."
    req = AudioGenerateRequest(
        capabilityId="audio.character_voice.clone",
        projectId="m33i-smoke",
        prompt=new_text,
        format="wav",
        kind="dialogue",
        registryId="m2101-voice-clone-022",
    )
    setattr(req, "referenceAudioPath", str(ref))
    setattr(req, "referenceTranscript", "disposable certification reference speech")
    gen = adapter.generate(req)
    payload = gen.to_dict() if hasattr(gen, "to_dict") else {}
    out = Path(str(payload.get("assetPath") or payload.get("path") or ""))
    dest = OUT / "clone_new_text_smoke.wav"
    if out.is_file():
        dest.write_bytes(out.read_bytes())
    info = _wav_info(dest)
    # Not a byte-identical replay of the reference
    same_as_ref = ref.is_file() and dest.is_file() and ref.read_bytes() == dest.read_bytes()
    result.update(
        {
            "ok": bool(info.get("decodable") and _non_silent(dest) and not same_as_ref),
            "wav": info,
            "nonSilent": _non_silent(dest),
            "notReplayOfReference": not same_as_ref,
            "newText": new_text,
            "reference": _wav_info(ref),
            "consentRequired": True,
            "lineage": payload,
            "finishedAt": _now(),
        }
    )
    return result


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    design = smoke_design()
    (OUT / "design-smoke.json").write_text(json.dumps(design, indent=2), encoding="utf-8")
    clone = smoke_clone()
    (OUT / "clone-smoke.json").write_text(json.dumps(clone, indent=2), encoding="utf-8")
    summary = {
        "ok": bool(design.get("ok") and clone.get("ok")),
        "designOk": design.get("ok"),
        "cloneOk": clone.get("ok"),
        "finishedAt": _now(),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if summary["ok"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
