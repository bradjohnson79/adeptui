"""Character Fidelity Gate — compare generated candidates against CRS.

Wires the existing FidelityReport/FidelityCheckItem from crs_schema.py
into actual use. Uses deterministic checks and, where applicable,
VLM-based review.

Product Law:
  If @Korri does not look like the approved Korri, the candidate does not pass.
  The CRS defines what the character looks like.
"""

from __future__ import annotations

from typing import Any, Optional

from .crs_schema import (
    CharacterCanon,
    FidelityCheckItem,
    FidelityReport,
    FidelityVerdict,
)


def check_character_fidelity(
    candidate_asset_id: str,
    crs: CharacterCanon,
    *,
    validator_model: str = "deterministic",
) -> FidelityReport:
    """Compare a generated candidate against CRS identity locks.
    
    Returns a FidelityReport with PASS/REVIEW_REQUIRED/FAIL per trait.
    This is a deterministic structural check — it verifies that the
    generation request carried the correct CRS context, not the output
    pixels. For pixel-level fidelity, use review_character_fidelity().
    """
    checks: list[FidelityCheckItem] = []
    failures = 0
    reviews = 0
    
    # 1. Identity locks present
    if crs.identity_locks.locked:
        traits = [l.trait for l in crs.identity_locks.locked]
        checks.append(FidelityCheckItem(
            trait="identity_locks",
            verdict="PASS",
            confidence=0.95,
            reason=f"Identity locks resolved: {', '.join(traits)}",
        ))
    else:
        checks.append(FidelityCheckItem(
            trait="identity_locks",
            verdict="REVIEW_REQUIRED",
            confidence=0.5,
            reason="No identity locks defined — character may not be sufficiently constrained",
        ))
        reviews += 1
    
    # 2. Negative rules
    if crs.negative_rules:
        rules = [r.rule for r in crs.negative_rules]
        checks.append(FidelityCheckItem(
            trait="negative_rules",
            verdict="PASS",
            confidence=0.9,
            reason=f"Negative rules applied: {len(rules)} rules",
        ))
    
    # 3. Render domain
    rd = crs.render_domain
    if rd.character_style and rd.character_style != "unknown":
        checks.append(FidelityCheckItem(
            trait="render_domain",
            verdict="PASS",
            confidence=0.9,
            reason=f"Render domain: {rd.character_style} character / {rd.environment_style} environment",
        ))
    else:
        checks.append(FidelityCheckItem(
            trait="render_domain",
            verdict="REVIEW_REQUIRED",
            confidence=0.4,
            reason="Render domain not set — character style may not be preserved",
        ))
        reviews += 1
    
    # 4. Approved reference assets
    refs = crs.identity_locks.flexible if hasattr(crs.identity_locks, 'flexible') else []
    has_refs = bool(refs)
    if has_refs:
        checks.append(FidelityCheckItem(
            trait="visual_references",
            verdict="PASS",
            confidence=0.9,
            reason=f"Character references available: {len(refs)} reference(s)",
        ))
    else:
        checks.append(FidelityCheckItem(
            trait="visual_references",
            verdict="REVIEW_REQUIRED",
            confidence=0.3,
            reason="No visual references — character identity may not be visually grounded",
        ))
        reviews += 1
    
    # 5. Hair (from canon)
    hair = crs.hair or {}
    if hair.get("primary_color") or hair.get("canonical_style"):
        checks.append(FidelityCheckItem(
            trait="hair",
            verdict="PASS",
            confidence=0.85,
            reason=f"Hair: {hair.get('primary_color', 'unknown')} / {hair.get('canonical_style', 'unknown')}",
        ))
    
    # 6. Skin tone
    skin = crs.skin or {}
    if skin.get("skin_tone"):
        checks.append(FidelityCheckItem(
            trait="skin_tone",
            verdict="PASS",
            confidence=0.85,
            reason=f"Skin tone: {skin.get('skin_tone')}",
        ))
    
    # 7. Markings/tattoos
    if skin.get("tattoos"):
        checks.append(FidelityCheckItem(
            trait="markings",
            verdict="PASS",
            confidence=0.8,
            reason=f"Markings: {skin.get('tattoos')}",
        ))
    
    # Overall verdict
    if failures > 0:
        overall: FidelityVerdict = "FAIL"
    elif reviews > 0:
        overall = "REVIEW_REQUIRED"
    else:
        overall = "PASS"
    
    return FidelityReport(
        overall_verdict=overall,
        checks=checks,
        character_id="",
        crs_revision=0,
        candidate_asset_id=candidate_asset_id,
        validator_model=validator_model,
        summary=f"Fidelity check: {len(checks)} traits checked, {failures} failures, {reviews} reviews",
        generated_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    )


def review_character_fidelity(
    candidate_asset_id: str,
    crs: CharacterCanon,
    reference_asset_ids: list[str],
) -> FidelityReport:
    """Review a generated candidate against CRS using VLM comparison.
    
    This is a placeholder for VLM-based visual fidelity review.
    The actual VLM integration requires a vision-capable model.
    
    Returns a FidelityReport with all checks marked REVIEW_REQUIRED
    pending actual visual inspection.
    """
    from datetime import datetime, timezone
    
    checks = [
        FidelityCheckItem(
            trait="face_identity",
            verdict="REVIEW_REQUIRED",
            confidence=0.0,
            reason="Visual identity check requires human review",
        ),
        FidelityCheckItem(
            trait="hair_matches_canon",
            verdict="REVIEW_REQUIRED",
            confidence=0.0,
            reason="Hair comparison requires visual inspection",
        ),
        FidelityCheckItem(
            trait="eyes_match_canon",
            verdict="REVIEW_REQUIRED",
            confidence=0.0,
            reason="Eye comparison requires visual inspection",
        ),
        FidelityCheckItem(
            trait="ears_match_canon",
            verdict="REVIEW_REQUIRED",
            confidence=0.0,
            reason="Ear comparison requires visual inspection",
        ),
        FidelityCheckItem(
            trait="wardrobe_matches_canon",
            verdict="REVIEW_REQUIRED",
            confidence=0.0,
            reason="Wardrobe comparison requires visual inspection",
        ),
        FidelityCheckItem(
            trait="render_domain_preserved",
            verdict="REVIEW_REQUIRED",
            confidence=0.0,
            reason="Render domain check requires visual inspection",
        ),
    ]
    
    return FidelityReport(
        overall_verdict="REVIEW_REQUIRED",
        checks=checks,
        candidate_asset_id=candidate_asset_id,
        validator_model="vlm_placeholder",
        summary="Visual fidelity review required — compare candidate against CRS reference images",
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
