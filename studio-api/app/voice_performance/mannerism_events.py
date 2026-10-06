"""Local vocal-event layer for Voice Studio mannerism cues.

Architecture:
  IndexTTS2 / QwenEmotion keep spoken dialogue, emotional tone, pacing, speaker identity.
  Discrete mannerisms (sigh, chuckle, gasp, breath, scoff, ...) are separate LOCAL
  vocal-event audio clips, then stitched into ONE final Take WAV.

Audit (reuse decision):
  - IndexTTS2/QwenEmotion: emo_text approximation ONLY — no native non-speech events.
  - Character reaction library: IndexTTS asterisk prompts (*thoughtful sigh*) — same gap.
  - MMAudio: canonical local SFX for foley/ambience — not speaker-conditioned vocal
    mannerisms; warm GPU residency conflicts with IndexTTS2 take generation.
  - Decision: lightweight local DSP vocal-event synthesizer (NOT a second ML audio engine).
    Reuses the same PCM WAV concat pattern as voice_performance.service._concat_wavs.
  - Speaker match honesty: events are level-matched to dialogue when possible.
    They are NOT speaker-cloned / speaker-conditioned. Do not claim speaker-matched sighs.
"""

from __future__ import annotations

import json
import math
import struct
import uuid
import wave
from array import array
from pathlib import Path
from typing import Any, Literal, Optional

MannerismIntensity = Literal["light", "medium", "strong"]
MannerismPosition = Literal["before", "during", "after"]

# Cues that require a discrete audible event (not emo_text alone).
DISCRETE_EVENT_CUES: frozenset[str] = frozenset(
    {
        "sigh",
        "chuckle",
        "laugh",
        "soft_laugh",
        "gasp",
        "breath_in",
        "breath_out",
        "scoff",
        "nervous_breath",
    }
)

# Delivery-only cues: keep emo_text / structural approximation (no separate event required).
DELIVERY_ONLY_CUES: frozenset[str] = frozenset({"whisper", "pause", "hesitate"})

MANNERISM_FAIL_MESSAGE = "That mannerism could not be created for this take."

SPEAKER_MATCH_NOTE = (
    "Mannerism events are local DSP vocal events, level-matched to dialogue when possible. "
    "They are NOT speaker-cloned or speaker-conditioned."
)


def cue_needs_discrete_event(cue_id: str) -> bool:
    return str(cue_id or "").strip().lower() in DISCRETE_EVENT_CUES


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def _intensity_scale(intensity: str) -> float:
    v = (intensity or "medium").strip().lower()
    if v in ("light", "low", "soft", "subtle"):
        return 0.55
    if v in ("strong", "high", "heavy", "hard"):
        return 1.0
    return 0.78


def _read_wav_mono(path: Path) -> tuple[list[float], int]:
    with wave.open(str(path), "rb") as w:
        nch = w.getnchannels()
        sw = w.getsampwidth()
        rate = w.getframerate() or 24000
        n = w.getnframes()
        raw = w.readframes(n)
    if sw != 2:
        raise ValueError(f"Unsupported sample width {sw} (need 16-bit PCM)")
    samples = array("h")
    samples.frombytes(raw)
    if nch == 1:
        mono = [s / 32768.0 for s in samples]
    else:
        mono = []
        for i in range(0, len(samples), nch):
            mono.append(sum(samples[i : i + nch]) / (nch * 32768.0))
    return mono, int(rate)


def _write_wav_mono(path: Path, samples: list[float], sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = array("h")
    for s in samples:
        frames.append(int(_clamp(s, -1.0, 1.0) * 32767.0))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(sample_rate))
        w.writeframes(frames.tobytes())


def _rms(samples: list[float]) -> float:
    if not samples:
        return 0.0
    acc = 0.0
    for s in samples:
        acc += s * s
    return math.sqrt(acc / len(samples))


