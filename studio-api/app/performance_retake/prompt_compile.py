"""Performance Retake prompt compiler — certified H3 owner Comfy dialect.

Dialect (semantic_contract.py, FM4-certified on the Timeline R2V path):
- ``<subject N> is Name.`` — 1-based, N matches ref_image_(N-1) connection order.
- ``<Audio j> is the voice-timbre reference for <subject N> (SN).``
- Dialogue lines: ``<subject N> (SN): "line"``
- Retake addition: ``<Video 1>`` binds the source window (ref_videos.ref_video_0).

Beats compile to timecoded lines; silence beats compile to explicit
NO DIALOGUE constraints — silence is authoritative, never implied.
"""

from __future__ import annotations

import re

from .contracts import PerformanceRetakeSpec, RetakeBeat


class PromptCompileError(ValueError):
    """The performance prompt violates the retake contract."""


def _timecode(seconds: float) -> str:
    total = max(0.0, float(seconds))
    minutes = int(total // 60)
    secs = total - minutes * 60
    return f"{minutes:02d}:{secs:04.1f}"


def _window_label(beat: RetakeBeat, window_start: float) -> str:
    """Beat timecodes are absolute on the scene timeline; the generated clip
    starts at the window IN, so prompt timecodes are window-relative."""
    return f"[{_timecode(beat.startSec - window_start)}-{_timecode(beat.endSec - window_start)}]"


def compile_performance_prompt(
    spec: PerformanceRetakeSpec,
    *,
    shot_observation: str = "",
    forbidden_dialogue: list[str] | None = None,
) -> str:
    """Compile the MiniMax H3 Input Text for the retake render.

    ``shot_observation`` is the Qwen2.5-Omni pre-review summary of the source
    window (camera, framing, action). ``forbidden_dialogue`` carries the
    scene's previous dialogue lines; if any leaks into the compiled prompt
    the compile fails (old-dialogue leak guard, governing doc §6.4).
    """
    sheets = spec.references.characterSheets
    subject_index: dict[str, int] = {
        sheet.characterId: position + 1 for position, sheet in enumerate(sheets)
    }

    lines: list[str] = []
    for sheet in sheets:
        index = subject_index[sheet.characterId]
        name = next(
            (b.characterName for b in spec.dialogue_beats if b.characterId == sheet.characterId),
            None,
        ) or "this character"
        lines.append(f"<subject {index}> is {name}.")

    if spec.references.sourceVideo:
        lines.append(
            "<Video 1> is the source take — keep its camera, framing, set, and "
            "action. Re-perform it with the new dialogue below."
        )

    beats = sorted(spec.beats, key=lambda b: (b.startSec, b.endSec))
    audio_index = 0
    for beat in beats:
        if beat.kind != "dialogue":
            continue
        audio_index += 1
        subject = subject_index[beat.characterId or ""]
        lines.append(
            f"<Audio {audio_index}> is the voice-timbre reference for "
            f"<subject {subject}> (S{subject})."
        )

    observation = " ".join(str(shot_observation or "").split())
    if observation:
        lines.append(f"Source take observation: {observation}")

    audio_index = 0
    for beat in beats:
        label = _window_label(beat, spec.window.startSec)
        if beat.kind == "silence":
            lines.append(
                f"{label} No dialogue. No speech. No singing. Ambient sound only."
            )
            continue
        audio_index += 1
        subject = subject_index[beat.characterId or ""]
        line = " ".join(str(beat.line or "").split())
        lines.append(f'{label} <subject {subject}> (S{subject}): "{line}"')

    prompt = "\n".join(lines)
    assert_prompt_honesty(prompt, spec, forbidden_dialogue=forbidden_dialogue)
    return prompt


def assert_prompt_honesty(
    prompt: str,
    spec: PerformanceRetakeSpec,
    *,
    forbidden_dialogue: list[str] | None = None,
) -> None:
    """Both directions: no beat line dropped/invented, no old dialogue leaked."""
    for beat in spec.dialogue_beats:
        line = " ".join(str(beat.line or "").split())
        if line not in prompt:
            raise PromptCompileError(
                f"dialogue line for {beat.characterName} is missing from the prompt: {line!r}"
            )
    lowered = prompt.lower()
    for old in forbidden_dialogue or []:
        token = " ".join(str(old or "").split()).strip().strip('"').lower()
        if token and token in lowered:
            raise PromptCompileError(
                f"old dialogue leaked into the performance prompt: {old!r}"
            )
    for beat in spec.beats:
        if beat.kind == "silence":
            label = _window_label(beat, spec.window.startSec)
            pattern = re.compile(
                rf"{re.escape(label)}\s+No dialogue\. No speech\.", re.IGNORECASE
            )
            if not pattern.search(prompt):
                raise PromptCompileError(
                    f"silence beat {label} lost its explicit NO DIALOGUE constraint"
                )
