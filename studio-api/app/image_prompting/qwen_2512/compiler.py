"""Structured Qwen-Image-2512 prompt compiler."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from .character_sheet_grammar import compile_character_sheet_block
from .composition_grammar import compile_composition_block, compile_environment_block, compile_pose_block
from .continuity_rules import compile_continuity_block
from .identity_lock import build_identity_anchor, build_identity_lock, extract_character_blueprint
from .negative_constraints import build_negative_constraints, compile_negative_constraints_block
from .prompt_validator import validate_compiled_package
from .style_grammar import compile_style_block

BLOCK_ORDER: tuple[str, ...] = (
    "request_intent",
    "subject_identity",
    "identity_lock",
    "face_features",
    "wardrobe_materials",
    "pose_expression",
    "composition_camera",
    "environment_lighting",
    "style_profile",
    "continuity_references",
    "character_sheet",
    "negative_constraints",
    "output_guardrails",
)

# Reference-first authority directive (Amendment 3). When a Character Reference
# / Reference Sheet is attached, this block makes the reference image the
# primary visual authority and demotes the written Character Profile to
# supplemental guidance. The profile may clarify personality/expression/pose
# and add details NOT visible in the reference, but must NOT override visible
# reference features (face/hair/eyes/ears/skin/wardrobe/accessories/circuitry/
# silhouette). If the profile conflicts with the reference, the reference wins.
REFERENCE_REPRODUCTION_BLOCK = (
    "REFERENCE-FIRST AUTHORITY: Reproduce the attached character reference as faithfully as possible. "
    "Preserve the same face, hairstyle, eye color, ears, skin tone, body proportions, wardrobe, "
    "accessories, tattoos/circuitry, and silhouette. Do not redesign or reinterpret the character. "
    "Only vary pose, expression, and background subtly. "
    "The attached reference image is the visual identity lock; the written profile is supplemental "
    "guidance only and must not override clearly visible reference details."
)


@dataclass(frozen=True)
class PromptBlock:
    index: int
    key: str
    label: str
    text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CharacterImagePromptPackage:
    schema_version: int
    model_key: str
    prompt_family: str
    character_name: str
    canon_version: str
    prompt: str
    negative_prompt: str
    blocks: list[PromptBlock]
    block_map: dict[str, str]
    identity_lock: dict[str, Any]
    validation: dict[str, Any]
    metadata: dict[str, Any]
    blueprint: dict[str, Any]
    compositionSummary: str
    environmentSummary: str
    styleSummary: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["blocks"] = [block.to_dict() for block in self.blocks]
        return data


def _text(value: Any) -> str:
    return str(value or "").strip()


def _join(parts: Sequence[str], separator: str = "; ") -> str:
    return separator.join(part for part in parts if _text(part))


def _summarize_face_features(blueprint: Mapping[str, Any]) -> str:
    parts = [
        f"{blueprint.get('hair_color')} hair" if _text(blueprint.get("hair_color")) else "",
        _text(blueprint.get("hair_style")),
        f"{blueprint.get('eye_color')} eyes" if _text(blueprint.get("eye_color")) else "",
        f"{blueprint.get('skin_tone')} skin" if _text(blueprint.get("skin_tone")) else "",
        _text(blueprint.get("skin_texture")),
        _text(blueprint.get("ears")),
    ]
    distinctives = blueprint.get("distinctives") or []
    if distinctives:
        parts.append("distinctives: " + ", ".join(str(item) for item in distinctives))
    return _join(parts)


def _summarize_wardrobe(blueprint: Mapping[str, Any]) -> str:
    return _join(
        [
            _text(blueprint.get("wardrobe_name")),
            _text(blueprint.get("wardrobe_description")),
            _text(blueprint.get("wardrobe_materials")),
            _text(blueprint.get("wardrobe_colors")),
            _text(blueprint.get("wardrobe_footwear")),
            _text(blueprint.get("wardrobe_accessories")),
        ]
    )


def _guardrail_block(identity_lock: Mapping[str, Any]) -> str:
    baseline = (
        "Use direct production language for Qwen-Image-2512. Do not write conversational fluff, "
        "do not merge character identity with style, and keep the final render faithful to the structured blocks above."
    )
    if identity_lock.get("is_korri"):
        baseline += " Preserve Korri's locked handmade black wardrobe and keep sibling-character drift fully rejected."
    return baseline


def compile_character_image_prompt(
    payload: Mapping[str, Any],
    *,
    prompt_goal: str = "single character portrait",
    composition: Mapping[str, Any] | None = None,
    style_profile: Mapping[str, Any] | None = None,
    references: Sequence[Mapping[str, Any]] | None = None,
    sheet_request: Mapping[str, Any] | None = None,
    extra_negative_constraints: Sequence[str] | None = None,
    reference_locked: bool = False,
) -> CharacterImagePromptPackage:
    """Compile a structured, stable 13-block Qwen-Image-2512 prompt package.

    When ``reference_locked`` is True (a Character Reference / Reference Sheet
    is attached), a reference-first authority block is prepended so the
    reference image is the primary visual identity lock and the written
    Character Profile is demoted to supplemental guidance that must not
    override visible reference features.
    """
    blueprint = extract_character_blueprint(payload)
    identity_lock = build_identity_lock(blueprint)
    motion = blueprint.get("motion") or {}
    performance = blueprint.get("performance") or {}

    style_summary = compile_style_block(style_profile)
    composition_summary = compile_composition_block(composition)
    environment_summary = compile_environment_block(composition, style_profile)
    negative_prompt = compile_negative_constraints_block(identity_lock, extra_negative_constraints)

    block_texts = {
        "request_intent": f"Create {prompt_goal.strip()} for {_text(blueprint.get('name'))}.",
        "subject_identity": build_identity_anchor(blueprint),
        "identity_lock": _join(
            [
                "locked traits: " + ", ".join(identity_lock.get("locked_traits") or []),
                "preserve every locked identity trait exactly with no substitutions or character drift",
            ]
        ),
        "face_features": _summarize_face_features(blueprint),
        "wardrobe_materials": _summarize_wardrobe(blueprint),
        "pose_expression": compile_pose_block(composition, motion, performance),
        "composition_camera": composition_summary,
        "environment_lighting": environment_summary,
        "style_profile": style_summary,
        "continuity_references": compile_continuity_block(blueprint, identity_lock, references),
        "character_sheet": compile_character_sheet_block(sheet_request, references),
        "negative_constraints": negative_prompt,
        "output_guardrails": _guardrail_block(identity_lock),
    }
    # Reference-first authority block is prepended (as block 1) when a reference
    # is attached, shifting the canonical blocks down by one. This makes the
    # reference-reproduction directive the first instruction the model reads.
    if reference_locked:
        block_texts = {"reference_reproduction": REFERENCE_REPRODUCTION_BLOCK, **block_texts}
        block_order = ("reference_reproduction",) + BLOCK_ORDER
    else:
        block_order = BLOCK_ORDER

    blocks = [
        PromptBlock(index=index, key=key, label=key.replace("_", " ").title(), text=block_texts[key])
        for index, key in enumerate(block_order, start=1)
    ]
    prompt = "\n".join(f"{block.index}. {block.label}: {block.text}" for block in blocks)
    package = CharacterImagePromptPackage(
        schema_version=1,
        model_key="qwen-image-2512",
        prompt_family="qwen_2512_character_image_prompt",
        character_name=_text(blueprint.get("name") or "Character"),
        canon_version=_text(blueprint.get("canon_version")),
        prompt=prompt,
        negative_prompt=", ".join(build_negative_constraints(identity_lock, extra_negative_constraints)),
        blocks=blocks,
        block_map={block.key: block.text for block in blocks},
        identity_lock=identity_lock,
        validation={},
        metadata={
            "stableBlockOrder": list(block_order),
            "blockCount": len(block_order),
            "referencesAttached": len(list(references or [])),
            "sheetMode": bool((sheet_request or {}).get("enabled") or (sheet_request or {}).get("views")),
            "referenceLocked": bool(reference_locked),
        },
        blueprint=blueprint,
        compositionSummary=composition_summary,
        environmentSummary=environment_summary,
        styleSummary=style_summary,
    )

    validation_issues = validate_compiled_package(package.to_dict(), expected_block_order=block_order)
    package_dict = package.to_dict()
    package_dict["validation"] = {
        "ok": not any(issue.severity == "error" for issue in validation_issues),
        "issues": [issue.to_dict() for issue in validation_issues],
    }
    return CharacterImagePromptPackage(
        schema_version=package.schema_version,
        model_key=package.model_key,
        prompt_family=package.prompt_family,
        character_name=package.character_name,
        canon_version=package.canon_version,
        prompt=package.prompt,
        negative_prompt=package.negative_prompt,
        blocks=package.blocks,
        block_map=package.block_map,
        identity_lock=package.identity_lock,
        validation=package_dict["validation"],
        metadata=package.metadata,
        blueprint=package.blueprint,
        compositionSummary=package.compositionSummary,
        environmentSummary=package.environmentSummary,
        styleSummary=package.styleSummary,
    )