def _fade(samples: list[float], fade_in: int, fade_out: int) -> list[float]:
    out = list(samples)
    n = len(out)
    fi = min(max(0, fade_in), n)
    fo = min(max(0, fade_out), n)
    for i in range(fi):
        out[i] *= i / float(fi or 1)
    for i in range(fo):
        idx = n - fo + i
        if 0 <= idx < n:
            out[idx] *= ((fo - 1 - i) / float(fo - 1)) if fo > 1 else 0.0
    return out


def _noise(n: int, seed: int = 1) -> list[float]:
    # Deterministic LCG noise (no numpy dependency).
    x = seed & 0xFFFFFFFF
    out = [0.0] * n
    for i in range(n):
        x = (1664525 * x + 1013904223) & 0xFFFFFFFF
        out[i] = ((x / 0xFFFFFFFF) * 2.0) - 1.0
    return out


def _one_pole_lowpass(samples: list[float], alpha: float) -> list[float]:
    a = _clamp(alpha, 0.01, 0.99)
    y = 0.0
    out = [0.0] * len(samples)
    for i, s in enumerate(samples):
        y = y + a * (s - y)
        out[i] = y
    return out


def _one_pole_highpass(samples: list[float], alpha: float) -> list[float]:
    a = _clamp(alpha, 0.01, 0.99)
    prev_x = 0.0
    prev_y = 0.0
    out = [0.0] * len(samples)
    for i, s in enumerate(samples):
        y = a * (prev_y + s - prev_x)
        out[i] = y
        prev_x = s
        prev_y = y
    return out


def _sine(n: int, rate: int, freq: float, amp: float = 1.0) -> list[float]:
    out = [0.0] * n
    for i in range(n):
        out[i] = amp * math.sin(2.0 * math.pi * freq * (i / float(rate)))
    return out


def _mix(*layers: list[float]) -> list[float]:
    n = max((len(L) for L in layers), default=0)
    out = [0.0] * n
    for L in layers:
        for i, s in enumerate(L):
            out[i] += s
    return out


def _scale(samples: list[float], gain: float) -> list[float]:
    return [s * gain for s in samples]


def _pad(samples: list[float], before: int = 0, after: int = 0) -> list[float]:
    return ([0.0] * max(0, before)) + list(samples) + ([0.0] * max(0, after))


def _envelope(n: int, attack: int, hold: int, release: int) -> list[float]:
    env = [0.0] * n
    a = max(1, attack)
    r = max(1, release)
    h = max(0, hold)
    for i in range(n):
        if i < a:
            env[i] = i / float(a)
        elif i < a + h:
            env[i] = 1.0
        elif i < a + h + r:
            env[i] = 1.0 - ((i - a - h) / float(r))
        else:
            env[i] = 0.0
    return env


def _apply_env(samples: list[float], env: list[float]) -> list[float]:
    n = min(len(samples), len(env))
    return [samples[i] * env[i] for i in range(n)]


