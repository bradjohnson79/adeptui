"""Deterministic Co-Director platform knowledge retrieval and replies."""

from __future__ import annotations

from pathlib import Path

from app.codirector.knowledgebase.lexicon import resolve_terms
from app.codirector.knowledgebase.loader import get_document, list_documents, load_all_documents
from app.codirector.knowledgebase.platform_replies import knowledge_reply
from app.codirector.knowledgebase.retrieve import retrieve_knowledge
from app.knowledgebase_api import list_models

WAN_RETIRED_SPOKEN = (
    "WAN is retired in Adept UI v1.1. Timeline uses MiniMax H3 and LTX 2.5 for Reference-to-Video. Do not restore WAN."
)
WAN_NETWORKING_SPOKEN = "In computer networking, WAN means Wide Area Network."
TIMELINE_QUERY = "What is Timeline?"
TIMELINE_SPOKEN = (
    "Timeline turns this project's pictures and Prompt Names into video. Local generators keep character and place sheets. They are not text-only movie machines."
)

_SERVICE = Path(__file__).resolve().parents[1] / "app" / "codirector" / "service.py"


def _require_spoken(*doc_ids: str) -> None:
    missing = [doc_id for doc_id in doc_ids if not (get_document(doc_id) and get_document(doc_id).spoken)]
    if missing:
        import pytest

        pytest.skip(f"spoken string not loaded for {missing}")


def test_wan_compile_remains_archival_and_spoken_is_retired() -> None:
    """WAN is retired. If the archival .md is on disk it must say retired; either way
    it must NOT load as an active generator knowledge file."""
    from app.codirector.knowledgebase.video_generators import load_video_generator_knowledge

    wan_kb = load_video_generator_knowledge("wan-local")
    assert not wan_kb.loaded, "wan-local is retired and must not load as active knowledge"
    # If the archival doc is still on disk, verify it says retired.
    wan_doc = get_document("wan-2.2")
    if wan_doc is not None:
        assert "retired" in wan_doc.spoken.lower()
        assert "do not restore" in wan_doc.spoken.lower()
        assert "first and last frame video" not in wan_doc.spoken.lower()


def test_loader_includes_current_video_generators_and_skips_python_packages() -> None:
    docs = load_all_documents()
    ids = {doc.id for doc in docs}
    assert "timeline" in ids
    assert "minimax-h3" in ids
    assert "ltx-2.5" in ids
    listed = {doc.id for doc in list_documents()}
    assert "timeline" in listed
    timeline = get_document("timeline")
    assert timeline is not None
    assert timeline.spoken
    assert "wan" not in timeline.spoken.lower()
    assert all("multimodal_continuity" not in str(doc.path) for doc in docs)


def test_wan_production_is_retired_vs_networking() -> None:
    production = resolve_terms("What is WAN?")
    assert production
    # WAN is retired in v1.1. In a production context it must NOT resolve to a
    # current/active generator. If the archival wan-2.2 entry is in the lexicon
    # it should be the production hit; if it was cleaned up, the production
    # hit must not be a current generator (minimax-h3, ltx-2.5, etc.).
    prod_hit = production[0]
    current_generators = {"minimax-h3", "ltx-2.5", "ltx-2.5-distilled", "ltx-2.5-full", "ltx-2.5-comfy"}
    if prod_hit.entity_id == "wan-2.2":
        assert prod_hit.domain == "adept_production"
    else:
        assert prod_hit.entity_id not in current_generators, (
            f'WAN is retired — "What is WAN?" must not resolve to current generator {prod_hit.entity_id}'
        )
    networking = resolve_terms("What does WAN mean in computer networking?")
    assert networking
    wan_net = next(hit for hit in networking if hit.term.upper() == "WAN")
    assert wan_net.domain == "computer_networking"
    assert wan_net.entity_id != "wan-2.2"
    lan = resolve_terms("Our office WAN talks to the LAN through a router and the ISP over TCP.")
    lan_wan = next(hit for hit in lan if hit.term.upper() == "WAN")
    assert lan_wan.domain == "computer_networking"
    assert lan_wan.entity_id != "wan-2.2"


def test_knowledge_reply_wan_is_retired() -> None:
    _require_spoken("wan-2.2")
    reply = knowledge_reply("What is WAN?")
    assert reply
    assert reply.startswith(WAN_RETIRED_SPOKEN) or WAN_RETIRED_SPOKEN in reply
    assert "wide area network" not in reply.lower()
    assert "first and last frame video" not in reply.lower()


def test_knowledge_reply_wan_networking() -> None:
    reply = knowledge_reply("What does WAN mean in computer networking?")
    assert reply == WAN_NETWORKING_SPOKEN
    ethernet = knowledge_reply("What is WAN on ethernet behind our ISP?")
    assert ethernet == WAN_NETWORKING_SPOKEN


