"""M2.12 hard safety contract - enforced bans (no fine-tuning / code rewrite / Manifest).

Evolution means structured lessons + policy/strategy versions only.
Gemma weights are never updated by this module.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

EXPECTED_MANIFEST_SHA256: Final[str] = (
    "cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc"
)

MANIFEST_RELATIVE: Final[str] = "config/capabilities/adept-ui-v1.0-provider-manifest.json"

HARD_BANS: Final[tuple[str, ...]] = (
    "no_autonomous_source_rewrite",
    "no_security_auth_rule_changes",
    "no_bypass_of_product_approval",
    "no_provider_promotion",
    "no_execution_lock_edits",
    "no_provider_manifest_edits",
    "no_silent_production_asset_mutation",
    "no_one_user_correction_to_global_without_system_approval",
    "no_learning_from_unverified_failed_outputs_without_classification",
    "no_instruction_injection_from_untrusted_content",
    "no_lesson_delete_without_audit_history",
    "no_model_fine_tuning_or_weight_updates",
)

FORBIDDEN_WRITE_SUFFIXES: Final[tuple[str, ...]] = (
    "adept-ui-v1.0-provider-manifest.json",
    "adept-ui-v1.0-provider-manifest.sha256",
    "adept-ui-v1.0-provider-manifest.schema.json",
    "execution_lock.py",
    "execution_lock.json",
)


class AdaptiveLearningSafetyError(RuntimeError):
    """Raised when a learning operation would violate a hard ban."""


def safety_contract() -> dict[str, Any]:
    return {
        "evolutionMode": "structured_lessons_and_strategy_packs",
        "fineTuningAllowed": False,
        "weightUpdatesAllowed": False,
        "autonomousSourceRewriteAllowed": False,
        "providerManifestEditsAllowed": False,
        "executionLockEditsAllowed": False,
        "silentAssetMutationAllowed": False,
        "systemLayerAutoActivateAllowed": False,
        "expectedManifestSha256": EXPECTED_MANIFEST_SHA256,
        "hardBans": list(HARD_BANS),
        "notes": (
            "M2.12 evolves Co-Director via versioned lessons and strategy JSON packs. "
            "Never fine-tune Gemma. Never rewrite production source. Never mutate "
            "Provider Manifest or execution locks."
        ),
    }


def assert_path_writable_by_learning(path: str | Path) -> None:
    """Reject writes that would touch Manifest, locks, or auth/security modules."""

    name = Path(path).name.lower()
    full = str(path).replace("\\", "/").lower()
    for suffix in FORBIDDEN_WRITE_SUFFIXES:
        if name == suffix.lower() or full.endswith("/" + suffix.lower()):
            raise AdaptiveLearningSafetyError(
                f"Learning module may not write forbidden path: {path}"
            )
    if "provider-manifest" in full or "execution_lock" in full:
        raise AdaptiveLearningSafetyError(
            f"Learning module may not write forbidden path: {path}"
        )


def assert_manifest_unchanged(repo_root: Path | None = None) -> str:
    """Return current digest; raise if it differs from the frozen sha256."""

    import hashlib

    root = repo_root or Path(__file__).resolve().parents[4]
    manifest = root / MANIFEST_RELATIVE
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    if digest != EXPECTED_MANIFEST_SHA256:
        raise AdaptiveLearningSafetyError(
            f"Provider Manifest sha256 changed: {digest} != {EXPECTED_MANIFEST_SHA256}"
        )
    return digest


def assert_no_system_auto_activate(layer: str, auto: bool) -> None:
    if layer == "system" and auto:
        raise AdaptiveLearningSafetyError(
            "System-layer lessons NEVER auto-activate; strongest approval required."
        )


def assert_verified_outcome(outcome: dict[str, Any] | None) -> None:
    """Block learning from unverified / failed outputs without classification."""

    if not outcome:
        raise AdaptiveLearningSafetyError("Outcome required for critique/learning.")
    verified = outcome.get("verified")
    status = str(outcome.get("status") or "").lower()
    classified = bool(outcome.get("mistakeClass") or outcome.get("classified"))
    if verified is False and not classified:
        raise AdaptiveLearningSafetyError(
            "Cannot learn from unverified failed outputs without classification."
        )
    if status in {"failed", "error", "unverified"} and not classified and verified is not True:
        raise AdaptiveLearningSafetyError(
            "Cannot learn from failed/unverified outputs without classification."
        )