def synthesize_vocal_event(
    cue_id: str,
    *,
    intensity: str = "medium",
    sample_rate: int = 24000,
    seed: int = 42,
) -> list[float]:
    """Synthesize a short non-verbal vocal event as mono float samples."""
    cid = str(cue_id or "").strip().lower()
    scale = _intensity_scale(intensity)
    sr = int(sample_rate) or 24000

    if cid == "sigh":
        dur = 0.55 + 0.25 * scale
        n = int(sr * dur)
        noise = _one_pole_lowpass(_noise(n, seed + 1), 0.08)
        # soft downward breath tone
        tone = [0.0] * n
        f0, f1 = 220.0 - 40 * scale, 140.0 - 30 * scale
        for i in range(n):
            t = i / float(n)
            f = f0 + (f1 - f0) * t
            tone[i] = 0.22 * math.sin(2.0 * math.pi * f * (i / float(sr))) * (1.0 - 0.35 * t)
        env = _envelope(n, int(0.08 * sr), int(0.18 * sr), int(0.28 * sr))
        body = _apply_env(_mix(_scale(noise, 0.55), tone), env)
        return _fade(_scale(body, 0.55 * scale), int(0.02 * sr), int(0.05 * sr))

    if cid in ("breath_out",):
        dur = 0.40 + 0.20 * scale
        n = int(sr * dur)
        noise = _one_pole_lowpass(_noise(n, seed + 2), 0.12)
        env = _envelope(n, int(0.05 * sr), int(0.12 * sr), int(0.22 * sr))
        return _fade(_scale(_apply_env(noise, env), 0.42 * scale), int(0.01 * sr), int(0.04 * sr))

    if cid in ("breath_in",):
        dur = 0.28 + 0.12 * scale
        n = int(sr * dur)
        noise = _one_pole_highpass(_one_pole_lowpass(_noise(n, seed + 3), 0.25), 0.55)
        env = _envelope(n, int(0.04 * sr), int(0.08 * sr), int(0.14 * sr))
        return _fade(_scale(_apply_env(noise, env), 0.38 * scale), int(0.01 * sr), int(0.03 * sr))

    if cid == "gasp":
        dur = 0.18 + 0.08 * scale
        n = int(sr * dur)
        noise = _one_pole_highpass(_noise(n, seed + 4), 0.35)
        tone = _sine(n, sr, 380.0 + 40 * scale, 0.18)
        env = _envelope(n, int(0.01 * sr), int(0.04 * sr), int(0.10 * sr))
        return _fade(_scale(_apply_env(_mix(noise, tone), env), 0.62 * scale), int(0.005 * sr), int(0.02 * sr))

    if cid == "nervous_breath":
        # two shallow breaths
        parts: list[float] = []
        for k in range(2):
            chunk = synthesize_vocal_event("breath_in", intensity="light", sample_rate=sr, seed=seed + 10 + k)
            parts.extend(chunk)
            parts.extend([0.0] * int(0.06 * sr))
            chunk2 = synthesize_vocal_event("breath_out", intensity="light", sample_rate=sr, seed=seed + 20 + k)
            parts.extend(_scale(chunk2, 0.7))
            parts.extend([0.0] * int(0.05 * sr))
        return _scale(parts, 0.9 * scale)

    if cid == "scoff":
        dur = 0.22 + 0.08 * scale
        n = int(sr * dur)
        noise = _one_pole_highpass(_noise(n, seed + 5), 0.4)
        tone = _sine(n, sr, 160.0, 0.25)
        env = _envelope(n, int(0.01 * sr), int(0.05 * sr), int(0.12 * sr))
        return _fade(_scale(_apply_env(_mix(_scale(noise, 0.7), tone), env), 0.55 * scale), int(0.005 * sr), int(0.02 * sr))

    if cid in ("chuckle", "soft_laugh", "laugh"):
        # Pulsed soft voiced bursts — audible chuckle/laugh energy (not spoken words).
        bursts = 2 if cid == "soft_laugh" else (3 if cid == "chuckle" else 4)
        gap = int((0.06 if cid != "laugh" else 0.05) * sr)
        parts = []
        base_f = 190.0 if cid == "soft_laugh" else (210.0 if cid == "chuckle" else 240.0)
        for b in range(bursts):
            dur = 0.09 + 0.03 * scale + (0.02 if cid == "laugh" else 0.0)
            n = int(sr * dur)
            f = base_f + b * 18.0
            tone = _sine(n, sr, f, 0.35)
            harm = _sine(n, sr, f * 2.0, 0.12)
            noise = _scale(_one_pole_lowpass(_noise(n, seed + 30 + b), 0.2), 0.15)
            env = _envelope(n, int(0.01 * sr), int(0.03 * sr), int(0.05 * sr))
            amp = (0.35 if cid == "soft_laugh" else 0.48 if cid == "chuckle" else 0.62) * scale
            parts.extend(_scale(_apply_env(_mix(tone, harm, noise), env), amp))
            parts.extend([0.0] * gap)
        return _fade(parts, int(0.01 * sr), int(0.03 * sr))

    raise ValueError(f"No discrete vocal-event synthesizer for cue '{cid}'")


