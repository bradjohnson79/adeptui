from types import SimpleNamespace

from app.character_identity.voice_preview import (
    brief_from_identity_fields,
    normalize_design_request,
    preview_sample_line,
    variation_instruct,
)


def test_preview_sample_line_stays_short():
    long = " ".join(f"w{i}" for i in range(20))
    out = preview_sample_line(long, "fallback")
    assert len(out.split()) == 14
    assert preview_sample_line("  Hey there.  ", "fallback") == "Hey there."


def test_brief_from_identity_fields_keeps_creator_description():
    brief = brief_from_identity_fields(
        sex="female",
        age="Young Adult 20-24",
        accent="Neutral American",
        prompt="Playful teenage elf, sharp and teasing.",
    )
    assert brief["gender"] == "Female"
    assert brief["perceivedAge"] == "Young Adult 20-24"
    assert "Playful teenage elf" in brief["additionalDirection"]


def test_variation_instruct_keeps_identity_and_differs():
    base = "Female young adult, teasing, clear."
    a = variation_instruct(base, 0)
    b = variation_instruct(base, 1)
    c = variation_instruct(base, 2)
    assert a == base
    assert a != b != c
    assert "same person" in b.lower()
    assert "same person" in c.lower()


def test_normalize_design_request_accepts_voice_identity_aliases():
    body = SimpleNamespace(
        designBrief=None,
        candidateCount=3,
        testLine=None,
        name=None,
        masterPrompt=None,
        promptDocument=None,
        method="design",
        parentCandidateId=None,
        appendToVoiceId=None,
        sex="female",
        age="Teen 16-19",
        script="Listen carefully.",
        prompt="Bright, mischievous, not breathy.",
        sampleCount=4,
        accent="Irish",
        archetype="Rebel",
    )
    norm = normalize_design_request(body)
    assert norm["candidateCount"] == 4
    assert norm["testLine"] == "Listen carefully."
    assert norm["masterPrompt"] == "Bright, mischievous, not breathy."
    assert norm["designBrief"]["gender"] == "Female"
    assert norm["designBrief"]["accent"] == "Irish"


def test_normalize_design_request_reads_async_job_dict_payload():
    norm = normalize_design_request(
        {
            "candidateCount": 1,
            "sampleCount": 1,
            "testLine": "The plan still holds.",
            "masterPrompt": "Warm tenor",
            "method": "design",
        }
    )
    assert norm["candidateCount"] == 1
    assert norm["testLine"] == "The plan still holds."
    assert norm["masterPrompt"] == "Warm tenor"
