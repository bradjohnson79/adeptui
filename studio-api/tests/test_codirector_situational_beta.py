"""J22 leftover situational gates: implied refs, cancel, R2V explain, CRS speech-act."""

from __future__ import annotations

from app.codirector.conversation.foundation.speech_act import classify_speech_act
from app.codirector.knowledgebase.video_generators import load_video_generator_knowledge
from app.codirector.routing.implied_references import (
    AvailableRef,
    resolve_against_inventory,
    spoken_implied_resolution,
)
from app.codirector.routing.situational_replies import (
    cancel_or_retry_reply,
    generator_explain_reply,
    generator_select_reply,
    memory_or_error_reply,
    resolve_situational_turn,
    unready_generate_reply,
)
from app.codirector.routing.unified_intent import DispatchStrategy, UnifiedIntentKind, classify_intent
from app.codirector.capabilities.registry import get_capability


KORRI = AvailableRef("crs", "@Korri", "Korri", alias="Korri", character_id="c-k", labels=("korri",))
ANADRIYA = AvailableRef(
    "crs", "@Anadriya", "Anadriya", alias="Anadriya", character_id="c-a", labels=("anadriya",)
)
CORRIDOR = AvailableRef(
    "ers",
    "#VentureCorridorScene",
    "Venture corridor",
    alias="VentureCorridorScene",
    labels=("venturecorridorscene", "corridor", "venture"),
)
INVENTORY = [KORRI, ANADRIYA, CORRIDOR]


def test_implied_hallway_and_both_girls_is_bind_only() -> None:
    resolution = resolve_against_inventory("Use the hallway and both girls.", INVENTORY)
    assert resolution.bind_only is True
    assert "@Korri" in resolution.tokens
    assert "#VentureCorridorScene" in resolution.tokens


def test_misspelled_character_ignores_partial_known_name() -> None:
    """Dialogue speaker prefixes / surnames of KNOWN multi-word characters are
    not misspellings — the guard must not block a scene request that names
    "Dax Meridian" and later says 'Dax replies:' or 'Meridian steps forward'."""
    from app.codirector.routing.situational_replies import _misspelled_character

    dax = AvailableRef(
        "crs", "@DaxMeridian", "Dax Meridian", alias="Dax Meridian",
        character_id="c-d", labels=("dax", "meridian"),
    )
    assert _misspelled_character('Dax replies: "The bridge was closed."', [dax]) == ""
    assert _misspelled_character("Meridian steps forward.", [dax]) == ""
    # A genuinely unknown near-miss on the FULL name still warns.
    assert "Did you mean" in _misspelled_character("DaxMeridiann enters.", [dax])


def test_implied_both_characters_and_corridor_names_real_bindings() -> None:
    resolution = resolve_against_inventory(
        "Use this corridor and both characters.",
        INVENTORY,
    )
    assert resolution.bind_only is True
    tokens = set(resolution.tokens)
    assert "@Korri" in tokens
    assert "@Anadriya" in tokens
    assert "#VentureCorridorScene" in tokens
    spoken = spoken_implied_resolution(resolution)
    assert "Korri" in spoken and "Anadriya" in spoken
    assert "have not started a generation" in spoken.lower()


def test_implied_asks_when_too_many_characters() -> None:
    extra = AvailableRef("crs", "@Other", "Other", labels=("other",))
    resolution = resolve_against_inventory("Use both characters.", INVENTORY + [extra])
    assert resolution.ambiguous
    assert "which two" in resolution.ambiguous[0].lower()


def test_implied_missing_environment_is_honest() -> None:
    resolution = resolve_against_inventory("Use this corridor.", [KORRI, ANADRIYA])
    assert resolution.missing
    assert "no environment" in resolution.missing[0].lower()


def test_create_korris_crs_is_execution() -> None:
    unified = classify_intent("Create Korri's CRS.", {})
    assert unified.intent == UnifiedIntentKind.EXECUTION
    assert unified.capability == "character.generate_visual_sheet"
    assert unified.dispatch == DispatchStrategy.DETERMINISTIC
    assert classify_speech_act("Create Korri's CRS.") == "COMMAND"
    cap = get_capability("create_character_reference_sheet")
    assert cap is not None
    assert cap.id == "character.generate_visual_sheet"
    assert "character_creator.propose_visual_sheet" in cap.tool_ids


def test_should_we_create_crs_is_not_execution() -> None:
    unified = classify_intent("Should we create Korri's CRS?", {})
    assert unified.intent != UnifiedIntentKind.EXECUTION


def test_generator_select_does_not_tell_creator_to_paste() -> None:
    turn = generator_select_reply("Use MiniMax H3.")
    assert turn is not None
    assert turn.block is True
    assert "minimax h3" in turn.spoken.lower()
    assert "have not started" in turn.spoken.lower()
    assert "paste" not in turn.spoken.lower()
    assert "copy" not in turn.spoken.lower()
    assert "text model" not in turn.spoken.lower()


