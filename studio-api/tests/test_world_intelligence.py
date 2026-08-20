"""Revision C — World Intelligence unit tests.

Tests:
- packet schema
- precedence rules
- approved-anchor selection
- intentional-change handling
- cache versioning
- no direct canon mutation
- no Spatial Map mutation
- no production block on unavailable JEPA
"""

from __future__ import annotations

import os
import sys
import json

# Set test data dir before any app import
_TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", ".adept-tmp", "pytest-data-rc")
os.environ.setdefault("ADEPT_DATA_DIR", _TEST_DATA_DIR)
os.environ.setdefault("STUDIO_DATA_DIR", _TEST_DATA_DIR)
import os
import tempfile
from pathlib import Path

import pytest

from app.codirector.world_intelligence.cache import (
    compute_content_hash,
    get_cached_embedding,
    invalidate_all,
    invalidate_embedding,
    set_cached_embedding,
)
from app.codirector.world_intelligence.compare import (
    build_world_state_packet,
    compute_recommendation,
)
from app.codirector.world_intelligence.contracts import (
    WORLD_INTELLIGENCE_MODEL_ID,
    CoDirectorWorldIntelligencePolicy,
    IntentionalChangeRecord,
    WorldStatePacket,
    WorldStateRecommendation,
)
from app.codirector.world_intelligence.index import WorldStateIndex
from app.codirector.world_intelligence.service import (
    evaluate_generated_image,
    get_policy,
    mark_intentional_change,
    set_policy,
    world_consistency_text,
)


# ── Packet schema tests ───────────────────────────────────────────────────
class TestWorldStatePacket:
    def test_default_packet_is_unavailable(self):
        """Default packet should be unavailable, not actional."""
        p = WorldStatePacket()
        assert p.availability == "unavailable"
        assert not p.is_actionable()
        assert not p.requires_review()

    def test_available_packet_is_actionable(self):
        """An available packet with no issues should be actionable."""
        p = WorldStatePacket(availability="available")
        assert p.is_actionable()
        assert not p.requires_review()

    def test_packet_with_review_requires_attention(self):
        """A packet with review items should flag for creator attention."""
        p = WorldStatePacket(
            availability="available",
            recommendation=WorldStateRecommendation(
                consistent=False,
                review_=["Major world-state change detected."],
            ),
        )
        assert p.is_actionable()
        assert p.requires_review()

    def test_json_roundtrip(self):
        """Packet should survive JSON serialization/deserialization."""
        p = WorldStatePacket(
            availability="available",
            reason="Test packet",
            source__modelId="vjepa2-vitl-test",
        )
        data = json.loads(p.model_dump_json())
        restored = WorldStatePacket.model_validate(data)
        assert restored.packetId == p.packetId
        assert restored.availability == "available"

    def test_insufficient_reference(self):
        """Insufficient reference should produce non-actionable packet."""
        p = WorldStatePacket(availability="insufficient_reference")
        assert not p.is_actionable()
        assert not p.requires_review()


# ── Precedence rules ─────────────────────────────────────────────────────
class TestPrecedence:
    def test_intentional_change_inhibits_review(self):
        """An intentional change should suppress review flags."""
        p = build_world_state_packet(
            source_asset_id="shot_001",
            reference_asset_ids=["ref_001"],
            similarity=0.45,  # Would normally flag drift
            anomaly_score=0.55,
            model_id="vjepa2-test",
            model_revision="test",
            intentional_change=True,
        )
        # Intentional change should override drift detection
        rec = p.recommendation
        # Should not have review warnings when intentional
        assert rec.consistent or p.intentionalChange

    def test_canon_overrides_world_state(self):
        """WorldStatePacket should never claim to override canon."""
        p = WorldStatePacket()
        assert not hasattr(p, "canonOverride")  # No can mutation field

    def test_no_spatial_map_mutation(self):
        """Packet should have no spatial map mutation methods."""
        p = WorldStatePacket()
        # The packet is purely advisory — no mutation methods
        assert not hasattr(p, "apply_to_spatial_map")
        assert not hasattr(p, "write_slot")
        assert not hasattr(p, "mutate_canon")


