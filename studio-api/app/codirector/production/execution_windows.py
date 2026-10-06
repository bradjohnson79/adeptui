"""Automatic Execution Window planning — CD-owned.

HARD LAW (Brad / CLEAR P2+):
- Windows from scene duration + generator capability ONLY.
- Creator batchCount / chat "N batches" is NON-AUTHORITATIVE.
- Timed Prompt → ExecutionPrompt projection is TWO-TIER:
  PRIMARY = beat whose start falls in the window (stages the event once).
  OVERLAP CARRY = continue/in-progress wording ONLY into ACTION/CONTINUITY —
  NEVER re-fire the whole beat (Scene 3 double-stage guard).
- Generator switch MUST mint a fresh SceneTake / execution revision boundary
  BEFORE rematerializing windows (coordinate Systems/Gen — CD does not edit
  timeline_builder).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .generator_capability import (
    GeneratorCapabilityError,
    capability_batch_plan,
    resolve_max_single_generation_seconds,
)


@dataclass(frozen=True)
class ExecutionWindow:
    index: int
    start: float
    end: float

    @property
    def length(self) -> float:
        return max(0.0, float(self.end) - float(self.start))


@dataclass
class BeatProjection:
    """PRIMARY + OVERLAP CARRY for one Execution Window."""

    primary_beat_indices: list[int] = field(default_factory=list)
    carry_beat_indices: list[int] = field(default_factory=list)
    carry_lines: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GeneratorSwitchPlanDelta:
    """Handoff for Timeline Gen — CD does not rematerialize batchBlocks."""

    requires_new_scene_take: bool
    requires_revision_bump: bool
    reason: str
    previous_generator_id: str
    new_generator_id: str
    previous_windows: list[dict[str, float]]
    new_windows: list[dict[str, float]]
    new_batch_count: int
    note: str = (
        "Mint fresh SceneTake / execution revision BEFORE rematerializing "
        "batchBlocks. Same stk_ continuity chain must NOT survive changed "
        "window topology. CD will recompile BatchPrompts after Gen confirms "
        "new take/revision."
    )


def plan_execution_windows(
    *,
    duration_seconds: float,
    generator_id: str,
    requested_batch_count: int | None = None,
) -> list[ExecutionWindow]:
    """Capability-driven Execution Windows. Creator requested count ignored."""
    del requested_batch_count  # non-authoritative — capability owns the plan
    max_window = resolve_max_single_generation_seconds(generator_id)
    pairs = capability_batch_plan(
        duration_seconds=duration_seconds,
        max_single_generation_seconds=max_window,
        requested_batch_count=None,
    )
    return [
        ExecutionWindow(index=i, start=float(s), end=float(e))
        for i, (s, e) in enumerate(pairs)
    ]


def plan_spec_execution_windows(spec: Any) -> tuple[int, list[dict[str, float]]]:
    """Stamp batch_count + batchWindows on a SceneProductionSpec from capability."""
    windows = plan_execution_windows(
        duration_seconds=float(getattr(spec, "duration_seconds", 0) or 0),
        generator_id=str(getattr(spec, "generator_id", "") or "minimax-h3"),
    )
    if not windows:
        # Fail closed to one empty-safe window only when duration unknown
        return 1, []
    payload = [{"start": w.start, "end": w.end} for w in windows]
    return len(windows), payload


def region_intersects_window(
    region_start: float,
    region_end: float,
    window_start: float,
    window_end: float,
) -> bool:
    """True when [region_start, region_end) overlaps [window_start, window_end)."""
    return float(region_start) < float(window_end) and float(region_end) > float(window_start)


def project_beats_two_tier(
    *,
    scene_beats: list[Any],
    timed_beats: list[Any],
    window_start: float,
    window_end: float,
    scene_duration: float,
    batch_index: int,
    batch_count: int,
) -> BeatProjection:
    """PRIMARY start-in-window + OVERLAP CARRY continue/in-progress (never re-fire)."""
    span = max(float(scene_duration or 10.0), 1.0)
    start = float(window_start)
    end = float(window_end)
    count = max(int(batch_count or 1), 1)
    primary: list[int] = []
    carry: list[int] = []
    carry_lines: list[str] = []

    beats = list(scene_beats or [])
    timed = list(timed_beats or [])

    if not beats:
        return BeatProjection()

    if not timed:
        # No timing: partition by order (PRIMARY only — no overlap carry).
        total = len(beats)
        lo = round(batch_index * total / count)
        hi = round((batch_index + 1) * total / count)
        return BeatProjection(primary_beat_indices=[b.index for b in beats[lo:hi]])

    for beat in beats:
        idx = int(getattr(beat, "index", 0) or 0)
        if idx >= len(timed):
            assigned = min(int(idx * count / max(len(beats), 1)), count - 1)
            if assigned == batch_index:
                primary.append(idx)
            continue
        tb = timed[idx]
        beat_start = min(max(float(getattr(tb, "start_sec", 0) or 0), 0.0), span)
        beat_end = min(max(float(getattr(tb, "end_sec", beat_start) or beat_start), beat_start), span)
        desc = str(
            getattr(tb, "description", None)
            or getattr(beat, "description", None)
            or ""
        ).strip()

        # PRIMARY: start falls in this window (last window catches late starts).
        if start <= beat_start < end or (batch_index == count - 1 and beat_start >= start):
            primary.append(idx)
            continue

        # OVERLAP CARRY: intersects window but started earlier — never re-fire
        if beat_start < start and region_intersects_window(beat_start, beat_end, start, end):
            carry.append(idx)
            label = desc or f"beat {idx}"
            carry_lines.append(
                f"Continue in progress (do not re-stage): {label}."
            )

    # Empty PRIMARY fallback: do NOT promote carry to primary (would re-fire).
    # Leave primary empty; caller may still emit continuity from carry_lines.
    return BeatProjection(
        primary_beat_indices=primary,
        carry_beat_indices=carry,
        carry_lines=carry_lines,
    )


def project_timed_regions_two_tier(
    regions: list[Any],
    *,
    window_start: float,
    window_end: float,
) -> tuple[list[Any], list[str]]:
    """PRIMARY regions (start in window) + CARRY lines for spanning regions."""
    primary: list[Any] = []
    carry_lines: list[str] = []
    start = float(window_start)
    end = float(window_end)
    for region in regions or []:
        rs = float(getattr(region, "start", 0) or 0)
        re = float(getattr(region, "end", 0) or 0)
        text = str(getattr(region, "text", "") or "").strip()
        if start <= rs < end:
            primary.append(region)
        elif rs < start and region_intersects_window(rs, re, start, end) and text:
            carry_lines.append(f"Continue in progress (do not re-stage): {text}")
    return primary, carry_lines


def generator_switch_plan_delta(
    *,
    previous_generator_id: str,
    new_generator_id: str,
    duration_seconds: float,
    previous_windows: list[dict[str, float]] | None = None,
) -> GeneratorSwitchPlanDelta:
    """Build Gen/Systems handoff when generator changes window topology."""
    prev = str(previous_generator_id or "")
    new = str(new_generator_id or "")
    new_windows = plan_execution_windows(
        duration_seconds=duration_seconds, generator_id=new
    )
    new_payload = [{"start": w.start, "end": w.end} for w in new_windows]
    prev_payload = list(previous_windows or [])
    topology_changed = [
        (round(float(w.get("start", 0)), 4), round(float(w.get("end", 0)), 4))
        for w in prev_payload
    ] != [(round(w.start, 4), round(w.end, 4)) for w in new_windows]
    must_mint = (prev != new) or topology_changed
    return GeneratorSwitchPlanDelta(
        requires_new_scene_take=must_mint,
        requires_revision_bump=must_mint,
        reason=(
            "generator_switch_window_topology_change"
            if topology_changed or prev != new
            else "generator_unchanged"
        ),
        previous_generator_id=prev,
        new_generator_id=new,
        previous_windows=prev_payload,
        new_windows=new_payload,
        new_batch_count=max(len(new_windows), 1),
    )
