"""Validation helpers for structured Qwen-Image-2512 prompts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class PromptValidationIssue:
    severity: str
    code: str
    message: str
    block_key: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "blockKey": self.block_key,
        }


def _text(value: Any) -> str:
    return str(value or "").strip()


def _block_map(blocks: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    return {str(block.get("key") or ""): _text(block.get("text")) for block in blocks}


def validate_compiled_package(
    package: Mapping[str, Any],
    *,
    expected_block_order: Sequence[str],
) -> list[PromptValidationIssue]:
    blocks = package.get("blocks") or []
    issues: list[PromptValidationIssue] = []
    found_order = [str(block.get("key") or "") for block in blocks]

    if found_order != list(expected_block_order):
        issues.append(
            PromptValidationIssue(
                severity="error",
                code="BLOCK_ORDER_MISMATCH",
                message="Compiled prompt blocks do not match the required stable order.",
            )
        )

    block_map = _block_map(blocks)
    negative_text = block_map.get("negative_constraints", "").lower()
    positive_text = "\n".join(
        text for key, text in block_map.items() if key and key != "negative_constraints"
    ).lower()

    required_positive_terms = (
        "purple eyes",
        "pale skin",
        "black twin ponytails",
        "light-circuitry markings",
        "not tattoos",
    )
    for term in required_positive_terms:
        if term not in positive_text:
            issues.append(
                PromptValidationIssue(
                    severity="error",
                    code="MISSING_REQUIRED_IDENTITY_TERM",
                    message=f"Required identity term missing from positive prompt: {term}",
                )
            )

    forbidden_positive_terms = ("blonde hair", "blue eyes", "aqua eyes", "human ears", "rounded ears")
    for term in forbidden_positive_terms:
        if term in positive_text:
            issues.append(
                PromptValidationIssue(
                    severity="error",
                    code="FORBIDDEN_IDENTITY_TERM",
                    message=f"Forbidden identity drift leaked into a positive block: {term}",
                )
            )

    for term in ("blonde hair", "blue eyes", "human ears", "Anadriya resemblance"):
        if term not in negative_text:
            issues.append(
                PromptValidationIssue(
                    severity="warning",
                    code="MISSING_NEGATIVE_CONSTRAINT",
                    message=f"Expected negative constraint missing: {term}",
                    block_key="negative_constraints",
                )
            )

    if "tattoo" in positive_text and "not tattoos" not in positive_text:
        issues.append(
            PromptValidationIssue(
                severity="error",
                code="INCORRECT_MARKINGS_LANGUAGE",
                message="Positive prompt used tattoo language instead of light-circuitry markings.",
            )
        )

    return issues
