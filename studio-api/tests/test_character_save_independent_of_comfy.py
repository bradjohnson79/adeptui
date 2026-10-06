"""Save Character must persist without Comfy :8188."""

from __future__ import annotations

import inspect

from app.character_identity import service
from app.character_identity.schemas import CharacterProfileCreate, CharacterProfileUpdate


def test_update_profile_source_does_not_call_comfy():
    src = inspect.getsource(service.update_profile)
    assert "comfy" not in src.lower()
    assert "8188" not in src
    assert "qwen" not in src.lower()


def test_create_profile_source_does_not_call_comfy():
    src = inspect.getsource(service.create_profile)
    assert "comfy" not in src.lower()
    assert "8188" not in src


def test_save_schemas_do_not_require_runtime():
    created = CharacterProfileCreate(name="Anadriya")
    updated = CharacterProfileUpdate(description="Profile text only")
    assert created.name == "Anadriya"
    assert updated.description == "Profile text only"
    assert not hasattr(created, "comfy_url")
    assert not hasattr(updated, "runtime_ready")
