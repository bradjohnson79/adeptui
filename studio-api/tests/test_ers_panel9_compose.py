"""Panel 9 template contract: cover-fit, no 3x3 fallback, no letterbox."""

from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image

from app.spatial_map.ers_collage_templates import (
    ErsCollageTemplateError,
    SENSENOVA_INTEGRATION_LAB_ERS_V1,
    SENSENOVA_TEMPLATE_ASSET_ID,
    lookup_collage_template,
)
from app.spatial_map.ers_compose_2k import COLLAGE_OCCUPIED_REGION, compose_occupied_into_collage


def _png(image: Image.Image) -> bytes:
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def test_sensenova_contract_is_bound_to_original_collage():
    contract = lookup_collage_template(collage_asset_id=SENSENOVA_TEMPLATE_ASSET_ID)
    assert contract is not None
    assert contract.template_id == SENSENOVA_INTEGRATION_LAB_ERS_V1
    assert contract.template_size == (1672, 941)
    assert contract.panel9_pixels == (1048, 496, 1660, 632)
    assert contract.contract_version == 1


def test_panel9_cover_fit_keeps_outside_pixels_and_fills_box():
    contract = lookup_collage_template(template_id=SENSENOVA_INTEGRATION_LAB_ERS_V1)
    assert contract is not None
    w, h = contract.template_size
    x0, y0, x1, y1 = contract.panel9_pixels
    collage = Image.new("RGB", (w, h), (40, 80, 120))
    collage.paste(Image.new("RGB", (x1 - x0, y0 - 428), (200, 180, 40)), (x0, 428))
    collage.paste(Image.new("RGB", (x1 - x0, y1 - y0), (10, 200, 10)), (x0, y0))
    occupied = Image.new("RGB", (200, 400), (220, 30, 30))
    occupied.paste(Image.new("RGB", (200, 200), (30, 30, 220)), (0, 200))

    before = collage.copy()
    out = Image.open(
        BytesIO(
            compose_occupied_into_collage(
                _png(collage),
                _png(occupied),
                collage_asset_id=SENSENOVA_TEMPLATE_ASSET_ID,
                template_id=SENSENOVA_INTEGRATION_LAB_ERS_V1,
            )
        )
    ).convert("RGB")

    assert out.size == (w, h)
    # Outside the contract box must be pixel-identical.
    for sample in ((10, 10), (x0 - 1, y0), (x0, y0 - 1), (x1, y0), (x0, y1), (800, 200)):
        assert out.getpixel(sample) == before.getpixel(sample)
    # Title strip unchanged.
    assert out.getpixel((x0 + 10, y0 - 4)) == (200, 180, 40)
    # Destination is filled (no letterbox pad).
    mid = out.getpixel(((x0 + x1) // 2, (y0 + y1) // 2))
    assert mid != (20, 24, 30)
    assert mid != (10, 200, 10)
    assert mid[0] > 160 or mid[2] > 160
    corner = out.getpixel((x0 + 2, y0 + 2))
    assert corner != (20, 24, 30)
    assert corner != (40, 80, 120)


def test_sensenova_template_without_matching_size_fails_closed():
    collage = Image.new("RGB", (300, 300), (12, 14, 16))
    occupied = Image.new("RGB", (90, 90), (220, 40, 40))
    with pytest.raises(ErsCollageTemplateError, match="does not match template"):
        compose_occupied_into_collage(
            _png(collage),
            _png(occupied),
            collage_asset_id=SENSENOVA_TEMPLATE_ASSET_ID,
        )


def test_unknown_collage_does_not_use_3x3_gallery_region():
    collage = Image.new("RGB", (300, 300), (12, 14, 16))
    occupied = Image.new("RGB", (90, 90), (220, 40, 40))
    with pytest.raises(ErsCollageTemplateError, match="template contract is missing"):
        compose_occupied_into_collage(_png(collage), _png(occupied))
    gallery_left = int(300 * COLLAGE_OCCUPIED_REGION["left"]) + 20
    gallery_top = int(300 * COLLAGE_OCCUPIED_REGION["top"]) + 20
    # Prove the 3x3 box would have been the wrong silent destination.
    assert gallery_left > 180
    assert gallery_top > 180


def test_gallery_template_still_uses_explicit_3x3_region():
    collage = Image.new("RGB", (300, 300), (12, 14, 16))
    occupied = Image.new("RGB", (90, 90), (220, 40, 40))
    out = Image.open(
        BytesIO(
            compose_occupied_into_collage(
                _png(collage),
                _png(occupied),
                template_id="gallery-3x3-v1",
            )
        )
    ).convert("RGB")
    left = int(300 * COLLAGE_OCCUPIED_REGION["left"]) + 20
    top = int(300 * COLLAGE_OCCUPIED_REGION["top"]) + 20
    assert out.getpixel((left, top))[0] > 180
    assert out.getpixel((10, 10)) == (12, 14, 16)
