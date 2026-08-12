"""Editing Recipes — project-scoped reusable edit presets (M42 W4)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4

from .store import read_json, write_json

BUILTIN_RECIPES: list[dict[str, Any]] = [
    {
        "recipeId": "builtin-remove-object",
        "name": "Remove Object",
        "builtin": True,
        "operation": "image.object_remove",
        "maskDefaults": {"role": "include", "feather": 8, "opacity": 1.0, "invert": False, "suggestedTool": "brush"},
        "recommendedWorkflowFamily": "zimage",
        "referenceRequirements": [],
        "preserveToggles": {
            "preserveComposition": True,
            "preserveSubject": True,
            "preserveBackground": True,
            "preserveLighting": True,
            "preservePalette": True,
        },
        "outputPreset": {"format": "png", "transparentBackground": False, "variants": 1, "resolution": "1080p"},
        "promptTemplate": "Remove the selected object seamlessly, preserve surrounding context, {detail}",
    },
    {
        "recipeId": "builtin-replace-clothing",
        "name": "Replace Character Clothing",
        "builtin": True,
        "operation": "image.object_replace",
        "maskDefaults": {"role": "replace", "feather": 6, "opacity": 1.0, "invert": False, "suggestedTool": "brush"},
        "recommendedWorkflowFamily": "zimage",
        "referenceRequirements": [{"role": "wardrobe", "required": True}],
        "preserveToggles": {
            "preserveComposition": True,
            "preserveSubject": True,
            "preserveBackground": True,
            "preserveLighting": True,
            "preservePalette": False,
        },
        "outputPreset": {"format": "png", "transparentBackground": False, "variants": 1, "resolution": "1080p"},
        "promptTemplate": "Replace wardrobe with approved reference, match lighting and fabric, {detail}",
    },
    {
        "recipeId": "builtin-fix-hands",
        "name": "Fix Hands",
        "builtin": True,
        "operation": "image.inpaint",
        "maskDefaults": {"role": "include", "feather": 4, "opacity": 1.0, "invert": False, "suggestedTool": "brush"},
        "recommendedWorkflowFamily": "zimage",
        "referenceRequirements": [],
        "preserveToggles": {
            "preserveComposition": True,
            "preserveSubject": True,
            "preserveBackground": True,
            "preserveLighting": True,
            "preservePalette": True,
        },
        "outputPreset": {"format": "png", "transparentBackground": False, "variants": 1, "resolution": "1080p"},
        "promptTemplate": "Repair hands with anatomically correct fingers, preserve face and pose, {detail}",
    },
    {
        "recipeId": "builtin-repair-face",
        "name": "Repair Face",
        "builtin": True,
        "operation": "image.face_restore",
        "maskDefaults": {"role": "include", "feather": 5, "opacity": 1.0, "invert": False, "suggestedTool": "brush"},
        "recommendedWorkflowFamily": "zimage",
        "referenceRequirements": [{"role": "identity", "required": False}],
        "preserveToggles": {
            "preserveComposition": True,
            "preserveSubject": True,
            "preserveBackground": True,
            "preserveLighting": True,
            "preservePalette": True,
        },
        "outputPreset": {"format": "png", "transparentBackground": False, "variants": 1, "resolution": "1080p"},
        "promptTemplate": "Restore facial detail and skin texture, preserve identity cues, {detail}",
    },
    {
        "recipeId": "builtin-sky-replacement",
        "name": "Sky Replacement",
        "builtin": True,
        "operation": "image.background_replace",
        "maskDefaults": {"role": "include", "feather": 12, "opacity": 1.0, "invert": False, "suggestedTool": "subject"},
        "recommendedWorkflowFamily": "zimage",
        "referenceRequirements": [{"role": "environment", "required": False}],
        "preserveToggles": {
            "preserveComposition": True,
            "preserveSubject": True,
            "preserveBackground": False,
            "preserveLighting": False,
            "preservePalette": False,
        },
        "outputPreset": {"format": "png", "transparentBackground": False, "variants": 1, "resolution": "1080p"},
        "promptTemplate": "Replace sky region with cinematic sky, match horizon line, {detail}",
    },
    {
        "recipeId": "builtin-moonlight-grade",
        "name": "Moonlight Grade",
        "builtin": True,
        "operation": "image.relight",
        "maskDefaults": {"role": "exclude", "feather": 0, "opacity": 0.0, "invert": False, "suggestedTool": "none"},
        "recommendedWorkflowFamily": "zimage",
        "referenceRequirements": [{"role": "lighting", "required": False}],
        "preserveToggles": {
            "preserveComposition": True,
            "preserveSubject": True,
            "preserveBackground": True,
            "preserveLighting": False,
            "preservePalette": False,
        },
        "outputPreset": {"format": "png", "transparentBackground": False, "variants": 1, "resolution": "1080p"},
        "promptTemplate": "Moonlit blue cinematic grade, cool shadows, soft rim light, {detail}",
    },
    {
        "recipeId": "builtin-concept-paintover",
        "name": "Concept Paintover",
        "builtin": True,
        "operation": "image.reference_edit",
        "maskDefaults": {"role": "exclude", "feather": 0, "opacity": 0.0, "invert": False, "suggestedTool": "none"},
        "recommendedWorkflowFamily": "zimage",
        "referenceRequirements": [{"role": "style", "required": False}, {"role": "composition", "required": False}],
        "preserveToggles": {
            "preserveComposition": False,
            "preserveSubject": True,
            "preserveBackground": False,
            "preserveLighting": False,
            "preservePalette": False,
        },
        "outputPreset": {"format": "png", "transparentBackground": False, "variants": 2, "resolution": "1080p"},
        "promptTemplate": "Concept art paintover, production design polish, {detail}",
    },
    {
        "recipeId": "builtin-poster-cleanup",
        "name": "Poster Cleanup",
        "builtin": True,
        "operation": "image.detail_enhance",
        "maskDefaults": {"role": "exclude", "feather": 0, "opacity": 0.0, "invert": False, "suggestedTool": "none"},
        "recommendedWorkflowFamily": "zimage",
        "referenceRequirements": [],
        "preserveToggles": {
            "preserveComposition": True,
            "preserveSubject": True,
            "preserveBackground": True,
            "preserveLighting": True,
            "preservePalette": True,
        },
        "outputPreset": {"format": "png", "transparentBackground": False, "variants": 1, "resolution": "2K"},
        "promptTemplate": "Poster finishing pass, sharpen typography edges, denoise, {detail}",
    },
]


def list_recipes(project_id: str) -> list[dict[str, Any]]:
    custom = read_json(project_id, "recipes.json", {"recipes": []})
    customs = list(custom.get("recipes") or [])
    return deepcopy(BUILTIN_RECIPES) + customs


def get_recipe(project_id: str, recipe_id: str) -> dict[str, Any] | None:
    for r in list_recipes(project_id):
        if r.get("recipeId") == recipe_id:
            return r
    return None


def create_recipe(project_id: str, body: dict[str, Any]) -> dict[str, Any]:
    data = read_json(project_id, "recipes.json", {"recipes": []})
    recipe = {
        "recipeId": str(body.get("recipeId") or f"recipe-{uuid4().hex[:10]}"),
        "name": str(body.get("name") or "Custom Recipe"),
        "builtin": False,
        "operation": str(body.get("operation") or "image.inpaint"),
        "maskDefaults": dict(body.get("maskDefaults") or {}),
        "recommendedWorkflowFamily": body.get("recommendedWorkflowFamily") or "zimage",
        "referenceRequirements": list(body.get("referenceRequirements") or []),
        "preserveToggles": dict(body.get("preserveToggles") or {}),
        "outputPreset": dict(body.get("outputPreset") or {}),
        "promptTemplate": str(body.get("promptTemplate") or "{detail}"),
    }
    data.setdefault("recipes", []).append(recipe)
    write_json(project_id, "recipes.json", data)
    return recipe


def update_recipe(project_id: str, recipe_id: str, body: dict[str, Any]) -> dict[str, Any] | None:
    if recipe_id.startswith("builtin-"):
        raise RuntimeError("Cannot mutate built-in recipes; save a copy instead")
    data = read_json(project_id, "recipes.json", {"recipes": []})
    for i, r in enumerate(data.get("recipes") or []):
        if r.get("recipeId") == recipe_id:
            r.update({k: v for k, v in body.items() if k not in {"builtin", "recipeId"}})
            data["recipes"][i] = r
            write_json(project_id, "recipes.json", data)
            return r
    return None


def delete_recipe(project_id: str, recipe_id: str) -> bool:
    if recipe_id.startswith("builtin-"):
        raise RuntimeError("Cannot delete built-in recipes")
    data = read_json(project_id, "recipes.json", {"recipes": []})
    before = len(data.get("recipes") or [])
    data["recipes"] = [r for r in (data.get("recipes") or []) if r.get("recipeId") != recipe_id]
    write_json(project_id, "recipes.json", data)
    return len(data["recipes"]) < before


def apply_recipe_to_request(recipe: dict[str, Any], detail: str = "") -> dict[str, Any]:
    tmpl = str(recipe.get("promptTemplate") or "{detail}")
    prompt = tmpl.replace("{detail}", detail or "")
    toggles = dict(recipe.get("preserveToggles") or {})
    return {
        "operation": recipe.get("operation"),
        "recipeId": recipe.get("recipeId"),
        "recipeName": recipe.get("name"),
        "prompt": prompt,
        "modelFamilyPreference": recipe.get("recommendedWorkflowFamily") or "zimage",
        "maskDefaults": dict(recipe.get("maskDefaults") or {}),
        "referenceRequirements": list(recipe.get("referenceRequirements") or []),
        "preferences": {
            "preserveComposition": toggles.get("preserveComposition", True),
            "preserveSubject": toggles.get("preserveSubject", True),
            "preserveBackground": toggles.get("preserveBackground", True),
            "preserveLighting": toggles.get("preserveLighting", True),
            "preservePalette": toggles.get("preservePalette", True),
        },
        "output": dict(recipe.get("outputPreset") or {}),
    }