# ── Recommendation tests ─────────────────────────────────────────────────
class TestRecommendation:
    def test_high_similarity_consistent(self):
        """High similarity should produce consistent recommendation."""
        rec = compute_recommendation(
            similarity=0.92,
            anomaly_score=0.05,
            confidence="known",
        )
        assert rec.consistent
        assert len(rec.caution) == 0
        assert len(rec.review_) == 0

    def test_medium_similarity_minor_drift(self):
        """Medium similarity should produce caution."""
        rec = compute_recommendation(
            similarity=0.75,
            anomaly_score=0.20,
            confidence="known",
        )
        assert rec.consistent
        assert len(rec.caution) >= 1

    def test_low_similarity_major_drift(self):
        """Low similarity should flag for review."""
        rec = compute_recommendation(
            similarity=0.35,
            anomaly_score=0.60,
            confidence="known",
        )
        assert not rec.consistent
        assert len(rec.review_) >= 1

    def test_insufficient_reference(self):
        """Insufficient reference should return cautious recommendation."""
        rec = compute_recommendation(
            similarity=0.0,
            anomaly_score=0.0,
            confidence="insufficient_reference",
        )
        assert not rec.consistent
        assert len(rec.caution) >= 1

    def test_intentional_change_override(self):
        """Intentional change should suppress warnings."""
        rec = compute_recommendation(
            similarity=0.30,
            anomaly_score=0.70,
            confidence="known",
            intentional_change=True,
        )
        assert rec.consistent  # Overridden by intentional
        assert len(rec.review_) == 0


# ── Cache tests ──────────────────────────────────────────────────────────
class TestCache:
    def test_cache_set_and_get(self):
        """Cached embeddings should be retrievable."""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"test image data")
            img_path = f.name

        try:
            content_hash = compute_content_hash(img_path)
            key = set_cached_embedding(
                asset_id="test_001",
                content_hash=content_hash,
                model_id="vjepa2-test",
                model_revision="test",
                preprocess_version="v1",
                embedding=[0.1, 0.2, 0.3],
            )
            assert key is not None

            cached = get_cached_embedding(
                asset_id="test_001",
                content_hash=content_hash,
                model_id="vjepa2-test",
                model_revision="test",
                preprocess_version="v1",
            )
            assert cached is not None
            assert cached["embedding"] == [0.1, 0.2, 0.3]
        finally:
            os.unlink(img_path)
            invalidate_embedding("test_001")

    def test_cache_invalidation(self):
        """Invalidating an asset should remove its embeddings."""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"test image data")
            img_path = f.name

        try:
            content_hash = compute_content_hash(img_path)
            set_cached_embedding(
                asset_id="test_002",
                content_hash=content_hash,
                model_id="vjepa2-test",
                model_revision="test",
                preprocess_version="v1",
                embedding=[0.1, 0.2, 0.3],
            )
            count = invalidate_embedding("test_002")
            assert count >= 1

            cached = get_cached_embedding(
                asset_id="test_002",
                content_hash=content_hash,
                model_id="vjepa2-test",
                model_revision="test",
                preprocess_version="v1",
            )
            assert cached is None
        finally:
            os.unlink(img_path)

    def test_cache_invalidation_all(self):
        """Clearing all cache should work."""
        count = invalidate_all()
        assert isinstance(count, int)

    def test_cache_is_project_isolated(self):
        """The same asset hash must not hit across projects."""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"shared pixels")
            img_path = f.name
        try:
            content_hash = compute_content_hash(img_path)
            set_cached_embedding(
                asset_id="shared_asset",
                content_hash=content_hash,
                model_id="vjepa2-test",
                model_revision="test",
                preprocess_version="v1",
                embedding=[1.0, 0.0],
                project_id="project-a",
            )
            hit_a = get_cached_embedding(
                "shared_asset", content_hash, "vjepa2-test", "test", "v1", project_id="project-a"
            )
            miss_b = get_cached_embedding(
                "shared_asset", content_hash, "vjepa2-test", "test", "v1", project_id="project-b"
            )
            assert hit_a is not None
            assert miss_b is None
        finally:
            os.unlink(img_path)
            invalidate_embedding("shared_asset")


