"""ERS sheet middle row: Spatial Map, Legend, Structuring / 3D."""

from app.codirector.knowledgebase.ers_compiler import compile_environment_reference_sheet_prompt
from app.spatial_map.ers_collage_templates import (
    ERS_SHEET_MASTER,
    ORIGINAL_ERS_V1,
    lookup_collage_template,
)


def test_legend_sits_between_spatial_map_and_structuring() -> None:
    contract = lookup_collage_template(template_id=ORIGINAL_ERS_V1)
    assert contract is not None
    assert ERS_SHEET_MASTER == (2048, 1536)
    spatial = contract.panel_content("spatial")
    legend = contract.panel_content("legend")
    structuring = contract.panel_content("structuring")
    assert spatial and legend and structuring
    assert legend["left"] >= spatial["left"] + spatial["width"] - 0.002
    assert structuring["left"] >= legend["left"] + legend["width"] - 0.002
    assert abs(legend["width"] - 0.16) < 0.02
    assert legend["width"] < spatial["width"]
    assert legend["width"] < structuring["width"]


def test_compiled_sheet_names_the_legend_row() -> None:
    compiled = compile_environment_reference_sheet_prompt(
        environment_name="Harbor Warehouse",
        environment_description="Cold warehouse interior.",
    )
    prompt = compiled["prompt"]
    assert "Create one horizontal row containing Spatial Map on the left, Legend in the center, and Structuring / 3D on the right." in prompt
    assert "Spatial Map | Legend | Structuring / 3D" in prompt
    assert "do not omit Legend" in prompt
    assert "do not merge Legend into another section" in prompt
    assert "Characters: Red, Orange, Yellow, Green" in prompt
    assert "Props: Aqua, Blue, Purple, Gray" in prompt
    assert "Use a color for each character or prop in scene." in prompt
    assert "~42% Spatial Map, ~16% Legend, ~42% Structuring / 3D" in prompt
    assert "2048x1536" in prompt