def test_wan_cannot_make_text_only_shot() -> None:
    _require_spoken("wan-2.2")
    reply = knowledge_reply("Can WAN make this text-only shot?")
    assert reply
    low = reply.lower()
    assert "retired" in low
    assert "do not restore" in low or "not restore" in low


def test_knowledge_reply_timeline_r2v() -> None:
    _require_spoken("timeline")
    reply = knowledge_reply(TIMELINE_QUERY)
    assert reply
    assert reply.startswith(TIMELINE_SPOKEN) or TIMELINE_SPOKEN in reply
    assert "wan" not in reply.lower()
    assert "wide area network" not in reply.lower()


def test_knowledge_reply_ignores_dialogue_question_mark_in_scene_request() -> None:
    """A Timeline scene-production request is never a platform Q&A.

    Regression: the original Scene 3 request ends with dialogue containing a
    question mark ('CADE: "Where is the Adept?"') plus a runtime sentence
    naming MiniMax H3. The bare `[?]` question detector classified the whole
    request as a platform question and answered with the MiniMax H3 knowledge
    card, so the scene was never prepared.
    """
    message = (
        "For Scene 3, I would like to create a Timeline prompt for the Character reference of "
        "Cade O'Connor, and using the Venture Corridor Scene environment reference sheet as the "
        "setting.\n\n"
        "Here is the prompt for the scene:\n\n"
        "Cinematic high-quality semi-realistic anime sci-fi scene.\n\n"
        "CAMERA: Begin with a slow, ominous forward dolly through the Venture Corridor toward a "
        "sealed metal door.\n\n"
        "ACTION: The sealed door suddenly buckles inward as an enormous punching dent violently "
        "appears from the opposite side. Cade is NOT yet visible.\n\n"
        "Cade steps through the mangled doorway.\n\n"
        "CADE: \u201cWhere is the Adept?\u201d\n\n"
        "After speaking, Cade continues advancing toward camera with unwavering focus.\n\n"
        "IMPORTANT CONTINUITY: Do not reveal Cade before the laser blast. Cade remains fully "
        "masked for the entire shot. Maintain the same Venture corridor throughout the shot.\n\n"
        "The scene will be 30 seconds long with 2 batches. 21:9, 1.0 MegaPixels using MiniMax H3."
    )
    assert knowledge_reply(message, workspace="timeline") is None
    assert knowledge_reply(message, workspace=None) is None


def test_knowledge_reply_still_answers_genuine_generator_question() -> None:
    """The production gate must not swallow honest platform questions."""
    reply = knowledge_reply("What is MiniMax H3 on Timeline?", workspace="timeline")
    assert reply
    assert "minimax" in reply.lower() or "h3" in reply.lower() or "timeline" in reply.lower()


def test_ers_is_gpt_image_2_only() -> None:
    if not (get_document("ers-spec") or get_document("ers-law")):
        import pytest

        pytest.skip("spoken string not loaded for ers-spec/ers-law")
    reply = knowledge_reply("Which generator creates an Environment Reference Sheet?")
    assert reply
    assert "GPT Image 2" in reply
    assert "only" in reply.lower() or "exclusively" in reply.lower()
    if "qwen" in reply.lower():
        assert "not" in reply.lower()


def test_posecraft_is_not_express() -> None:
    _require_spoken("posecraft")
    reply = knowledge_reply("Is PoseCraft a Co-Director Express tool?")
    assert reply
    low = reply.lower()
    assert "image generator" in low
    assert "posecraft" not in low
    assert "spatial map" not in low


def test_spatial_map_is_rectangular_not_circular_viewport() -> None:
    _require_spoken("spatial-map")
    reply = knowledge_reply("What does Spatial Map do?")
    assert reply
    low = reply.lower()
    assert "environment creator" in low
    assert "spatial map" not in low
    assert "posecraft" not in low
    assert "fire3d" not in low
    assert "scenecraft" not in low


def test_crs_character_reference_sheet() -> None:
    _require_spoken("character-creator")
    reply = knowledge_reply("What's a CRS?")
    assert reply
    low = reply.lower()
    assert "character reference sheet" in low or "character" in low
    assert "timeline" in low or "scene creator" in low or "sheet" in low


def test_ltx_on_demand_is_not_broken() -> None:
    _require_spoken("adept-readiness")
    reply = knowledge_reply("LTX On Demand — is it broken?")
    assert reply
    low = reply.lower()
    assert "on demand" in low
    assert "not broken" in low or ("not" in low and "broken" in low)
    assert "offline" not in low


def test_minimax_h3_vs_route_a() -> None:
    reply = knowledge_reply("MiniMax H3 vs Route A")
    assert reply
    low = reply.lower()
    assert "h3" in low or "minimax" in low
    assert "route a" in low or "on demand" in low
    assert "timeline" in low or "reference-to-video" in low or "reference to video" in low


