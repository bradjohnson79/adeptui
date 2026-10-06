"""Write Adept-built LTX/WAN/H3 graphs for Comfy MCP validate_workflow."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = Path(__file__).resolve().parent / "evidence"
sys.path.insert(0, str(ROOT / "studio-api"))

from app.config import settings  # noqa: E402
from app.workflows.h3_ref2v_builder import build_h3_ref2v  # noqa: E402
from app.workflows.ltx_builder import build_ltx_simple_i2v  # noqa: E402
from app.workflows.wan_builder import build_wan_flf_workflow  # noqa: E402


def _write(name: str, graph: dict) -> Path:
    path = OUT_DIR / f"{name}.json"
    path.write_text(json.dumps(graph, indent=2), encoding="utf-8")
    return path


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ltx = build_ltx_simple_i2v(
        checkpoint=settings.ltx_checkpoint,
        positive="closure probe",
        negative="blurry",
        width=768,
        height=432,
        length=17,
        fps=24,
        seed=1,
        start_image="Venture Corridor.png",
        text_encoder=settings.ltx_text_encoder,
    )
    wan = build_wan_flf_workflow(
        high_noise=settings.wan_high_noise,
        low_noise=settings.wan_low_noise,
        vae_name=settings.wan_vae,
        text_encoder=settings.wan_text_encoder,
        positive="closure probe",
        negative="blurry",
        width=832,
        height=480,
        length=17,
        fps=16,
        seed=1,
        start_image="Venture Corridor.png",
        end_image="Korri Character Sheet.png",
    )
    h3 = build_h3_ref2v(
        prompt="closure probe",
        ref_comfy_names=["Venture Corridor.png"],
        filename_prefix="studio/h3_mcp_probe",
        seed=1,
        length=5,
    )
    paths = {
        "ltx_23": str(_write("mcp_graph_ltx_23", ltx)),
        "wan_flf": str(_write("mcp_graph_wan_flf", wan)),
        "h3_ref2v": str(_write("mcp_graph_h3_ref2v", h3)),
        "ltx_checkpoint": settings.ltx_checkpoint,
        "ltx_text_encoder": settings.ltx_text_encoder,
        "wan_high_noise": settings.wan_high_noise,
        "wan_low_noise": settings.wan_low_noise,
        "wan_vae": settings.wan_vae,
        "wan_text_encoder": settings.wan_text_encoder,
    }
    print(json.dumps(paths, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
