"""Phase 4 — Story Intelligence comprehensive test suite.

Covers: instruction/content separation, Schnick Coffee compilation,
validators, negative assertions, proposal routing, and adversarial cases.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.codirector.story_intelligence.compilers.logline import (
    compile_logline,
    validate_logline,
)
from app.codirector.story_intelligence.compilers.long_summary import (
    compile_long_summary,
    validate_long_summary,
)
from app.codirector.story_intelligence.compilers.short_summary import (
    compile_short_summary,
    validate_short_summary,
)
from app.codirector.story_intelligence.proposal import (
    get_current_story_field,
    route_compiler_output,
)
from app.codirector.story_intelligence.sanitize import (
    is_contamination_free,
    is_instruction_text,
    separate_instruction,
)
from app.codirector.story_intelligence.story_model import (
    StoryEvidenceModel,
    StoryFact,
)


# =========================================================================
# Test Class 1 — Instruction / Content Separation
# =========================================================================


class TestInstructionSeparation:

    def test_standard_instruction_prefix(self):
        instruction, content = separate_instruction(
            "Place this into short summary: Korri sells green coffee."
        )
        assert content == "Korri sells green coffee."

    def test_make_shorter_instruction(self):
        instruction, content = separate_instruction(
            "Make this shorter and put it in the logline: "
            "Korri sells a disgusting green coffee before revealing the ad is a joke."
        )
        assert "Korri sells a disgusting green coffee" in content
        assert "Make this shorter" in instruction

    def test_creator_edit_detected(self):
        instruction, content = separate_instruction(
            "Short summary should say exactly: Korri pitches green coffee."
        )
        assert instruction == ""
        assert content == "Korri pitches green coffee."

    def test_plain_text_unchanged(self):
        instruction, content = separate_instruction("Korri sells green coffee.")
        assert instruction == ""
        assert content == "Korri sells green coffee."

    def test_instruction_only_detected(self):
        assert is_instruction_text("Add this to the summary") is True

    def test_content_not_instruction(self):
        assert is_instruction_text("Korri sells green coffee.") is False

    def test_contamination_detected(self):
        assert is_contamination_free("Place this in the short summary") is False

    def test_contamination_clean(self):
        assert is_contamination_free("Korri sells green coffee.") is True


# =========================================================================
# Fixture — Schnick Coffee evidence
# =========================================================================


@pytest.fixture
def schnick_coffee_evidence():
    return StoryEvidenceModel(
        project_id="test",
        format=StoryFact(
            value="commercial",
            source="project",
            source_ref="projects.name",
            provenance="creator-stated",
        ),
        title=StoryFact(
            value="Schnick Coffee",
            source="project",
            source_ref="projects.name",
            provenance="creator-stated",
        ),
        protagonist=StoryFact(
            value="Korri",
            source="script_writer",
            source_ref="script:draft-1",
            provenance="creator-stated",
            confidence=1.0,
        ),
        setting=StoryFact(
            value="coffee shop",
            source="script_writer",
            source_ref="script:draft-1",
            provenance="creator-stated",
        ),
        premise=StoryFact(
            value="Korri promotes a disgusting green coffee and breaks the fourth wall",
            source="script_writer",
            source_ref="script:draft-1",
            provenance="creator-stated",
        ),
        objective=StoryFact(
            value="sell Schnick Coffee",
            source="script_writer",
            source_ref="script:draft-1",
            provenance="creator-stated",
        ),
        conflict=StoryFact(
            value="the coffee is disgusting and Korri breaks character",
            source="script_writer",
            source_ref="script:draft-1",
            provenance="creator-stated",
        ),
        stakes=StoryFact(
            value="the ad is a gag, not a real product",
            source="script_writer",
            source_ref="script:draft-1",
            provenance="creator-stated",
        ),
        tone=StoryFact(
            value="comedic",
            source="script_writer",
            source_ref="script:draft-1",
            provenance="creator-stated",
        ),
        genre=StoryFact(
            value="commercial/spoof",
            source="project",
            source_ref="projects.primary_project_type",
            provenance="creator-stated",
        ),
    )


@pytest.fixture
def empty_evidence():
    return StoryEvidenceModel(project_id="empty")


# =========================================================================
# Test Class 2 — Schnick Coffee Compilation
# =========================================================================


class TestSchnickCoffeeCompilation:

    def test_logline_schnick(self, schnick_coffee_evidence):
        result = compile_logline(schnick_coffee_evidence)

        assert result, "Logline should be non-empty"
        assert "Korri" in result
        assert "coffee" in result or "product" in result
        assert ("gag" in result or "break" in result or "character" in result)
        assert "\n" not in result or "\r" not in result
        assert result.count(".") == 1 or result.endswith(".")
        assert not any(
            phrase in result.lower()
            for phrase in ["i think", "here's a", "i suggest", "as an ai"]
        )

        vr = validate_logline(result, schnick_coffee_evidence)
        assert vr.valid, f"Logline validation failed: {vr.errors}"

    def test_short_summary_schnick(self, schnick_coffee_evidence):
        result = compile_short_summary(schnick_coffee_evidence)

        assert result, "Short summary should be non-empty"
        assert "Korri" in result
        assert "coffee" in result or "green" in result

        wc = len(result.split())
        assert 20 <= wc <= 150, f"Word count {wc} out of bounds"

        assert is_contamination_free(result)
        assert "•" not in result

        vr = validate_short_summary(result, schnick_coffee_evidence)
        assert vr.valid, f"Short summary validation failed: {vr.errors}"

    def test_long_summary_schnick(self, schnick_coffee_evidence):
        result = compile_long_summary(schnick_coffee_evidence)

        assert result, "Long summary should be non-empty"
        assert "Korri" in result

        wc = len(result.split())
        assert 30 <= wc <= 400, f"Word count {wc} out of bounds"

        assert is_contamination_free(result)
        assert not any(
            p in result.lower()
            for p in ["in conclusion", "to summarize", "as we have seen"]
        )

        vr = validate_long_summary(result, schnick_coffee_evidence)
        assert vr.valid, f"Long summary validation failed: {vr.errors}"


# =========================================================================
# Test Class 3 — Validators
# =========================================================================


class TestValidators:

    @staticmethod
    def _minimal_evidence():
        return StoryEvidenceModel(project_id="x")

    def test_logline_empty_rejected(self):
        ev = self._minimal_evidence()
        vr = validate_logline("", ev)
        assert not vr.valid

    def test_logline_empty_rejected_no_evidence(self):
        ev = StoryEvidenceModel(project_id="x")
        vr = validate_logline("", ev)
        assert not vr.valid

    def test_logline_contamination_rejected(self, schnick_coffee_evidence):
        vr = validate_logline(
            "Place this in the short summary", schnick_coffee_evidence
        )
        assert not vr.valid
        assert any("instruction" in e.lower() for e in vr.errors)

    def test_logline_meta_commentary_rejected(self, schnick_coffee_evidence):
        vr = validate_logline("I think Korri sells coffee.", schnick_coffee_evidence)
        assert not vr.valid
        assert any("meta" in e.lower() for e in vr.errors)

    def test_logline_multi_sentence_warning(self, schnick_coffee_evidence):
        vr = validate_logline(
            "Korri sells coffee. She breaks character.", schnick_coffee_evidence
        )
        assert not vr.valid
        assert any("sentence" in e.lower() for e in vr.errors)

    def test_short_summary_empty_rejected(self):
        ev = self._minimal_evidence()
        vr = validate_short_summary("", ev)
        assert not vr.valid

    def test_short_summary_empty_rejected_no_evidence(self):
        ev = StoryEvidenceModel(project_id="x")
        vr = validate_short_summary("", ev)
        assert not vr.valid

    def test_short_summary_too_long(self, schnick_coffee_evidence):
        long_text = "Korri sells coffee. " * 60
        vr = validate_short_summary(long_text, schnick_coffee_evidence)
        assert not vr.valid
        assert any("long" in e.lower() for e in vr.errors)

    def test_long_summary_empty_rejected(self):
        ev = self._minimal_evidence()
        vr = validate_long_summary("", ev)
        assert not vr.valid

    def test_long_summary_empty_rejected_no_evidence(self):
        ev = StoryEvidenceModel(project_id="x")
        vr = validate_long_summary("", ev)
        assert not vr.valid

    def test_long_summary_padding_rejected(self, schnick_coffee_evidence):
        vr = validate_long_summary(
            "In conclusion, Korri sells coffee.", schnick_coffee_evidence
        )
        assert not vr.valid
        assert any("padding" in e.lower() for e in vr.errors)


# =========================================================================
# Test Class 4 — Negative Assertions
# =========================================================================


class TestNegativeAssertions:

    def test_logline_no_invented_stakes(self, schnick_coffee_evidence):
        result = compile_logline(schnick_coffee_evidence)
        lower = result.lower()
        assert "save the world" not in lower
        assert "overcome impossible odds" not in lower

    def test_logline_no_unrelated_characters(self, schnick_coffee_evidence):
        result = compile_logline(schnick_coffee_evidence)
        assert "Zorg" not in result and "Blorb" not in result and "Malvado" not in result

    def test_sanitize_preserves_creator_text(self):
        _, content = separate_instruction(
            "Short summary should say exactly: Korri pitches green coffee."
        )
        assert content == "Korri pitches green coffee."

    def test_no_hallucination_on_empty_evidence(self, empty_evidence):
        result = compile_logline(empty_evidence)
        assert result == ""

    def test_no_hallucination_on_empty_evidence_short(self, empty_evidence):
        result = compile_short_summary(empty_evidence)
        assert result == ""

    def test_no_hallucination_on_empty_evidence_long(self, empty_evidence):
        result = compile_long_summary(empty_evidence)
        assert result == ""


# =========================================================================
# Test Class 5 — Proposal Module
# =========================================================================


class TestProposalModule:

    def test_empty_output_no_proposal(self):
        db = MagicMock()
        result = route_compiler_output(
            db, project_id="p1", artifact_type="logline",
            proposed_value="", evidence=None,
        )
        assert result is None

    def test_no_change_no_proposal(self):
        with patch(
            "app.codirector.story_intelligence.proposal.get_current_story_field",
            return_value="Korri sells coffee.",
        ):
            db = MagicMock()
            result = route_compiler_output(
                db, project_id="p1", artifact_type="logline",
                proposed_value="Korri sells coffee.",
                evidence=None,
            )
            assert result is None


# =========================================================================
# Test Class 6 — Contamination Adversarial
# =========================================================================


class TestContaminationAdversarial:

    def test_case1_instruction_prefix_stripped(self):
        _, content = separate_instruction(
            "Place this into short summary: "
            "Korri tries to sell a foul-smelling green coffee."
        )
        assert "Place this into short summary" not in content
        assert "Korri tries to sell" in content

    def test_case2_make_shorter_stripped(self):
        _, content = separate_instruction(
            "Make this shorter and put it in the logline: "
            "Korri sells a disgusting green coffee "
            "before revealing the ad is a joke."
        )
        assert "Make this shorter" not in content
        assert "Korri sells a disgusting green coffee" in content

    def test_case3_creator_edit_preserved(self):
        instruction, content = separate_instruction(
            "Short summary should say exactly: "
            "Korri pitches green coffee and then breaks character."
        )
        assert instruction == ""
        assert (
            content
            == "Korri pitches green coffee and then breaks character."
        )

    def test_case4_improve_allowed(self):
        assert is_instruction_text("Improve this summary.") is False