def test_approved_voice_reaches_timeline_lip_sync() -> None:
    reply = knowledge_reply("How approved voice reaches Timeline Lip Sync")
    if not reply:
        import pytest

        pytest.skip("spoken string not loaded for approved-voice / lip-sync path")
    low = reply.lower()
    assert "voice" in low
    assert "timeline" in low or "lip" in low or "audio" in low or "h3" in low
    assert "approved" in low or "attach" in low or "character" in low


def test_retrieval_does_not_dump_corpus() -> None:
    docs = load_all_documents()
    corpus_chars = sum(len(doc.body) + len(doc.spoken) for doc in docs)
    result = retrieve_knowledge(TIMELINE_QUERY)
    assert result.docs_retrieved <= 4
    assert len(result.doc_ids) <= 4
    assert result.elapsed_ms >= 0
    assert result.context_chars > 0
    assert result.context_chars < corpus_chars
    assert result.context_chars <= 4 * 1600
    assert "timeline" in result.doc_ids
    # WAN is retired. If the archival wan-2.2.md is on disk it may appear in
    # retrieval; if it was cleaned up it won't. Either way, retrieval must stay bounded.
    wan_result = retrieve_knowledge("What is WAN?")
    assert wan_result.docs_retrieved <= 4
    assert len(wan_result.doc_ids) <= 4


def test_on_demand_is_not_offline() -> None:
    hits = resolve_terms("LTX On Demand — is it broken?")
    assert any(hit.entity_id == "adept-readiness" for hit in hits)
    reply = knowledge_reply("Is LTX On Demand offline?")
    assert reply
    assert "offline" not in reply.lower()
    assert "on demand" in reply.lower()


def test_chat_paths_enter_one_durable_turn() -> None:
    src = _SERVICE.read_text(encoding="utf-8")
    assert "def _maybe_platform_knowledge_reply" in src
    assert "from .knowledgebase.platform_replies import knowledge_reply" in src
    for name in ("async def chat_for_project", "async def stream_for_project", "async def _stream_for_project_inner"):
        assert name not in src
    router = (_SERVICE.parents[1] / "routers" / "codirector.py").read_text(encoding="utf-8")
    chat = router[router.find("async def chat(") : router.find("async def chat_stream(")]
    stream = router[router.find("async def chat_stream(") : router.find("async def chat_stream(") + 2500]
    assert "begin_turn(" in chat and "begin_turn(" in stream
    assert "chat_for_project(" not in chat and "stream_for_project(" not in stream


def test_platform_hook_writes_routing_receipt() -> None:
    from app.codirector import service as codirector_service
    from app.codirector.knowledgebase.routing_receipt import last_routing_receipt

    reply = codirector_service._maybe_platform_knowledge_reply(
        TIMELINE_QUERY,
        None,
        project_id="proj-receipt",
        consumer="codirector.chat",
    )
    assert reply
    assert "wide area network" not in reply.lower()
    assert "wan" not in reply.lower()
    receipt = last_routing_receipt(project_id="proj-receipt")
    assert receipt
    assert receipt["query"] == TIMELINE_QUERY
    assert receipt["consumer"] == "codirector.chat"
    assert receipt["landed"] is True
    assert "timeline" in (receipt.get("retrievedIds") or [])


def test_grounded_routing_probe_executes_hook() -> None:
    import asyncio

    from app.codirector.status.registry import StatusContext, _probe_codirector_grounded_routing

    payload = asyncio.run(_probe_codirector_grounded_routing(StatusContext(db=None, project_id="proj-probe")))  # type: ignore[arg-type]
    details = payload["details"]
    assert details["routed"] is True
    assert details["landed"] is True
    assert details["replyable"] is True
    assert details["r2vContentNotReimplemented"] is False
    assert details["timelineSpokenCard"] is True
    assert details.get("probeQuery") == TIMELINE_QUERY
    assert (details.get("routingReceipt") or {}).get("query") == TIMELINE_QUERY
    assert payload["status"] == "healthy"


def test_overflow_list_models_does_not_advertise_wan_t2v() -> None:
    models = {str(item.get("id")): item for item in list_models() if isinstance(item, dict)}
    # WAN is retired in v1.1. It must not be advertised as a T2V model.
    # If wan_2_2 is listed, it must not advertise T2V and must be marked superseded.
    wan = models.get("wan_2_2")
    if wan is not None:
        caps = wan.get("capabilities") or {}
        assert caps.get("text_to_video") is False
        assert wan.get("superseded")
    # LTX 2.3 is retired. If listed, it must not advertise T2V.
    ltx = models.get("ltx_2_3")
    if ltx:
        assert (ltx.get("capabilities") or {}).get("text_to_video") is False
