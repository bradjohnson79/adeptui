"""Sound profiles for MAGI Upscale.

Analysis and treatment stay inside the existing upscale job.
Engineering stays here; the creator only picks a profile.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from .media import ffprobe_json, run_ffmpeg

ANALYSIS_VERSION = "sound-analysis-v1"

PROFILES: tuple[dict[str, str], ...] = (
    {"id": "preserve_original", "label": "Preserve Original"},
    {"id": "cinematic_stereo", "label": "Cinematic Stereo"},
    {"id": "dialogue_enhance", "label": "Dialogue Enhance"},
    {"id": "wide_stereo", "label": "Wide Stereo"},
    {"id": "clean_restore", "label": "Clean & Restore"},
    {"id": "cinema_51", "label": "5.1 Cinema Upmix"},
    {"id": "cinema_71", "label": "7.1 Cinema Upmix"},
    {"id": "headphone_spatial", "label": "Headphone Spatial"},
)

_STEREO_PROFILES = {"cinematic_stereo", "dialogue_enhance", "wide_stereo", "headphone_spatial"}
_UPMIX_PROFILES = {"cinema_51": "5.1", "cinema_71": "7.1"}
_FILTERS: set[str] | None = None


def _ffmpeg_filters() -> set[str]:
    global _FILTERS
    if _FILTERS is not None:
        return _FILTERS
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-filters"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    names = set()
    for line in (proc.stdout or "").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1].isidentifier():
            names.add(parts[1])
    _FILTERS = names
    return names


def profile_catalog() -> list[dict[str, Any]]:
    filters = _ffmpeg_filters()
    rows = []
    for row in PROFILES:
        available = True
        note = ""
        needed = {
            "dialogue_enhance": "dialoguenhance",
            "wide_stereo": "extrastereo",
            "clean_restore": "afftdn",
            "cinema_51": "pan",
            "cinema_71": "pan",
            "headphone_spatial": "earwax",
            "cinematic_stereo": "loudnorm",
        }.get(row["id"])
        if needed and needed not in filters:
            available = False
            note = "Component unavailable"
        rows.append({**row, "available": available, "unavailableReason": note})
    return rows


def profile_label(profile_id: str) -> str:
    for row in PROFILES:
        if row["id"] == profile_id:
            return row["label"]
    return profile_id


def sound_profile_from_intent(text: str) -> str | None:
    """Map a creator sentence onto one upscale sound profile."""
    raw = (text or "").lower()
    if not raw.strip():
        return None
    if re.search(r"preserve (the )?original|keep (the )?original audio|original audio", raw):
        return "preserve_original"
    if re.search(r"7\.1", raw):
        return "cinema_71"
    if re.search(r"5\.1", raw):
        return "cinema_51"
    if re.search(r"headphone", raw):
        return "headphone_spatial"
    if re.search(r"dialogue enhance|enhance (the )?dialogue|clearer dialogue|speech clarity", raw):
        return "dialogue_enhance"
    if re.search(r"wide stereo", raw):
        return "wide_stereo"
    if re.search(r"\b(clean|restore|denoise)\b", raw) and re.search(r"\b(audio|sound)\b", raw):
        return "clean_restore"
    if re.search(r"cinematic stereo", raw):
        return "cinematic_stereo"
    if re.search(r"recommended sound|sound enhancement|recommended audio", raw):
        return "recommended"
    return None


def _audio_stream(path: Path) -> dict[str, Any] | None:
    info = ffprobe_json(path)
    for stream in info.get("streams") or []:
        if stream.get("codec_type") == "audio":
            return stream
    return None


def _db_from(text: str, key: str) -> float | None:
    match = re.search(rf"{key}:\s*(-?\d+(?:\.\d+)?)\s*dB", text or "")
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _measure(path: Path, audio_filter: str, *, seconds: float) -> tuple[float | None, float | None]:
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-t",
            f"{seconds:.3f}",
            "-i",
            str(path),
            "-vn",
            "-af",
            audio_filter,
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    text = proc.stderr or ""
    return _db_from(text, "max_volume"), _db_from(text, "mean_volume")


def _loudness(path: Path, *, seconds: float) -> dict[str, float | None]:
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-t",
            f"{seconds:.3f}",
            "-i",
            str(path),
            "-vn",
            "-af",
            "ebur128=peak=true",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    text = proc.stderr or ""
    summary = text.split("Summary:")[-1] if "Summary:" in text else text
    integrated = re.search(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", summary)
    lra = re.search(r"LRA:\s*(-?\d+(?:\.\d+)?)\s*LU", summary)
    peak = re.search(r"Peak:\s*(-?\d+(?:\.\d+)?)\s*dBFS", summary)
    def grab(match: re.Match[str] | None) -> float | None:
        if not match:
            return None
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return {"integrated": grab(integrated), "lra": grab(lra), "peak": grab(peak)}


def _lin(db: float | None) -> float:
    if db is None:
        return 0.0
    return 10 ** (db / 20.0)


def analyze_source(path: str | Path, *, sample_seconds: float = 12.0) -> dict[str, Any]:
    """Lightweight read of the soundtrack. No stem separation."""
    src = Path(path)
    stream = _audio_stream(src)
    if stream is None:
        return {
            "version": ANALYSIS_VERSION,
            "hasAudio": False,
            "channels": 0,
            "channelLayout": "",
            "sampleRate": 0,
            "codec": "",
            "bitrate": 0,
            "duration": 0.0,
            "dialogue": False,
            "music": False,
            "sfx": False,
            "noise": "none",
            "clippingRisk": False,
            "multichannel": False,
            "stereoWidth": "",
            "speechDominance": False,
            "infoLine": "No audio",
            "summary": "No audio detected",
        }
    info = ffprobe_json(src)
    duration = 0.0
    try:
        duration = float((info.get("format") or {}).get("duration") or stream.get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    window = min(max(duration, 0.5), sample_seconds) if duration else sample_seconds
    channels = int(stream.get("channels") or 0)
    layout = str(stream.get("channel_layout") or "")
    rate = int(stream.get("sample_rate") or 0)
    codec = str(stream.get("codec_name") or "")
    bitrate = int(stream.get("bit_rate") or (info.get("format") or {}).get("bit_rate") or 0)
    full_max, full_mean = _measure(path, "volumedetect", seconds=window)
    speech_max, speech_mean = _measure(path, "highpass=f=300,lowpass=f=3400,volumedetect", seconds=window)
    low_max, low_mean = _measure(path, "lowpass=f=160,volumedetect", seconds=window)
    high_max, high_mean = _measure(path, "highpass=f=6000,volumedetect", seconds=window)
    side_max, side_mean = (None, None)
    if channels >= 2:
        _, side_mean = _measure(path, "pan=mono|c0=0.5*c0-0.5*c1,volumedetect", seconds=window)
    loud = _loudness(path, seconds=window)
    full_lin = _lin(full_mean)
    speech_share = _lin(speech_mean) / full_lin if full_lin else 0.0
    low_share = _lin(low_mean) / full_lin if full_lin else 0.0
    high_share = _lin(high_mean) / full_lin if full_lin else 0.0
    side_share = _lin(side_mean) / full_lin if full_lin else 0.0
    peak = loud.get("peak")
    if peak is None:
        peak = full_max
    span = None
    if full_max is not None and full_mean is not None:
        span = full_max - full_mean
    clipping = peak is not None and peak > -1.0
    noisy = bool(span is not None and span < 8 and (full_mean or -99) > -24)
    dialogue = speech_share > 0.35 and (speech_mean or -99) > -42
    music = low_share > 0.12 and (low_mean or -99) > -48
    sfx = high_share > 0.04 and (high_mean or -99) > -50
    speech_dominance = dialogue and speech_share > 0.62 and not (music and sfx and speech_share < 0.8)
    if channels >= 6:
        width = "surround"
    elif side_share > 0.35:
        width = "wide"
    elif side_share < 0.08:
        width = "narrow"
    else:
        width = "normal"
    hiss = dialogue and not music and high_share > 0.5 and (span or 99) < 18
    if not dialogue and not music and not sfx and (full_mean or -99) < -50:
        noise = "quiet"
    elif clipping:
        noise = "clipped"
    elif noisy or hiss:
        noise = "noisy"
    else:
        noise = "clean"
    rate_label = f"{rate // 1000} kHz" if rate and rate % 1000 == 0 else (f"{rate} Hz" if rate else "—")
    if channels >= 6:
        info = f"{layout or str(channels) + ' channels'} · {rate_label} · {noise} mix"
    elif channels == 1:
        info = f"Mono · {rate_label} · {noise} mix"
    else:
        info = f"Stereo · {rate_label} · {noise} mix"
    return {
        "version": ANALYSIS_VERSION,
        "hasAudio": True,
        "channels": channels,
        "channelLayout": layout,
        "sampleRate": rate,
        "codec": codec,
        "bitrate": bitrate,
        "duration": duration,
        "sampleSeconds": window,
        "peakDb": peak,
        "meanDb": full_mean,
        "integratedLufs": loud.get("integrated"),
        "loudnessRange": loud.get("lra"),
        "dynamicSpanDb": span,
        "dialogue": dialogue,
        "music": music,
        "sfx": sfx,
        "speechShare": round(speech_share, 3),
        "lowShare": round(low_share, 3),
        "highShare": round(high_share, 3),
        "sideShare": round(side_share, 3),
        "noise": noise,
        "clippingRisk": clipping,
        "multichannel": channels >= 6,
        "stereoWidth": width,
        "speechDominance": speech_dominance,
        "infoLine": info,
        "summary": _summary(dialogue, music, sfx, noise, channels),
    }


def _summary(dialogue: bool, music: bool, sfx: bool, noise: str, channels: int) -> str:
    if channels <= 0:
        return "No audio detected"
    parts = []
    if dialogue:
        parts.append("dialogue")
    if music:
        parts.append("music")
    if sfx:
        parts.append("SFX")
    heard = ", ".join(parts) if parts else "a soundtrack"
    if channels >= 6:
        return f"{heard} in a surround mix"
    if noise == "noisy":
        return f"{heard} with a noisy floor"
    return f"{heard} in a stereo mix" if channels >= 2 else f"{heard} in a mono mix"


def recommend(analysis: dict[str, Any]) -> dict[str, Any]:
    """Deterministic profile choice. The creator can still pick another."""
    if not analysis.get("hasAudio"):
        return {
            "profile": "preserve_original",
            "label": "Preserve Original",
            "confidence": "high",
            "reason": "No audio detected.",
        }
    channels = int(analysis.get("channels") or 0)
    dialogue = bool(analysis.get("dialogue"))
    music = bool(analysis.get("music"))
    sfx = bool(analysis.get("sfx"))
    noise = str(analysis.get("noise") or "")
    if channels >= 6:
        return _rec(
            "preserve_original",
            "high",
            "The soundtrack is already a surround mix, so the original channels stay as they are.",
        )
    hiss = float(analysis.get("highShare") or 0) > 0.5 and float(analysis.get("dynamicSpanDb") or 99) < 18
    if dialogue and (noise in {"noisy", "clipped"} or (hiss and not music)):
        return _rec(
            "clean_restore",
            "high",
            "Speech is present and the recording sounds rough, so a gentle cleanup is the better start.",
        )
    if dialogue and music and not sfx and bool(analysis.get("speechDominance")):
        return _rec(
            "dialogue_enhance",
            "medium",
            "Speech dominates the clip and background music is present.",
        )
    if dialogue and (music or sfx):
        return _rec(
            "cinematic_stereo",
            "high",
            "Dialogue, music, and SFX were detected in a stereo mix." if channels >= 2 and sfx and music
            else "Dialogue and other sound were detected together in the mix.",
        )
    if not dialogue and music and noise == "clean" and str(analysis.get("stereoWidth")) == "narrow":
        return _rec(
            "wide_stereo",
            "medium",
            "The music is clean and the stereo image is narrow.",
        )
    if noise == "clean" and not bool(analysis.get("clippingRisk")):
        return _rec(
            "preserve_original",
            "medium",
            "The source is already clean and well balanced.",
        )
    if dialogue:
        return _rec("dialogue_enhance", "medium", "Speech is the main thing in this clip.")
    return _rec("cinematic_stereo", "low", "A light film-style stereo master fits this clip.")


def _rec(profile: str, confidence: str, reason: str) -> dict[str, Any]:
    return {
        "profile": profile,
        "label": profile_label(profile),
        "confidence": confidence,
        "reason": reason,
    }


def normalize_sound_request(requested: str) -> str:
    """Validate a creator choice before a job starts. Empty keeps the original audio."""
    choice = (requested or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "preserve": "preserve_original",
        "original": "preserve_original",
        "cinematic": "cinematic_stereo",
        "dialogue": "dialogue_enhance",
        "wide": "wide_stereo",
        "clean": "clean_restore",
        "restore": "clean_restore",
        "5.1": "cinema_51",
        "51": "cinema_51",
        "7.1": "cinema_71",
        "71": "cinema_71",
        "headphone": "headphone_spatial",
    }
    choice = aliases.get(choice, choice)
    if not choice:
        return "preserve_original"
    if choice == "recommended":
        return "recommended"
    known = {row["id"]: row for row in profile_catalog()}
    if choice not in known:
        raise ValueError("That sound profile is not available.")
    if not known[choice]["available"]:
        raise ValueError(known[choice]["unavailableReason"] or "Component unavailable")
    return choice


def resolve_profile(requested: str, analysis: dict[str, Any]) -> str:
    choice = (requested or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "recommended": "",
        "preserve": "preserve_original",
        "original": "preserve_original",
        "cinematic": "cinematic_stereo",
        "dialogue": "dialogue_enhance",
        "wide": "wide_stereo",
        "clean": "clean_restore",
        "restore": "clean_restore",
        "5.1": "cinema_51",
        "51": "cinema_51",
        "7.1": "cinema_71",
        "71": "cinema_71",
        "headphone": "headphone_spatial",
    }
    choice = aliases.get(choice, choice)
    if not choice:
        choice = str(recommend(analysis).get("profile") or "preserve_original")
    known = {row["id"]: row for row in profile_catalog()}
    if choice not in known:
        raise ValueError("That sound profile is not available.")
    if not known[choice]["available"]:
        raise ValueError(known[choice]["unavailableReason"] or "Component unavailable")
    if not analysis.get("hasAudio"):
        return "preserve_original"
    return choice


def output_layout(profile: str, analysis: dict[str, Any]) -> tuple[int, str]:
    channels = int(analysis.get("channels") or 0)
    if profile == "preserve_original":
        return channels, str(analysis.get("channelLayout") or "")
    if channels >= 6 and profile in _STEREO_PROFILES | set(_UPMIX_PROFILES):
        if profile == "headphone_spatial":
            return 2, "stereo"
        if profile in _UPMIX_PROFILES and channels < (6 if profile == "cinema_51" else 8):
            pass
        else:
            return channels, str(analysis.get("channelLayout") or "")
    if profile in _UPMIX_PROFILES:
        layout = _UPMIX_PROFILES[profile]
        return (6 if profile == "cinema_51" else 8), layout
    return 2, "stereo"


def _trim(duration: float, rate: int) -> str:
    end = max(duration, 0.05)
    sample = rate if rate >= 8000 else 48000
    return (
        f"atrim=end={end:.3f},asetpts=PTS-STARTPTS,"
        f"aformat=sample_fmts=fltp:sample_rates={sample}"
    )


def _native_master(analysis: dict[str, Any], duration: float) -> str:
    layout = str(analysis.get("channelLayout") or "").strip()
    prefix = f"aformat=channel_layouts={layout}," if layout else ""
    rate = int(analysis.get("sampleRate") or 48000)
    return prefix + "loudnorm=I=-16:TP=-1.5:LRA=12,alimiter=limit=0.89:level=false," + _trim(duration, rate)


def filter_graph(profile: str, analysis: dict[str, Any], duration: float) -> str | None:
    """FFmpeg audio graph for one profile. None means copy the source stream."""
    if profile == "preserve_original" or not analysis.get("hasAudio"):
        return None
    channels = int(analysis.get("channels") or 0)
    rate = int(analysis.get("sampleRate") or 48000)
    if channels >= 6 and profile != "headphone_spatial":
        if profile in _UPMIX_PROFILES and channels >= (6 if profile == "cinema_51" else 8):
            return None
        return _native_master(analysis, duration)
    noise = str(analysis.get("noise") or "")
    narrow = str(analysis.get("stereoWidth") or "") == "narrow"
    buried = bool(analysis.get("dialogue")) and float(analysis.get("speechShare") or 0) < 0.55
    tail = _trim(duration, rate)
    if profile == "cinematic_stereo":
        presence = "equalizer=f=2800:width_type=q:width=1:g=1.5," if buried else ""
        widen = "extrastereo=m=1.12," if narrow else ""
        if noise == "clean" and not buried and not narrow:
            return f"aformat=channel_layouts=stereo,loudnorm=I=-16:TP=-1.5:LRA=12,alimiter=limit=0.89:level=false,{tail}"
        return (
            "aformat=channel_layouts=stereo,highpass=f=30,"
            + presence
            + widen
            + f"loudnorm=I=-16:TP=-1.5:LRA=12,alimiter=limit=0.89:level=false,{tail}"
        )
    if profile == "dialogue_enhance":
        return (
            "aformat=channel_layouts=stereo,highpass=f=70,"
            "dialoguenhance=original=0.65:enhance=1.35:voice=8,"
            "equalizer=f=3000:width_type=q:width=1:g=1.5,"
            f"loudnorm=I=-16:TP=-1.5:LRA=11,alimiter=limit=0.89:level=false,{tail}"
        )
    if profile == "wide_stereo":
        return (
            "aformat=channel_layouts=stereo,extrastereo=m=1.35,"
            f"loudnorm=I=-16:TP=-1.5:LRA=12,alimiter=limit=0.89:level=false,{tail}"
        )
    if profile == "clean_restore":
        amount = "4" if noise == "clean" else "12"
        return (
            "aformat=channel_layouts=stereo,highpass=f=55,"
            f"afftdn=nr={amount}:nf=-50,"
            f"loudnorm=I=-16:TP=-1.5:LRA=11,alimiter=limit=0.89:level=false,{tail}"
        )
    if profile == "cinema_51":
        return _upmix_graph(6, duration, rate)
    if profile == "cinema_71":
        return _upmix_graph(8, duration, rate)
    if profile == "headphone_spatial":
        return (
            "aformat=channel_layouts=stereo,earwax,crossfeed=strength=0.3:range=0.45,"
            f"loudnorm=I=-16:TP=-1.5:LRA=11,alimiter=limit=0.89:level=false,{tail}"
        )
    return None


def _upmix_graph(count: int, duration: float, rate: int) -> str:
    end = max(duration, 0.05)
    sample = rate if rate >= 8000 else 48000
    # Center is the shared middle. Surrounds are difference, not copies of L/R.
    # LFE is only the low band.
    splits = ["fl", "fr", "fc", "lfe", "bl", "br"]
    if count == 8:
        splits.extend(["sl", "sr"])
    split = "".join(f"[{name}]" for name in splits)
    labels = "".join(f"[{name}o]" for name in splits)
    layout = "5.1" if count == 6 else "7.1"
    lines = [
        f"[0:a]aformat=channel_layouts=stereo,asplit={count}{split}",
        "[fl]pan=mono|c0=0.9*c0[flo]",
        "[fr]pan=mono|c0=0.9*c1[fro]",
        "[fc]pan=mono|c0=0.5*c0+0.5*c1,highpass=f=140,lowpass=f=5000[fco]",
        "[lfe]lowpass=f=110,pan=mono|c0=0.5*c0+0.5*c1,volume=0.55[lfeo]",
        "[bl]pan=mono|c0=0.42*c0-0.28*c1,volume=0.65[blo]",
        "[br]pan=mono|c0=0.42*c1-0.28*c0,volume=0.65[bro]",
    ]
    if count == 8:
        lines.append("[sl]pan=mono|c0=0.32*c0-0.12*c1,volume=0.55[slo]")
        lines.append("[sr]pan=mono|c0=0.32*c1-0.12*c0,volume=0.55[sro]")
    lines.append(
        f"{labels}amerge=inputs={count},aformat=channel_layouts={layout}:sample_rates={sample},"
        f"alimiter=limit=0.89:level=false,atrim=end={end:.3f},asetpts=PTS-STARTPTS"
    )
    return ";".join(lines)


def _encode_graph(source: str | Path, dest: str | Path, graph: str, profile: str, analysis: dict[str, Any]) -> None:
    use_complex = profile in _UPMIX_PROFILES and int(analysis.get("channels") or 0) < 6 and "amerge" in graph

    def _run(active: str) -> None:
        if use_complex:
            run_ffmpeg(["-i", str(source), "-vn", "-filter_complex", active, "-c:a", "pcm_s16le", str(dest)])
        else:
            run_ffmpeg(["-i", str(source), "-vn", "-af", active, "-c:a", "pcm_s16le", str(dest)])

    try:
        _run(graph)
    except RuntimeError:
        if "loudnorm=" not in graph:
            raise
        _run(re.sub(r"loudnorm=[^,]+,", "", graph))


def render_enhanced_audio(
    source: str | Path,
    dest: str | Path,
    profile: str,
    analysis: dict[str, Any],
    *,
    duration: float,
) -> dict[str, Any]:
    graph = filter_graph(profile, analysis, duration)
    out = Path(dest)
    out.parent.mkdir(parents=True, exist_ok=True)
    if graph is None:
        return {"mode": "copy", "profile": profile}
    _encode_graph(source, out, graph, profile, analysis)
    return {"mode": "processed", "profile": profile, "graph": graph}


def attach_soundtrack(
    video: str | Path,
    source: str | Path,
    dest: str | Path,
    profile: str,
    analysis: dict[str, Any],
    *,
    duration: float,
) -> dict[str, Any]:
    """Mux treated audio onto an already upscaled picture. Picture frames are copied."""
    video_path = Path(video)
    dest_path = Path(dest)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    if not analysis.get("hasAudio") or duration <= 0:
        if video_path.resolve() != dest_path.resolve():
            dest_path.write_bytes(video_path.read_bytes())
        return {"mode": "silent", "profile": "preserve_original", "channels": 0, "layout": ""}
    graph = filter_graph(profile, analysis, duration)
    if graph is None:
        try:
            run_ffmpeg(
                [
                    "-i",
                    str(video_path),
                    "-t",
                    f"{duration:.3f}",
                    "-i",
                    str(source),
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    "-c:v",
                    "copy",
                    "-c:a",
                    "copy",
                    "-t",
                    f"{duration:.3f}",
                    str(dest_path),
                ]
            )
            copied = probe_audio(dest_path)
            return {
                "mode": "copy",
                "profile": profile,
                "channels": int(copied.get("channels") or analysis.get("channels") or 0),
                "layout": str(copied.get("layout") or analysis.get("channelLayout") or ""),
            }
        except RuntimeError:
            graph = (
                _native_master(analysis, duration)
                if int(analysis.get("channels") or 0) >= 6
                else f"aformat=channel_layouts=stereo,{_trim(duration, int(analysis.get('sampleRate') or 48000))}"
            )
            profile = "preserve_original"
    wav = dest_path.with_suffix(".wav")
    _encode_graph(source, wav, graph, profile, analysis)
    channels, layout = output_layout(profile, analysis)
    run_ffmpeg(
        [
            "-i",
            str(video_path),
            "-i",
            str(wav),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "320k",
            "-ac",
            str(channels or 2),
            "-t",
            f"{duration:.3f}",
            str(dest_path),
        ]
    )
    try:
        wav.unlink(missing_ok=True)
    except OSError:
        pass
    probed = probe_audio(dest_path)
    return {
        "mode": "processed",
        "profile": profile,
        "channels": int(probed.get("channels") or channels or 0),
        "layout": str(probed.get("layout") or layout or ""),
    }


def side_to_mid_ratio(path: str | Path) -> float:
    """How much side energy a stereo file has. Used to spot a hollow, phasey widen."""
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(path),
            "-vn",
            "-af",
            "pan=mono|c0=0.5*c0+0.5*c1,volumedetect",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    mid = _db_from(proc.stderr or "", "mean_volume")
    proc2 = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(path),
            "-vn",
            "-af",
            "pan=mono|c0=0.5*c0-0.5*c1,volumedetect",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    side = _db_from(proc2.stderr or "", "mean_volume")
    mid_lin = _lin(mid)
    if mid_lin <= 0:
        return 0.0
    return _lin(side) / mid_lin


def probe_audio(path: str | Path) -> dict[str, Any]:
    info = ffprobe_json(path)
    streams = [s for s in (info.get("streams") or []) if s.get("codec_type") == "audio"]
    stream = streams[0] if streams else {}
    duration = 0.0
    try:
        duration = float((info.get("format") or {}).get("duration") or stream.get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    return {
        "streams": len(streams),
        "codec": stream.get("codec_name") or "",
        "sampleRate": int(stream.get("sample_rate") or 0),
        "channels": int(stream.get("channels") or 0),
        "layout": str(stream.get("channel_layout") or ""),
        "duration": duration,
    }


def peak_db(path: str | Path) -> float | None:
    _max, _mean = _measure(Path(path), "volumedetect", seconds=3600)
    return _max
