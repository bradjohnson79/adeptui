"""Shared Timed Prompt name-binding contract.

Prompt Name is creator prose. binding_id is the production reference.
tag is locked Adept grammar (@ CRS / # ERS / % PRS). Compile uses IDs, not
string replacement of the authored prompt.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

PromptBindingType = Literal["character", "prop", "environment"]


class PromptNameBinding(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    binding_id: str = Field(default="", alias="bindingId")
    prompt_name: str = Field(default="", alias="promptName")
    type: PromptBindingType = "character"
    tag: str = ""
    asset_id: str = Field(default="", alias="assetId")
    identity_id: str = Field(default="", alias="identityId")
    reference_sheet_id: str = Field(default="", alias="referenceSheetId")


def normalize_prompt_binding_type(raw: Any) -> PromptBindingType:
    token = str(raw or "").strip().lower()
    if token in {"prop", "vehicle"}:
        return "prop"
    if token in {"environment", "location", "place", "scene"}:
        return "environment"
    return "character"


def dump_prompt_name_binding(row: Any) -> dict[str, str]:
    if isinstance(row, dict):
        return {
            "binding_id": str(row.get("binding_id") or row.get("bindingId") or "").strip(),
            "prompt_name": str(row.get("prompt_name") or row.get("promptName") or "").strip(),
            "type": normalize_prompt_binding_type(row.get("type")),
            "tag": str(row.get("tag") or "").strip(),
            "asset_id": str(row.get("asset_id") or row.get("assetId") or "").strip(),
            "identity_id": str(row.get("identity_id") or row.get("identityId") or "").strip(),
            "reference_sheet_id": str(
                row.get("reference_sheet_id") or row.get("referenceSheetId") or ""
            ).strip(),
        }
    return {
        "binding_id": str(
            getattr(row, "binding_id", None) or getattr(row, "bindingId", "") or ""
        ).strip(),
        "prompt_name": str(
            getattr(row, "prompt_name", None) or getattr(row, "promptName", "") or ""
        ).strip(),
        "type": normalize_prompt_binding_type(getattr(row, "type", None)),
        "tag": str(getattr(row, "tag", "") or "").strip(),
        "asset_id": str(
            getattr(row, "asset_id", None) or getattr(row, "assetId", "") or ""
        ).strip(),
        "identity_id": str(
            getattr(row, "identity_id", None) or getattr(row, "identityId", "") or ""
        ).strip(),
        "reference_sheet_id": str(
            getattr(row, "reference_sheet_id", None) or getattr(row, "referenceSheetId", "") or ""
        ).strip(),
    }


def dump_prompt_name_bindings(rows: Any) -> list[dict[str, str]]:
    return [dump_prompt_name_binding(row) for row in (rows or [])]


def parse_prompt_name_bindings(rows: Any) -> list[PromptNameBinding]:
    return [PromptNameBinding.model_validate(dump_prompt_name_binding(row)) for row in (rows or [])]


def binding_ids_from_name_bindings(rows: Any) -> list[str]:
    ids: list[str] = []
    for row in dump_prompt_name_bindings(rows):
        token = row["binding_id"]
        if token and token not in ids:
            ids.append(token)
    return ids


def name_binding_index(rows: Any) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in dump_prompt_name_bindings(rows):
        token = row["binding_id"]
        if token and token not in out:
            out[token] = row
    return out
