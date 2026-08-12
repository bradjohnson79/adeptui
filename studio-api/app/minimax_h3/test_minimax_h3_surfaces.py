from __future__ import annotations

from app.minimax_h3.capability import capability_snapshot
from app.minimax_h3.contracts import AdeptMiniMaxH3Request, H3ReferenceAssignment
from app.minimax_h3.planner import build_plan
from app.minimax_h3.preflight import evaluate_request
from app.minimax_h3.service import create_job_or_block, prepare_plan
from app.minimax_h3.three_frame import build_segmented_plan
from app.minimax_h3 import store


def _three_frame_request(*, deployment: str = "local_weights", territory: str = "CA") -> AdeptMiniMaxH3Request:
    return AdeptMiniMaxH3Request(
        projectId="proj-h3",
        prompt="A young inventor crosses the lab, pauses in the middle, then reaches the final door.",
        territory=territory,
        sourceSurface="api",
        mode="three-frame",
        deployment=deployment,  # type: ignore[arg-type]
        durationSec=6,
        referenceAssignments=[
            H3ReferenceAssignment(role="start", assetId="asset-start", displayName="Start"),
            H3ReferenceAssignment(role="middle", assetId="asset-middle", displayName="Middle"),
            H3ReferenceAssignment(role="end", assetId="asset-end", displayName="End"),
        ],
    )


def _t2va_request(*, territory: str = "CA") -> AdeptMiniMaxH3Request:
    return AdeptMiniMaxH3Request(
        projectId="proj-h3",
        prompt="A lone musician stands at a coastal observatory bathed in blue light.",
        territory=territory,
        sourceSurface="text-to-video",
        mode="text-to-video",
        deployment="local_weights",
        durationSec=5,
    )


def test_us_local_blocked() -> None:
    result = evaluate_request(_three_frame_request(territory="US"))
    assert result.status == "blocked"
    assert any("not licensed" in blocker for blocker in result.blockers)


def test_ca_local_not_license_blocked() -> None:
    result = evaluate_request(_three_frame_request(territory="CA"))
    assert result.status == "blocked"
    assert all("not licensed" not in blocker for blocker in result.blockers)
    assert any("not certified" in blocker for blocker in result.blockers)


def test_three_frame_native_is_false() -> None:
    snapshot = capability_snapshot(territory="CA", deployment="api")
    assert snapshot["threeFrameNative"] is False


def test_segmented_strategy_produces_two_intervals() -> None:
    plan = build_segmented_plan(_three_frame_request())
    assert [interval.label for interval in plan.intervals] == ["Start-Middle", "Middle-End"]


def test_ltx_fallback_offer_present_when_blocked() -> None:
    result = evaluate_request(_three_frame_request(territory="US"))
    assert result.fallbackOffer is not None
    assert result.fallbackOffer.providerId == "ltx-local"


