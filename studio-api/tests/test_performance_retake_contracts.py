"""Performance Retake contract validation tests."""

from __future__ import annotations

import pytest

from app.performance_retake.contracts import (
    CharacterSheetRef,
    PerformanceRetakeError,
    PerformanceRetakeSpec,
    RetakeBeat,
    RetakeReferences,
    RetakeWindow,
    validate_spec,
)

ANADRIYA = "4c1c0bc8-a771-4998-b652-5d549b2a2b8d"
KORRI = "4a2e9cbe-e1e0-4d87-a411-6a8851b2f0ed"


def _spec(**overrides) -> PerformanceRetakeSpec:
    spec = PerformanceRetakeSpec(
        projectId="p",
        sceneId="s",
        window=RetakeWindow(startSec=0.0, endSec=10.016),
        masterDurationSec=10.016,
        beats=[
            RetakeBeat(
                kind="dialogue",
                startSec=0.0,
                endSec=3.0,
                characterId=ANADRIYA,
                characterName="Anadriya",
                line="We've neutralized Cade. The threat is over.",
                voiceAssetId="voice-a",
            ),
            RetakeBeat(
                kind="dialogue",
                startSec=4.0,
                endSec=7.0,
                characterId=KORRI,
                characterName="Korri",
                line="We did it, sis!",
                voiceAssetId="voice-k",
            ),
            RetakeBeat(kind="silence", startSec=7.0, endSec=10.016),
        ],
        references=RetakeReferences(
            characterSheets=[
                CharacterSheetRef(characterId=ANADRIYA, assetId="sheet-a"),
                CharacterSheetRef(characterId=KORRI, assetId="sheet-k"),
            ]
        ),
    )
    for key, value in overrides.items():
        setattr(spec, key, value)
    return spec


def test_valid_spec_passes():
    assert validate_spec(_spec()) is not None


def test_window_must_be_forward():
    spec = _spec(window=RetakeWindow(startSec=5.0, endSec=5.0))
    with pytest.raises(PerformanceRetakeError, match="not before end"):
        validate_spec(spec)


def test_window_inside_master():
    spec = _spec(window=RetakeWindow(startSec=0.0, endSec=11.0))
    with pytest.raises(PerformanceRetakeError, match="exceeds master duration"):
        validate_spec(spec)


def test_dialogue_beat_requires_voice_asset():
    spec = _spec()
    spec.beats[0].voiceAssetId = None
    with pytest.raises(PerformanceRetakeError, match="voiceAssetId"):
        validate_spec(spec)


def test_dialogue_beat_requires_line_and_character():
    spec = _spec()
    spec.beats[0].line = "  "
    with pytest.raises(PerformanceRetakeError, match="missing its line"):
        validate_spec(spec)
    spec = _spec()
    spec.beats[0].characterId = ""
    with pytest.raises(PerformanceRetakeError, match="characterId"):
        validate_spec(spec)


def test_silence_beat_is_authoritative():
    spec = _spec()
    spec.beats[2].line = "secret line"
    with pytest.raises(PerformanceRetakeError, match="silence beat must not carry a line"):
        validate_spec(spec)
    spec = _spec()
    spec.beats[2].voiceAssetId = "voice-x"
    with pytest.raises(PerformanceRetakeError, match="must not carry a voiceAssetId"):
        validate_spec(spec)


def test_overlapping_beats_rejected():
    spec = _spec()
    spec.beats[1].startSec = 2.5
    with pytest.raises(PerformanceRetakeError, match="beats overlap"):
        validate_spec(spec)


def test_beat_escaping_window_rejected():
    spec = _spec()
    spec.beats[2].endSec = 12.0
    with pytest.raises(PerformanceRetakeError, match="escapes the retake window"):
        validate_spec(spec)


def test_dialogue_character_needs_sheet():
    spec = _spec()
    spec.references.characterSheets = spec.references.characterSheets[:1]
    with pytest.raises(PerformanceRetakeError, match="without a character sheet"):
        validate_spec(spec)


def test_sheet_ceiling_and_duplicates():
    spec = _spec()
    spec.references.characterSheets = [
        CharacterSheetRef(characterId=f"c{i}", assetId=f"a{i}") for i in range(9)
    ] + spec.references.characterSheets
    with pytest.raises(PerformanceRetakeError, match="ceiling"):
        validate_spec(spec)
    spec = _spec()
    spec.references.characterSheets.append(
        CharacterSheetRef(characterId=ANADRIYA, assetId="sheet-a2")
    )
    with pytest.raises(PerformanceRetakeError, match="duplicate characterId"):
        validate_spec(spec)


def test_empty_beats_rejected():
    spec = _spec(beats=[])
    with pytest.raises(PerformanceRetakeError, match="no beats"):
        validate_spec(spec)
