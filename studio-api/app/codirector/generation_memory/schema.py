"""Allowlists for schema-driven retry inheritance. No generic dict.update."""

from __future__ import annotations

INHERIT_EXACT: frozenset[str] = frozenset(
    {
        "originalUserInstructions",
        "referenceAssetIds",
        "visionFacts",
        "referenceRole",
        "characterIds",
        "propIds",
        "environmentIds",
        "continuityConstraints",
        "negativeConstraints",
        "aspectRatio",
        "width",
        "height",
        "qualityIntent",
    }
)

LOCKED_ROUTE_LEVELS: frozenset[str] = frozenset({"PREFERRED", "STRICT"})

# These describe a restated generator lock. An UNLOCKED AUTO turn must not
# carry them forward as if the creator asked for that generator again.
GENERATOR_LOCK_FIELDS: frozenset[str] = frozenset(
    {
        "route",
        "provider",
        "modelId",
        "requestedProvider",
        "requestedModelId",
        "lockLevel",
        "lockScope",
    }
)

OVERRIDE_IF_STATED: frozenset[str] = frozenset(
    {
        "route",
        "provider",
        "modelId",
        "aspectRatio",
        "width",
        "height",
        "qualityIntent",
        "lockLevel",
        "lockScope",
        "requestedProvider",
        "requestedModelId",
        "artifactType",
        "action",
        "referenceAssetIds",
    }
)

RECOMPUTE_ALWAYS_ON_RETRY: frozenset[str] = frozenset(
    {
        "compiledGeneratorPrompt",
        "generationParameters",
        "workflowKey",
        "providerPayload",
    }
)

EXCLUDED_CAPABILITIES: frozenset[str] = frozenset(
    {
        "timeline.generate_shot",
        "timeline.prepare_scene",
        "timeline.deposit_video",
        "ers.generate",
        "atlas.generate",
        "scene.generate",
        "storyboard.generate",
        "storyboard.regenerate_frame",
        "character.visual_sheet",
        "character.generate_visual_sheet",
        "spatial_map.generate",
    }
)