def match_level_to_dialogue(event: list[float], dialogue: list[float], *, target_ratio: float = 0.55) -> list[float]:
    """Level-match event RMS to a fraction of dialogue RMS (not speaker cloning)."""
    d_rms = _rms(dialogue) or 0.08
    e_rms = _rms(event) or 1e-6
    target = d_rms * target_ratio
    gain = _clamp(target / e_rms, 0.15, 2.5)
    return _scale(event, gain)


def _resample_linear(samples: list[float], src_rate: int, dst_rate: int) -> list[float]:
    if src_rate == dst_rate or not samples:
        return list(samples)
    ratio = float(dst_rate) / float(src_rate)
    n_out = max(1, int(round(len(samples) * ratio)))
    out = [0.0] * n_out
    for i in range(n_out):
        src_pos = i / ratio
        j = int(src_pos)
        frac = src_pos - j
        a = samples[j] if j < len(samples) else 0.0
        b = samples[j + 1] if (j + 1) < len(samples) else a
        out[i] = a + (b - a) * frac
    return out


def find_phrase_boundary(samples: list[float], sample_rate: int) -> Optional[int]:
    """Find a low-energy valley in the middle third for a 'during' insert. None if unsafe."""
    n = len(samples)
    if n < int(sample_rate * 0.6):
        return None
    start = int(n * 0.33)
    end = int(n * 0.67)
    win = max(1, int(sample_rate * 0.04))
    best_i = None
    best_e = 1e9
    i = start
    while i + win < end:
        chunk = samples[i : i + win]
        e = _rms(chunk)
        if e < best_e:
            best_e = e
            best_i = i + win // 2
        i += win // 2
    # Require quiet enough relative to overall
    overall = _rms(samples) or 1e-6
    if best_i is None or best_e > overall * 0.35:
        return None
    return best_i


