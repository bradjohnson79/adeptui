"""Preflight checks for MiniMax H3 plans and requests."""

from __future__ import annotations

from .capability import capability_snapshot
from .contracts import AdeptMiniMaxH3Request, H3FallbackOffer, H3GenerationPlan, H3PreflightResult
from .private_access import private_local_enabled
from .route_a_adapter import RouteARuntimeAdapter
from .three_frame import validate_three_distinct_asset_roles


def _frame_exists(request: AdeptMiniMaxH3Request, role: str) -> bool:
    return any(item.role == role and str(item.assetId).strip() for item in request.referenceAssignments)


def _fallback_offer(reason: str) -> H3FallbackOffer:
    return H3FallbackOffer(reason=reason)


def _route_a_ready() -> bool:
    """Probe the isolated Route A runtime once. Best-effort; never raises."""
    try:
        return bool(RouteARuntimeAdapter().readiness().get("ready"))
    except Exception:
        return False


def _validate_request_inputs(request: AdeptMiniMaxH3Request) -> list[str]:
    blockers: list[str] = []
    # The Experimental Private Profile uses a fixed 5-frame run; the 4–15s
    # duration blocker only applies to the non-private (public/hosted) path.
    private_active = private_local_enabled() and request.deployment == "local_weights"
    if not private_active:
        if request.durationSec < 4 or request.durationSec > 15:
            blockers.append("MiniMax H3 clips need a duration between 4 and 15 seconds.")
    if request.mode == "one-frame" and not _frame_exists(request, "start"):
        blockers.append("Add a starting frame before using one-frame MiniMax H3.")
    if request.mode == "first-last":
        if not _frame_exists(request, "start"):
            blockers.append("Add a starting frame before using start-to-end MiniMax H3.")
        if not _frame_exists(request, "end"):
            blockers.append("Add an ending frame before using start-to-end MiniMax H3.")
    if request.mode == "three-frame":
        try:
            validate_three_distinct_asset_roles(request.referenceAssignments)
        except ValueError as exc:
            blockers.append(str(exc))
    if request.mode == "reference" and not request.referenceAssignments:
        blockers.append("Add at least one reference before using reference-guided MiniMax H3.")
    return blockers


def evaluate_request(request: AdeptMiniMaxH3Request) -> H3PreflightResult:
    blockers = _validate_request_inputs(request)
    warnings: list[str] = []
    capability = capability_snapshot(territory=request.territory, deployment=request.deployment)
    fallback_offer = None
    private_active = private_local_enabled() and request.deployment == "local_weights"

    if request.deployment == "local_weights":
        if private_active:
            # Private owner-only Route A: text-to-video and one-frame (I2V) are
            # executable. Other modes stay blocked with an explicit LTX offer
            # (never auto-switched / never silently downgraded I2V → T2V).
            if request.mode not in {"text-to-video", "one-frame"}:
                blockers.append(
                    "The Experimental Private Profile supports text-to-video and "
                    "one-frame image-to-video. Three Frame and reference modes are not available yet."
                )
                fallback_offer = _fallback_offer(
                    "Use LTX if you want to keep the same prompt and frames on a supported local path."
                )
                return H3PreflightResult(
                    status="blocked",
                    territory=str(request.territory or "").strip().upper(),
                    deployment=request.deployment,
                    durationSec=request.durationSec,
                    blockers=blockers,
                    warnings=warnings,
                    approvalRequired=False,
                    fallbackOffer=fallback_offer,
                    capability=capability,
                )
            if blockers:
                # e.g. one-frame without a start role — fail closed, no T2V downgrade.
                fallback_offer = _fallback_offer(
                    "Use LTX if you want to keep the same prompt and frames on a supported local path."
                )
                return H3PreflightResult(
                    status="blocked",
                    territory=str(request.territory or "").strip().upper(),
                    deployment=request.deployment,
                    durationSec=request.durationSec,
                    blockers=blockers,
                    warnings=warnings,
                    approvalRequired=False,
                    fallbackOffer=fallback_offer,
                    capability=capability,
                )
            if not _route_a_ready():
                blockers.append("MiniMax H3 private runtime is not ready right now.")
                fallback_offer = _fallback_offer(
                    "Use LTX if you want to keep the same prompt on a supported local path while MiniMax H3 is unavailable."
                )
                return H3PreflightResult(
                    status="blocked",
                    territory=str(request.territory or "").strip().upper(),
                    deployment=request.deployment,
                    durationSec=request.durationSec,
                    blockers=blockers,
                    warnings=warnings,
                    approvalRequired=False,
                    fallbackOffer=fallback_offer,
                    capability=capability,
                )
            if request.mode == "one-frame":
                warnings.append(
                    "MiniMax H3 will run image-to-video on the Experimental Private Profile "
                    "(Private Local · Owner Only) using your starting frame."
                )
            else:
                warnings.append(
                    "MiniMax H3 will run on the Experimental Private Profile (Private Local · Owner Only). "
                    "Output is a short motion draft with native audio."
                )
            return H3PreflightResult(
                status="ready",
                territory=str(request.territory or "").strip().upper(),
                deployment=request.deployment,
                durationSec=request.durationSec,
                blockers=[],
                warnings=warnings,
                approvalRequired=False,
                fallbackOffer=None,
                capability=capability,
            )
        if capability["territoryAllowed"] is False:
            blockers.append("MiniMax H3 local weights are not licensed for this territory.")
        else:
            blockers.append("MiniMax H3 local setup is not certified in this build yet.")
        fallback_offer = _fallback_offer("Use LTX if you want to keep the same prompt and frames on a supported local path.")
        return H3PreflightResult(
            status="blocked",
            territory=str(request.territory or "").strip().upper(),
            deployment=request.deployment,
            durationSec=request.durationSec,
            blockers=blockers,
            warnings=warnings,
            approvalRequired=False,
            fallbackOffer=fallback_offer,
            capability=capability,
        )

    if blockers:
        return H3PreflightResult(
            status="blocked",
            territory=str(request.territory or "").strip().upper(),
            deployment=request.deployment,
            durationSec=request.durationSec,
            blockers=blockers,
            warnings=warnings,
            approvalRequired=not bool(request.approvalId),
            fallbackOffer=fallback_offer,
            capability=capability,
        )

    if not request.approvalId:
        warnings.append("Hosted MiniMax H3 needs explicit creator approval before anything is sent out of the project.")
        return H3PreflightResult(
            status="needs_approval",
            territory=str(request.territory or "").strip().upper(),
            deployment=request.deployment,
            durationSec=request.durationSec,
            blockers=[],
            warnings=warnings,
            approvalRequired=True,
            fallbackOffer=None,
            capability=capability,
        )

    blockers.append("MiniMax H3 hosted execution is not wired in this build yet, so the request stays an honest plan.")
    return H3PreflightResult(
        status="blocked",
        territory=str(request.territory or "").strip().upper(),
        deployment=request.deployment,
        durationSec=request.durationSec,
        blockers=blockers,
        warnings=warnings,
        approvalRequired=False,
        fallbackOffer=None,
        capability=capability,
    )


def evaluate_plan(plan: H3GenerationPlan, *, approval_id: str | None = None) -> H3PreflightResult:
    request = plan.request.model_copy(deep=True)
    if approval_id:
        request.approvalId = approval_id
    return evaluate_request(request)