def test_no_silent_api_without_approval(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(store, "_root", lambda: tmp_path)
    plan = prepare_plan(_three_frame_request(deployment="api"))
    result = create_job_or_block(plan.projectId, plan.planId)
    assert result["status"] == "needs_approval"
    assert "approval" in str(result["message"]).lower()


def test_creator_plan_has_no_internal_runtime_labels() -> None:
    plan = build_plan(_three_frame_request(deployment="api"))
    primary_labels = " ".join(
        [
            plan.creatorSummary,
            plan.creatorDisclosure,
            *(assignment.displayName for assignment in plan.referenceAssignments),
        ]
    ).lower()
    assert "comfy" not in primary_labels
    assert ".safetensors" not in primary_labels
    assert "fl2va" not in primary_labels


# --- Private owner-only Route A path --------------------------------------


def _enable_private_local(monkeypatch) -> None:
    from app.minimax_h3 import capability, preflight, private_access, route_a_adapter, service

    # Patch the source module (used by access_snapshot / assert_private_owner_access).
    monkeypatch.setattr(private_access, "private_local_enabled", lambda: True)
    monkeypatch.setattr(private_access, "public_creator_enabled", lambda: False)
    monkeypatch.setattr(private_access, "best_match_enabled", lambda: False)
    monkeypatch.setattr(private_access, "general_routing_enabled", lambda: False)
    monkeypatch.setattr(
        private_access,
        "runtime_url_is_isolated_route_a",
        lambda url=None: True,
    )
    # Patch the imported aliases in every consumer module.
    for mod in (capability, preflight, service):
        monkeypatch.setattr(mod, "private_local_enabled", lambda: True)
    for mod in (capability,):
        monkeypatch.setattr(mod, "public_creator_enabled", lambda: False)
        monkeypatch.setattr(mod, "best_match_enabled", lambda: False)
        monkeypatch.setattr(mod, "general_routing_enabled", lambda: False)
    monkeypatch.setattr(preflight, "_route_a_ready", lambda: True)


def test_private_gate_fail_closed_when_disabled(monkeypatch) -> None:
    from app.minimax_h3 import private_access

    monkeypatch.setattr(private_access, "private_local_enabled", lambda: False)
    snap = private_access.access_snapshot()
    assert snap["privateLocalEnabled"] is False
    assert snap["ownerAccessActive"] is False
    try:
        private_access.assert_private_owner_access()
        raised = False
    except PermissionError:
        raised = True
    assert raised is True


def test_private_gate_passes_when_enabled(monkeypatch) -> None:
    _enable_private_local(monkeypatch)
    from app.minimax_h3 import private_access

    snap = private_access.assert_private_owner_access()
    assert snap["privateLocalEnabled"] is True
    assert snap["ownerAccessActive"] is True
    assert snap["publicCreatorEnabled"] is False
    assert snap["bestMatchEnabled"] is False
    assert snap["generalRoutingEnabled"] is False


def test_private_readiness_ready_when_runtime_up(monkeypatch) -> None:
    _enable_private_local(monkeypatch)
    from app.minimax_h3 import route_a_adapter

    monkeypatch.setattr(
        route_a_adapter.RouteARuntimeAdapter,
        "readiness",
        lambda self: {
            "ok": True,
            "ready": True,
            "creatorStatus": "MiniMax H3 — Ready for Private Local Use",
            "profile": {
                "label": "Experimental Private Profile",
                "width": 480,
                "height": 256,
                "length": 5,
                "steps": 4,
                "nativeAudio": True,
            },
            "missingFiles": [],
            "missingNodes": [],
        },
    )
    from app.minimax_h3.service import readiness

    result = readiness()
    assert result["ready"] is True
    assert result["privateLocalEnabled"] is True
    assert result["profile"]["label"] == "Experimental Private Profile"
    assert result["profile"]["height"] == 256


def test_private_t2va_preflight_ready(monkeypatch) -> None:
    _enable_private_local(monkeypatch)
    result = evaluate_request(_t2va_request())
    assert result.status == "ready"
    assert result.deployment == "local_weights"
    assert result.approvalRequired is False
    assert result.fallbackOffer is None


def test_private_one_frame_preflight_ready_with_start(monkeypatch) -> None:
    _enable_private_local(monkeypatch)
    req = AdeptMiniMaxH3Request(
        projectId="proj-h3",
        prompt="Keep the subject identity; gentle camera drift.",
        territory="CA",
        sourceSurface="one-frame",
        mode="one-frame",
        deployment="local_weights",
        durationSec=5,
        referenceAssignments=[
            H3ReferenceAssignment(role="start", assetId="asset-start", displayName="Start"),
        ],
    )
    result = evaluate_request(req)
    assert result.status == "ready"
    assert result.fallbackOffer is None


def test_private_one_frame_blocked_without_start(monkeypatch) -> None:
    _enable_private_local(monkeypatch)
    req = AdeptMiniMaxH3Request(
        projectId="proj-h3",
        prompt="missing start",
        territory="CA",
        sourceSurface="one-frame",
        mode="one-frame",
        deployment="local_weights",
        durationSec=5,
        referenceAssignments=[],
    )
    result = evaluate_request(req)
    assert result.status == "blocked"
    assert any("starting frame" in b.lower() for b in result.blockers)


def test_private_non_t2va_modes_blocked_with_ltx_offer(monkeypatch) -> None:
    _enable_private_local(monkeypatch)
    result = evaluate_request(_three_frame_request())
    assert result.status == "blocked"
    assert result.fallbackOffer is not None
    assert result.fallbackOffer.providerId == "ltx-local"
    assert any("not available yet" in b.lower() or "three frame" in b.lower() for b in result.blockers)


def test_private_duration_blocker_skipped_for_t2va(monkeypatch) -> None:
    _enable_private_local(monkeypatch)
    req = _t2va_request()
    req.durationSec = 1.0
    result = evaluate_request(req)
    assert result.status == "ready"
    assert not any("4 and 15" in b for b in result.blockers)


def test_private_blocked_when_runtime_down_offers_ltx(monkeypatch) -> None:
    from app.minimax_h3 import capability, preflight, private_access, service

    monkeypatch.setattr(private_access, "private_local_enabled", lambda: True)
    monkeypatch.setattr(private_access, "public_creator_enabled", lambda: False)
    monkeypatch.setattr(private_access, "best_match_enabled", lambda: False)
    monkeypatch.setattr(private_access, "general_routing_enabled", lambda: False)
    monkeypatch.setattr(
        private_access,
        "runtime_url_is_isolated_route_a",
        lambda url=None: True,
    )
    for mod in (capability, preflight, service):
        monkeypatch.setattr(mod, "private_local_enabled", lambda: True)
    for mod in (capability,):
        monkeypatch.setattr(mod, "public_creator_enabled", lambda: False)
        monkeypatch.setattr(mod, "best_match_enabled", lambda: False)
        monkeypatch.setattr(mod, "general_routing_enabled", lambda: False)
    monkeypatch.setattr(preflight, "_route_a_ready", lambda: False)
    result = evaluate_request(_t2va_request())
    assert result.status == "blocked"
    assert result.fallbackOffer is not None
    assert result.fallbackOffer.providerId == "ltx-local"


def test_private_duplicate_submit_prevented(monkeypatch, tmp_path) -> None:
    _enable_private_local(monkeypatch)
    monkeypatch.setattr(store, "_root", lambda: tmp_path)
    from app.minimax_h3 import route_a_adapter, service

    import threading

    release = threading.Event()

    class _FakeState:
        def __init__(self, **kw):
            self.__dict__.update(kw)
            self.status = "running"
            self.stage = "Generating video and audio"
            self.cancelled = False
            self.ended_at = None

    def _stub_submit(self, *, project_id, plan_id, prompt, seed=424242):
        return _FakeState(
            job_id="job-running",
            project_id=project_id,
            plan_id=plan_id,
            prompt=prompt,
            seed=seed,
            prompt_id="prompt-1",
        )

    def _stub_poll(self, state, *, timeout_sec=900.0):
        # Keep the job "running" until the test releases the thread.
        release.wait(timeout=10.0)
        return state

    monkeypatch.setattr(route_a_adapter.RouteARuntimeAdapter, "submit_t2va", _stub_submit)
    monkeypatch.setattr(route_a_adapter.RouteARuntimeAdapter, "poll", _stub_poll)
    monkeypatch.setattr(route_a_adapter.RouteARuntimeAdapter, "readiness", lambda self: {"ready": True})
    monkeypatch.setattr(route_a_adapter.RouteARuntimeAdapter, "_persist_job", lambda self, s: None)

    plan = prepare_plan(_t2va_request())
    first = create_job_or_block(plan.projectId, plan.planId)
    assert first["status"] == "running"
    second = create_job_or_block(plan.projectId, plan.planId)
    assert second["status"] == "duplicate"
    release.set()
    service._RUNNING_JOBS.clear()


def test_private_cancel_marks_plan_and_interrupts(monkeypatch, tmp_path) -> None:
    _enable_private_local(monkeypatch)
    monkeypatch.setattr(store, "_root", lambda: tmp_path)
    from app.minimax_h3 import route_a_adapter, service

    import threading

    release = threading.Event()
    cancelled = {"called": False}

    class _FakeState:
        def __init__(self, **kw):
            self.__dict__.update(kw)
            self.status = "running"
            self.stage = "Generating video and audio"
            self.cancelled = False
            self.ended_at = None

    def _stub_submit(self, *, project_id, plan_id, prompt, seed=424242):
        return _FakeState(
            job_id="job-cancel",
            project_id=project_id,
            plan_id=plan_id,
            prompt=prompt,
            seed=seed,
            prompt_id="prompt-c",
        )

    def _stub_poll(self, state, *, timeout_sec=900.0):
        release.wait(timeout=10.0)
        return state

    def _stub_cancel(self, state):
        cancelled["called"] = True
        state.cancelled = True
        state.status = "cancelled"
        state.stage = "Cancelled"
        state.ended_at = 0.0
        return state

    monkeypatch.setattr(route_a_adapter.RouteARuntimeAdapter, "submit_t2va", _stub_submit)
    monkeypatch.setattr(route_a_adapter.RouteARuntimeAdapter, "poll", _stub_poll)
    monkeypatch.setattr(route_a_adapter.RouteARuntimeAdapter, "cancel", _stub_cancel)
    monkeypatch.setattr(route_a_adapter.RouteARuntimeAdapter, "readiness", lambda self: {"ready": True})
    monkeypatch.setattr(route_a_adapter.RouteARuntimeAdapter, "_persist_job", lambda self, s: None)

    plan = prepare_plan(_t2va_request())
    create_job_or_block(plan.projectId, plan.planId)
    cancelled_plan = service.cancel(plan.projectId, plan.planId, reason="creator")
    assert cancelled_plan.status == "cancelled"
    assert cancelled["called"] is True
    release.set()
    service._RUNNING_JOBS.clear()


def test_private_capability_disables_public_best_match_routing(monkeypatch) -> None:
    _enable_private_local(monkeypatch)
    snap = capability_snapshot(territory="CA", deployment="local_weights")
    assert snap["privateLocal"] is True
    assert snap["ownerOnly"] is True
    assert snap["experimental"] is True
    assert snap["creatorEnabled"] is False
    assert snap["bestMatchEnabled"] is False
    assert snap["automaticRoutingEnabled"] is False
    assert snap["executable"] is True
    assert snap["supportsTextToVideo"] is True
    assert snap["supportsNativeAudio"] is True
    assert snap["supportsImageToVideo"] is True
    assert snap["supportsStartFrame"] is True
    assert snap["supportsStartEndFrame"] is False


def test_private_provenance_no_api_or_ltx_mislabel(monkeypatch, tmp_path) -> None:
    _enable_private_local(monkeypatch)
    monkeypatch.setattr(store, "_root", lambda: tmp_path)
    from app.minimax_h3 import route_a_adapter, service

    class _FakeState:
        def __init__(self, **kw):
            self.__dict__.update(kw)
            self.status = "running"
            self.stage = "Generating video and audio"
            self.cancelled = False
            self.ended_at = None

    def _stub_submit(self, *, project_id, plan_id, prompt, seed=424242):
        return _FakeState(
            job_id="job-prov",
            project_id=project_id,
            plan_id=plan_id,
            prompt=prompt,
            seed=seed,
            prompt_id="prompt-p",
        )

    monkeypatch.setattr(route_a_adapter.RouteARuntimeAdapter, "submit_t2va", _stub_submit)
    monkeypatch.setattr(route_a_adapter.RouteARuntimeAdapter, "poll", lambda self, s, **k: s)
    monkeypatch.setattr(route_a_adapter.RouteARuntimeAdapter, "readiness", lambda self: {"ready": True})
    monkeypatch.setattr(route_a_adapter.RouteARuntimeAdapter, "_persist_job", lambda self, s: None)

    plan = prepare_plan(_t2va_request())
    result = create_job_or_block(plan.projectId, plan.planId)
    assert result["status"] == "running"
    prov = result["provenance"]
    assert prov["modelId"] == "minimax-h3-route-a-local"
    assert prov["deployment"] == "private-local"
    assert prov["access"] == "owner-only"
    assert prov["runtime"] == "route-a"
    assert prov["apiUsed"] is False
    assert prov["ltxUsed"] is False
    service._RUNNING_JOBS.clear()
