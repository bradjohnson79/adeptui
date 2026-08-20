"""Measure unmasked pixel drift. Do not change zimage.inpaint unless leak is proven."""

from __future__ import annotations

from pathlib import Path


def unmasked_mean_delta(output: str | Path, source: str | Path, mask: str | Path) -> float:
    """Mean absolute RGB delta on pixels the mask leaves untouched (mask < 16)."""
    from PIL import Image
    import numpy as np

    with Image.open(output) as out_im, Image.open(source) as src_im, Image.open(mask) as mask_im:
        out_rgb = np.asarray(out_im.convert("RGB"), dtype=np.float32)
        src_rgb = np.asarray(src_im.convert("RGB"), dtype=np.float32)
        mask_l = np.asarray(mask_im.convert("L").resize(src_im.size), dtype=np.float32)
        if out_rgb.shape != src_rgb.shape:
            out_im_r = out_im.convert("RGB").resize(src_im.size)
            out_rgb = np.asarray(out_im_r, dtype=np.float32)
        untouched = mask_l < 16.0
        if not np.any(untouched):
            return 0.0
        delta = np.abs(out_rgb - src_rgb)
        return float(delta[untouched].mean())


LEAK_THRESHOLD = 2.0
