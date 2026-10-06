"""MiniMax H3 resolution-fit guidance — never Not viable for 720p/1080p on 32GB class."""

from __future__ import annotations

from app.video_runtime.h3_resolution_guidance import (
    H3_RESOLUTION_FIT,
    apply_h3_resolution_fit,
    decorate_h3_ladder,
    display_product_label,
    is_minimax_h3_product,
)
from app.video_runtime.vram_viability import evaluate_ladder


def test_h3_product_detection():
    assert is_minimax_h3_product("minimax-h3")
    assert is_minimax_h3_product("minimax-h3-i2v-local")
    assert display_product_label("minimax-h3") == "MiniMax H3"
    assert not is_minimax_h3_product("ltx-2.5")


def test_h3_guidance_table_matches_owner_contract():
    assert H3_RESOLUTION_FIT["480p"]["adviceLabel"] == "Fastest / Recommended for drafts"
    assert H3_RESOLUTION_FIT["720p"]["adviceLabel"] == "Viable / Higher Quality"
    assert H3_RESOLUTION_FIT["1080p"]["adviceLabel"] == "Viable / High Quality"
    assert H3_RESOLUTION_FIT["2K"]["adviceLabel"] == "Not certified"
    assert H3_RESOLUTION_FIT["4K"]["adviceLabel"] == "Not native/certified"


def test_demonstrated_tiers_never_not_viable_on_32gb():
    for tier in ("480p", "720p", "1080p"):
        row = apply_h3_resolution_fit(
            tier,
            row={
                "tier": tier,
                "verdict": "NOT VIABLE",
                "honestyLabel": "Native",
                "estimatedPeakGb": 40.0,
                "reason": "stale peak",
                "suggestions": ["Try 1080p or 720p for this generator"],
            },
            total_gb=31.84,
        )
        assert row["verdict"] == "VIABLE", tier
        assert row["adviceLabel"]
        assert "Not viable" not in row["adviceLabel"].lower()
        assert row["verdict"] != "NOT VIABLE"


def test_2k_4k_certification_not_not_viable_label():
    two_k = apply_h3_resolution_fit(
        "2K",
        row={"tier": "2K", "verdict": "NOT VIABLE", "honestyLabel": "x"},
        total_gb=31.84,
    )
    four_k = apply_h3_resolution_fit(
        "4K",
        row={"tier": "4K", "verdict": "NOT VIABLE", "honestyLabel": "x"},
        total_gb=31.84,
    )
    assert two_k["verdict"] == "NOT CERTIFIED"
    assert two_k["adviceLabel"] == "Not certified"
    assert four_k["verdict"] == "NOT NATIVE"
    assert four_k["adviceLabel"] == "Not native/certified"


def test_evaluate_ladder_15s_h3_on_live_gpu_never_not_viable_720_1080(monkeypatch):
    # Force 5090-class telemetry regardless of momentary residency.
    fake = {
        "ok": True,
        "gpuName": "NVIDIA GeForce RTX 5090",
        "driverVersion": "test",
        "memoryTotalMib": 32607.0,
        "memoryUsedMib": 29375.0,
        "memoryFreeMib": 2813.0,
        "memoryTotalGb": 31.84,
        "memoryUsedGb": 28.69,
        "memoryFreeGb": 2.75,
        "utilizationGpuPct": 100.0,
        "residentNote": "test",
    }
    monkeypatch.setattr("app.video_runtime.vram_viability._telemetry", lambda: fake)
    ladder = evaluate_ladder("minimax-h3", aspect="16:9", fps=24, duration_sec=15.0, surface="t2v")
    assert ladder["productLabel"] == "MiniMax H3"
    assert ladder["mutatesRequest"] is False
    by_tier = {t["tier"]: t for t in ladder["tiers"]}
    assert by_tier["480p"]["verdict"] == "VIABLE"
    assert by_tier["720p"]["verdict"] == "VIABLE"
    assert by_tier["1080p"]["verdict"] == "VIABLE"
    assert by_tier["720p"]["adviceLabel"] == "Viable / Higher Quality"
    assert by_tier["1080p"]["adviceLabel"] == "Viable / High Quality"
    assert by_tier["2K"]["verdict"] == "NOT CERTIFIED"
    assert by_tier["4K"]["verdict"] == "NOT NATIVE"
    for tier in ("480p", "720p", "1080p"):
        assert by_tier[tier]["verdict"] != "NOT VIABLE"
        assert "not viable" not in (by_tier[tier].get("adviceLabel") or "").lower()
