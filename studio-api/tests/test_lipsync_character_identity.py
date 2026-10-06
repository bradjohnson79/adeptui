"""Lip Sync speaker gate accepts clip/track character identity."""

from __future__ import annotations

from app.director_timeline import DirectorTimeline
from app.director_timeline_w46.generation.speech_compile import lipsync_speaker_errors
from app.lipsync_tracks import LipSyncClip, LipSyncTrack, LipSyncTracks


def test_character_id_on_clip_satisfies_speaker_gate() -> None:
    timeline = DirectorTimeline(
        duration_sec=5,
        lipsync=LipSyncTracks(
            tracks=[
                LipSyncTrack(
                    slot=1,
                    character_id="char-korri",
                    character_name="Korri",
                    clips=[
                        LipSyncClip(
                            start=0,
                            length=2.5,
                            audio_asset_id="aud-k",
                            speaker_binding_id=None,
                            character_id="char-korri",
                            character_name="Korri",
                        )
                    ],
                )
            ]
        ),
    )
    assert lipsync_speaker_errors(timeline) == []


def test_track_character_id_satisfies_speaker_gate() -> None:
    timeline = DirectorTimeline(
        duration_sec=5,
        lipsync=LipSyncTracks(
            tracks=[
                LipSyncTrack(
                    id="ls-korri",
                    slot=1,
                    character_id="char-korri",
                    character_name="Korri",
                    clips=[
                        LipSyncClip(
                            start=0,
                            length=2.5,
                            audio_asset_id="aud-k",
                            speaker_binding_id=None,
                        )
                    ],
                )
            ]
        ),
    )
    assert lipsync_speaker_errors(timeline) == []
