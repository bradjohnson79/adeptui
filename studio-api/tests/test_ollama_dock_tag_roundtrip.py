"""Live Ollama dock ids must round-trip exact tags (colon preserved)."""

from app.production_control.runtime_map import dock_id_for_ollama_tag, llm_ollama_for_dock_model


def test_live_ollama_tag_roundtrip():
    tag = "qwen3.6:35b-a3b"
    dock_id = dock_id_for_ollama_tag(tag)
    assert dock_id == "ollama-tag:qwen3.6:35b-a3b"
    assert llm_ollama_for_dock_model(dock_id) == tag


def test_legacy_static_gemma_still_maps():
    assert llm_ollama_for_dock_model("ollama-gemma4-31b") == "gemma4:31b-it-qat"


def test_mangled_hyphen_id_does_not_invent_tag():
    # Former bug: ollama-qwen3.6-35b-a3b → qwen3.6-35b-a3b (invalid)
    assert llm_ollama_for_dock_model("ollama-qwen3.6-35b-a3b") is None
