"""Ollama Co-Director provider — backend-only HTTP to local Ollama."""

from __future__ import annotations

import json
import time
from typing import Any, AsyncIterator
from urllib.parse import urlparse

import httpx

from app.codirector.creator_response_gate import (
    extract_creator_content,
    gate_creator_facing,
    record_contamination_incident,
)
from app.codirector.errors import (
    MODEL_NOT_FOUND,
    NO_MODELS_INSTALLED,
    OLLAMA_EMPTY_RESPONSE,
    OLLAMA_MODEL_NOT_FOUND,
    PROVIDER_RESPONSE_INVALID,
    PROVIDER_UNAVAILABLE,
    CoDirectorError,
    classify_httpx_error,
    redact_secrets,
)
from app.codirector.providers.base import ChatRequest, ChatResult, ProviderHealthResult, ProviderModel

# Keep selected local models warm between ordinary conversational turns.
_DEFAULT_KEEP_ALIVE = "30m"
# Avoid /api/tags on every generate — cache health briefly.
_HEALTH_CACHE_TTL_SEC = 30.0


def normalize_ollama_endpoint(url: str) -> str:
    raw = (url or "").strip() or "http://127.0.0.1:11434"
    if "://" not in raw:
        raw = f"http://{raw}"
    parsed = urlparse(raw)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 11434
    scheme = parsed.scheme or "http"
    return f"{scheme}://{host}:{port}".rstrip("/")


def _message_text(msg: dict[str, Any] | None) -> str:
    """Creator-facing content only — never promote thinking/reasoning fields."""
    return extract_creator_content(msg).creatorFacingContent


