"""Draft environment profiles are not Project Environment Reference Sheets."""

from app.environment_reference_sheet.orchestrator import create_sheet
from app.environment_reference_sheet.store import (
    find_reusable_environment_draft,
    sheet_is_project_reference,
)


def test_name_and_description_are_not_a_reference_sheet():
    sheet = create_sheet(project_id="p1", name="Coffee House", description="A quiet cafe")
    assert sheet.status == "draft"
    assert sheet_is_project_reference(sheet) is False


def test_reference_input_without_a_visual_is_not_a_reference_sheet():
    sheet = create_sheet(project_id="p1", name="Coffee House", description="A quiet cafe")
    sheet.provenance.details = {"environmentCreatorPlan": {"referenceImageAssetId": "ref-1"}}
    assert sheet_is_project_reference(sheet) is False


def test_official_visual_is_a_reference_sheet():
    approved = create_sheet(project_id="p1", name="Coffee House", description="A quiet cafe")
    approved.status = "approved"
    approved.ers_composite_asset_id = "asset-approved"
    generated = create_sheet(project_id="p1", name="Schnick Coffee House", description="Generated")
    generated.composition.renderedAssetIds = {"composite": "asset-generated"}
    assert sheet_is_project_reference(approved) is True
    assert sheet_is_project_reference(generated) is True


def test_failed_start_reuses_the_unfinished_sheet_instead_of_a_second_row():
    failed = create_sheet(project_id="p1", name="Coffee House", description="first attempt")
    real = create_sheet(project_id="p1", name="Coffee House", description="finished")
    real.ers_composite_asset_id = "asset-real"
    other = create_sheet(project_id="p2", name="Coffee House", description="elsewhere")
    reused = find_reusable_environment_draft(
        [real, other, failed],
        project_id="p1",
        name="coffee house",
    )
    assert reused is failed
    assert find_reusable_environment_draft([real], project_id="p1", name="Coffee House") is None
