"""Performance Retake contract — spec model + validation.

Pure data + validation. No I/O, no Comfy, no ffmpeg.

Invariants (governing doc §3):
- Beats partition the window with no overlap; silence beats are explicit.
- Every dialogue beat carries character identity, the exact line, and a
  voiceAssetId rendered from that exact line by the character's approved
  Qwen3-TTS voice.
- characterSheets <= 8 (9-image node cap; source video uses the video
  channel, not image slots).
- Window bounds stay inside the master duration.
"""

from __future__ import annotations

from dataclasses import dataclass, field

SPEC_VERSION = 1

MAX_CHARACTER_SHEETS = 8
MAX_REF_VIDEOS = 3  # live MiniMaxH3ReferenceToVideo schema ceiling


class PerformanceRetakeError(ValueError):
    """Base class for Performance Retake contract violations."""


@dataclass
class RetakeWindow:
    startSec: float
    endSec: float
    scope: str = "whole_shot"  # whole_shot | sub_window
    boundarySource: str = "creator_manual"  # qwen_shot_analysis | creator_manual

    @property
    def length(self) -> float:
        return self.endSec - self.startSec


@dataclass
class RetakeBeat:
    kind: str  # dialogue | silence
    startSec: float
    endSec: float
    characterId: str | None = None
    characterName: str | None = None
    line: str | None = None
    voiceAssetId: str | None = None

    @property
    def length(self) -> float:
        return self.endSec - self.startSec


@dataclass
class CharacterSheetRef:
    characterId: str
    assetId: str


@dataclass
class RetakeReferences:
    characterSheets: list[CharacterSheetRef] = field(default_factory=list)
    sourceVideo: bool = True
    includeSourceAudio: bool = False  # old-dialogue leak guard — default OFF


@dataclass
class PerformanceRetakeSpec:
    projectId: str
    sceneId: str
    window: RetakeWindow
    beats: list[RetakeBeat]
    references: RetakeReferences
    masterDurationSec: float
    generator: str = "minimax-h3-r2v-local"  # | seedance-2.5-hosted-fallback
    quality: str = "quality"  # quality | fast
    qwenPreReview: bool = True
    qwenPostReview: bool = True
    specVersion: int = SPEC_VERSION

    @property
    def dialogue_beats(self) -> list[RetakeBeat]:
        return [b for b in self.beats if b.kind == "dialogue"]


def validate_spec(spec: PerformanceRetakeSpec) -> PerformanceRetakeSpec:
    """Raise PerformanceRetakeError on any contract violation. Returns spec."""
    w = spec.window
    if w.scope not in {"whole_shot", "sub_window"}:
        raise PerformanceRetakeError(f"window.scope {w.scope!r} must be whole_shot | sub_window")
    if w.startSec < 0.0:
        raise PerformanceRetakeError("window.startSec is negative")
    if w.startSec >= w.endSec:
        raise PerformanceRetakeError(
            f"window start {w.startSec} is not before end {w.endSec}"
        )
    if spec.masterDurationSec > 0 and w.endSec > spec.masterDurationSec + 1e-9:
        raise PerformanceRetakeError(
            f"window end {w.endSec} exceeds master duration {spec.masterDurationSec}"
        )
    if spec.quality not in {"quality", "fast"}:
        raise PerformanceRetakeError(f"quality {spec.quality!r} must be quality | fast")

    if not spec.beats:
        raise PerformanceRetakeError("spec has no beats — declare dialogue and silence explicitly")

    beats = sorted(spec.beats, key=lambda b: (b.startSec, b.endSec))
    for beat in beats:
        if beat.kind not in {"dialogue", "silence"}:
            raise PerformanceRetakeError(f"beat kind {beat.kind!r} must be dialogue | silence")
        if beat.startSec < w.startSec - 1e-9 or beat.endSec > w.endSec + 1e-9:
            raise PerformanceRetakeError(
                f"beat [{beat.startSec}, {beat.endSec}] escapes the retake window "
                f"[{w.startSec}, {w.endSec}]"
            )
        if beat.startSec >= beat.endSec:
            raise PerformanceRetakeError(
                f"beat start {beat.startSec} is not before end {beat.endSec}"
            )
        if beat.kind == "dialogue":
            if not (beat.characterId or "").strip():
                raise PerformanceRetakeError("dialogue beat is missing characterId")
            if not (beat.characterName or "").strip():
                raise PerformanceRetakeError("dialogue beat is missing characterName")
            if not (beat.line or "").strip():
                raise PerformanceRetakeError("dialogue beat is missing its line")
            if not (beat.voiceAssetId or "").strip():
                raise PerformanceRetakeError(
                    f"dialogue beat for {beat.characterName} is missing voiceAssetId — "
                    "render the exact line with the character's approved voice first"
                )
        else:  # silence is authoritative — it must not smuggle dialogue
            if (beat.line or "").strip():
                raise PerformanceRetakeError("silence beat must not carry a line")
            if (beat.voiceAssetId or "").strip():
                raise PerformanceRetakeError("silence beat must not carry a voiceAssetId")

    for prev, nxt in zip(beats, beats[1:]):
        if prev.endSec > nxt.startSec + 1e-9:
            raise PerformanceRetakeError(
                f"beats overlap: [{prev.startSec}, {prev.endSec}] vs "
                f"[{nxt.startSec}, {nxt.endSec}]"
            )

    sheets = spec.references.characterSheets
    if len(sheets) > MAX_CHARACTER_SHEETS:
        raise PerformanceRetakeError(
            f"{len(sheets)} character sheets exceed the {MAX_CHARACTER_SHEETS}-sheet retake ceiling"
        )
    dialogue_chars = {b.characterId for b in beats if b.kind == "dialogue"}
    sheet_chars = {s.characterId for s in sheets}
    missing = dialogue_chars - sheet_chars
    if missing:
        raise PerformanceRetakeError(
            f"dialogue characters without a character sheet reference: {sorted(missing)}"
        )
    if len(sheet_chars) != len(sheets):
        raise PerformanceRetakeError("duplicate characterId in characterSheets")

    return spec
