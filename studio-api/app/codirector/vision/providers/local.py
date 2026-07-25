"""Local vision provider: OpenCV/Pillow technical metrics; ML slots stubbed."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional


def _pillow_metrics(path: Path) -> dict[str, Any]:
    try:
        from PIL import Image, ImageStat
    except Exception:
        return {"decodeError": "pillow_unavailable"}

    try:
        with Image.open(path) as img:
            rgb = img.convert("RGB")
            width, height = rgb.size
            stat = ImageStat.Stat(rgb)
            mean = stat.mean
            mean_luma = 0.299 * mean[0] + 0.587 * mean[1] + 0.114 * mean[2]
            # crude saturation proxy from channel spread
            spreads = [max(c) - min(c) for c in zip(*list(rgb.getdata())[:: max(1, width * height // 2000)])] if width and height else [0]
            mean_sat = (sum(spreads) / max(len(spreads), 1)) / 255.0 if spreads else 0.0
            return {
                "width": width,
                "height": height,
                "aspectRatio": round(width / height, 4) if height else None,
                "meanLuma": float(mean_luma),
                "meanSaturation": float(mean_sat),
                "source": "pillow",
            }
    except Exception as exc:
        return {"decodeError": str(exc)}


def _opencv_metrics(path: Path) -> dict[str, Any]:
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except Exception:
        return {}

    try:
        data = np.fromfile(str(path), dtype=np.uint8)
        image = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if image is None:
            return {"decodeError": "opencv_imdecode_failed"}
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        h, w = gray.shape[:2]
        return {
            "width": int(w),
            "height": int(h),
            "aspectRatio": round(w / h, 4) if h else None,
            "laplacianVariance": variance,
            "meanLuma": float(gray.mean()),
            "source": "opencv",
        }
    except Exception as exc:
        return {"decodeError": str(exc)}


class LocalVisionProvider:
    provider_id = "local"

    def prepare_asset_context(
        self,
        *,
        asset_path: Optional[str],
        reference_path: Optional[str],
        requirements: dict[str, Any],
        fixture_profile: Optional[str] = None,
    ) -> dict[str, Any]:
        media_kind = str(requirements.get("mediaKind") or "image")
        metrics: dict[str, Any] = {}
        if asset_path:
            path = Path(asset_path)
            if path.is_file():
                metrics = _opencv_metrics(path)
                if not metrics or metrics.get("decodeError"):
                    pillow = _pillow_metrics(path)
                    metrics = {**pillow, **{k: v for k, v in metrics.items() if k not in pillow}}
            else:
                metrics = {"decodeError": "asset_missing"}
        else:
            metrics = {"decodeError": "asset_path_missing"}

        # Explicit stubs: never invent ML pass results.
        return {
            "provider": self.provider_id,
            "mediaKind": media_kind,
            "assetPath": asset_path,
            "referencePath": reference_path,
            "fixtureProfile": fixture_profile,
            "technicalMetrics": metrics,
            "mlIdentityAvailable": False,
            "mlContinuityAvailable": False,
            "mlLightingAvailable": False,
            "mlCameraAvailable": False,
            "mlCompositionAvailable": False,
            "mlColorAvailable": False,
            "mlMotionAvailable": False,
        }
