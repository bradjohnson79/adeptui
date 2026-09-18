"""RetakeContextPackage - ESTABLISHED SCENE + TARGET BEAT + USER DELTA.

LAW: Re-Take text is DELTA, not a new scene prompt.
Compiled = established setup + target beat (primary shot) + neighbor context
+ user delta + hard constraints (T1>T2>T3>T4).
Timeline compile path authoritative. No chat dumps. No character_identity_bind.
No fake I2V. H3: adapters have supportsNegativePrompt=False / supportsCameraControls=False
— crew-out and camera override are prompt-law only (no fake negativePrompt/cameraMotion).
"""

from __future__ import annotations

import re
from typing import Any

_SHOT_MARK_RE = re.compile(r"\[SHOT\s*(\d+)[^\]]*\]", re.IGNORECASE)
_SHOT_HEADER_RE = re.compile(r"\[SHOT\s*\d+[^\]]*\]", re.IGNORECASE)
_CU_RE = re.compile(r"\b(full\s+close\s*up|close[\s-]*up|MCU|CU|tight)\b", re.IGNORECASE)
_CREW_RE = re.compile(r"\b(film\s+crew|crew|interviewer|camera\s+crew|documentary)\b", re.IGNORECASE)
_PARA_SPLIT_RE = re.compile(r"\n\s*\n")

# Lines/sentences that assert crew IS present / being interviewed (contradict crew-out).
_CREW_PRESENT_SENT_RE = re.compile(
    r"[^.!\n]*(?:"
    r"documentary\s+film\s+crew|"
    r"film\s+crew\s+with\s+them|"
    r"being\s+interviewed\s+by\s+(?:the\s+)?(?:film\s+)?crew|"
    r"interviewer\s+behind\s+the\s+camera|"
    r"crew\s+present|"
    r"camera\s+operators?\s+(?:are\s+)?(?:with|visible|in\s+frame)|"
    r"there\s+is\s+a\s+(?:documentary\s+)?(?:film\s+)?crew"
    r")[^.!\n]*[.!]?",
    re.IGNORECASE,
)

# Default effective H3 exclusions (prompt-law; adapter has no negative socket).
_DEFAULT_H3_EXCLUSIONS: list[str] = [
    "film crew",
    "documentary crew",
    "interviewer",
    "camera operators",
    "camera crew",
    "boom mic operator",
    "crew in frame",
    "wide establishing interview set with crew",
]


def _seg_text(seg: Any) -> str:
    return str(getattr(seg, "text", None) or "").strip()


