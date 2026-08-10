"""G1-G3 regression tests: verify write-path authority boundaries."""
import os
os.environ["STUDIO_API_PORT"] = "1"
os.environ["STUDIO_E2E"] = "1"

from app.codirector.conversation.schemas import ProjectIntelligenceSnapshot, WikiCandidate
from app.codirector.conversation.knowledge import apply_wiki_candidates
from app.codirector.notes.service import _ensure_notes_list
from app.codirector.wiki_intelligence.correction.classify import _find_matching_records
from app.codirector.wiki_intelligence.correction.apply import _find_entries_containing


def test_g2_notes_bridge_filters_rejected_superseded():
    snapshot = ProjectIntelligenceSnapshot(projectId="test-g2", knowledgeEntries=[
        WikiCandidate(id="a", text="Maya is a detective", state="confirmed", section="characters"),
        WikiCandidate(id="b", text="Rejected text", state="rejected", section="storyAndEpisodes"),
        WikiCandidate(id="c", text="Superseded text", state="superseded", section="storyAndEpisodes"),
    ])
    object.__setattr__(snapshot, "workingNotes", None)
    notes = _ensure_notes_list(snapshot)
    note_texts = [n.text for n in notes]
    assert "Rejected text" not in note_texts, f"Rejected leaked: {note_texts}"
    assert "Superseded text" not in note_texts, f"Superseded leaked: {note_texts}"
    assert "Maya is a detective" in note_texts, f"Confirmed missing: {note_texts}"
    print("G2 PASS: rejected/superseded filtered from Notes bridge")


def test_g3_classify_filters_rejected_superseded():
    snapshot = ProjectIntelligenceSnapshot(projectId="test-g3", knowledgeEntries=[
        WikiCandidate(id="a", text="Maya is a detective", state="confirmed", section="characters"),
        WikiCandidate(id="b", text="Rejected text", state="rejected", section="storyAndEpisodes"),
        WikiCandidate(id="c", text="Superseded text", state="superseded", section="storyAndEpisodes"),
    ])
    result = _find_matching_records(snapshot, ["Maya", "Rejected", "Superseded"])
    matched_texts = [r["text"] for r in result]
    assert "Rejected text" not in matched_texts, f"Rejected in match: {matched_texts}"
    assert "Superseded text" not in matched_texts, f"Superseded in match: {matched_texts}"
    assert "Maya is a detective" in matched_texts, f"Maya should match: {matched_texts}"
    print("G3 PASS (classify): rejected/superseded filtered from _find_matching_records")


def test_g3_apply_filters_rejected_superseded():
    snapshot = ProjectIntelligenceSnapshot(projectId="test-g3-apply", knowledgeEntries=[
        WikiCandidate(id="a", text="Maya is a detective", state="confirmed", section="characters"),
        WikiCandidate(id="b", text="Rejected text", state="rejected", section="storyAndEpisodes"),
        WikiCandidate(id="c", text="Superseded text", state="superseded", section="storyAndEpisodes"),
    ])
    r1 = _find_entries_containing(snapshot, "Maya")
    assert len(r1) == 1, f"Maya should match, got {len(r1)}"
    r2 = _find_entries_containing(snapshot, "Rejected")
    assert len(r2) == 0, f"Rejected should not match, got {len(r2)}"
    r3 = _find_entries_containing(snapshot, "Superseded")
    assert len(r3) == 0, f"Superseded should not match, got {len(r3)}"
    print("G3 PASS (apply): rejected/superseded filtered from _find_entries_containing")


def test_g1_apply_wiki_candidates_accepts_story_correction():
    snapshot = ProjectIntelligenceSnapshot(projectId="test-g1")
    candidate = WikiCandidate(
        id="test-correction", text="This is a story correction.",
        state="confirmed", section="storyAndEpisodes",
        provenance="USER_EXPLICIT_WIKI_WRITE",
    )
    snapshot = apply_wiki_candidates(snapshot, [candidate], "This is a story correction.")
    assert len(snapshot.knowledgeEntries) == 1
    print("G1 PASS: explicit story correction accepted via apply_wiki_candidates")


def test_g1_apply_wiki_candidates_rejects_question():
    snapshot = ProjectIntelligenceSnapshot(projectId="test-g1-q")
    candidate = WikiCandidate(
        id="question-test", text="What should I define next?",
        state="confirmed", section="storyAndEpisodes",
        provenance="USER_EXPLICIT_WIKI_WRITE",
    )
    snapshot = apply_wiki_candidates(snapshot, [candidate], "What should I define next?")
    assert len(snapshot.knowledgeEntries) == 0
    print("G1 PASS: question rejected by apply_wiki_candidates")


if __name__ == "__main__":
    test_g2_notes_bridge_filters_rejected_superseded()
    test_g3_classify_filters_rejected_superseded()
    test_g3_apply_filters_rejected_superseded()
    test_g1_apply_wiki_candidates_accepts_story_correction()
    test_g1_apply_wiki_candidates_rejects_question()
    print("\nALL G1-G3 TESTS PASS")
