"""RegistryId -> sandbox adapter factory (lock + feature flag gated)."""

from __future__ import annotations

from typing import Callable

from ..m29.providers import ProviderUnavailable
from .adapters.fixture_ci import FIXTURE_REGISTRY_ID, FixtureCiAudioAdapter
from .adapters.generic_sandbox import GENERIC_CANDIDATES, GenericSandboxAudioAdapter
from .adapters.kokoro import KOKORO_REGISTRY_ID, KokoroSandboxAdapter
from .contract import AudioGenerationProviderABC
from .execution_lock import is_execution_authorized
from .flags import fixture_mode_enabled, m210b_audio_sandbox_enabled

AdapterFactory = Callable[[], AudioGenerationProviderABC]

_FACTORIES: dict[str, AdapterFactory] = {
    KOKORO_REGISTRY_ID: KokoroSandboxAdapter,
    **{rid: (lambda r=rid: GenericSandboxAudioAdapter(r)) for rid in GENERIC_CANDIDATES},
}


def registered_ids() -> list[str]:
    return sorted(_FACTORIES.keys())


def get_adapter(registry_id: str | None) -> AudioGenerationProviderABC | None:
    """Return an adapter only when feature flag + execution lock authorize.

    Fixture CI adapter is returned only under fixture env flags.
    Unapproved ids return None (caller should raise ProviderUnavailable).
    """
    if not registry_id:
        return None
    rid = str(registry_id).strip()
    if not rid:
        return None

    if rid == FIXTURE_REGISTRY_ID:
        if not fixture_mode_enabled():
            return None
        if not m210b_audio_sandbox_enabled() and not fixture_mode_enabled():
            return None
        return FixtureCiAudioAdapter()

    if not m210b_audio_sandbox_enabled():
        return None
    if not is_execution_authorized(rid):
        return None
    factory = _FACTORIES.get(rid)
    if factory is None:
        return None
    return factory()


def require_adapter(registry_id: str | None) -> AudioGenerationProviderABC:
    adapter = get_adapter(registry_id)
    if adapter is not None:
        return adapter
    rid = (registry_id or "").strip() or "<missing>"
    if not m210b_audio_sandbox_enabled():
        raise ProviderUnavailable(
            "STUDIO_FEATURE_M210B_AUDIO_SANDBOX_V1 is disabled; sandbox audio unavailable."
        )
    if not is_execution_authorized(rid):
        raise ProviderUnavailable(
            f"Registry id {rid!r} is not authorized by the M2.10b execution lock."
        )
    raise ProviderUnavailable(f"No sandbox adapter registered for {rid!r}.")