def _seg_start(seg: Any) -> float:
    try:
        return float(getattr(seg, "start", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _seg_length(seg: Any) -> float:
    try:
        return float(getattr(seg, "length", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _intervals_overlap(a0: float, a_len: float, b0: float, b_len: float) -> bool:
    a1 = a0 + max(0.0, a_len)
    b1 = b0 + max(0.0, b_len)
    return a0 < b1 and b0 < a1



# ---------------------------------------------------------------------------
# Unauthorized production equipment AUTHORITY (prompt-law; Final Check consumes)
# ONE authority for diegetic crew/boom/camera-crew Hard Defect — do not invent
# a second equipment exclusion list elsewhere.
# ---------------------------------------------------------------------------

UNAUTHORIZED_PRODUCTION_EQUIPMENT_CODE = "UNAUTHORIZED_PRODUCTION_EQUIPMENT"
UNAUTHORIZED_PRODUCTION_EQUIPMENT_AUTHORITY = "retake_context_package.prompt_law_crew_out"

# Canonical exclusion phrases (same list H3 HARD CONSTRAINTS use).
UNAUTHORIZED_EQUIPMENT_EXCLUSIONS: list[str] = list(_DEFAULT_H3_EXCLUSIONS)

# Observation labels Omni visual / creator QC may emit → map to equipment Hard.
UNAUTHORIZED_EQUIPMENT_OBSERVATION_LABELS: tuple[str, ...] = (
    "film crew",
    "documentary crew",
    "camera crew",
    "camera operator",
    "camera operators",
    "boom mic",
    "boom mic operator",
    "boom operator",
    "boom in frame",
    "crew in frame",
    "interviewer",
    "diegetic crew",
    "production equipment in frame",
    "microphone boom",
    "clapperboard",
    "slate in frame",
)

# Disposition ids — ONE authority for in-frame vs off-screen vs uncertain (12B policy).
CREW_OBSERVATION_HARD = "hard"
CREW_OBSERVATION_AUTHORIZED_OFFSCREEN = "authorized_offscreen"
CREW_OBSERVATION_UNCERTAIN = "uncertain"
CREW_OBSERVATION_NONE = "none"

# Labels that themselves assert diegetic / in-picture gear (no extra cue required).
_INHERENTLY_INFRAME_EQUIPMENT_LABELS: tuple[str, ...] = (
    "crew in frame",
    "boom in frame",
    "boom mic",
    "boom mic operator",
    "boom operator",
    "boom pole",
    "microphone boom",
    "diegetic crew",
    "production equipment in frame",
    "clapperboard",
    "slate in frame",
)

# Ambiguous role/crew nouns — Hard only with in-frame evidence; off-screen = authorized.
_AMBIGUOUS_CREW_ROLE_LABELS: tuple[str, ...] = (
    "interviewer",
    "film crew",
    "documentary crew",
    "camera crew",
    "camera operator",
    "camera operators",
)

_OFFSCREEN_CREW_RE = re.compile(
    r"\b("
    r"off[\s-]*screen|behind\s+(?:the\s+)?camera|out\s+of\s+(?:frame|shot|picture)|"
    r"not\s+(?:visible|seen|in\s+frame|in\s+shot)|unseen|off\s+camera|"
    r"voice[\s-]*over\s+interviewer|authorized\s+interview(?:\s+setup)?"
    r")\b",
    re.IGNORECASE,
)

_INFRAME_CREW_RE = re.compile(
    r"\b("
    r"in[\s-]*frame|in[\s-]*shot|in\s+(?:the\s+)?picture|"
    r"visible(?:\s+in\s+(?:the\s+)?(?:picture|frame|shot|background))?|"
    r"on[\s-]*camera|on[\s-]*screen|appears?\s+on\s+screen|"
    r"seen\s+in\s+(?:the\s+)?(?:frame|shot|picture)|"
    r"crew\s+members?\s+visible|cameras?\s+(?:and\s+crew\s+)?(?:are\s+)?visible|"
    r"operator\s+visible|cameras?\s+visible|crew\s+visible|"
    r"diegetic\s+crew|boom\s+(?:mic|pole|operator)|clapperboard|slate\s+in\s+frame"
    r")\b",
    re.IGNORECASE,
)


def classify_crew_equipment_observation(
    text: str | None, *, context: str | None = None
) -> str:
    """ONE authority disposition for crew/equipment Omni observations (12B).

    - hard: in-frame / visible in picture / on camera / inherently diegetic gear
    - authorized_offscreen: behind camera / off-screen / authorized interview setup
      without visible crew in frame (Primary 12B refire prompt)
    - uncertain: bare role label (e.g. "interviewer") with no framing evidence —
      review only; absence of in-frame evidence ≠ presence (cross-modality law)
    - none: no crew/equipment observation
    """
    raw = str(text or "").strip().lower()
    ctx_extra = str(context or "").strip().lower()
    blob = f"{raw} {ctx_extra}".strip()
    if not blob:
        return CREW_OBSERVATION_NONE

    has_label = any(lab in blob for lab in UNAUTHORIZED_EQUIPMENT_OBSERVATION_LABELS) or bool(
        _CREW_RE.search(blob)
    )
    if not has_label:
        return CREW_OBSERVATION_NONE

    has_inframe = bool(_INFRAME_CREW_RE.search(blob)) or any(
        lab in blob for lab in _INHERENTLY_INFRAME_EQUIPMENT_LABELS
    )
    has_offscreen = bool(_OFFSCREEN_CREW_RE.search(blob))

    # Visible/in-frame evidence wins over off-screen interview-setup language.
    if has_inframe:
        return CREW_OBSERVATION_HARD
    if has_offscreen:
        return CREW_OBSERVATION_AUTHORIZED_OFFSCREEN

    # Bare interviewer/crew role with no framing → UNCERTAIN (do not auto-retake).
    if any(lab in raw for lab in _AMBIGUOUS_CREW_ROLE_LABELS) or any(
        lab in blob for lab in _AMBIGUOUS_CREW_ROLE_LABELS
    ):
        return CREW_OBSERVATION_UNCERTAIN

    return CREW_OBSERVATION_UNCERTAIN


def unauthorized_equipment_authority() -> dict:
    """Public authority packet for Final Check equipment / camera Hard Defect."""
    return {
        "authoritySource": UNAUTHORIZED_PRODUCTION_EQUIPMENT_AUTHORITY,
        "code": UNAUTHORIZED_PRODUCTION_EQUIPMENT_CODE,
        "exclusions": list(UNAUTHORIZED_EQUIPMENT_EXCLUSIONS),
        "observationLabels": list(UNAUTHORIZED_EQUIPMENT_OBSERVATION_LABELS),
        "taxonomy": "Hard",
        "note": (
            "ONE authority (prompt_law_crew_out). Interviewer/crew behind camera OFF-SCREEN "
            "is AUTHORIZED (12B). CREW_IN_FRAME Hard only for IN-FRAME gear/operators. "
            "Bare 'interviewer' without in-frame evidence → UNCERTAIN / review, not auto-destroy. "
            "Creative camera taste never auto-retakes."
        ),
        "neverInventFromBadOutput": True,
        "offscreenAuthorized": True,
        "uncertainWithoutInFrameEvidence": True,
        "dispositions": {
            "hard": CREW_OBSERVATION_HARD,
            "authorizedOffscreen": CREW_OBSERVATION_AUTHORIZED_OFFSCREEN,
            "uncertain": CREW_OBSERVATION_UNCERTAIN,
            "none": CREW_OBSERVATION_NONE,
        },
    }


def observation_matches_unauthorized_equipment(text: str | None, *, context: str | None = None) -> bool:
    """True only for Hard IN-FRAME diegetic crew/equipment (not off-screen, not uncertain)."""
    return (
        classify_crew_equipment_observation(text, context=context) == CREW_OBSERVATION_HARD
    )


def established_scene_text(batch: Any) -> str:
    """Master Timed Prompt from batch promptSegments (full text for inheritance)."""
    parts: list[str] = []
    for seg in getattr(batch, "promptSegments", None) or []:
        timed = _seg_text(seg)
        if timed:
            parts.append(timed)
    return "\n".join(parts).strip()


def _neutralize_crew_present_prose(setup: str) -> str:
    """Strip crew-present / interview-set assertions; keep location/style/cast.

    Do not leave crew-present + crew-out contradiction in the H3-bound prompt.
    """
    text = (setup or "").strip()
    if not text:
        return ""
    cleaned = _CREW_PRESENT_SENT_RE.sub("", text)
    # Collapse leftover whitespace / empty paragraphs
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"  +", " ", cleaned).strip()
    # If we stripped crew-present language, ensure an explicit crew-out remains
    if _CREW_RE.search(text) or "crew" in text.lower() or "interview" in text.lower():
        if "out of frame" not in cleaned.lower() and "out of shot" not in cleaned.lower():
            cleaned = (
                cleaned.rstrip()
                + "\n\nFilm crew, documentary crew, interviewer, and camera operators stay OUT OF FRAME."
            )
    return cleaned.strip()


def established_setup_only(established: str) -> str:
    """Setup / style / cast context WITHOUT the [SHOT n] sequence.

    Range retake delivery must not re-open on Wide 2 Shot just because the
    master Timed Prompt starts with an establishing shot list.
    Crew-present prose is neutralized so it cannot contradict HARD CONSTRAINTS.
    """
    text = (established or "").strip()
    if not text:
        return ""
    m = _SHOT_HEADER_RE.search(text)
    if not m:
        setup = text
    else:
        setup = text[: m.start()].strip()
    if not setup:
        setup = text.split("\n\n", 1)[0].strip()
    return _neutralize_crew_present_prose(setup)


def _shot_blocks(text: str) -> list[tuple[int, int, str, int | None]]:
    """Return (start_char, end_char, block_text, shot_num)."""
    marks = list(_SHOT_MARK_RE.finditer(text))
    if not marks:
        return []
    blocks: list[tuple[int, int, str, int | None]] = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        block = text[m.start() : end].strip()
        num = None
        try:
            num = int(m.group(1))
        except Exception:
            num = None
        if block:
            blocks.append((m.start(), end, block, num))
    return blocks


def _primary_shot_index(
    blocks: list[tuple[int, int, str, int | None]],
    *,
    seg_s: float,
    seg_l: float,
    range_start: float,
    range_end: float,
    user_delta: str = "",
) -> int:
    """Pick ONE primary shot for the repair window.

    Prefer: (1) shot whose center is closest to range midpoint among overlaps,
    (2) CU/MCU shot if user delta names a single speaker and that shot matches,
    (3) never keep every overlapping shot (Shot3 bleed).
    """
    n = len(blocks)
    if n == 0:
        return -1
    mid = (range_start + range_end) / 2.0
    scored: list[tuple[float, int]] = []
    delta_l = (user_delta or "").lower()
    for i, (_c0, _c1, block, _num) in enumerate(blocks):
        shot_t0 = seg_s + (seg_l * i / n)
        shot_t1 = seg_s + (seg_l * (i + 1) / n)
        if not (shot_t1 > range_start and shot_t0 < range_end):
            continue
        center = (shot_t0 + shot_t1) / 2.0
        overlap = max(0.0, min(shot_t1, range_end) - max(shot_t0, range_start))
        span = max(1e-6, range_end - range_start)
        overlap_frac = overlap / span
        dist = abs(center - mid)
        cu_boost = -0.35 if _CU_RE.search(block) and ("korri" in delta_l or "close" in delta_l or "cu" in delta_l) else 0.0
        name_boost = 0.0
        for name in ("korri", "anadriya"):
            if name in delta_l and name in block.lower():
                name_boost -= 0.25
                break
        score = dist - (overlap_frac * 0.5) + cu_boost + name_boost
        scored.append((score, i))
    if not scored:
        for i, _b in enumerate(blocks):
            shot_t0 = seg_s + (seg_l * i / n)
            shot_t1 = seg_s + (seg_l * (i + 1) / n)
            center = (shot_t0 + shot_t1) / 2.0
            scored.append((abs(center - mid), i))
    scored.sort(key=lambda x: x[0])
    return scored[0][1]


def _block_label(block: str, num: int | None, fallback_i: int) -> str:
    header = (block or "").split("\n", 1)[0].strip()
    if header:
        return header
    return f"SHOT {num if num is not None else fallback_i + 1}"


def extract_local_beat(
    *,
    established: str,
    batch: Any,
    range_start: float,
    range_length: float,
    user_delta: str = "",
) -> dict[str, Any]:
    """Extract PRIMARY shot/beat for the range window — not every overlapping shot.

    Prefer a single [SHOT] block centered on the range midpoint so a mark that
    slightly bleeds into Shot3 does not pull Anadriya OTS into a Korri CU repair.
    Neighbor shots are returned as prev/next context only (never generation scope).
    """
    range_start = max(0.0, float(range_start or 0.0))
    range_length = max(0.0, float(range_length or 0.0))
    range_end = range_start + range_length
    segments = list(getattr(batch, "promptSegments", None) or [])
    overlapping = [
        seg
        for seg in segments
        if _seg_text(seg)
        and _intervals_overlap(_seg_start(seg), _seg_length(seg), range_start, range_length)
    ]
    if not overlapping and segments:
        mid = (range_start + range_end) / 2.0
        overlapping = [
            min(
                segments,
                key=lambda s: abs((_seg_start(s) + _seg_length(s) / 2.0) - mid),
            )
        ]

    pieces: list[str] = []
    method = "none"
    dropped: list[str] = []
    primary_header = ""
    prev_beat_text = ""
    next_beat_text = ""
    prev_beat_label = ""
    next_beat_label = ""
    overlapping_shot_labels: list[str] = []

    for seg in overlapping:
        text = _seg_text(seg)
        seg_s = _seg_start(seg)
        seg_l = _seg_length(seg) or max(range_length, 1.0)
        blocks = _shot_blocks(text)
        if len(blocks) >= 2:
            # Collect all shots that overlap the marked range (for UX warning)
            n = len(blocks)
            for j, (_a, _b, blk, num) in enumerate(blocks):
                shot_t0 = seg_s + (seg_l * j / n)
                shot_t1 = seg_s + (seg_l * (j + 1) / n)
                if shot_t1 > range_start and shot_t0 < range_end:
                    overlapping_shot_labels.append(_block_label(blk, num, j))

            primary_i = _primary_shot_index(
                blocks,
                seg_s=seg_s,
                seg_l=seg_l,
                range_start=range_start,
                range_end=range_end,
                user_delta=user_delta,
            )
            if primary_i >= 0:
                primary = blocks[primary_i][2]
                pieces.append(primary)
                primary_header = primary.split("\n", 1)[0].strip()
                method = "primary_shot"
                if primary_i > 0:
                    prev_beat_text = blocks[primary_i - 1][2]
                    prev_beat_label = _block_label(
                        prev_beat_text, blocks[primary_i - 1][3], primary_i - 1
                    )
                if primary_i + 1 < len(blocks):
                    next_beat_text = blocks[primary_i + 1][2]
                    next_beat_label = _block_label(
                        next_beat_text, blocks[primary_i + 1][3], primary_i + 1
                    )
                for j, (_a, _b, blk, num) in enumerate(blocks):
                    if j == primary_i:
                        continue
                    shot_t0 = seg_s + (seg_l * j / len(blocks))
                    shot_t1 = seg_s + (seg_l * (j + 1) / len(blocks))
                    if shot_t1 > range_start and shot_t0 < range_end:
                        dropped.append(f"SHOT {num if num is not None else j + 1}")
                continue
        # Proportional character slice expanded to paragraph boundaries
        if seg_l > 0 and len(text) > 80 and range_length > 0 and range_length < seg_l * 0.85:
            rel0 = max(0.0, (range_start - seg_s) / seg_l)
            rel1 = min(1.0, (range_end - seg_s) / seg_l)
            c0 = int(len(text) * rel0)
            c1 = max(c0 + 1, int(len(text) * rel1))
            left = text.rfind("\n\n", 0, c0)
            right = text.find("\n\n", c1)
            c0 = 0 if left < 0 else left + 2
            c1 = len(text) if right < 0 else right
            sliced = text[c0:c1].strip()
            sub_blocks = _shot_blocks(sliced)
            if len(sub_blocks) >= 2:
                pi = _primary_shot_index(
                    sub_blocks,
                    seg_s=0.0,
                    seg_l=float(len(sub_blocks)),
                    range_start=0.0,
                    range_end=float(len(sub_blocks)),
                    user_delta=user_delta,
                )
                if pi >= 0:
                    pieces.append(sub_blocks[pi][2])
                    method = "primary_shot_from_slice"
                    primary_header = sub_blocks[pi][2].split("\n", 1)[0].strip()
                    if pi > 0:
                        prev_beat_text = sub_blocks[pi - 1][2]
                        prev_beat_label = _block_label(
                            prev_beat_text, sub_blocks[pi - 1][3], pi - 1
                        )
                    if pi + 1 < len(sub_blocks):
                        next_beat_text = sub_blocks[pi + 1][2]
                        next_beat_label = _block_label(
                            next_beat_text, sub_blocks[pi + 1][3], pi + 1
                        )
                    continue
            if sliced and len(sliced) < len(text) * 0.9:
                pieces.append(sliced)
                method = "proportional_paragraph"
                continue
        pieces.append(text)
        method = "nearest_segment" if method == "none" else method

    local = "\n\n".join(p for p in pieces if p).strip()
    full_dump = bool(local) and local == established.strip() and len(established) > 120
    if full_dump and range_length > 0:
        paras = [p.strip() for p in _PARA_SPLIT_RE.split(established) if p.strip()]
        if len(paras) >= 3:
            planned = float(getattr(getattr(batch, "duration", None), "plannedDuration", 0) or 0) or (
                max((_seg_start(s) + _seg_length(s) for s in segments), default=range_end) or range_end
            )
            mid_ratio = 0.5
            if planned > 0:
                mid_ratio = min(0.99, max(0.0, ((range_start + range_end) / 2.0) / planned))
            idx = int(mid_ratio * (len(paras) - 1))
            lo = max(0, idx - 1)
            hi = min(len(paras), idx + 2)
            local = "\n\n".join(paras[lo:hi]).strip()
            method = "paragraph_cluster"
            full_dump = local == established.strip()

    spans_multiple = bool(dropped) or len({x.upper() for x in overlapping_shot_labels}) > 1
    range_too_wide = bool(dropped) or spans_multiple

    return {
        "text": local,
        "method": method,
        "isFullDump": bool(full_dump),
        "rangeStart": range_start,
        "rangeLength": range_length,
        "primaryShotHeader": primary_header or None,
        "droppedOverlappingShots": dropped,
        "rangeTooWideHint": range_too_wide,
        "spansMultipleShots": spans_multiple,
        "overlappingShotLabels": overlapping_shot_labels,
        "prevBeatText": prev_beat_text or None,
        "prevBeatLabel": prev_beat_label or None,
        "nextBeatText": next_beat_text or None,
        "nextBeatLabel": next_beat_label or None,
    }


def _t1_overrides_from_delta(user_delta: str, local_beat: str) -> list[str]:
    """T1 retake overrides derived from USER DELTA (+ target framing)."""
    lines: list[str] = []
    delta = (user_delta or "").strip()
    delta_l = delta.lower()
    header = ""
    m = _SHOT_HEADER_RE.search(local_beat or "")
    if m:
        header = m.group(0).strip("[]")
    if delta:
        lines.append(f"USER DELTA (authoritative for this repair): {delta}")
    if header and (_CU_RE.search(header) or _CU_RE.search(delta) or "close" in delta_l):
        lines.append(
            f"Framing override from target: {header} — hold for whole TARGET BEAT "
            "(do not open wide / do not cut to other shot sizes)."
        )
    elif _CU_RE.search(local_beat or "") or _CU_RE.search(delta):
        lines.append("Framing override: tight close-up / MCU for whole TARGET BEAT.")
    if "korri" in delta_l and ("not anadriya" in delta_l or "anadriya not" in delta_l or "not Anadriya".lower() in delta_l):
        lines.append("Speaker ownership (T1): Korri speaks the line — Anadriya does not.")
    elif "korri" in delta_l and "anadriya" in delta_l and "not" in delta_l:
        lines.append("Speaker ownership (T1): Korri speaks the line — Anadriya does not.")
    elif "korri" in delta_l:
        lines.append("Speaker / focus (T1): Keep Korri as the on-screen focus for whole TARGET BEAT.")
    if "out of frame" in delta_l or "crew out" in delta_l or "no crew" in delta_l:
        lines.append("Crew-out from USER DELTA (T1): film crew / interviewer stay OUT OF FRAME.")
    return lines


def _hard_constraints_block(
    *,
    local_beat: str,
    user_delta: str,
    established_setup: str,
    exclusions: list[str],
    style_phrase: str = "",
    supports_image_to_video: bool | None = None,
    supports_reference_to_video: bool | None = None,
) -> str:
    """HARD CONSTRAINTS with explicit T1>T2>T3>T4 priority (prompt-law for H3)."""
    t1 = _t1_overrides_from_delta(user_delta, local_beat)
    if not t1:
        t1 = ["Apply USER DELTA inside TARGET BEAT only; delta outranks soft setup language."]

    t2: list[str] = [
        "Film crew, documentary crew, interviewer, and camera operators stay OUT OF FRAME "
        "for the ENTIRE TARGET BEAT duration — no crew visible at any time.",
        "Preserve Quarters / location and cast identity refs from ESTABLISHED setup.",
        (
            "Effective H3 exclusions (prompt-law; adapter has no negative socket): "
            + ", ".join(exclusions)
            + "."
        ),
    ]
    header = ""
    m = _SHOT_HEADER_RE.search(local_beat or "")
    if m:
        header = m.group(0).strip("[]")
    if header:
        t2.insert(
            0,
            f"Camera override for whole TARGET BEAT duration (every frame; "
            f"adapter has no cameraControls socket — prompt-law only): hold {header}.",
        )
    else:
        t2.insert(
            0,
            "Camera override for whole TARGET BEAT duration (every frame; "
            "adapter has no cameraControls socket — prompt-law only): stay on TARGET BEAT framing; "
            "do NOT open on a wide establishing two-shot.",
        )
    if _CREW_RE.search(established_setup or ""):
        t2.append("Suppress any residual crew-visibility language from setup; crew-out wins.")

    t3: list[str] = [
        "Continuity honesty: entry/exit must match TARGET BEAT only — do not regenerate NEXT BEAT.",
        "No fake I2V / dual start-frame conditioning when the adapter does not support image-to-video.",
    ]
    if supports_reference_to_video:
        t3.append(
            "supportsReferenceToVideo=True — keep generationMode=reference and "
            "DR→ref_image_N (CRS/ERS/PRS/Front); never fall back to T2V or Seedance I2V."
        )
    if supports_image_to_video is False:
        t3.append("supportsImageToVideo=False — do not invent a start-frame I2V lock.")

    t4: list[str] = []
    if style_phrase:
        t4.append(f"Soft style preference: {style_phrase}.")
    else:
        t4.append("Soft style: preserve ESTABLISHED cinematic/anime style phrasing without overriding T1/T2.")

    lines: list[str] = [
        "[HARD CONSTRAINTS — T1 then T2]",
        "Priority order (highest wins): T1 > T2 > T3 > T4.",
        "",
        "T1 — retake overrides (from USER DELTA / target framing):",
        *[f"- {ln}" for ln in t1],
        "",
        "T2 — scene hard (crew-out, location, identity, camera override):",
        *[f"- {ln}" for ln in t2],
        "",
        "T3 — continuity (entry/exit honesty; no fake I2V):",
        *[f"- {ln}" for ln in t3],
        "",
        "T4 — soft style:",
        *[f"- {ln}" for ln in t4],
    ]
    return "\n".join(lines)


def _visual_lock(*, local_beat: str, user_delta: str, established_setup: str) -> str:
    """Back-compat helper — framing + crew-out bullets (folded into HARD CONSTRAINTS)."""
    lines: list[str] = []
    header = ""
    m = _SHOT_HEADER_RE.search(local_beat or "")
    if m:
        header = m.group(0)
    framing = header.strip("[]") if header else ""
    if framing:
        lines.append(
            f"Hold this framing for the ENTIRE TARGET BEAT duration (every frame): {framing}."
        )
    elif _CU_RE.search(local_beat or ""):
        lines.append("Hold a tight close-up / MCU for the ENTIRE TARGET BEAT duration (every frame).")
    else:
        lines.append(
            "Do NOT open on a wide establishing two-shot. Stay on the TARGET BEAT framing "
            "for the ENTIRE TARGET BEAT duration."
        )
    lines.append(
        "Film crew, documentary crew, interviewer, and camera operators stay OUT OF FRAME "
        "for the ENTIRE TARGET BEAT duration — no crew visible at any time."
    )
    lines.append(
        "Do not cut away to other characters or other shot sizes during this repair window."
    )
    delta_l = (user_delta or "").lower()
    if "korri" in delta_l and "anadriya" in delta_l and "not" in delta_l:
        lines.append("Speaker ownership: Korri delivers the line — not Anadriya.")
    elif "korri" in delta_l:
        lines.append("Keep Korri as the on-screen focus for the entire TARGET BEAT duration.")
    if _CREW_RE.search(established_setup or ""):
        lines.append("Preserve quarters/location and style; suppress any crew visibility from setup.")
    return "\n".join(f"- {ln}" for ln in lines)


def _scene_bound_refs(batch: Any) -> list[dict[str, Any]]:
    """Scene-bound @/#/% from active promptSegments - not full project library."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for seg in getattr(batch, "promptSegments", None) or []:
        bindings = list(getattr(seg, "referenceNameBindings", None) or [])
        for b in bindings:
            if isinstance(b, dict):
                binding_id = str(b.get("binding_id") or b.get("bindingId") or "").strip()
                tag = str(b.get("tag") or "").strip()
                prompt_name = str(b.get("prompt_name") or b.get("promptName") or "").strip()
                typ = str(b.get("type") or "").strip()
            else:
                binding_id = str(getattr(b, "binding_id", None) or getattr(b, "bindingId", None) or "").strip()
                tag = str(getattr(b, "tag", None) or "").strip()
                prompt_name = str(
                    getattr(b, "prompt_name", None) or getattr(b, "promptName", None) or ""
                ).strip()
                typ = str(getattr(b, "type", None) or "").strip()
            key = binding_id or tag or prompt_name
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "bindingId": binding_id or None,
                    "tag": tag or None,
                    "promptName": prompt_name or None,
                    "type": typ or None,
                    "assetId": None,
                    "identityId": None,
                }
            )
        for bid in list(getattr(seg, "referenceBindingIds", None) or []):
            bid_s = str(bid or "").strip()
            if bid_s and bid_s not in seen:
                seen.add(bid_s)
                out.append(
                    {
                        "bindingId": bid_s,
                        "tag": None,
                        "promptName": None,
                        "type": None,
                        "assetId": None,
                        "identityId": None,
                    }
                )
    ref_by_binding: dict[str, dict[str, Any]] = {}
    for ref in getattr(batch, "references", None) or []:
        if not isinstance(ref, dict):
            continue
        bid = str(ref.get("bindingId") or ref.get("binding_id") or "").strip()
        if bid:
            ref_by_binding[bid] = ref
    for row in out:
        bid = str(row.get("bindingId") or "").strip()
        hit = ref_by_binding.get(bid) if bid else None
        if hit:
            row["assetId"] = hit.get("assetId") or hit.get("asset_id")
            row["identityId"] = hit.get("identityId") or hit.get("identity_id")
    return out


def _speaker_cues(
    *,
    batch: Any,
    established: str,
    local_beat: str,
    db: Any = None,
    project_id: str | None = None,
) -> dict[str, Any]:
    try:
        from .speech_compile import extract_dialogue_cues_from_text
    except Exception:
        extract_dialogue_cues_from_text = None  # type: ignore

    binding_ids: list[str] = []
    name_bindings: list[Any] = []
    for seg in getattr(batch, "promptSegments", None) or []:
        binding_ids.extend(list(getattr(seg, "referenceBindingIds", None) or []))
        name_bindings.extend(list(getattr(seg, "referenceNameBindings", None) or []))
    source = local_beat or established
    cues: list[dict[str, Any]] = []
    status = "PARTIAL"
    note = "speech_compile cues unavailable"
    if extract_dialogue_cues_from_text is not None:
        try:
            cues = extract_dialogue_cues_from_text(
                source,
                db=db,
                project_id=project_id,
                reference_binding_ids=binding_ids,
                reference_name_bindings=name_bindings,
            )
            if cues:
                status = "ok"
                note = "structured speaker cues from speech_compile"
            else:
                status = "PARTIAL"
                note = (
                    "No structured cues hit; owner prose may lack @Token says \"...\" "
                    "or extended Name says form / bindings."
                )
        except Exception as exc:
            status = "PARTIAL"
            note = f"speech_compile error: {exc}"
    return {"status": status, "cues": cues, "note": note}


def _shot_parse(text: str) -> dict[str, Any]:
    if not (text or "").strip():
        return {"status": "PARTIAL", "shots": [], "note": "empty text"}
    try:
        from ...codirector.entity_resolver import parse_shot_requests

        shots = parse_shot_requests(text)
        payload = []
        for s in shots:
            if hasattr(s, "model_dump"):
                payload.append(s.model_dump(mode="json"))
            elif isinstance(s, dict):
                payload.append(s)
            else:
                payload.append(
                    {
                        "index": getattr(s, "index", None),
                        "raw_text": getattr(s, "raw_text", None),
                        "framing": getattr(s, "framing", None),
                        "angle": getattr(s, "angle", None),
                        "characters": list(getattr(s, "characters", None) or []),
                    }
                )
        return {
            "status": "ok" if payload else "PARTIAL",
            "shots": payload,
            "note": (
                "parse_shot_requests reused; primary TARGET BEAT should be one shot"
                if payload
                else "parse_shot_requests returned no shots"
            ),
        }
    except Exception as exc:
        return {"status": "PARTIAL", "shots": [], "note": f"parse_shot_requests error: {exc}"}


def _build_overlap_warning(beat: dict[str, Any]) -> dict[str, Any] | None:
    """Gen-side UX surface when range spans / drops overlapping shots."""
    dropped = list(beat.get("droppedOverlappingShots") or [])
    spans = bool(beat.get("spansMultipleShots")) or bool(dropped)
    range_too_wide = bool(beat.get("rangeTooWideHint"))
    if not spans and not range_too_wide and not dropped:
        return None
    dropped_disp = ", ".join(dropped) if dropped else "(none)"
    message = (
        "Marked range overlaps multiple shots; generation scope is TARGET BEAT "
        f"(primary) only. Dropped from generation scope: {dropped_disp}. "
        "PREV/NEXT are context only — do not regenerate them unless marked as primary."
    )
    return {
        "spansMultipleShots": spans,
        "droppedShots": dropped,
        "message": message,
        "rangeTooWideHint": range_too_wide,
    }


def compile_retake_prompt(
    *,
    established: str,
    local_beat: str,
    user_delta: str,
    range_start: float = 0.0,
    range_length: float = 0.0,
    established_full: str | None = None,
    prev_beat: str | None = None,
    next_beat: str | None = None,
    prev_label: str | None = None,
    next_label: str | None = None,
    exclusions: list[str] | None = None,
    style_phrase: str = "",
    supports_image_to_video: bool | None = None,
    supports_reference_to_video: bool | None = None,
) -> str:
    """Labeled ESTABLISHED SETUP + PREV/TARGET/NEXT + USER DELTA + HARD CONSTRAINTS."""
    end = float(range_start or 0.0) + float(range_length or 0.0)
    setup = established_setup_only(established_full or established)
    if established and not _SHOT_HEADER_RE.search(established):
        setup = _neutralize_crew_present_prose(established.strip())
    excl = list(exclusions or _DEFAULT_H3_EXCLUSIONS)
    hard = _hard_constraints_block(
        local_beat=local_beat,
        user_delta=user_delta,
        established_setup=setup,
        exclusions=excl,
        style_phrase=style_phrase,
        supports_image_to_video=supports_image_to_video,
        supports_reference_to_video=supports_reference_to_video,
    )

    prev_section = (prev_beat or "").strip() or "(none — no previous shot in segment)"
    next_section = (next_beat or "").strip() or "(none — no next shot in segment)"
    next_name = (next_label or "NEXT").strip()
    # Explicit: never put NEXT body into generation scope
    next_guard = (
        f"Do NOT regenerate {next_name} / NEXT unless the marked range's primary shot "
        "truly IS that shot. Context only — excluded from this repair."
    )

    sections = [
        "[ESTABLISHED SCENE — setup only; do not play the full shot list]",
        setup or "(none)",
        "",
        "[PREV BEAT — context only; do not regenerate]",
        prev_section,
        "",
        f"[TARGET BEAT — regenerate this only — range {float(range_start):.2f}s–{end:.2f}s]",
        (local_beat or "").strip() or "(none)",
        "",
        "[NEXT BEAT — excluded from this repair; do not regenerate]",
        next_section,
        next_guard,
        "",
        "[USER DELTA]",
        (user_delta or "").strip() or "(none)",
        "",
        hard,
        "",
        (
            "Apply the USER DELTA inside the TARGET BEAT only. "
            "Preserve ESTABLISHED setup, cast, style, and references. "
            "HARD CONSTRAINTS (T1>T2>T3>T4) outrank establishing shot language from the master Timed Prompt. "
            "Do not regenerate PREV or NEXT."
        ),
    ]
    return "\n".join(sections).strip()


def build_retake_context_package(
    *,
    batch: Any,
    snapshot: Any = None,
    range_rep: dict[str, Any] | None = None,
    user_correction: dict[str, Any] | None = None,
    project_style: str = "",
    style_phrase: str = "",
    supports_image_to_video: bool | None = None,
    supports_reference_to_video: bool | None = None,
    db: Any = None,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Build inheritance package for range retake compile."""
    range_rep = dict(range_rep or {})
    continuity = {}
    if snapshot is not None:
        continuity = dict(getattr(snapshot, "continuityState", None) or {})
        if not range_rep:
            raw = continuity.get("rangeReplacement")
            if isinstance(raw, dict):
                range_rep = dict(raw)
    user_correction = dict(user_correction or {})
    if not user_correction and isinstance(continuity.get("userCorrection"), dict):
        user_correction = dict(continuity["userCorrection"])

    established_full = established_scene_text(batch)
    range_start = float(range_rep.get("start") or user_correction.get("start") or 0.0)
    range_length = float(range_rep.get("length") or user_correction.get("length") or 0.0)
    user_delta = str(
        range_rep.get("prompt")
        or user_correction.get("delta")
        or user_correction.get("prompt")
        or ""
    ).strip()
    # F: Manifest dialogueRetakeRepair is retake prompt authority — not ASR.
    from .dialogue_authority import consume_dialogue_retake_repair

    repair_auth = consume_dialogue_retake_repair(batch, user_delta)
    if repair_auth.get("consumed") and repair_auth.get("delta"):
        user_delta = str(repair_auth["delta"])
        merged = dict(repair_auth.get("userCorrection") or {})
        merged.update(user_correction)
        merged["delta"] = user_delta
        merged["prompt"] = user_delta
        merged["text"] = user_delta
        merged["source"] = "dialogue_manifest"
        user_correction = merged

    beat = extract_local_beat(
        established=established_full,
        batch=batch,
        range_start=range_start,
        range_length=range_length,
        user_delta=user_delta,
    )
    local_beat = str(beat.get("text") or "").strip()
    setup = established_setup_only(established_full)
    exclusions = list(_DEFAULT_H3_EXCLUSIONS)
    prev_text = str(beat.get("prevBeatText") or "").strip() or None
    next_text = str(beat.get("nextBeatText") or "").strip() or None
    prev_label = str(beat.get("prevBeatLabel") or "").strip() or None
    next_label = str(beat.get("nextBeatLabel") or "").strip() or None

    compiled = compile_retake_prompt(
        established=setup,
        local_beat=local_beat,
        user_delta=user_delta,
        range_start=range_start,
        range_length=range_length,
        established_full=established_full,
        prev_beat=prev_text,
        next_beat=next_text,
        prev_label=prev_label,
        next_label=next_label,
        exclusions=exclusions,
        style_phrase=style_phrase or "",
        supports_image_to_video=supports_image_to_video,
        supports_reference_to_video=supports_reference_to_video,
    )

    from ..current_take import resolve_current_take

    current = resolve_current_take(batch) or {}
    current_expose = {
        "currentTakeId": current.get("takeId") or getattr(batch, "currentTakeId", None),
        "currentTakeAssetId": current.get("assetId") or getattr(batch, "currentTakeAssetId", None),
        "candidateId": current.get("candidateId"),
        "source": current.get("source"),
        "parentTakeId": getattr(current.get("candidate"), "parentTakeId", None)
        if current.get("candidate") is not None
        else None,
        "takeState": dict(getattr(current.get("candidate"), "takeState", None) or {})
        if current.get("candidate") is not None
        else {},
    }

    speakers = _speaker_cues(
        batch=batch,
        established=established_full,
        local_beat=local_beat,
        db=db,
        project_id=project_id,
    )
    shots = _shot_parse(local_beat or setup)
    refs = _scene_bound_refs(batch)
    overlap_warning = _build_overlap_warning(beat)

    hard_text = _hard_constraints_block(
        local_beat=local_beat,
        user_delta=user_delta,
        established_setup=setup,
        exclusions=exclusions,
        style_phrase=style_phrase or "",
        supports_image_to_video=supports_image_to_video,
        supports_reference_to_video=supports_reference_to_video,
    )

    boundary: dict[str, Any] = {
        "supportsImageToVideo": supports_image_to_video,
        "supportsReferenceToVideo": supports_reference_to_video,
        "startImageAssetId": range_rep.get("startImageAssetId") or range_rep.get("referenceImageAssetId"),
        "sourceAssetId": range_rep.get("sourceAssetId"),
    }
    if supports_reference_to_video:
        boundary["honesty"] = (
            "Generator is Reference-to-Video; Visual image-frame / CRS/ERS/PRS/Front "
            "inherit as R2V refs (DR→ref_image_N, generationMode=reference). "
            "Classic start-frame I2V is not invented. No T2V fallback / no Seedance substitution."
        )
        boundary["i2vAttached"] = False
        boundary["r2vAttached"] = bool(boundary.get("startImageAssetId"))
    elif supports_image_to_video is False:
        boundary["honesty"] = (
            "Generator does not support image-to-video; cut-in / last-frame I2V "
            "boundary continuity is NOT faked. Range retake inherits prompt/refs only. "
            "HARD CONSTRAINTS carry framing + crew-out (prompt-law) for the whole TARGET BEAT."
        )
        boundary["i2vAttached"] = False
        boundary["r2vAttached"] = False
    elif supports_image_to_video is True and boundary.get("startImageAssetId"):
        boundary["i2vAttached"] = True
        boundary["r2vAttached"] = False
        boundary["honesty"] = "Cut-in / start image attached for I2V-capable generator."
    else:
        boundary["i2vAttached"] = bool(boundary.get("startImageAssetId"))
        boundary["r2vAttached"] = False
        boundary["honesty"] = "Boundary continuity follows generator I2V capability and cut-in availability."

    root_cause_hints: dict[str, Any] | None = None
    if beat.get("droppedOverlappingShots") or beat.get("rangeTooWideHint"):
        root_cause_hints = {
            "droppedShots": list(beat.get("droppedOverlappingShots") or []),
            "rangeTooWideHint": bool(beat.get("rangeTooWideHint")),
            "spansMultipleShots": bool(beat.get("spansMultipleShots")),
            "note": (
                "Marked range overlapped multiple shots; primary_shot drops non-primary "
                "from generation scope (FAIL compile shot_window bleed class A+B)."
            ),
        }

    target_beat = {
        "text": local_beat,
        "header": beat.get("primaryShotHeader"),
        "rangeStart": range_start,
        "rangeLength": range_length,
        "method": beat.get("method"),
    }
    prev_beat_context = {
        "label": prev_label,
        "text": prev_text,
        "role": "context_only",
        "doNotRegenerate": True,
    }
    next_beat_excluded = {
        "label": next_label,
        "text": next_text,
        "role": "excluded",
        "doNotRegenerate": True,
        "containsShot3": bool(
            (next_label and "SHOT 3" in str(next_label).upper())
            or (next_text and "[SHOT 3" in str(next_text).upper())
        ),
    }

    package = {
        "establishedScene": established_full,
        "establishedSetup": setup,
        "localBeat": local_beat,  # back-compat alias of targetBeat.text
        "targetBeat": target_beat,
        "prevBeatContext": prev_beat_context,
        "nextBeatExcluded": next_beat_excluded,
        "localBeatMeta": beat,
        "userDelta": user_delta,
        "compiledPrompt": compiled,
        "actualH3BoundPrompt": compiled,
        "generatorRequestPrompt": compiled,
        "authoredPrompt": established_full,
        "hardConstraints": hard_text,
        "effectiveH3Exclusions": exclusions,
        "overlapWarning": overlap_warning,
        "userCorrection": {
            "delta": user_delta,
            "prompt": user_delta,
            "start": range_start,
            "length": range_length,
        },
        "inherited": {
            "style": project_style or None,
            "stylePhrase": style_phrase or None,
            "refs": refs,
            "setup": setup[:400] if setup else None,
            "constraints": {
                "rangeStart": range_start,
                "rangeLength": range_length,
                "durationIsRangeLength": True,
                "visualLock": True,
                "hardConstraints": True,
                "primaryShotOnly": True,
                "droppedOverlappingShots": beat.get("droppedOverlappingShots") or [],
                "effectiveH3Exclusions": exclusions,
                "cameraOverrideWholeTargetBeat": True,
                "priorityOrder": "T1>T2>T3>T4",
                "supportsReferenceToVideo": supports_reference_to_video,
                "r2vFamily": "FM4/FM5" if supports_reference_to_video else None,
            },
            "generatorId": getattr(batch, "generatorId", None),
            "batchBlockId": getattr(batch, "id", None),
            "sceneId": getattr(batch, "sceneId", None),
        },
        "speakers": speakers,
        "shots": shots,
        "currentTake": current_expose,
        "rangeReplacement": {
            "start": range_start,
            "length": range_length,
            "sourceAssetId": range_rep.get("sourceAssetId"),
            "startImageAssetId": range_rep.get("startImageAssetId"),
            "referenceImageAssetId": range_rep.get("referenceImageAssetId"),
            "repairId": range_rep.get("repairId"),
        },
        "boundaryContinuity": boundary,
        "r2vInheritance": {
            "enabled": bool(supports_reference_to_video),
            "generationMode": "reference" if supports_reference_to_video else None,
            "family": "FM4/FM5" if supports_reference_to_video else None,
            "directReference": "ref_image_N" if supports_reference_to_video else None,
            "slots": ["CRS1", "CRS2", "ERS3", "PRS4"] if supports_reference_to_video else [],
            "noT2VFallback": True,
            "noSeedanceSubstitution": True,
        } if supports_reference_to_video else {
            "enabled": False,
            "generationMode": None,
            "family": None,
            "directReference": None,
            "slots": [],
            "noT2VFallback": True,
            "noSeedanceSubstitution": True,
        },
        "debug": {
            # Prove dump — labeled fields required for hard-constraint prove
            "userDelta": user_delta,
            "targetBeat": target_beat,
            "hardConstraints": hard_text,
            "nextBeatExcluded": next_beat_excluded,
            "prevBeatContext": prev_beat_context,
            "actualH3BoundPrompt": compiled,
            "rootCauseHints": root_cause_hints,
            # Back-compat aliases
            "compiledPrompt": compiled,
            "generatorRequestPrompt": compiled,
            "authoredPrompt": established_full,
            "establishedSetup": setup,
            "localBeatMethod": beat.get("method"),
            "localBeatIsFullDump": beat.get("isFullDump"),
            "primaryShotHeader": beat.get("primaryShotHeader"),
            "droppedOverlappingShots": beat.get("droppedOverlappingShots"),
            "rangeTooWideHint": beat.get("rangeTooWideHint"),
            "overlapWarning": overlap_warning,
            "effectiveH3Exclusions": exclusions,
        },
    }
    return package


__all__ = [
    "build_retake_context_package",
    "compile_retake_prompt",
    "established_scene_text",
    "established_setup_only",
    "extract_local_beat",
]