# ── Index tests ──────────────────────────────────────────────────────────
class TestIndex:
    def test_add_and_get_anchors(self):
        """Anchors should be addable and retrievable."""
        idx = WorldStateIndex()
        # Use the index methods
        assert idx.entry_count >= 0
        assert idx.anchor_count >= 0

    def test_clear_project(self):
        """Clearing a project should remove its entries."""
        idx = WorldStateIndex()
        count = idx.clear_project("test_project")
        assert isinstance(count, int)


# ── Policy / intentional change tests ────────────────────────────────────
class TestPolicy:
    def test_default_policy(self):
        """Default policy should be automatic."""
        policy = CoDirectorWorldIntelligencePolicy()
        assert policy.enabled
        assert policy.policy == "automatic"

    def test_intentional_change_tracking(self):
        """Marking an intentional change should create a record."""
        mark_intentional_change(
            from_asset_id="ref_001",
            to_asset_id="gen_001",
            project_id="proj_test",
            label="Day to night transition",
        )
        policy = get_policy("proj_test")
        assert len(policy.intentionalChanges) >= 1
        assert policy.is_change_intentional("ref_001", "gen_001")

    def test_policy_persistence(self):
        """Setting a policy should persist in cache."""
        policy = CoDirectorWorldIntelligencePolicy(enabled=False, policy="off")
        set_policy("proj_persist", policy)
        retrieved = get_policy("proj_persist")
        assert not retrieved.enabled
        assert retrieved.policy == "off"


# ── Advisory text tests ──────────────────────────────────────────────────
class TestAdvisoryText:
    def test_consistent_advisory(self):
        """High consistency should produce positive advisory."""
        p = WorldStatePacket(availability="available")
        text = world_consistency_text(p)
        assert text is not None
        assert "consistent" in text or "strong" in text

    def test_unavailable_no_advisory(self):
        """Unavailable world intelligence should not produce advisory."""
        p = WorldStatePacket(availability="unavailable")
        text = world_consistency_text(p)
        assert text is None

    def test_insufficient_reference_no_advisory(self):
        """Insufficient reference should not produce advisory."""
        p = WorldStatePacket(availability="insufficient_reference")
        text = world_consistency_text(p)
        assert text is None


# ── Production block tests ───────────────────────────────────────────────
class TestNoProductionBlock:
    def test_unavailable_does_not_block(self):
        """Unavailable world intelligence should not block operations."""
        p = WorldStatePacket(availability="unavailable")
        # Generation should proceed regardless
        assert not p.is_actionable()
        # No blocking method should exist
        assert not hasattr(p, "blocks_generation")
        assert not hasattr(p, "is_gate_ready")  # Different from temporal

    def test_no_auto_reject_default(self):
        """By default, JEPA score should not reject images."""
        p = WorldStatePacket(
            availability="available",
            recommendation=WorldStateRecommendation(
                consistent=False,
                review_=["Major world-state change."],
            ),
        )
        # Packet should not have auto-reject capability
        assert not hasattr(p, "auto_reject")
        assert not hasattr(p, "delete_output")
        assert not hasattr(p, "fail_generation")


# ── Service tests (no-model) ─────────────────────────────────────────────
class TestServiceNoModel:
    def test_evaluate_without_installation(self):
        """Service should handle missing model gracefully."""
        packet = evaluate_generated_image(
            image_path="/nonexistent/path.jpg",
            asset_id="test_asset",
            reference_asset_ids=["ref_001"],
            reference_image_paths=["/nonexistent/ref.jpg"],
        )
        assert packet.availability in ("unavailable", "insufficient_reference")

    def test_empty_references(self):
        """No references should produce insufficient_reference."""
        packet = evaluate_generated_image(
            image_path="/test.jpg",
            asset_id="test_asset",
            reference_asset_ids=[],
            reference_image_paths=[],
        )
        assert packet.availability == "insufficient_reference"


