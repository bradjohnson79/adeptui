"""Hosted Kie / fal / WaveSpeed LLM providers for the existing Co-Director picker."""

from __future__ import annotations

from typing import Any, AsyncIterator

from ...hosted_providers.registry import PROVIDERS
from ...secrets_store import get_secret
from .base import ChatRequest, ChatResult, ProviderHealthResult, ProviderModel

_DISPLAY = {
    "kie": "Kie.ai",
    "wavespeed": "WaveSpeed.ai",
    "fal": "fal.ai",
}

_DEFAULT_MODELS = {
    "kie": "gemini-3-pro",
    "wavespeed": "deepseek/deepseek-v4-flash",
    "fal": "fal-ai/any-llm",
}


def hosted_key_configured(provider_id: str) -> bool:
    defn = PROVIDERS.get(provider_id)
    if not defn:
        return False
    return bool(get_secret(defn.secret_name))


def configured_hosted_llm_ids() -> list[str]:
    return [pid for pid in ("kie", "wavespeed", "fal") if hosted_key_configured(pid)]


class HostedLlmProvider:
    """One stored provider key unlocks that provider's official chat model(s)."""

    def __init__(self, provider_id: str, *, default_model: str | None = None) -> None:
        pid = (provider_id or "").strip().lower()
        if pid not in _DISPLAY:
            raise ValueError(f"Unknown hosted LLM provider: {provider_id}")
        self.id = pid
        self.display_name = f"{_DISPLAY[pid]} LLM"
        self.default_model = (default_model or "").strip() or _DEFAULT_MODELS[pid]

    def _catalog_llm_rows(self) -> list[dict[str, Any]]:
        try:
            from ...hosted_providers.discovery import _PROVIDER_CATALOG
        except Exception:
            return []
        return [r for r in (_PROVIDER_CATALOG.get(self.id) or []) if r.get("modality") == "llm"]

    async def list_models(self) -> list[ProviderModel]:
        rows = self._catalog_llm_rows()
        out: list[ProviderModel] = []
        for row in rows:
            mid = str(row.get("providerModelId") or "")
            if not mid:
                continue
            out.append(
                ProviderModel(
                    id=mid,
                    name=str(row.get("displayName") or mid),
                    family=self.id,
                )
            )
        if not out:
            out.append(ProviderModel(id=self.default_model, name=self.default_model, family=self.id))
        return out

    async def health(self) -> ProviderHealthResult:
        defn = PROVIDERS.get(self.id)
        key = get_secret(defn.secret_name) if defn else None
        models = await self.list_models()
        selected = self.default_model
        if models and selected not in {m.id for m in models}:
            selected = models[0].id
        if not key:
            return ProviderHealthResult(
                provider_id=self.id,
                display_name=self.display_name,
                status="Not Configured",
                reachable=False,
                endpoint=defn.docs_url if defn else "",
                selected_model=selected,
                model_available=False,
                models=models,
                message=f"No {_DISPLAY[self.id]} API key configured.",
                code="NOT_CONFIGURED",
                recommended_action="connect_provider",
            )
        return ProviderHealthResult(
            provider_id=self.id,
            display_name=self.display_name,
            status="Ready",
            reachable=True,
            endpoint=defn.docs_url if defn else "",
            selected_model=selected,
            model_available=True,
            models=models,
            message=f"{_DISPLAY[self.id]} key is configured. Hosted LLM is selectable.",
        )

    async def generate(self, request: ChatRequest) -> ChatResult:
        defn = PROVIDERS[self.id]
        key = get_secret(defn.secret_name)
        if not key:
            raise RuntimeError(f"No {_DISPLAY[self.id]} API key configured.")
        model = (request.model_id or self.default_model).strip()
        messages = list(request.messages or [])
        prompt_parts = []
        system_prompt = ""
        for m in messages:
            role = str(m.get("role") or "user")
            content = str(m.get("content") or "")
            if role == "system":
                system_prompt = content
            else:
                prompt_parts.append(f"{role}: {content}" if role != "user" else content)
        prompt = "\n\n".join(p for p in prompt_parts if p).strip()
        if request.project_context:
            system_prompt = (system_prompt + "\n\n" + request.project_context).strip()

        if self.id == "fal":
            from ...hosted_providers.adapters.fal_adapter import chat_fal

            # fal-ai/any-llm uses a nested model enum; strip the endpoint id if selected.
            nested = model if model != "fal-ai/any-llm" else "google/gemini-2.5-flash-lite"
            result = await chat_fal(
                key,
                prompt=prompt or "Hello",
                model=nested,
                system_prompt=system_prompt,
                temperature=request.temperature,
            )
        elif self.id == "kie":
            from ...hosted_providers.adapters.kie_adapter import chat_kie

            chat_messages = []
            if system_prompt:
                chat_messages.append({"role": "system", "content": system_prompt})
            chat_messages.extend(messages if messages else [{"role": "user", "content": prompt or "Hello"}])
            result = await chat_kie(
                key,
                model_id=model if model in ("gemini-3-pro", "gemini-2.5-flash", "gemini-3-flash", "gemini-2.5-pro") else "gemini-3-pro",
                messages=chat_messages,
                temperature=request.temperature,
            )
        else:
            from ...hosted_providers.adapters.wavespeed_adapter import chat_wavespeed

            chat_messages = []
            if system_prompt:
                chat_messages.append({"role": "system", "content": system_prompt})
            chat_messages.extend(messages if messages else [{"role": "user", "content": prompt or "Hello"}])
            result = await chat_wavespeed(
                key,
                model_id=model,
                messages=chat_messages,
                temperature=request.temperature,
            )

        if not result.get("ok"):
            raise RuntimeError(result.get("message") or f"{_DISPLAY[self.id]} LLM call failed.")
        return ChatResult(
            request_id=request.request_id,
            reply=str(result.get("output") or ""),
            model_id=str(result.get("modelId") or model),
            provider_id=self.id,
            raw=result.get("raw") if isinstance(result.get("raw"), dict) else result,
        )

    def supports_stream(self) -> bool:
        return False

    async def stream(self, request: ChatRequest) -> AsyncIterator[dict[str, Any]]:
        result = await self.generate(request)
        yield {"type": "delta", "requestId": request.request_id, "text": result.reply}
        yield {
            "type": "done",
            "requestId": request.request_id,
            "providerId": self.id,
            "modelId": result.model_id,
        }
