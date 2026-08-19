"""Character Reference System (CRS) schema — platform-level visual canon.

Builds on the existing Character Identity schemas (character_identity/schemas.py)
to provide a first-class CRS object aggregating visual canon, reference roles,
confidence, render domain, and identity locks.

Product Law:
  THE CRS DEFINES WHAT THE CHARACTER LOOKS LIKE.
  THE JSON DEFINES WHAT ADEPT UI KNOWS ABOUT THAT VISUAL CANON.
  @KORRI RESOLVES BOTH.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# Re-export existing types for convenience
from .schemas import (
    ApprovalStatus,
    CharacterProfileOut,
    CoverageReport,
    HairProfile,
    MotionProfile,
    PerformanceProfile,
    PersonalityProfile,
    ProfileStatus,
    SkinProfile,
)


# ── Render Domain ────────────────────────────────────────────────────────

RenderDomainStyle = Literal[
    "cinematic_anime",
    "cinematic_photoreal",
    "illustration",
    "semi_realistic",
    "stylized_3d",
    "pixel_art",
    "unknown",
]

class CharacterRenderDomain(BaseModel):
    """Character and environment render style, independently represented.
    
    Law 6: An anime character remains an anime character even inside a
    photorealistic environment.
    """
    character_style: RenderDomainStyle = "unknown"
    environment_style: RenderDomainStyle = "unknown"
    allow_photoreal_character: bool = False
    allow_photoreal_environment: bool = True
    notes: str = ""


# ── Confidence Map ───────────────────────────────────────────────────────

ConfidenceLevel = Literal["unknown", "low", "medium", "high", "confirmed"]

TRAIT_CONFIDENCE_KEYS = Literal[
    "face",
    "eye_color",
    "eye_shape",
    "pupil_style",
    "hair_color",
    "hair_style",
    "hair_silhouette",
    "front_hair",
    "side_hair",
    "rear_hair",
    "ear_shape",
    "skin_tone",
    "body_proportions",
    "markings",
    "tattoos",
    "wardrobe",
    "footwear",
    "accessories",
    "render_domain",
]

class ConfidenceMap(BaseModel):
    """Per-trait visual certainty. Unknown ≠ canonical.
    
    A single front-facing image might establish:
      face: high, eyes: high, front hair: high
      side: low, rear: unknown
    
    More coverage improves confidence.
    """
    model_config = ConfigDict(extra="allow")
    face: ConfidenceLevel = "unknown"
    eye_color: ConfidenceLevel = "unknown"
    eye_shape: ConfidenceLevel = "unknown"
    pupil_style: ConfidenceLevel = "unknown"
    hair_color: ConfidenceLevel = "unknown"
    hair_style: ConfidenceLevel = "unknown"
    hair_silhouette: ConfidenceLevel = "unknown"
    front_hair: ConfidenceLevel = "unknown"
    side_hair: ConfidenceLevel = "unknown"
    rear_hair: ConfidenceLevel = "unknown"
    ear_shape: ConfidenceLevel = "unknown"
    skin_tone: ConfidenceLevel = "unknown"
    body_proportions: ConfidenceLevel = "unknown"
    markings: ConfidenceLevel = "unknown"
    tattoos: ConfidenceLevel = "unknown"
    wardrobe: ConfidenceLevel = "unknown"
    footwear: ConfidenceLevel = "unknown"
    accessories: ConfidenceLevel = "unknown"
    render_domain: ConfidenceLevel = "unknown"
    notes: str = ""


# ── Identity Locks ────────────────────────────────────────────────────────

LockCategory = Literal[
    "immutable",
    "strongly_constrained",
    "flexible",
    "scene_specific",
]

class IdentityLock(BaseModel):
    """A single locked trait with its constraint level."""
    trait: str
    category: LockCategory = "immutable"
    description: str = ""
    provenance: str = ""


class IdentityLocks(BaseModel):
    """Which traits are immutable vs flexible.
    
    Law 11: Locked traits — face, eyes, hair, ears, body proportions,
    major markings, render domain.
    Law 12: Flexible traits — expression, pose, environment, camera,
    lighting, temporary props.
    """
    locked: list[IdentityLock] = Field(default_factory=list)
    flexible: list[str] = Field(default_factory=list)
    notes: str = ""


# ── Negative Identity Rules ──────────────────────────────────────────────

class NegativeIdentityRule(BaseModel):
    """A character-specific negative rule.
    
    Example: "do not reinterpret as photoreal human"
    Not generic negative-prompt sludge.
    """
    rule: str
    category: str = "identity"
    severity: Literal["hard", "soft"] = "hard"


# ── Visual References ────────────────────────────────────────────────────

ReferenceRole = Literal[
    "primary_identity",
    "portrait",
    "full_body_front",
    "full_body_side",
    "full_body_rear",
    "three_quarter",
    "wardrobe",
    "detail",
    "expression_sheet",
    "turnaround_sheet",
]

class VisualReference(BaseModel):
    """A single visual reference with its role and asset ID."""
    asset_id: str
    role: ReferenceRole
    label: str = ""
    width: int = 0
    height: int = 0
    notes: str = ""


class VisualReferences(BaseModel):
    """All visual references for a character, organized by role.
    
    Law 3: One image is enough to start.
    Law 4: More coverage improves confidence.
    """
    primary_reference_asset_id: Optional[str] = None
    references: list[VisualReference] = Field(default_factory=list)
    reference_count: int = 0
    multi_view: bool = False


# ── Character Canon JSON ─────────────────────────────────────────────────

class CharacterCanon(BaseModel):
    """Structured visual canon for a character.
    
    This is the structured truth that @Character resolves.
    It tells Adept UI what is known about the visual identity.
    
    Law 1: CRS = Visual Truth + Structured Truth.
    The CRS tells Adept UI what the character actually looks like.
    The JSON tells Adept UI what is known about that visual identity.
    Neither replaces the other.
    """
    # Identity
    name: str = ""
    tag: str = ""
    species_or_type: str = "human"
    render_domain: CharacterRenderDomain = Field(default_factory=CharacterRenderDomain)
    
    # Appearance (from existing SkinProfile, HairProfile, etc.)
    skin: dict[str, Any] = Field(default_factory=dict)
    hair: dict[str, Any] = Field(default_factory=dict)
    eyes: dict[str, Any] = Field(default_factory=dict)
    facial_structure: dict[str, Any] = Field(default_factory=dict)
    body_proportions: dict[str, Any] = Field(default_factory=dict)
    markings: list[str] = Field(default_factory=list)
    tattoos: list[str] = Field(default_factory=list)
    accessories: list[str] = Field(default_factory=list)
    
    # Wardrobe
    canonical_wardrobe: dict[str, Any] = Field(default_factory=dict)
    
    # Identity
    identity_locks: IdentityLocks = Field(default_factory=IdentityLocks)
    negative_rules: list[NegativeIdentityRule] = Field(default_factory=list)
    confidence: ConfidenceMap = Field(default_factory=ConfidenceMap)
    
    # Provenance
    schema_version: int = 1
    generated_at: str = ""
    source_profile_version_id: str = ""


# ── CRS Object ───────────────────────────────────────────────────────────

class CRSStatus(BaseModel):
    """CRS status for a character."""
    status: Literal["none", "draft", "approved", "superseded"] = "none"
    crs_revision: int = 0
    reference_coverage: str = "none"  # "none", "single", "multi_view"
    visual_canon_ready: bool = False
    confidence_summary: str = ""


class CharacterReferenceSummary(BaseModel):
    """Compact CRS summary for Co-Director and platform consumers.
    
    Law 19: Co-Director project state should include a compact summary,
    not the entire Character Canon JSON.
    """
    character_id: str
    name: str
    tag: str
    crs_revision: int = 0
    canon_status: CRSStatus = Field(default_factory=CRSStatus)
    reference_coverage: str = "none"
    render_domain: CharacterRenderDomain = Field(default_factory=CharacterRenderDomain)
    has_approved_reference: bool = False
    approved_reference_asset_id: Optional[str] = None


# ── Fidelity Validation ─────────────────────────────────────────────────—

FidelityVerdict = Literal["PASS", "REVIEW_REQUIRED", "FAIL"]

class FidelityCheckItem(BaseModel):
    """Single item in a fidelity check."""
    trait: str
    verdict: FidelityVerdict
    confidence: float = 0.0
    reason: str = ""


class FidelityReport(BaseModel):
    """Result of comparing a generated candidate against CRS.
    
    Law 38: Identity Validation Result uses PASS / REVIEW_REQUIRED / FAIL.
    """
    overall_verdict: FidelityVerdict
    checks: list[FidelityCheckItem] = Field(default_factory=list)
    character_id: str = ""
    crs_revision: int = 0
    candidate_asset_id: str = ""
    validator_model: str = ""
    summary: str = ""
    generated_at: str = ""


class GenerationConditioningPacket(BaseModel):
    """Shared packet that resolves CRS + ERS into generator-ready conditioning.
    
    This is the authoritative output of the conditioning compiler.
    Every generator adapter consumes this same packet.
    """
    # Character
    character_id: str = ""
    character_name: str = ""
    character_tag: str = ""
    crs_revision: int = 0
    render_domain: CharacterRenderDomain = Field(default_factory=CharacterRenderDomain)
    identity_locks: list[str] = Field(default_factory=list)
    negative_rules: list[str] = Field(default_factory=list)
    
    # Visual references
    selected_reference_assets: list[str] = Field(default_factory=list)
    all_reference_assets: list[str] = Field(default_factory=list)
    
    # Environment
    ers_id: str = ""
    ers_revision: int = 0
    environment_reference_assets: list[str] = Field(default_factory=list)
    
    # Generation
    prompt: str = ""
    generator: str = ""
    aspect_ratio: str = "16:9"
    
    # Provenance
    generated_at: str = ""