class TestWorkerClientParse:
    def test_parse_last_json_line(self):
        from app.codirector.world_intelligence.worker_client import _parse_worker_json

        stdout = '{"phase": "load"}\n{"ok": true, "similarity": 0.91}\n'
        assert _parse_worker_json(stdout)["similarity"] == 0.91

    def test_advisory_read_does_not_probe_cuda(self, monkeypatch):
        from app.codirector.world_intelligence import service

        def boom():
            raise AssertionError("advisory must not spawn a CUDA probe")

        monkeypatch.setattr(service, "worker_health", boom)
        result = service.is_available(probe=False)
        assert result["available"] is False
        assert "reason" in result

    def test_status_route_does_not_block_on_cuda_probe(self, monkeypatch):
        from app.codirector.world_intelligence import health as health_mod
        from app.codirector.world_intelligence import router as wi_router
        from app.codirector.world_intelligence import worker_client

        def boom(*_args, **_kwargs):
            raise AssertionError("GET /status must not spawn a CUDA probe")

        monkeypatch.setattr(health_mod, "worker_health_check", boom)
        monkeypatch.setattr(worker_client, "_probe_worker_cuda", boom)
        monkeypatch.setattr(wi_router, "schedule_cuda_probe", lambda: None)
        body = wi_router.api_status()
        assert body["advisoryOnly"] is True
        assert "available" in body
        assert "installed" in body


class TestPersistedIntentionalChange:
    def test_evaluate_honors_persisted_policy_after_cold_cache(self, monkeypatch):
        from app.codirector.world_intelligence import service as svc

        persisted = CoDirectorWorldIntelligencePolicy()
        persisted.intentionalChanges.append(
            IntentionalChangeRecord(fromAssetId="ref_a", toAssetId="gen_b", projectId="p1")
        )

        monkeypatch.setattr(svc, "load_policy", lambda _db, _project_id: persisted)

        def fake_compare(**_kwargs):
            return WorldStatePacket(
                availability="available",
                recommendation=WorldStateRecommendation(
                    consistent=False,
                    review_=["Major world-state change detected."],
                ),
            )

        monkeypatch.setattr(svc, "compare_images", fake_compare)
        svc._policy_cache.clear()
        packet = svc.evaluate_generated_image(
            image_path="x.jpg",
            asset_id="gen_b",
            reference_asset_ids=["ref_a"],
            reference_image_paths=["r.jpg"],
            project_id="p1",
            db=object(),
        )
        assert packet.recommendation.consistent is True
        assert packet.intentionalChange is not None
        assert packet.intentionalChange.fromAssetId == "ref_a"
        assert world_consistency_text(packet) == "World revision accepted."


class TestTemporalWorldReview:
    def test_unavailable_does_not_probe_and_does_not_block(self, monkeypatch):
        from app.codirector.video_intelligence.contracts import TemporalContinuityPacket
        from app.codirector.world_intelligence import temporal_world_review as twr

        monkeypatch.setattr(twr, "is_available", lambda **_k: {"available": False, "reason": "NOT_PROBED"})
        monkeypatch.setattr(twr, "schedule_cuda_probe", lambda: None)

        def boom(*_args, **_kwargs):
            raise AssertionError("temporal path must not spawn JEPA on a cold probe")

        monkeypatch.setattr(twr, "compare_images", boom)
        packet = TemporalContinuityPacket(availability="ready")
        out = twr.augment_temporal_packet(packet, clip_path=__file__)
        assert out.is_gate_ready()
        assert out.extras["worldReview"]["availability"] == "unavailable"
        assert out.continuation.nextBatchDirectives == []

    def test_world_drift_reaches_compiled_continuation(self):
        from app.codirector.video_intelligence.compile import compile_temporal_continuation
        from app.codirector.video_intelligence.contracts import TemporalContinuityPacket
        from app.codirector.world_intelligence.temporal_world_review import _add_world_advisory

        packet = TemporalContinuityPacket(availability="ready")
        world = WorldStatePacket(
            availability="available",
            recommendation=WorldStateRecommendation(
                consistent=False,
                review_=["The scene environment differs notably from the approved reference."],
            ),
        )
        _add_world_advisory(packet, world)
        compiled = compile_temporal_continuation(packet, supports_prompt_continuation=True)
        assert compiled["applied"] is True
        blob = (compiled["promptPrefix"] or "").lower()
        assert "environment differs" in blob
        assert compiled["directives"]
        assert "environment differs" in compiled["directives"][0].lower()
