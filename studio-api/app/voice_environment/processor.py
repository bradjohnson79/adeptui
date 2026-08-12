"""Deterministic local acoustic processing for Voice Environment."""

from __future__ import annotations

import math
import wave
from pathlib import Path
from typing import Any

import numpy as np

from .contracts import VoiceEnvironmentTiming


def _read_wav_mono(path: Path) -> tuple[np.ndarray, int]:
    try:
        import soundfile as sf

        data, sr = sf.read(str(path), always_2d=True)
        mono = data.mean(axis=1).astype(np.float32)
        return mono, int(sr)
    except Exception:
        with wave.open(str(path), "rb") as wf:
            sr = wf.getframerate()
            frames = wf.readframes(wf.getnframes())
            width = wf.getsampwidth()
            channels = wf.getnchannels()
            if width == 2:
                arr = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            else:
                arr = np.frombuffer(frames, dtype=np.uint8).astype(np.float32)
                arr = (arr - 128.0) / 128.0
            if channels > 1:
                arr = arr.reshape(-1, channels).mean(axis=1)
            return arr.astype(np.float32), int(sr)


def _write_wav(path: Path, samples: np.ndarray, sr: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import soundfile as sf

        sf.write(str(path), samples.astype(np.float32), sr)
        return
    except Exception:
        clipped = np.clip(samples, -1.0, 1.0)
        pcm = (clipped * 32767.0).astype(np.int16)
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(pcm.tobytes())


def _db_to_lin(db: float) -> float:
    return float(10 ** (db / 20.0))


def _one_pole_lp(x: np.ndarray, cutoff_hz: float, sr: int) -> np.ndarray:
    if cutoff_hz <= 0 or cutoff_hz >= sr / 2:
        return x
    rc = 1.0 / (2.0 * math.pi * cutoff_hz)
    dt = 1.0 / sr
    a = dt / (rc + dt)
    y = np.empty_like(x)
    prev = 0.0
    for i, sample in enumerate(x):
        prev = prev + a * (float(sample) - prev)
        y[i] = prev
    return y


def _one_pole_hp(x: np.ndarray, cutoff_hz: float, sr: int) -> np.ndarray:
    if cutoff_hz <= 0:
        return x
    rc = 1.0 / (2.0 * math.pi * cutoff_hz)
    dt = 1.0 / sr
    a = rc / (rc + dt)
    y = np.empty_like(x)
    prev_x = 0.0
    prev_y = 0.0
    for i, sample in enumerate(x):
        cur = float(sample)
        prev_y = a * (prev_y + cur - prev_x)
        prev_x = cur
        y[i] = prev_y
    return y


def _simple_reverb(x: np.ndarray, sr: int, reverb_ms: float, wet: float, tail_ms: float) -> np.ndarray:
    delays_ms = [reverb_ms * 0.22, reverb_ms * 0.37, reverb_ms * 0.53, reverb_ms * 0.71]
    gains = [0.35, 0.28, 0.22, 0.18]
    tail_samples = int(sr * max(tail_ms, 0.0) / 1000.0)
    out = np.zeros(len(x) + tail_samples, dtype=np.float32)
    out[: len(x)] = x
    wet_bus = np.zeros_like(out)
    for delay_ms, g in zip(delays_ms, gains):
        d = max(1, int(sr * delay_ms / 1000.0))
        if d >= len(out):
            continue
        end = min(len(out), d + len(x))
        wet_bus[d:end] += x[: end - d] * g
    mixed = (1.0 - wet) * out
    mixed += wet * wet_bus
    return mixed.astype(np.float32)


def _stereo_pan(mono: np.ndarray, pan: float) -> np.ndarray:
    pan = float(np.clip(pan, -1.0, 1.0))
    left = math.cos((pan + 1.0) * 0.25 * math.pi)
    right = math.sin((pan + 1.0) * 0.25 * math.pi)
    return np.stack([mono * left, mono * right], axis=1).astype(np.float32)


def _detect_speech_start_ms(samples: np.ndarray, sr: int) -> float:
    if samples.size == 0:
        return 0.0
    window = max(1, int(sr * 0.01))
    energy = np.convolve(samples**2, np.ones(window) / window, mode="same")
    threshold = float(np.max(energy) * 0.02)
    idx = int(np.argmax(energy >= threshold)) if threshold > 0 else 0
    return (idx / sr) * 1000.0


def process_environment(
    dry_path: Path,
    out_processed: Path,
    out_room_tone: Path | None,
    out_walla: Path | None,
    dsp_plan: dict[str, Any],
) -> VoiceEnvironmentTiming:
    dry, sr = _read_wav_mono(dry_path)
    speech_start = _detect_speech_start_ms(dry, sr)
    dry_duration_ms = (len(dry) / sr) * 1000.0

    space = dsp_plan.get("space") or {}
    distance = dsp_plan.get("distance") or {}
    direction = dsp_plan.get("direction") or {}
    tone = dsp_plan.get("tone") or {}
    device = dsp_plan.get("device") or {}
    walla = dsp_plan.get("walla") or {}
    hints = dsp_plan.get("timingHints") or {}

    x = dry.copy()
    # Tone shelves approximated with gentle LP/HP + gain.
    if tone.get("lp_hz"):
        x = _one_pole_lp(x, float(tone["lp_hz"]), sr)
    high_shelf = float(tone.get("high_shelf_db") or 0.0)
    low_shelf = float(tone.get("low_shelf_db") or 0.0)
    if high_shelf < 0:
        x = _one_pole_lp(x, 9000.0, sr) * _db_to_lin(high_shelf * 0.25 + 0.01)
        x = x + dry * (1.0 - 0.25)
    if low_shelf != 0:
        x = x * _db_to_lin(low_shelf * 0.15)

    # Distance
    x = x * _db_to_lin(float(distance.get("gain_db") or 0.0))
    x = _one_pole_lp(x, float(distance.get("hf_cut_hz") or 12000), sr)

    # Device band-limit + mild drive
    x = _one_pole_hp(x, float(device.get("band_low_hz") or 40), sr)
    x = _one_pole_lp(x, float(device.get("band_high_hz") or 16000), sr)
    drive = float(device.get("drive") or 0.0)
    if drive > 0:
        x = np.tanh(x * (1.0 + drive * 4.0)).astype(np.float32)

    # Space / reverb (adds tail; does not shift speech start metadata)
    x = _simple_reverb(
        x,
        sr,
        reverb_ms=float(space.get("reverb_ms") or 200),
        wet=float(space.get("wet") or 0.1),
        tail_ms=float(space.get("tail_ms") or 100),
    )

    brightness = float(direction.get("brightness") or 1.0)
    if brightness != 1.0:
        x = x * brightness

    pan = float(direction.get("pan") or 0.0)
    stereo = _stereo_pan(x, pan)
    # Store mono mixdown for broad compatibility; pan encoded in channel balance then summed.
    processed = stereo.mean(axis=1).astype(np.float32)

    processing_latency_ms = float(hints.get("processingLatencyMs") or 0.0)
    tail_duration_ms = max(0.0, (len(processed) / sr) * 1000.0 - dry_duration_ms)
    # Do not pad leading silence for device latency — keep speechStartOffsetMs dry-aligned.
    _write_wav(out_processed, processed, sr)

    if out_room_tone is not None:
        room_len = len(processed)
        room = (np.random.default_rng(7).normal(0, 0.003, room_len).astype(np.float32))
        room = _one_pole_lp(room, 800.0, sr) * float(space.get("wet") or 0.1)
        _write_wav(out_room_tone, room, sr)

    if out_walla is not None:
        level = float(walla.get("level") or 0.0)
        if level > 0:
            walla_len = len(processed)
            noise = np.random.default_rng(21).normal(0, 0.01, walla_len).astype(np.float32)
            noise = _one_pole_lp(noise, 2500.0, sr) * level
            _write_wav(out_walla, noise, sr)
        else:
            _write_wav(out_walla, np.zeros(len(processed), dtype=np.float32), sr)

    return VoiceEnvironmentTiming(
        speechStartOffsetMs=float(speech_start),
        processingLatencyMs=processing_latency_ms,
        tailDurationMs=float(tail_duration_ms),
        dryDurationMs=float(dry_duration_ms),
        processedDurationMs=(len(processed) / sr) * 1000.0,
    )
