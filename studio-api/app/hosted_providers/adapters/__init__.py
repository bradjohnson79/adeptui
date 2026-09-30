"""Live credential probes and enqueue/chat for hosted providers — never fabricate success."""

from .fal_adapter import chat_fal, enqueue_fal, probe_fal
from .kie_adapter import chat_kie, enqueue_kie, probe_kie
from .openai_compatible_adapter import probe_openai_compatible
from .wavespeed_adapter import chat_wavespeed, enqueue_wavespeed, probe_wavespeed
try:
    from .elevenlabs_adapter import generate_sfx_to_file, generate_tts_to_file, probe_elevenlabs
except ImportError:  # optional provider module absent
    generate_sfx_to_file = generate_tts_to_file = probe_elevenlabs = None  # type: ignore[assignment]

__all__ = [
    "probe_fal",
    "probe_kie",
    "probe_wavespeed",
    "probe_openai_compatible",
    "probe_elevenlabs",
    "generate_tts_to_file",
    "generate_sfx_to_file",
    "enqueue_fal",
    "enqueue_kie",
    "enqueue_wavespeed",
    "chat_fal",
    "chat_kie",
    "chat_wavespeed",
]
