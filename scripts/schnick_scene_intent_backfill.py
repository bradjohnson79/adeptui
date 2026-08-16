"""One-time backfill: Schnick Coffee Scene Intent lineage (plan W6).

Writes a canonical SceneIntent snapshot onto the existing Schnick Coffee
Spatial Map and Environment Reference Sheet **in place** — no Atlas regen, no
new project (one project, one library law).

Sources:
- Atlas asset prompt_meta (originating prompt text, "Korri Coffee House.png").
- Original environment reference image asset (4d3062e8-...).

Run from repo root:
    studio-api/.venv/Scripts/python.exe scripts/schnick_scene_intent_backfill.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "studio-api"))

from app.db import Asset, SessionLocal  # noqa: E402
from app.environment_reference_sheet.store import load_sheet, save_sheet  # noqa: E402
from app.spatial_map.scene_intent import SceneIntent, lineage_fingerprint  # noqa: E402
from app.spatial_map.schemas import SpatialMapUpdateBody  # noqa: E402
from app.spatial_map.service import get_document, update_document  # noqa: E402

PROJECT_ID = "2347bf46-3762-4763-86c5-4a6032522278"
MAP_ID = "6bc36d92-d21a-4c2f-b85f-71d1f6aa9081"
SHEET_ID = "db095959-5678-4f11-98d1-e93e0810d119"
ATLAS_ASSET_ID = "caa72759-d965-41f9-b1d5-77cdcf9b9614"
ORIGINAL_IMAGE_ID = "4d3062e8-8c30-4230-8376-bc25d1d4f735"  # Korri Coffee House.png

SCENE_INTENT = SceneIntent(
    sceneTitle="Schnick Coffee",
    locationType="coffee_shop",
    summary=(
        "A warm neighborhood coffee shop — Schnick Coffee — the primary "
        "location for our commercial scene. Cozy café interior with counter, "
        "seating, and coffee bar."
    ),
    productionIntent=(
        "Primary environment for the Schnick Coffee commercial; character "
        "Korri appears here with a coffee cup."
    ),
    keySubjects=["Korri"],
    keyProps=["coffee cup"],
    environmentTraits=["warm", "cozy", "café interior", "neighborhood coffee shop"],
    sourcePromptSummary=(
        "Creator request: Atlas shot for the Schnick Coffee café environment "
        "(reference image: Korri Coffee House.png)."
    ),
    sourceReferenceAssetIds=[ORIGINAL_IMAGE_ID],
)


def main() -> None:
    with SessionLocal() as db:
        before = get_document(db, PROJECT_ID, MAP_ID)
        if before.backgroundAssetId != ATLAS_ASSET_ID:
            print(
                f"WARN: map background {before.backgroundAssetId} != expected atlas {ATLAS_ASSET_ID}"
            )
        after = update_document(
            db,
            PROJECT_ID,
            MAP_ID,
            SpatialMapUpdateBody(
                sceneIntent=SCENE_INTENT,
                originalEnvironmentReferenceAssetId=ORIGINAL_IMAGE_ID,
                originatingUserPrompt=SCENE_INTENT.sourcePromptSummary,
            ),
        )
        print(
            f"MAP updated: sceneIntent v{after.sceneIntent.version if after.sceneIntent else '?'}, "
            f"fingerprint={after.groundingFingerprint}"
        )

        # Atlas asset prompt_meta lineage stamp (prompt_meta_json is a JSON text column).
        atlas = db.get(Asset, ATLAS_ASSET_ID)
        if atlas is not None:
            try:
                meta = json.loads(atlas.prompt_meta_json or "{}")
            except Exception:
                meta = {}
            meta["sceneIntent"] = SCENE_INTENT.model_dump()
            meta["originalEnvironmentReferenceAssetIds"] = [ORIGINAL_IMAGE_ID]
            atlas.prompt_meta_json = json.dumps(meta)
            print("ATLAS asset prompt_meta stamped with sceneIntent + original reference.")
        else:
            print(f"WARN: atlas asset {ATLAS_ASSET_ID} not found in DB")

        db.commit()

    # ERS sheet profile + provenance lineage (JSON file store).
    sheet = load_sheet(PROJECT_ID, SHEET_ID)
    if sheet is None:
        print(f"WARN: ERS sheet {SHEET_ID} not found on disk")
    else:
        sheet.profile.environmentName = SCENE_INTENT.sceneTitle
        sheet.profile.environmentType = SCENE_INTENT.locationType
        sheet.name = f"{SCENE_INTENT.sceneTitle} — Environment Reference Sheet"
        if sheet.description.startswith("Programmatically composed"):
            sheet.description = SCENE_INTENT.summary
        prov = sheet.provenance
        if prov is not None:
            details = dict(getattr(prov, "details", None) or {})
            details["sceneIntent"] = SCENE_INTENT.model_dump()
            details["sceneIntentVersion"] = SCENE_INTENT.version
            details["originalEnvironmentReferenceAssetId"] = ORIGINAL_IMAGE_ID
            details["groundingAssetIds"] = [ORIGINAL_IMAGE_ID, ATLAS_ASSET_ID]
            details["groundingFingerprint"] = lineage_fingerprint(
                SCENE_INTENT,
                background_asset_id=ATLAS_ASSET_ID,
                original_reference_asset_id=ORIGINAL_IMAGE_ID,
            )
            details["backfill"] = "schnick_scene_intent_backfill (W6)"
            prov.details = details
        save_sheet(sheet)
        print(f"SHEET updated: {sheet.name!r}, type={sheet.profile.environmentType}")

    print("DONE — Schnick Coffee Scene Intent backfill committed.")
    print(json.dumps(SCENE_INTENT.model_dump(), indent=2))


if __name__ == "__main__":
    main()
