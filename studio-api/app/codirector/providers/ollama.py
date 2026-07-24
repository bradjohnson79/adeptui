"""Ollama Co-Director provider — backend-only HTTP to local Ollama."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator
from urllib.parse import urlparse

import httpx

from app.codirector.errors import (
    MODEL_NOT_FOUND,
    NO_MODELS_INSTALLED,
    PROVIDER_RESPONSE_INVALID,
    PROVIDER_UNAVAILABLE,
    CoDirectorError,
    classify_httpx_error,
    redact_secrets,
)
from app.codirector.providers.base import ChatRequest, ChatResult, ProviderHealthResult, ProviderModel


def normalize_ollama_endpoint(url: str) -> str:
    raw = (url or "").strip() or "http://127.0.0.1:11434"
    if "://" not in raw:
        raw = f"http://{raw}"
    parsed = urlparse(raw)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 11434
    scheme = parsed.scheme or "http"
    return f"{scheme}://{host}:{port}".rstrip("/")


def _model_from_tag(item: dict[str, Any]) -> ProviderModel:
    name = str(item.get("name") or item.get("model") or "").strip()
    details = item.get("details") if isinstance(item.get("details"), dict) else {}
    return ProviderModel(
        id=name,
        name=name,
        size_bytes=int(item["size"]) if isinstance(item.get("size"), int) else None,
        modified_at=str(item.get("modified_at") or "") or None,
        family=str(details.get("family") or "") or None,
        parameter_size=str(details.get("parameter_size") or "") or None,
        quantization=str(details.get("quantization_level") or "") or None,
    )


class OllamaProvider:
    id = "ollama"
    display_name = "Ollama"

    def __init__(self, *, base_url: str, default_model: str, timeout_sec: float = 120.0) -> None:
        self.endpoint = normalize_ollama_endpoint(base_url)
        self.default_model = (default_model or "").strip() or None
        self.timeout_sec = float(timeout_sec)

    async def list_models(self) -> list[ProviderModel]:
        try:
            async with httpx.AsyncClient(timeout=min(8.0, self.timeout_sec)) as client:
                r = await client.get(f"{self.endpoint}/api/tags")
                r.raise_for_status()
                data = r.json()
        except Exception as exc:  # noqa: BLE001
            raise classify_httpx_error(exc, endpoint=self.endpoint, provider=self.id) from exc
        models_raw = data.get("models") if isinstance(data, dict) else None
        if not isinstance(models_raw, list):
            raise CoDirectorError(
                PROVIDER_RESPONSE_INVALID,
                "Ollama returned an invalid model list.",
                details={"provider": self.id, "endpoint": self.endpoint},
                recommended_action="retry_or_check_service",
            )
        out: list[ProviderModel] = []
        for item in models_raw:
            if isinstance(item, dict):
                m = _model_from_tag(item)
                if m.id:
                    out.append(m)
        return out

    async def health(self) -> ProviderHealthResult:
        try:
            models = await self.list_models()
        except CoDirectorError as err:
            status = "Not Running" if err.code in ("CONNECTION_REFUSED", "PROVIDER_UNAVAILABLE") else "Degraded"
            return ProviderHealthResult(
                provider_id=self.id,
                display_name=self.display_name,
                status=status,
                reachable=False,
                endpoint=self.endpoint,
                selected_model=self.default_model,
                model_available=False,
                models=[],
                message=err.message,
                code=err.code,
                recommended_action=err.recommended_action,
            )

        if not models:
            return ProviderHealthResult(
                provider_id=self.id,
                display_name=self.display_name,
                status="No Models",
                reachable=True,
                endpoint=self.endpoint,
                selected_model=self.default_model,
                model_available=False,
                models=[],
                message="Ollama is running, but no compatible models are installed.",
                code=NO_MODELS_INSTALLED,
                recommended_action="install_or_select_model",
            )

        selected = self.default_model
        ids = {m.id for m in models}
        # Allow tag-less match (model:tag vs model)
        available = False
        if selected:
            available = selected in ids or any(m.id.split(":")[0] == selected.split(":")[0] for m in models)
        if selected and not available:
            return ProviderHealthResult(
                provider_id=self.id,
                display_name=self.display_name,
                status="Model Missing",
                reachable=True,
                endpoint=self.endpoint,
                selected_model=selected,
                model_available=False,
                models=models,
                message=f"The selected model '{selected}' is not installed.",
                code=MODEL_NOT_FOUND,
                recommended_action="select_model",
            )
        if not selected:
            return ProviderHealthResult(
                provider_id=self.id,
                display_name=self.display_name,
                status="Not Configured",
                reachable=True,
                endpoint=self.endpoint,
                selected_model=None,
                model_available=False,
                models=models,
                message="Select a model before chatting with Co-Director.",
                code="MODEL_NOT_SELECTED",
                recommended_action="select_model",
            )
        return ProviderHealthResult(
            provider_id=self.id,
            display_name=self.display_name,
            status="Ready",
            reachable=True,
            endpoint=self.endpoint,
            selected_model=selected,
            model_available=True,
            models=models,
            message="Ollama is ready.",
        )

    async def generate(self, request: ChatRequest) -> ChatResult:
        health = await self.health()
        if not health.reachable:
            raise CoDirectorError(
                health.code or PROVIDER_UNAVAILABLE,
                health.message or f"Co-Director could not reach Ollama at {self.endpoint}.",
                details={"provider": self.id, "endpoint": self.endpoint},
                recommended_action=health.recommended_action or "retry_or_check_service",
            )
        if health.code == NO_MODELS_INSTALLED:
            raise CoDirectorError(
                NO_MODELS_INSTALLED,
                health.message,
                details={"provider": self.id, "endpoint": self.endpoint},
                recommended_action="install_or_select_model",
            )

        model = (request.model_id or health.selected_model or "").strip()
        if not model:
            raise CoDirectorError(
                "MODEL_NOT_SELECTED",
                "Select a model before chatting with Co-Director.",
                details={"provider": self.id},
                recommended_action="select_model",
            )
        ids = {m.id for m in health.models}
        if model not in ids and not any(m.id.split(":")[0] == model.split(":")[0] for m in health.models):
            raise CoDirectorError(
                MODEL_NOT_FOUND,
                f"The selected model '{model}' is not installed. Choose an available model in Co-Director Options.",
                details={"provider": self.id, "model": model, "endpoint": self.endpoint},
                recommended_action="select_model",
            )

        payload = {
            "model": model,
            "messages": request.messages,
            "stream": False,
            "options": {"temperature": float(request.temperature)},
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                r = await client.post(f"{self.endpoint}/api/chat", json=payload)
                if r.status_code >= 400:
                    body = redact_secrets((r.text or "")[:300])
                    if r.status_code == 404 or "not found" in body.lower():
                        raise CoDirectorError(
                            MODEL_NOT_FOUND,
                            f"The selected model '{model}' is not installed.",
                            details={"provider": self.id, "model": model},
                            recommended_action="select_model",
                        )
                    raise CoDirectorError(
                        PROVIDER_RESPONSE_INVALID,
                        "Ollama returned an error for this chat request.",
                        details={"provider": self.id, "status": r.status_code, "body": body},
                        recommended_action="retry_or_check_service",
                    )
                data = r.json()
        except CoDirectorError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise classify_httpx_error(exc, endpoint=self.endpoint, provider=self.id) from exc

        msg = data.get("message") if isinstance(data, dict) else None
        content = ""
        if isinstance(msg, dict):
            content = str(msg.get("content") or "")
        if not content.strip():
            raise CoDirectorError(
                PROVIDER_RESPONSE_INVALID,
                "Ollama returned an empty reply.",
                details={"provider": self.id, "model": model},
                recommended_action="retry",
            )
        return ChatResult(
            request_id=request.request_id,
            reply=content,
            model_id=model,
            provider_id=self.id,
            raw={"eval_count": data.get("eval_count") if isinstance(data, dict) else None},
        )

    def supports_stream(self) -> bool:
        return True

    async def stream(self, request: ChatRequest) -> AsyncIterator[dict[str, Any]]:
        # Non-chunked path for reliability: generate then emit tokens.
        # Full NDJSON streaming can be added later without changing FE event schema.
        yield {"type": "request_started", "requestId": request.request_id}
        yield {"type": "provider_connected", "requestId": request.request_id, "providerId": self.id}
        result = await self.generate(request)
        # Emit as a few chunks so UI can show incremental updates
        text = result.reply
        step = max(24, len(text) // 8) if text else 24
        for i in range(0, len(text), step):
            yield {"type": "token", "requestId": request.request_id, "content": text[i : i + step]}
        yield {
            "type": "completed",
            "requestId": request.request_id,
            "content": text,
            "modelId": result.model_id,
            "providerId": self.id,
        }


def parse_stream_line(line: str) -> dict[str, Any] | None:
    line = (line or "").strip()
    if not line:
        return None
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None
