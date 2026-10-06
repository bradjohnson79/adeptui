"""Authoritative per-turn runtime capability object for Co-Director.

vision_supported = the selected model advertises vision (Ollama capabilities).
vision_active = this turn actually attached JPEG images[] (vision_trace.hasImages).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

VisionState = Literal[
    "SUPPORTED",
    "ACTIVE",
    "UNAVAILABLE",
    "FAILED",
    "NOT_REQUESTED",
]


class RuntimeCapabilities(BaseModel):
    provider: str = ""
    model: str = ""
    vision_supported: bool = False
    vision_active: bool = False
    vision_state: VisionState = "NOT_REQUESTED"
    attachment_count: int = 0
    resolved_image_count: int = 0
    tools_available: bool = True
    degraded: bool = False
    degraded_reason: str = ""

    def to_context_block(self) -> str:
        """Structured context for the model — not a cosmetic prose sentence."""

        return "\n".join(
            [
                "=== Runtime capabilities (authoritative this turn) ===",
                f"provider: {self.provider or '(unknown)'}",
                f"model: {self.model or '(unknown)'}",
                f"vision_supported: {str(self.vision_supported).lower()}",
                f"vision_active: {str(self.vision_active).lower()}",
                f"vision_state: {self.vision_state}",
                f"attachment_count: {self.attachment_count}",
                f"resolved_image_count: {self.resolved_image_count}",
                f"tools_available: {str(self.tools_available).lower()}",
                f"degraded: {str(self.degraded).lower()}",
                f"degraded_reason: {self.degraded_reason or '(none)'}",
                "Answer capability questions from this object only. Do not invent a healthier state.",
            ]
        )

    def answer_capability_question(self) -> str:
        """Deterministic capability answer. No project/character/branding."""

        if self.degraded and self.degraded_reason:
            degraded_line = f" The runtime is currently degraded: {self.degraded_reason}."
        elif self.degraded:
            degraded_line = " The runtime is currently degraded."
        else:
            degraded_line = ""

        if self.vision_state == "ACTIVE" or self.vision_active:
            return (
                f"Yes — vision is active this turn. I can see {self.resolved_image_count or self.attachment_count or 1} "
                f"attached image(s) with {self.model or 'the current model'}."
                f"{degraded_line}"
            )
        if self.vision_state == "FAILED":
            reason = self.degraded_reason or "the image could not be read"
            return (
                f"Vision was requested this turn but failed. "
                f"I couldn't read that image because {reason}. "
                "Adept vision exists — this is a technical failure, not a missing capability."
                f"{degraded_line}"
            )
        if self.vision_state == "UNAVAILABLE":
            return (
                "Vision Provider Unavailable. Adept can read creator-supplied project images "
                "when the vision provider is configured, but it is not available this turn."
                f"{degraded_line}"
            )
        if self.vision_supported:
            return (
                f"The current model ({self.model or 'unknown'}) supports vision, "
                "but no image is attached to this turn, so vision is not active."
                f"{degraded_line}"
            )
        return (
            f"I am running on {self.provider or 'the selected provider'} "
            f"with {self.model or 'the current model'}. "
            "Vision is not active this turn."
            f"{degraded_line}"
        )


def _vision_state(
    *,
    vision_supported: bool | None,
    vision_active: bool,
    vision_failed: bool,
    requested: bool,
) -> VisionState:
    if vision_failed:
        return "FAILED"
    if vision_active:
        return "ACTIVE"
    if vision_supported is False:
        return "UNAVAILABLE"
    if vision_supported and not vision_active:
        return "SUPPORTED"
    if requested and not vision_active:
        return "NOT_REQUESTED"
    return "NOT_REQUESTED"


def build_runtime_capabilities(
    *,
    provider: str = "",
    model: str = "",
    vision_supported: bool | None = None,
    vision_trace: dict[str, Any] | None = None,
    attachment_ids: list[str] | None = None,
    resolved_image_count: int | None = None,
    tools_available: bool = True,
    degraded: bool = False,
    degraded_reason: str = "",
) -> RuntimeCapabilities:
    trace = vision_trace if isinstance(vision_trace, dict) else {}
    has_images = bool(trace.get("hasImages"))
    encoded = trace.get("encodedCount")
    try:
        encoded_count = int(encoded) if encoded is not None else 0
    except (TypeError, ValueError):
        encoded_count = 0
    attachments = [a for a in (attachment_ids or []) if a]
    attachment_count = len(attachments)
    if resolved_image_count is None:
        resolved_image_count = encoded_count or (attachment_count if has_images else 0)
    vision_failed = str(trace.get("error") or trace.get("status") or "").lower() in {
        "failed",
        "error",
        "unavailable",
    } or bool(trace.get("failed"))
    requested = has_images or attachment_count > 0 or encoded_count > 0
    supported = bool(vision_supported) if vision_supported is not None else False
    pixels_present = bool(has_images and (encoded_count > 0 or attachment_count > 0 or resolved_image_count > 0))
    if has_images and encoded_count > 0:
        pixels_present = True
    active = bool(pixels_present and supported)
    return RuntimeCapabilities(
        provider=provider or "",
        model=model or "",
        vision_supported=supported,
        vision_active=active,
        vision_state=_vision_state(
            vision_supported=vision_supported,
            vision_active=active,
            vision_failed=vision_failed,
            requested=requested,
        ),
        attachment_count=attachment_count,
        resolved_image_count=int(resolved_image_count or 0),
        tools_available=bool(tools_available),
        degraded=bool(degraded),
        degraded_reason=(degraded_reason or "").strip(),
    )


def capabilities_from_provider(
    provider: Any,
    *,
    model: str | None = None,
    vision_trace: dict[str, Any] | None = None,
    attachment_ids: list[str] | None = None,
    health: Any = None,
    tools_available: bool = True,
    degraded: bool = False,
    degraded_reason: str = "",
) -> RuntimeCapabilities:
    """Build capabilities from the live provider + this turn's vision_trace."""

    provider_id = str(getattr(provider, "id", None) or getattr(health, "provider_id", None) or "")
    model_id = str(model or getattr(health, "selected_model", None) or "")
    supported: bool | None = None
    supports = getattr(provider, "model_supports_vision", None)
    if callable(supports):
        try:
            flag = supports(model_id, health)
            if flag is not None:
                supported = bool(flag)
        except Exception:
            supported = None
    status = str(getattr(health, "status", None) or "")
    honesty = str(getattr(health, "honesty", None) or "")
    if not degraded and status.lower() in {"degraded", "error", "unavailable"}:
        degraded = True
        degraded_reason = degraded_reason or status
    if honesty and "degraded" in honesty.lower():
        degraded = True
        degraded_reason = degraded_reason or honesty
    return build_runtime_capabilities(
        provider=provider_id,
        model=model_id,
        vision_supported=supported,
        vision_trace=vision_trace,
        attachment_ids=attachment_ids,
        tools_available=tools_available,
        degraded=degraded,
        degraded_reason=degraded_reason,
    )