def stitch_take(
    dialogue_path: Path,
    events: list[dict[str, Any]],
    dest: Path,
    *,
    transition_ms: int = 80,
) -> dict[str, Any]:
    """Stitch dialogue + mannerism events into one Take WAV.

    events: list of {position, samples, cue_id, intensity}
    """
    dialogue, rate = _read_wav_mono(Path(dialogue_path))
    trans = max(0, int(rate * (transition_ms / 1000.0)))
    silence = [0.0] * trans

    before_parts: list[float] = []
    after_parts: list[float] = []
    during_inserts: list[tuple[int, list[float]]] = []
    placed: list[dict[str, Any]] = []

    for ev in events:
        pos = str(ev.get("position") or "before").lower()
        samples = list(ev.get("samples") or [])
        if not samples:
            continue
        # ensure same rate (events already generated at dialogue rate ideally)
        if pos == "before":
            before_parts.extend(samples)
            before_parts.extend(silence)
            placed.append({"cueId": ev.get("cue_id"), "position": "before", "samples": len(samples)})
        elif pos == "after":
            after_parts.extend(silence)
            after_parts.extend(samples)
            placed.append({"cueId": ev.get("cue_id"), "position": "after", "samples": len(samples)})
        else:
            boundary = find_phrase_boundary(dialogue, rate)
            if boundary is None:
                raise RuntimeError("during_insert_no_phrase_boundary")
            during_inserts.append((boundary, samples))
            placed.append({"cueId": ev.get("cue_id"), "position": "during", "atSample": boundary, "samples": len(samples)})

    # Apply during inserts from end to start so indices stay valid
    body = list(dialogue)
    for at, samples in sorted(during_inserts, key=lambda x: x[0], reverse=True):
        # duck a tiny region and insert event + micro silence
        insert = silence[: trans // 2] + samples + silence[: trans // 2]
        body = body[:at] + insert + body[at:]

    final = before_parts + body + after_parts
    # soft peak normalize to avoid clip
    peak = max((abs(s) for s in final), default=0.0)
    if peak > 0.98:
        final = _scale(final, 0.98 / peak)
    _write_wav_mono(Path(dest), final, rate)
    return {
        "ok": True,
        "path": str(dest),
        "sampleRate": rate,
        "durationMs": int(1000 * len(final) / float(rate)),
        "placed": placed,
        "speakerMatchNote": SPEAKER_MATCH_NOTE,
    }


def render_mannerism_event_wav(
    cue_id: str,
    dest: Path,
    *,
    intensity: str = "medium",
    sample_rate: int = 24000,
    dialogue_path: Path | None = None,
    seed: int = 42,
) -> dict[str, Any]:
    samples = synthesize_vocal_event(cue_id, intensity=intensity, sample_rate=sample_rate, seed=seed)
    if dialogue_path and Path(dialogue_path).is_file():
        try:
            dialogue, d_rate = _read_wav_mono(Path(dialogue_path))
            if d_rate != sample_rate:
                samples = _resample_linear(samples, sample_rate, d_rate)
                sample_rate = d_rate
            samples = match_level_to_dialogue(samples, dialogue)
        except Exception:
            pass
    _write_wav_mono(Path(dest), samples, sample_rate)
    return {
        "ok": True,
        "cueId": cue_id,
        "intensity": intensity,
        "path": str(dest),
        "sampleRate": sample_rate,
        "durationMs": int(1000 * len(samples) / float(sample_rate or 1)),
        "generator": "local_dsp_vocal_event",
        "speakerMatched": False,
        "speakerMatchNote": SPEAKER_MATCH_NOTE,
    }


def apply_mannerisms_to_take_audio(
    *,
    db: Any,
    project_id: str,
    take_id: str,
    dialogue_asset_id: str | None,
    dialogue_path: str | Path | None,
    cues: list[dict[str, Any]] | None,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    """Generate discrete mannerism events and stitch into one final take WAV.

    Returns metadata for persistence on the take direction snapshot.
    On failure for required discrete cues: does NOT silently omit — sets
    mannerismSatisfied=False and failureMessage.
    """
    from ..character_identity.voice_runtime import _project_audio_dir, _register_asset
    from ..db import Asset

    cues = list(cues or [])
    discrete = [c for c in cues if cue_needs_discrete_event(str(c.get("id") or ""))]
    meta: dict[str, Any] = {
        "mannerismEvents": [],
        "mannerismSatisfied": True,
        "mannerismFailureMessage": None,
        "mannerismStitchedAssetId": None,
        "mannerismStitchedPath": None,
        "speakerMatched": False,
        "speakerMatchNote": SPEAKER_MATCH_NOTE,
        "generator": "local_dsp_vocal_event",
    }
    if not discrete:
        meta["mannerismSatisfied"] = True
        meta["note"] = "No discrete vocal-event cues; delivery-only cues (if any) use emo_text/structural path."
        return meta

    # Resolve dialogue path
    d_path: Path | None = Path(str(dialogue_path)) if dialogue_path else None
    if (not d_path or not d_path.is_file()) and dialogue_asset_id and db is not None:
        asset = db.get(Asset, dialogue_asset_id)
        if asset and asset.path and Path(asset.path).is_file():
            d_path = Path(asset.path)
    if not d_path or not d_path.is_file():
        meta["mannerismSatisfied"] = False
        meta["mannerismFailureMessage"] = MANNERISM_FAIL_MESSAGE
        meta["error"] = "dialogue_audio_missing"
        return meta

    try:
        dialogue, rate = _read_wav_mono(d_path)
    except Exception as exc:
        meta["mannerismSatisfied"] = False
        meta["mannerismFailureMessage"] = MANNERISM_FAIL_MESSAGE
        meta["error"] = f"dialogue_read_failed:{exc}"
        return meta

    base_dir = Path(out_dir) if out_dir else _project_audio_dir(project_id)
    base_dir.mkdir(parents=True, exist_ok=True)
    event_payloads: list[dict[str, Any]] = []

    for idx, cue in enumerate(discrete):
        cue_id = str(cue.get("id") or "")
        intensity = str(cue.get("intensity") or "medium")
        position = str(cue.get("position") or "before").lower()
        if position not in ("before", "during", "after"):
            position = "before"
        event_path = base_dir / f"mannerism_{take_id[:8]}_{cue_id}_{idx}_{uuid.uuid4().hex[:6]}.wav"
        try:
            rendered = render_mannerism_event_wav(
                cue_id,
                event_path,
                intensity=intensity,
                sample_rate=rate,
                dialogue_path=d_path,
                seed=41 + idx * 17,
            )
            samples, ev_rate = _read_wav_mono(event_path)
            if ev_rate != rate:
                samples = _resample_linear(samples, ev_rate, rate)
            samples = match_level_to_dialogue(samples, dialogue)
            asset_id = None
            if db is not None:
                asset_id = _register_asset(
                    db,
                    project_id,
                    event_path,
                    kind="audio",
                    name=f"Mannerism {cue_id}",
                    tag="mannerism_event",
                    extra_meta={
                        "source": "voice_performance.mannerism_events",
                        "cueId": cue_id,
                        "position": position,
                        "intensity": intensity,
                        "takeId": take_id,
                        "speakerMatched": False,
                        "generator": "local_dsp_vocal_event",
                    },
                )
            event_payloads.append(
                {
                    "cue_id": cue_id,
                    "position": position,
                    "intensity": intensity,
                    "samples": samples,
                    "path": str(event_path),
                    "assetId": asset_id,
                    "durationMs": rendered.get("durationMs"),
                    "speakerMatched": False,
                }
            )
            meta["mannerismEvents"].append(
                {
                    "cueId": cue_id,
                    "position": position,
                    "intensity": intensity,
                    "assetId": asset_id,
                    "path": str(event_path),
                    "durationMs": rendered.get("durationMs"),
                    "generator": "local_dsp_vocal_event",
                    "speakerMatched": False,
                    "status": "ready",
                }
            )
        except Exception as exc:
            meta["mannerismSatisfied"] = False
            meta["mannerismFailureMessage"] = MANNERISM_FAIL_MESSAGE
            meta["mannerismEvents"].append(
                {
                    "cueId": cue_id,
                    "position": position,
                    "intensity": intensity,
                    "status": "failed",
                    "error": str(exc),
                }
            )
            return meta

    # During-position safety: if any during cue and no boundary, fail that cue
    for ev in event_payloads:
        if ev["position"] == "during":
            if find_phrase_boundary(dialogue, rate) is None:
                meta["mannerismSatisfied"] = False
                meta["mannerismFailureMessage"] = MANNERISM_FAIL_MESSAGE
                for m in meta["mannerismEvents"]:
                    if m.get("cueId") == ev["cue_id"] and m.get("position") == "during":
                        m["status"] = "failed"
                        m["error"] = "no_valid_phrase_boundary"
                return meta

    stitched_path = base_dir / f"take_stitched_{take_id[:10]}_{uuid.uuid4().hex[:8]}.wav"
    try:
        stitch_info = stitch_take(
            d_path,
            event_payloads,
            stitched_path,
            transition_ms=80,
        )
    except Exception as exc:
        meta["mannerismSatisfied"] = False
        meta["mannerismFailureMessage"] = MANNERISM_FAIL_MESSAGE
        meta["error"] = f"stitch_failed:{exc}"
        return meta

    stitched_asset_id = None
    if db is not None:
        stitched_asset_id = _register_asset(
            db,
            project_id,
            stitched_path,
            kind="audio",
            name=f"Take stitched {take_id[:8]}",
            tag="dialogue",
            extra_meta={
                "source": "voice_performance.mannerism_events.stitch",
                "takeId": take_id,
                "dialogueAssetId": dialogue_asset_id,
                "mannerismEventAssetIds": [e.get("assetId") for e in meta["mannerismEvents"]],
                "speakerMatched": False,
            },
        )
    meta["mannerismStitchedAssetId"] = stitched_asset_id
    meta["mannerismStitchedPath"] = str(stitched_path)
    meta["stitch"] = stitch_info
    meta["mannerismSatisfied"] = True
    return meta