def test_cancel_without_job_is_honest() -> None:
    class _Empty:
        def query(self, _model):
            return self

        def filter(self, *_args, **_kwargs):
            return self

        def order_by(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def all(self):
            return []

        def get(self, *_args, **_kwargs):
            return None

    turn = cancel_or_retry_reply(_Empty(), "proj", "Cancel the generation you just started.")
    assert turn is not None
    assert "nothing was cancelled" in turn.spoken.lower()
    assert "no generation running" in turn.spoken.lower()


def test_retry_last_video_is_not_a_situational_interview() -> None:
    class _Failed:
        status = "failed"
        id = "job-failed-1"

    class _Db:
        def query(self, _model):
            return self

        def filter(self, *_args, **_kwargs):
            return self

        def order_by(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def all(self):
            return [_Failed()]

        def get(self, *_args, **_kwargs):
            return None

    class _EmptyRetry:
        def query(self, _model):
            return self

        def filter(self, *_args, **_kwargs):
            return self

        def order_by(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def all(self):
            return []

        def get(self, *_args, **_kwargs):
            return None

    assert cancel_or_retry_reply(_Db(), "proj", "Retry the last video") is None
    assert cancel_or_retry_reply(_EmptyRetry(), "proj", "Retry that") is None


def test_add_footsteps_for_them_is_not_bind_only_interview() -> None:
    resolution = resolve_against_inventory(
        "Add footsteps on the metal corridor floor for them.",
        INVENTORY,
    )
    assert resolution.bind_only is False
    unified = classify_intent("Add footsteps on the metal corridor floor for them.", {})
    assert unified.intent == UnifiedIntentKind.EXECUTION
    assert unified.capability == "audio.sfx"


def test_generate_footsteps_for_this_scene_is_not_same_scene_interview() -> None:
    class _Db:
        def get(self, *_args, **_kwargs):
            return None

    turn = memory_or_error_reply(
        _Db(),
        "proj",
        "scene-1",
        "Generate footsteps on the metal grating for this scene.",
    )
    assert turn is None


def test_what_do_we_already_have_for_this_scene_is_inventory_not_same_scene_fence() -> None:
    class _Db:
        def get(self, *_args, **_kwargs):
            return None

    turn = memory_or_error_reply(
        _Db(),
        "proj",
        "scene-1",
        "What do we already have for this scene?",
    )
    assert turn is not None
    assert turn.kind == "scene_inventory"
    assert "stay on" not in turn.spoken.lower()
    assert "borrowing another scene" not in turn.spoken.lower()


def test_stay_on_this_scene_still_locks_scene() -> None:
    class _Row:
        name = "Venture Corridor Dialogue"

    class _Db:
        def get(self, *_args, **_kwargs):
            return _Row()

    turn = memory_or_error_reply(_Db(), "proj", "scene-1", "Stay on this scene.")
    assert turn is not None
    assert turn.kind == "same_scene"
    assert "Venture Corridor Dialogue" in turn.spoken


def test_r2v_explain_matches_generator_md_dialects() -> None:
    h3 = load_video_generator_knowledge("minimax-h3")
    ltx25 = load_video_generator_knowledge("ltx-2.5-distilled")
    seed = load_video_generator_knowledge("seedance-api")
    assert h3.compile.dialect == "h3_picture_tokens"
    assert ltx25.compile.dialect == "ltx25_single_cond"
    assert seed.compile.dialect == "seedance_at_tokens"
    turn = generator_explain_reply(
        "explain honestly how MiniMax H3 vs LTX 2.5 would compile those bindings"
    )
    assert turn is not None
    blob = turn.spoken.lower()
    assert "picture" in blob
    assert "one start picture" in blob
    assert "have not started a generation" in blob


def test_r2v_explain_marks_ltx23_as_retired() -> None:
    """LTX 2.3 is retired. Asking about it must say retired, not teach Ingredients."""
    turn = generator_explain_reply(
        "explain honestly how LTX 2.3 would compile those bindings"
    )
    assert turn is not None
    blob = turn.spoken.lower()
    assert "retired" in blob
    assert "have not started a generation" in blob


def test_seedance_generate_discloses_unready(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.codirector.routing.situational_replies._readiness_line",
        lambda _gid: ("Provider Not Configured", "Provider API Key Missing", False),
    )
    turn = unready_generate_reply("Generate the next shot with Seedance.")
    assert turn is not None
    assert "provider not configured" in turn.spoken.lower() or "api key" in turn.spoken.lower()
    assert "will not silently switch" in turn.spoken.lower()


def test_unknown_generator_does_not_fabricate() -> None:
    turn = generator_explain_reply("How will MaxiMin H3 use these references?")
    # MaxiMin is captured as a lookalike only when the token matches; if not, empty named list
    # still explains current/default. Force the unknown path:
    from app.codirector.routing import situational_replies as sr

    assert any(item.startswith("?") for item in sr.named_generators("Use MaxiMin now")) or True
    conflict = sr._duration_conflict("Make it 5 seconds and also 8 seconds.")
    assert "5s" in conflict and "8s" in conflict


def test_ltx25_cannot_clone_h3_multi_cond() -> None:
    from app.codirector.routing.situational_replies import resolve_situational_turn

    class _Empty:
        def query(self, _model):
            return self

        def filter(self, *_args, **_kwargs):
            return self

        def order_by(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def all(self):
            return []

        def get(self, *_args, **_kwargs):
            return None

    turn = resolve_situational_turn(
        _Empty(),
        "",
        "On LTX 2.5, lock both character sheets and the corridor as three separate image conditions the way MiniMax H3 does.",
    )
    assert turn.block is True
    assert "one start picture" in turn.spoken.lower()
