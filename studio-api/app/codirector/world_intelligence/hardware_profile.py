"""Hardware profiling for V-JEPA world intelligence."""

from __future__ import annotations

from typing import Optional


def estimate_vram_gb(model_id: str) -> float:
    """Approximate VRAM requirements for V-JEPA models."""
    estimates = {
        "vjepa2-vitl-fpc64-256": 2.5,   # ViT-L/16, ~300M params
        "vjepa2.1-vitl-384": 3.5,       # ViT-L/16, 384px input
        "vjepa2-vith-fpc64-256": 5.0,   # ViT-H/16, ~600M params
        "vjepa2-vitg-fpc64-256": 8.0,   # ViT-G/14, ~1B params
        "vjepa2-vitg-fpc64-384": 12.0,  # ViT-G/14, 384px input
    }
    return estimates.get(model_id, 4.0)


def gpu_memory_info() -> dict:
    """Get current GPU memory info if available."""
    try:
        import torch
        if not torch.cuda.is_available():
            return {"available": False, "reason": "CPU_ONLY"}
        free_gb = []
        total_gb = []
        for i in range(torch.cuda.device_count()):
            free, total = torch.cuda.mem_get_info(i)
            free_gb.append(round(free / (1024**3), 1))
            total_gb.append(round(total / (1024**3), 1))
        return {
            "available": True,
            "deviceCount": torch.cuda.device_count(),
            "freeGb": free_gb,
            "totalGb": total_gb,
            "deviceNames": [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())],
        }
    except Exception as exc:
        return {"available": False, "reason": str(exc)[:80]}


def can_run_model(model_id: str, min_free_gb: Optional[float] = None) -> dict:
    """Check if the current hardware can run the specified model."""
    min_vram = min_free_gb or estimate_vram_gb(model_id)
    info = gpu_memory_info()
    if not info.get("available"):
        return {"ok": False, "reason": info.get("reason", "NO_GPU"), "recommendedGb": min_vram}
    free = info.get("freeGb", [0])[0] if info.get("freeGb") else 0
    if free < min_vram:
        return {
            "ok": False,
            "reason": "INSUFFICIENT_VRAM",
            "freeGb": free,
            "requiredGb": min_vram,
            "recommendedGb": min_vram,
        }
    return {"ok": True, "freeGb": free, "requiredGb": min_vram}
