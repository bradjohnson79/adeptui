"""Resolve VideoGeneratorAdapter by generatorId — no silent substitution."""

from __future__ import annotations

from typing import Iterable

from .adapters.kling_api import ALIASES as KLING_ALIASES
from .adapters.kling_api import KlingApiAdapter
from .adapters.ltx_local import LtxLocalAdapter
from .adapters.minimax_h3_i2v_local import ALIASES as MINIMAX_I2V_ALIASES
from .adapters.minimax_h3_i2v_local import MiniMaxH3I2VLocalAdapter
from .adapters.minimax_h3_local import ALIASES as MINIMAX_T2V_ALIASES
from .adapters.minimax_h3_local import MiniMaxH3LocalAdapter
from .adapters.seedance_api import ALIASES as SEEDANCE_ALIASES
from .adapters.seedance_api import SeedanceApiAdapter
from .adapters.stub_cert import ALIASES as STUB_CERT_ALIASES
from .adapters.stub_cert import StubCertAdapter, stub_enabled
from .contracts import VideoGeneratorCapabilities


class GeneratorNotFoundError(LookupError):
    pass


class SilentFallbackForbiddenError(RuntimeError):
    pass


class VideoGeneratorRegistry:
    def __init__(self) -> None:
        self._adapters = {
            MiniMaxH3LocalAdapter.id: MiniMaxH3LocalAdapter(),
            MiniMaxH3I2VLocalAdapter.id: MiniMaxH3I2VLocalAdapter(),
            LtxLocalAdapter.id: LtxLocalAdapter(),
            SeedanceApiAdapter.id: SeedanceApiAdapter(),
            KlingApiAdapter.id: KlingApiAdapter(),
        }
        self._aliases: dict[str, str] = {}
        for alias in MINIMAX_T2V_ALIASES:
            self._aliases[alias] = MiniMaxH3LocalAdapter.id
        for alias in MINIMAX_I2V_ALIASES:
            self._aliases[alias] = MiniMaxH3I2VLocalAdapter.id
        for alias in SEEDANCE_ALIASES:
            self._aliases[alias] = SeedanceApiAdapter.id
        for alias in KLING_ALIASES:
            self._aliases[alias] = KlingApiAdapter.id
        self._aliases["ltx-local"] = LtxLocalAdapter.id
        # CERT_STUB_ENV_GATED: the certification stub replaces the provider
        # execution boundary only when ADEPT_TIMELINE_CERT_STUB=1. Invisible
        # in production.
        if stub_enabled():
            self._adapters[StubCertAdapter.id] = StubCertAdapter()
            for alias in STUB_CERT_ALIASES:
                self._aliases[alias] = StubCertAdapter.id

    def resolve_id(self, generator_id: str | None) -> str:
        if not generator_id:
            raise GeneratorNotFoundError("generatorId is required — no default generator substitution.")
        if generator_id in self._adapters:
            return generator_id
        if generator_id in self._aliases:
            return self._aliases[generator_id]
        raise GeneratorNotFoundError(f"Unknown generatorId={generator_id}")

    def get(self, generator_id: str | None):
        resolved = self.resolve_id(generator_id)
        adapter = self._adapters.get(resolved)
        if adapter is None:
            raise GeneratorNotFoundError(f"Unknown generatorId={generator_id}")
        return adapter

    def capabilities(self, generator_id: str | None) -> VideoGeneratorCapabilities:
        return self.get(generator_id).capabilities

    def list_capabilities(self, generator_id: str | None = None) -> list[VideoGeneratorCapabilities]:
        if generator_id is not None:
            return [self.capabilities(generator_id)]
        return [a.capabilities for a in self._adapters.values()]

    def known_ids(self) -> Iterable[str]:
        return list(self._adapters.keys()) + list(self._aliases.keys())


_REGISTRY: VideoGeneratorRegistry | None = None


def get_registry() -> VideoGeneratorRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = VideoGeneratorRegistry()
    return _REGISTRY
