"""Adept UI LoRA Registry — one authoritative registry + compatibility layer.

Shared by Image Generator, Scene Creator, Scene Creator Mini, Character
Creator, Prop Creator, and Timeline. Single source of truth for installed
LoRAs; generators ask the registry \"what enabled LoRAs are compatible with
the active model?\" and render only those.
"""

from .registry import (  # noqa: F401
    LoraRecord,
    compatible_loras,
    get_lora,
    list_loras,
    register_lora,
    resolve_lora_for_generation,
    scan_for_loras,
    set_lora_enabled,
    unregister_lora,
)
