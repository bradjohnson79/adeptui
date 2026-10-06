"""plan_image_route — exact, then compatible hosted, then AUTO local. Never silent."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from typing import Any

from ...production_control.image_generator_query import (
    ImageGeneratorCandidate,
    list_compatible_image_generators,
    match_explicit_image_generator,
    select_auto_image_generator,
)
from .availability import evaluate_candidate, observe_hosted_provider_state
from .contracts import (
    CandidateAvailability,
    FallbackAudit,
    ImageRoutePlan,
    ProviderAvailability,
    RouteLock,
)
from .lock import creator_route_label

_LABEL_RANK = {
    "Certified": 4,
    "Available": 3,
    "Testing": 2,
    "Draft": 1,
}
_HOSTED_PROVIDER_ALIASES = {"fal", "fal.ai", "hosted", "api"}


MatchFn = Callable[..., ImageGeneratorCandidate | None]
ListFn = Callable[..., list[ImageGeneratorCandidate]]
SelectFn = Callable[..., Any]
ObserveFn = Callable[[str], ProviderAvailability]


def _norm_provider(value: str) -> str:
    token = (value or "").strip().lower().replace(".ai", "")
    if token in {"hosted", "api", "falai"}:
        return "fal"
    return token


def _norm_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _candidate_matches_token(candidate: ImageGeneratorCandidate, token: str) -> bool:
    needle = _norm_token(token)
    if len(needle) < 3:
        return False
    if needle in {"gptimage2", "gptimage2kie", "gptimage2fal"}:
        hay = _norm_token(f"{candidate.model_id} {candidate.label} {candidate.family}")
        return "gptimage2" in hay or hay.endswith("gptimage")
    haystacks = (
        _norm_token(candidate.model_id),
        _norm_token(candidate.label),
        _norm_token(candidate.family),
    )
    return any(
        hay and (needle == hay or needle in hay or hay.startswith(needle) or needle.startswith(hay))
        for hay in haystacks
    )


def _same_provider(candidate: ImageGeneratorCandidate, provider: str) -> bool:
    want = _norm_provider(provider)
    if not want:
        return False
    have = _norm_provider(candidate.provider)
    mid = (candidate.model_id or "").lower()
    if want == "fal":
        return have == "fal" or "fal" in mid
    if want in {"local", "comfy"}:
        return candidate.is_local
    return have == want or want in mid


def _rank(candidates: Sequence[ImageGeneratorCandidate]) -> list[ImageGeneratorCandidate]:
    try:
        from ...hosted_providers.registry import PRIORITY_ORDER

        order = {pid: idx for idx, pid in enumerate(PRIORITY_ORDER)}
    except Exception:
        order = {"kie": 0, "wavespeed": 1, "fal": 2}

    def key(item: ImageGeneratorCandidate) -> tuple[int, int, int, int]:
        pid = _norm_provider(item.provider)
        return (
            1 if item.default_eligible else 0,
            _LABEL_RANK.get(item.capability_label, 0),
            0 if item.is_local else 1,
            -(order.get(pid, 99)),
        )

    return sorted(candidates, key=key, reverse=True)


def _provider_state(
    provider_id: str,
    *,
    injected: dict[str, ProviderAvailability] | None,
    observe: ObserveFn,
) -> ProviderAvailability:
    pid = _norm_provider(provider_id)
    if injected and pid in injected:
        return injected[pid]
    if injected and provider_id in injected:
        return injected[provider_id]
    return observe(pid or provider_id)


def _disclose(
    *,
    lock: RouteLock,
    selected: ImageGeneratorCandidate,
    step: str,
) -> str:
    requested = lock.requested_model_id or lock.requested_provider
    label = creator_route_label(requested or selected.label)
    if step == "exact":
        return ""
    if step == "auto_local" and lock.level == "UNLOCKED":
        # AUTO is local-first. Local success is the intended path, not a fallback.
        return ""
    if selected.is_local:
        return "The hosted routes aren't available right now, so I'm generating this locally instead."
    if lock.requested_model_id:
        return f"{label} isn't available on that API, so I'm using the next available image API."
    if lock.requested_provider:
        return f"{creator_route_label(lock.requested_provider)} isn't available, so I'm using the next available image API."
    return "The local image engine isn't available right now, so I'm using a hosted image API instead."


def _strict_block(lock: RouteLock, availability: CandidateAvailability | None) -> str:
    if lock.scope == "model":
        label = creator_route_label(lock.requested_model_id)
        reason = (availability.why if availability else "it isn't available")
        return f"{label} isn't available ({reason}). You asked me to use only that model, so I stopped."
    if lock.scope == "provider":
        label = creator_route_label(lock.requested_provider)
        reason = (availability.why if availability else "it isn't available")
        return f"{label} isn't available ({reason}). You asked me to use only that API, so I stopped."
    return "That image generator isn't available. You asked me not to switch, so I stopped."


def _incompatible_pair_error(
    lock: RouteLock,
    matched: ImageGeneratorCandidate | None,
    availability: CandidateAvailability | None,
) -> str:
    """Creator-facing reason when a named model does not live on the named API."""

    model_label = creator_route_label(lock.requested_model_id)
    provider_label = creator_route_label(lock.requested_provider)
    if matched is None:
        return (
            f"{model_label} isn't available on {provider_label}. "
            f"I can't generate with {provider_label} + {model_label}."
        )
    actual = creator_route_label(matched.provider or matched.locality)
    if availability is not None and not availability.executable_catalog:
        ready = "isn't ready to run"
    else:
        ready = (availability.why if availability and availability.why else "isn't available")
    return (
        f"{model_label} isn't available on {provider_label}. "
        f"{model_label} runs on {actual} and {ready}. "
        f"I can't generate with {provider_label} + {model_label}."
    )


def plan_image_route(
    *,
    task: str = "text_to_image",
    lock: RouteLock | None = None,
    explicit_name: str = "",
    requested_provider: str = "",
    requested_model_id: str = "",
    project_id: str = "",
    attempted: set[str] | None = None,
    local_runtime_ready: bool = True,
    catalog: Sequence[ImageGeneratorCandidate] | None = None,
    provider_states: dict[str, ProviderAvailability] | None = None,
    match_explicit: MatchFn | None = None,
    list_compatible: ListFn | None = None,
    select_auto: SelectFn | None = None,
    observe_provider: ObserveFn | None = None,
) -> ImageRoutePlan:
    """Exact requested route, then fail-forward unless STRICT."""

    route_lock = lock or RouteLock()
    if requested_provider:
        route_lock = RouteLock(
            level=route_lock.level,
            scope=route_lock.scope or ("provider" if not requested_model_id else route_lock.scope),
            requested_provider=_norm_provider(requested_provider) or route_lock.requested_provider,
            requested_model_id=route_lock.requested_model_id,
            restated=route_lock.restated,
        )
    if requested_model_id:
        route_lock = RouteLock(
            level=route_lock.level,
            scope=route_lock.scope or "model",
            requested_provider=route_lock.requested_provider,
            requested_model_id=requested_model_id,
            restated=route_lock.restated,
        )
    name = (explicit_name or route_lock.requested_model_id or "").strip()
    if _norm_provider(name) in _HOSTED_PROVIDER_ALIASES and not route_lock.requested_provider:
        route_lock = RouteLock(
            level=route_lock.level,
            scope=route_lock.scope or "provider",
            requested_provider="fal",
            requested_model_id="",
            restated=route_lock.restated,
        )
        name = ""

    match_fn = match_explicit or match_explicit_image_generator
    list_fn = list_compatible or list_compatible_image_generators
    select_fn = select_auto or select_auto_image_generator
    observe = observe_provider or observe_hosted_provider_state
    tried = set(attempted or ())
    probes: list[dict[str, Any]] = []
    seen_eval: list[dict[str, Any]] = []
    last_fail: CandidateAvailability | None = None

    def _eval(candidate: ImageGeneratorCandidate | None, named: str = "") -> CandidateAvailability:
        nonlocal last_fail
        pid = ""
        if candidate is not None:
            pid = _norm_provider(candidate.provider) or ("comfy" if candidate.is_local else "")
        state = (
            None
            if not pid or pid in {"comfy", "local"}
            else _provider_state(pid, injected=provider_states, observe=observe)
        )
        if state is not None and not any(p.get("providerId") == state.provider_id for p in probes):
            probes.append(state.as_dict())
        result = evaluate_candidate(
            candidate,
            task=task,
            provider_state=state,
            local_runtime_ready=local_runtime_ready,
            named=named,
        )
        seen_eval.append(result.as_dict())
        if not result.model_available:
            last_fail = result
        return result

    def _list(locality: str | None, executable_only: bool) -> list[ImageGeneratorCandidate]:
        if catalog is not None:
            rows = list(catalog)
            if rows and all(isinstance(item, ImageGeneratorCandidate) for item in rows):
                return [
                    item
                    for item in rows
                    if (locality is None or item.locality == locality)
                    and (not executable_only or item.executable)
                ]
        kwargs: dict[str, Any] = {
            "task": task,
            "locality": locality,
            "executable_only": executable_only,
        }
        if catalog is not None:
            kwargs["models"] = catalog
        try:
            return list(list_fn(**kwargs))
        except TypeError:
            kwargs.pop("models", None)
            return list(list_fn(task, locality))

    def _finish(
        selected: ImageGeneratorCandidate | None,
        *,
        step: str,
        blocked: bool,
        error: str = "",
        disclose: str = "",
    ) -> ImageRoutePlan:
        funding = "unknown"
        failure = last_fail.failure_class if last_fail else ""
        if selected is not None:
            avail = next(
                (row for row in seen_eval if row.get("modelId") == selected.model_id and row.get("modelAvailable")),
                None,
            )
            if avail:
                funding = str(avail.get("fundingState") or "unknown")
        why = ""
        if selected is not None:
            why = f"step={step}; selected={selected.model_id}; lock={route_lock.level}"
        elif error:
            why = error
        audit = FallbackAudit(
            requested_provider=route_lock.requested_provider,
            requested_model_id=route_lock.requested_model_id or name,
            lock_level=route_lock.level,
            lock_scope=route_lock.scope,
            probes=probes,
            candidates=seen_eval,
            selected_model_id=selected.model_id if selected else "",
            selected_provider=(selected.provider if selected else ""),
            selected_locality=(selected.locality if selected else ""),
            why=why,
            funding_state=funding,
            disclose=disclose,
            attempted=sorted(tried),
            step=step,
            failure_class=failure or "",
        )
        return ImageRoutePlan(
            selected=selected,
            blocked=blocked,
            error=error,
            disclose=disclose,
            lock=route_lock,
            audit=audit,
            hosted=bool(selected is not None and not selected.is_local),
            step=step,
            attempted=tried,
        )

    def _take(candidate: ImageGeneratorCandidate, step: str) -> ImageRoutePlan | None:
        if candidate.model_id in tried:
            return None
        availability = _eval(candidate, named=candidate.model_id)
        tried.add(candidate.model_id)
        if not availability.model_available:
            return None
        disclose = _disclose(lock=route_lock, selected=candidate, step=step)
        return _finish(candidate, step=step, blocked=False, disclose=disclose)

    # UNLOCKED is AUTO local-first. Leftover dock/profile/preference names
    # (gptimage2, fal, a prior job id) must not become step=exact.
    # A creator-named model or API is PREFERRED or STRICT from parse_route_lock.
    unlocked_auto = route_lock.level == "UNLOCKED"
    if unlocked_auto:
        name = ""
        named_request = False
        raw_model = ""
        model_token = ""
    else:
        named_request = bool(name or route_lock.requested_provider)
        raw_model = (route_lock.requested_model_id or name or "").strip()
        model_token = "" if _norm_provider(raw_model) in _HOSTED_PROVIDER_ALIASES else raw_model
    matched_named: ImageGeneratorCandidate | None = None

    if named_request and name and _norm_provider(name) not in _HOSTED_PROVIDER_ALIASES:
        matched = None
        try:
            matched = match_fn(name)
        except TypeError:
            matched = match_fn(name)
        matched_named = matched
        if matched is not None and matched.model_id not in tried:
            taken = _take(matched, "exact")
            if taken is not None:
                return taken
            if route_lock.blocks_other_models():
                return _finish(
                    None,
                    step="exact",
                    blocked=True,
                    error=_strict_block(route_lock, last_fail),
                )
        elif matched is None:
            last_fail = _eval(None, named=name)
            tried.add(name)
            if route_lock.blocks_other_models():
                return _finish(
                    None,
                    step="exact",
                    blocked=True,
                    error=_strict_block(route_lock, last_fail),
                )

    # Named model + named API must compose on that API. Search the named
    # provider before declaring the pair impossible. Do not silently hand
    # the still to Flux, Qwen, or a different hosted API.
    if route_lock.requested_provider and model_token:
        candidate = matched_named
        if candidate is None:
            try:
                candidate = match_fn(model_token)
            except TypeError:
                candidate = match_fn(model_token)
            except Exception:
                candidate = None
        if candidate is None or not _same_provider(candidate, route_lock.requested_provider):
            composing = [
                item
                for item in _list("hosted", False)
                if _same_provider(item, route_lock.requested_provider)
                and _candidate_matches_token(item, model_token)
                and item.model_id not in tried
            ]
            for item in _rank(composing):
                taken = _take(item, "exact")
                if taken is not None:
                    return taken
            avail = last_fail
            if candidate is not None and candidate.model_id not in {row.get("modelId") for row in seen_eval}:
                avail = _eval(candidate, named=candidate.model_id)
                tried.add(candidate.model_id)
            elif candidate is None and model_token not in tried:
                avail = _eval(None, named=model_token)
                tried.add(model_token)
            return _finish(
                None,
                step="exact",
                blocked=True,
                error=_incompatible_pair_error(route_lock, candidate, avail),
            )

    provider_for_exact = route_lock.requested_provider
    if named_request and provider_for_exact and (not name or _norm_provider(name) in _HOSTED_PROVIDER_ALIASES):
        pool = [
            item
            for item in _list("hosted", False)
            if _same_provider(item, provider_for_exact) and item.model_id not in tried
        ]
        for candidate in _rank(pool):
            taken = _take(candidate, "exact")
            if taken is not None:
                return taken
        if route_lock.blocks_other_providers():
            return _finish(
                None,
                step="exact",
                blocked=True,
                error=_strict_block(route_lock, last_fail),
            )

    if not unlocked_auto and not route_lock.blocks_other_models():
        same_provider = route_lock.requested_provider
        if not same_provider and last_fail is not None:
            same_provider = last_fail.provider
        if same_provider:
            locality = "local" if same_provider in {"local", "comfy"} else "hosted"
            pool = [
                item
                for item in _list(locality, False)
                if _same_provider(item, same_provider) and item.model_id not in tried
            ]
            for candidate in _rank(pool):
                taken = _take(candidate, "same_provider")
                if taken is not None:
                    return taken
            if route_lock.blocks_other_providers():
                return _finish(
                    None,
                    step="same_provider",
                    blocked=True,
                    error=_strict_block(route_lock, last_fail),
                )

    if route_lock.blocks_other_providers():
        return _finish(
            None,
            step="blocked",
            blocked=True,
            error=_strict_block(route_lock, last_fail),
        )

    if not unlocked_auto:
        hosted_pool = [item for item in _list("hosted", False) if item.model_id not in tried]
        for candidate in _rank(hosted_pool):
            taken = _take(candidate, "other_hosted")
            if taken is not None:
                return taken

    if unlocked_auto:
        auto_kwargs: dict[str, Any] = {"task": task, "project_id": project_id}
        if catalog is not None:
            auto_kwargs["models"] = catalog
        try:
            auto = select_fn(**auto_kwargs)
        except TypeError:
            auto_kwargs.pop("models", None)
            auto = select_fn(task, project_id=project_id)
        local_pick = getattr(auto, "selected", None)
        if (
            local_pick is not None
            and getattr(local_pick, "is_local", False)
            and local_pick.model_id not in tried
        ):
            taken = _take(local_pick, "auto_local")
            if taken is not None:
                return taken
        hosted_pool = [item for item in _list("hosted", False) if item.model_id not in tried]
        for candidate in _rank(hosted_pool):
            taken = _take(candidate, "other_hosted")
            if taken is not None:
                return taken
    else:
        auto_kwargs = {"task": task, "project_id": project_id}
        if catalog is not None:
            auto_kwargs["models"] = catalog
        try:
            auto = select_fn(**auto_kwargs)
        except TypeError:
            auto_kwargs.pop("models", None)
            auto = select_fn(task)
        local_pick = getattr(auto, "selected", None)
        if (
            local_pick is not None
            and getattr(local_pick, "is_local", False)
            and local_pick.model_id not in tried
        ):
            taken = _take(local_pick, "auto_local")
            if taken is not None:
                return taken
        for candidate in _list("local", False):
            if candidate.model_id in tried:
                continue
            taken = _take(candidate, "auto_local")
            if taken is not None:
                return taken

    return _finish(
        None,
        step="exhausted",
        blocked=True,
        error=(
            last_fail.why
            if last_fail and last_fail.why
            else "No compatible image generator is available right now."
        ),
    )
