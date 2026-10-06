"""Creator Lip Sync UX surface — Owner law aligned with FE TIMELINE_LIPSYNC_CREATOR_UI.

OWNER LAW (aligns with studio-web `timelineLipSyncCreatorUi.ts`):
  TIMELINE_LIPSYNC_CREATOR_UI = false

  No API default, parse path, generate/prepare/handoff, bake/apply, or
  DirectorTimeline.default may reintroduce creator Lip Sync UX (minting
  "Lip Sync 1", enabling +/- track chrome, or creator prepare/bake/apply/
  PUT lipsync-tracks / POST lipsync mutations) without an explicit Owner
  CLEAR that flips this contract.

  Empty Timeline scenes stay lipsync.tracks=[] — speech_compile /
  LIPSYNC_SPEAKER_REQUIRED simply finds no clips. Generate_scene video
  path remains intact without Lip Sync creator mint.
"""

from __future__ import annotations

from typing import Any

# Mirror FE Owner flag name/meaning (timelineLipSyncCreatorUi.ts).
TIMELINE_LIPSYNC_CREATOR_UI = False

# Owner safeguard: reintroducing creator Lip Sync generate/prepare/handoff UX
# is forbidden until Owner CLEAR. Keep True while TIMELINE_LIPSYNC_CREATOR_UI
# is False.
OWNER_LIPSYNC_UX_REINTRODUCE_FORBIDDEN = True

CREATOR_LIPSYNC_MUTATION_DISABLED = "CREATOR_LIPSYNC_MUTATION_DISABLED"

_CREATOR_LIPSYNC_MSG = (
    "Timeline creator Lip Sync generate/prepare/handoff is disabled. "
    "PUT lipsync-tracks, bake, apply, and POST lipsync are blocked; "
    "empty scenes must not mint Lip Sync 1. "
    "Owner law: TIMELINE_LIPSYNC_CREATOR_UI=false — Lip Sync creator UX "
    "must not be reintroduced without Owner CLEAR."
)


def owner_lipsync_ux_reintroduce_forbidden() -> bool:
    """True when Owner forbids creator Lip Sync mint/defaults/mutations."""
    return bool(OWNER_LIPSYNC_UX_REINTRODUCE_FORBIDDEN) and not bool(
        TIMELINE_LIPSYNC_CREATOR_UI
    )


def creator_lipsync_mutation_blocked(reason: str = "") -> dict[str, Any]:
    """Constant error for creator lipsync mutation / prepare / handoff paths."""
    msg = _CREATOR_LIPSYNC_MSG
    if reason:
        msg = f"{msg} ({reason})"
    return {
        "ok": False,
        "error": CREATOR_LIPSYNC_MUTATION_DISABLED,
        "message": msg,
        "mock": False,
        "ownerLaw": "TIMELINE_LIPSYNC_CREATOR_UI=false",
    }


def empty_lipsync_tracks():
    """Owner-law empty lipsync: tracks=[] — never mint Lip Sync 1.

    Used by parse_lipsync_tracks empty/invalid paths and DirectorTimeline.default
    while creator Lip Sync UX is locked. Does not raise — returning empty
    tracks *is* compliance. generate_scene speech_compile finds no clips.
    """
    from ..lipsync_tracks import LipSyncTracks

    _ = owner_lipsync_ux_reintroduce_forbidden()
    return LipSyncTracks(tracks=[])


def forbid_creator_lipsync_mutation(context: str = "") -> None:
    """Raise when a path is about to mutate/mint creator Lip Sync UX.

    Call immediately before PUT/bake/apply/POST lipsync or any default that
    would mint Lip Sync 1. Empty parse/default must use empty_lipsync_tracks()
    instead (returns tracks=[]).
    """
    if not owner_lipsync_ux_reintroduce_forbidden():
        return
    detail = context.strip() or "creator Lip Sync mutation"
    raise RuntimeError(
        f"OWNER_LIPSYNC_UX_REINTRODUCE_FORBIDDEN: {detail}. "
        "TIMELINE_LIPSYNC_CREATOR_UI=false — leave lipsync.tracks=[] ; "
        "do not mint Lip Sync 1 or expose prepare/bake/apply."
    )
