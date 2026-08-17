"""Locked bilingual glossary. English and Chinese are views of the same facts."""

from __future__ import annotations

COMPILER_VERSION = "cd-multimodal-continuity-v1"

# Each hard fact id maps to the English token and Chinese token that MUST
# co-occur when that fact is a hard generation constraint.
GLOSSARY: dict[str, tuple[str, str]] = {
    "behind_service_counter": ("behind the service counter", "服务吧台后方"),
    "espresso_station": ("espresso station", "咖啡机工作区"),
    "employee_side": ("staff side", "员工一侧"),
    "customer_side": ("customer side", "顾客一侧"),
    "front_of_counter": ("in front of the counter", "吧台前方"),
    "customer_seating": ("customer seating", "顾客座位区"),
    "preserve_environment": (
        "Use the supplied reference image as the exact physical environment",
        "以提供的参考图像作为唯一权威的物理环境",
    ),
    "only_camera": (
        "Only change the camera viewpoint. Do not redesign, mirror, move, add, or remove major architectural or furniture elements",
        "只改变摄像机视角。不要重新设计、镜像、移动、增加或删除主要建筑结构和固定家具",
    ),
    "service_counter": ("service counter", "服务吧台"),
    "pastry_case": ("pastry case", "糕点展示柜"),
    "storefront_windows": ("storefront windows", "店面窗户"),
    "main_entrance": ("main entrance", "主入口"),
    "lounge_couch": ("lounge couch", "休息区沙发"),
    "occupied_scale_only": (
        "placed subjects only in the occupied-scale panel",
        "仅在占用比例面板中显示已放置的人物",
    ),
}

# Qwen / GPT phrase library — from Adept ERS live language, not internet dump.
QWEN_KEEP = "保持同一物理环境。不要重新设计。"
QWEN_VIEW_WHOLE = "生成同一锁定环境的统一环境参考表（production_ers）。"
GPT_KEEP = "Preserve this physical set. Do not redesign the room."
GPT_VIEW_WHOLE = "Generate one unified Environment Reference Sheet of this same locked place."

# Krea 2 is Qwen-Image-based (Qwen Image VAE + Qwen3VL encoder), so it reuses the
# Qwen Chinese-first keep phrase. Only the view phrase is Krea-specific (the
# renderer stays a tiny translator of the canonical packet — no second compiler).
KREA2_KEEP = QWEN_KEEP
KREA2_VIEW_WHOLE = "生成同一锁定环境的统一环境参考表（krea2 production_ers）。"
