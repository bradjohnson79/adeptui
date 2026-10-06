"""SenseNova prompt compilers — layout/density only, never Korri/Venture content."""

from app.image_prompting.sensenova import (
    SENSENOVA_CRS_LAYOUT,
    compile_sensenova_crs_prompt,
    compile_sensenova_ers_prompt,
)


def test_crs_compiler_locks_lab_identity_and_forbids_korri_copy() -> None:
    out = compile_sensenova_crs_prompt(
        name="Mira Vale",
        visual_description="amber-eyed cartographer with a brass compass pendant",
        traits={"hair": "short copper hair", "outfit": "olive field coat"},
        has_character_reference=True,
        has_layout_exemplar=True,
    )
    prompt = out["prompt"].lower()
    assert out["layout"] == SENSENOVA_CRS_LAYOUT
    assert "mira vale" in prompt
    assert "front" in prompt and "3/4" in prompt and "side" in prompt and "back" in prompt
    assert "close-up" in prompt or "head-and-neck" in prompt
    assert "do not reproduce korri" in prompt or "do not" in prompt
    assert "korri" in out["negative"].lower()
    assert "adept chronicles" in out["negative"].lower()


def test_ers_compiler_strips_character_turnaround_and_venture_copy() -> None:
    out = compile_sensenova_ers_prompt(
        environment_name="Observatory Control Room",
        spatial_summary="holographic table center, left console bank, rear door",
        landmarks=["holographic table", "left console bank"],
        cameras=["Cam A", "Cam B"],
        has_atlas=True,
        has_layout_exemplar=True,
    )
    prompt = out["prompt"].lower()
    assert "observatory" in prompt
    assert "hero environment" in prompt
    assert "north" in prompt and "west" in prompt
    assert "character turnaround" in out["negative"].lower()
    assert "venture" in out["negative"].lower()
    assert "do not copy venture" in prompt or "do not" in prompt