async def _chat_once(
    client: httpx.AsyncClient,
    endpoint: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    r = await client.post(f"{endpoint}/api/chat", json=payload)
    if r.status_code >= 400:
        body = redact_secrets((r.text or "")[:300])
        model = str(payload.get("model") or "")
        if r.status_code == 404 or "not found" in body.lower():
            raise CoDirectorError(
                OLLAMA_MODEL_NOT_FOUND,
                f"The selected model '{model}' is not installed.",
                details={"provider": "ollama", "model": model},
                recommended_action="select_model",
            )
        raise CoDirectorError(
            PROVIDER_RESPONSE_INVALID,
            "Ollama returned an error for this chat request.",
            details={"provider": "ollama", "status": r.status_code, "body": body},
            recommended_action="retry_or_check_service",
        )
    data = r.json()
    return data if isinstance(data, dict) else {}


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
        self.keep_alive = _DEFAULT_KEEP_ALIVE
        self._health_cache: ProviderHealthResult | None = None
        self._health_cache_at: float = 0.0

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

    async def health(self, *, force: bool = False) -> ProviderHealthResult:
        now = time.monotonic()
        if (
            not force
            and self._health_cache is not None
            and (now - self._health_cache_at) < _HEALTH_CACHE_TTL_SEC
        ):
            return self._health_cache

        result = await self._health_uncached()
        self._health_cache = result
        self._health_cache_at = now
        return result

    async def _health_uncached(self) -> ProviderHealthResult:
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

    def _resolve_model(self, request: ChatRequest, health: ProviderHealthResult) -> str:
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
        return model

    def _chat_options(self, request: ChatRequest) -> dict[str, Any]:
        """Bound context window to prompt size — oversized num_ctx inflates prefill TTFT."""
        chars = sum(len(str(m.get("content") or "")) for m in (request.messages or []))
        # ~4 chars/token; pad for reply headroom but keep ordinary chat under 8k.
        approx_tokens = max(512, chars // 4)
        num_ctx = 2048 if approx_tokens < 1200 else 4096 if approx_tokens < 2800 else 8192
        if approx_tokens >= 6000:
            num_ctx = 16384
        return {"temperature": float(request.temperature), "num_ctx": num_ctx}

    async def is_model_loaded(self, model_id: str | None) -> bool | None:
        """Return True if model is in Ollama /api/ps, False if not, None if probe failed."""
        if not model_id:
            return None
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(f"{self.endpoint}/api/ps")
                if r.status_code >= 400:
                    return None
                data = r.json() if r.content else {}
                models = data.get("models") if isinstance(data, dict) else None
                if not isinstance(models, list):
                    return None
                needle = model_id.split(":")[0].lower()
                for m in models:
                    name = str((m or {}).get("name") or (m or {}).get("model") or "").lower()
                    if name == model_id.lower() or name.split(":")[0] == needle:
                        return True
                return False
        except Exception:  # noqa: BLE001
            return None

    async def generate(self, request: ChatRequest) -> ChatResult:
        health = await self.health()
        model = self._resolve_model(request, health)
        payload = {
            "model": model,
            "messages": request.messages,
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": self._chat_options(request),
        }
        internal_reasoning: str | None = None
        try:
            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                data = await _chat_once(client, self.endpoint, payload)
                msg = data.get("message") if isinstance(data, dict) else None
                turn = extract_creator_content(msg if isinstance(msg, dict) else None)
                content = turn.creatorFacingContent
                internal_reasoning = turn.internalReasoning
                # Empty creator content: one same-model retry with think disabled (never merge thinking).
                if not content.strip():
                    retry_payload = {**payload, "think": False}
                    data = await _chat_once(client, self.endpoint, retry_payload)
                    msg = data.get("message") if isinstance(data, dict) else None
                    turn = extract_creator_content(msg if isinstance(msg, dict) else None)
                    content = turn.creatorFacingContent
                    internal_reasoning = turn.internalReasoning or internal_reasoning
                gated = gate_creator_facing(
                    content, internal_reasoning=internal_reasoning, request_id=request.request_id
                )
                if gated.contaminated and not gated.creatorFacingContent.strip():
                    # Regenerate once with think=false after contamination block.
                    record_contamination_incident(
                        project_id="",
                        request_id=request.request_id,
                        matches=gated.contaminationMatches,
                        action="regenerate_think_false",
                    )
                    retry_payload = {**payload, "think": False}
                    data = await _chat_once(client, self.endpoint, retry_payload)
                    msg = data.get("message") if isinstance(data, dict) else None
                    turn = extract_creator_content(msg if isinstance(msg, dict) else None)
                    gated = gate_creator_facing(
                        turn.creatorFacingContent,
                        internal_reasoning=turn.internalReasoning,
                        request_id=request.request_id,
                    )
                content = gated.creatorFacingContent
                internal_reasoning = gated.internalReasoning
        except CoDirectorError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise classify_httpx_error(exc, endpoint=self.endpoint, provider=self.id) from exc

        if not content.strip():
            raise CoDirectorError(
                OLLAMA_EMPTY_RESPONSE,
                "Ollama returned an empty reply. The request reached the model, but no creator-facing text was produced.",
                details={
                    "provider": self.id,
                    "model": model,
                    "streamInspected": False,
                    "contentTokens": 0,
                    "retriedOnce": True,
                },
                recommended_action="retry",
            )
        return ChatResult(
            request_id=request.request_id,
            reply=content,
            model_id=model,
            provider_id=self.id,
            raw={
                "eval_count": data.get("eval_count") if isinstance(data, dict) else None,
                "internalReasoningPresent": bool(internal_reasoning),
            },
        )

    def supports_stream(self) -> bool:
        return True

    async def stream(self, request: ChatRequest) -> AsyncIterator[dict[str, Any]]:
        """True NDJSON token stream from Ollama (stream=true)."""
        health = await self.health()
        model = self._resolve_model(request, health)
        payload = {
            "model": model,
            "messages": request.messages,
            "stream": True,
            "keep_alive": self.keep_alive,
            "options": self._chat_options(request),
        }
        yield {"type": "request_started", "requestId": request.request_id}
        yield {"type": "provider_connected", "requestId": request.request_id, "providerId": self.id}

        text_parts: list[str] = []
        try:
            timeout = httpx.Timeout(self.timeout_sec, connect=min(30.0, self.timeout_sec))
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", f"{self.endpoint}/api/chat", json=payload) as resp:
                    if resp.status_code >= 400:
                        body = redact_secrets((await resp.aread()).decode("utf-8", errors="ignore")[:300])
                        if resp.status_code == 404 or "not found" in body.lower():
                            raise CoDirectorError(
                                OLLAMA_MODEL_NOT_FOUND,
                                f"The selected model '{model}' is not installed.",
                                details={"provider": self.id, "model": model},
                                recommended_action="select_model",
                            )
                        raise CoDirectorError(
                            PROVIDER_RESPONSE_INVALID,
                            "Ollama returned an error for this chat request.",
                            details={"provider": self.id, "status": resp.status_code, "body": body},
                            recommended_action="retry_or_check_service",
                        )
                    async for line in resp.aiter_lines():
                        from ..service import is_cancelled

                        if is_cancelled(request.request_id):
                            await resp.aclose()
                            yield {"type": "cancelled", "requestId": request.request_id}
                            return
                        data = parse_stream_line(line)
                        if not data:
                            continue
                        msg = data.get("message") if isinstance(data.get("message"), dict) else None
                        # Stream creator-facing content only — never emit thinking/reasoning tokens.
                        piece = str((msg or {}).get("content") or "") if msg else ""
                        if piece:
                            text_parts.append(piece)
                            yield {
                                "type": "token",
                                "requestId": request.request_id,
                                "content": piece,
                            }
                        if data.get("done"):
                            break
        except CoDirectorError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise classify_httpx_error(exc, endpoint=self.endpoint, provider=self.id) from exc

        text = "".join(text_parts)
        gated = gate_creator_facing(text, request_id=request.request_id)
        if gated.contaminated and not gated.creatorFacingContent.strip():
            text = ""
        else:
            text = gated.creatorFacingContent
        if not text.strip():
            # One safe non-stream retry with think disabled (same model; no silent swap).
            try:
                async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                    data = await _chat_once(
                        client,
                        self.endpoint,
                        {
                            "model": model,
                            "messages": request.messages,
                            "stream": False,
                            "keep_alive": self.keep_alive,
                            "think": False,
                            "options": self._chat_options(request),
                        },
                    )
                msg = data.get("message") if isinstance(data, dict) else None
                turn = extract_creator_content(msg if isinstance(msg, dict) else None)
                gated = gate_creator_facing(
                    turn.creatorFacingContent,
                    internal_reasoning=turn.internalReasoning,
                    request_id=request.request_id,
                )
                text = gated.creatorFacingContent
                if text.strip():
                    # Replace any contaminated stream with clean final content.
                    yield {
                        "type": "token",
                        "requestId": request.request_id,
                        "content": text,
                        "replace": True,
                    }
            except CoDirectorError:
                raise
            except Exception as exc:  # noqa: BLE001
                raise classify_httpx_error(exc, endpoint=self.endpoint, provider=self.id) from exc
        if not text.strip():
            raise CoDirectorError(
                OLLAMA_EMPTY_RESPONSE,
                "Ollama returned an empty reply. The stream completed without creator-facing content.",
                details={
                    "provider": self.id,
                    "model": model,
                    "streamInspected": True,
                    "contentTokens": 0,
                    "retriedOnce": True,
                },
                recommended_action="retry",
            )
        yield {
            "type": "completed",
            "requestId": request.request_id,
            "content": text,
            "modelId": model,
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
