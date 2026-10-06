"""Export the exact Character Creator Comfy graphs and MCP-validate them on :8188.

Does not change product prompting, routing, or certified keys.
Builds graphs through studio-api ``build_leaf_graph`` with the same
width/steps/cfg/denoise Character Creator actually queues today.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:\AdeptFilmWorks\AIVideoStudio")
API_ROOT = REPO / "studio-api"
MCP_EXE = REPO / "data" / "venvs" / "mcp" / "Scripts" / "comfy-mcp.exe"
COMFY_BIN = REPO / "data" / "venvs" / "mcp" / "Scripts" / "comfy.exe"

REVIEW_DIR = REPO / "docs" / "release-gate" / "character-creator" / "workflows"
ARTIFACT_DIR = REPO / "artifacts" / "character-creator" / "workflows"
COMFY_USER_DIR = Path(
    r"C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\user\default\workflows\Character Creator"
)

FRONT_GOAL = (
    "one person, full body, front-facing, neutral standing pose, centered, "
    "simple background, no collage, no text, no second person"
)
BACK_GOAL = (
    "the same person as the front reference, full body, viewed from behind, "
    "same hair clothing colors and identity, no collage, no second person"
)
DEFAULT_NEGATIVE = (
    "multiple people, collage, contact sheet, grid, inset portrait, "
    "duplicate figure, text, watermark, cropped body, low quality"
)
REF_IMAGE = "character_creator_reference.png"
FRONT_IMAGE = "character_creator_approved_front.png"

# Live CC enqueue uses studio/{projectId[:8]}_imagegen. Dedicated export prefix
# is stable for owner review; mapping report records the live pattern.
CC_PREFIX = "studio/character_creator"


def _sys_path() -> None:
    root = str(API_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def _class_types(graph: dict) -> list[str]:
    return sorted(
        {
            str(node.get("class_type") or "")
            for node in graph.values()
            if isinstance(node, dict)
        }
    )


def _has_load_image(graph: dict) -> bool:
    return any(
        isinstance(node, dict) and node.get("class_type") == "LoadImage"
        for node in graph.values()
    )


def _sampler_fields(graph: dict) -> dict[str, object]:
    for node in graph.values():
        if not isinstance(node, dict) or node.get("class_type") != "KSampler":
            continue
        inputs = node.get("inputs") or {}
        return {
            "steps": inputs.get("steps"),
            "cfg": inputs.get("cfg"),
            "denoise": inputs.get("denoise"),
            "sampler_name": inputs.get("sampler_name"),
            "scheduler": inputs.get("scheduler"),
        }
    return {}


def _build_specs(settings) -> list[dict]:
    """Character Creator route → execute key → live queue/execute params."""
    w, h = 2048, 2048
    default_steps = int(settings.imagegen_default_steps)
    default_cfg = float(settings.imagegen_default_cfg)
    return [
        {
            "id": "qwen2512_front_t2i",
            "filename": "character_qwen2512_front_t2i.json",
            "family": "Qwen Image 2512",
            "route": "Front, no reference (text-to-image)",
            "workflowKey": "qwen2512.txt2img",
            "builder": "build_qwen_2512_txt2img_workflow",
            "builderPath": "studio-api/app/workflows/qwen_image_2512.py",
            "mode": "txt2img",
            "prompt": FRONT_GOAL,
            "negative": DEFAULT_NEGATIVE,
            "width": w,
            "height": h,
            "steps": default_steps,
            "cfg": default_cfg,
            "denoise": None,
            "checkpoint": None,
            "image": None,
            "dedicatedExisted": False,
        },
        {
            "id": "qwen2512_front_i2i",
            "filename": "character_qwen2512_front_i2i.json",
            "family": "Qwen Image 2512",
            "route": "Front, reference attached (I2I / pixel bind)",
            "workflowKey": "qwen2512.ref",
            "builder": "build_qwen_2512_ref_workflow",
            "builderPath": "studio-api/app/workflows/qwen_image_2512.py",
            "mode": "i2i",
            "prompt": FRONT_GOAL,
            "negative": DEFAULT_NEGATIVE,
            "width": w,
            "height": h,
            "steps": default_steps,
            "cfg": default_cfg,
            "denoise": 0.35,
            "checkpoint": None,
            "image": REF_IMAGE,
            "dedicatedExisted": False,
            "notes": [
                "Execute remaps generic steps {8,20} → qwen_image_2512_steps (50) and generic cfg {1.0, imagegen_default_cfg} → qwen_image_2512_cfg (4.0).",
                "Graph denoise is hardcoded 1.0. Character Creator job denoise=0.35 is not applied to this Qwen I2I graph.",
            ],
        },
        {
            "id": "qwen2512_back_from_front",
            "filename": "character_qwen2512_back_from_front.json",
            "family": "Qwen Image 2512",
            "route": "Back from approved Front (I2I / pixel bind)",
            "workflowKey": "qwen2512.ref",
            "builder": "build_qwen_2512_ref_workflow",
            "builderPath": "studio-api/app/workflows/qwen_image_2512.py",
            "mode": "i2i",
            "prompt": BACK_GOAL,
            "negative": DEFAULT_NEGATIVE,
            "width": w,
            "height": h,
            "steps": default_steps,
            "cfg": default_cfg,
            "denoise": 0.35,
            "checkpoint": None,
            "image": FRONT_IMAGE,
            "dedicatedExisted": False,
            "notes": [
                "Same topology as Front I2I. LoadImage slot is the approved Front, not the original reference.",
            ],
        },
        {
            "id": "flux_front_t2i",
            "filename": "character_flux_front_t2i.json",
            "family": "FLUX",
            "route": "Front, no reference (text-to-image)",
            "workflowKey": "flux.txt2img",
            "builder": "build_flux_txt2img_workflow",
            "builderPath": "studio-api/app/workflows/flux_image.py",
            "mode": "txt2img",
            "prompt": FRONT_GOAL,
            "negative": DEFAULT_NEGATIVE,
            "width": w,
            "height": h,
            "steps": default_steps,
            "cfg": default_cfg,
            "denoise": None,
            "checkpoint": settings.imagegen_flux_checkpoint,
            "image": None,
            "dedicatedExisted": False,
        },
        {
            "id": "flux_front_i2i",
            "filename": "character_flux_front_i2i.json",
            "family": "FLUX",
            "route": "Front, reference attached (I2I / pixel bind)",
            "workflowKey": "flux.img2img",
            "builder": "build_flux_img2img_workflow",
            "builderPath": "studio-api/app/workflows/flux_image.py",
            "mode": "i2i",
            "prompt": FRONT_GOAL,
            "negative": DEFAULT_NEGATIVE,
            "width": w,
            "height": h,
            "steps": default_steps,
            "cfg": default_cfg,
            "denoise": 0.35,
            "checkpoint": settings.imagegen_flux_checkpoint,
            "image": REF_IMAGE,
            "dedicatedExisted": False,
        },
        {
            "id": "flux_back_from_front",
            "filename": "character_flux_back_from_front.json",
            "family": "FLUX",
            "route": "Back from approved Front (I2I / pixel bind)",
            "workflowKey": "flux.img2img",
            "builder": "build_flux_img2img_workflow",
            "builderPath": "studio-api/app/workflows/flux_image.py",
            "mode": "i2i",
            "prompt": BACK_GOAL,
            "negative": DEFAULT_NEGATIVE,
            "width": w,
            "height": h,
            "steps": default_steps,
            "cfg": default_cfg,
            "denoise": 0.35,
            "checkpoint": settings.imagegen_flux_checkpoint,
            "image": FRONT_IMAGE,
            "dedicatedExisted": False,
            "notes": [
                "Same topology as Front I2I. LoadImage slot is the approved Front.",
            ],
        },
        {
            "id": "zimage_front_t2i",
            "filename": "character_zimage_front_t2i.json",
            "family": "Z-Image",
            "route": "Front, no reference (text-to-image)",
            "workflowKey": "zimage.txt2img",
            "builder": "build_zimage_txt2img_workflow",
            "builderPath": "studio-api/app/workflows/image_tools.py",
            "mode": "txt2img",
            "prompt": FRONT_GOAL,
            "negative": DEFAULT_NEGATIVE,
            "width": w,
            "height": h,
            "steps": int(settings.zimage_steps),
            "cfg": float(settings.zimage_cfg),
            "denoise": None,
            "checkpoint": None,
            "image": None,
            "dedicatedExisted": False,
        },
        {
            "id": "zimage_front_i2i",
            "filename": "character_zimage_front_i2i.json",
            "family": "Z-Image",
            "route": "Front, reference attached (I2I / pixel bind)",
            "workflowKey": "zimage.ref_edit",
            "builder": "build_zimage_ref_workflow",
            "builderPath": "studio-api/app/workflows/image_tools.py",
            "mode": "i2i",
            "prompt": FRONT_GOAL,
            "negative": DEFAULT_NEGATIVE,
            "width": w,
            "height": h,
            "steps": int(settings.zimage_steps),
            "cfg": float(settings.zimage_cfg),
            "denoise": 0.35,
            "checkpoint": None,
            "image": REF_IMAGE,
            "dedicatedExisted": False,
            "notes": [
                "Execute zimage.ref_edit does not pass job denoise into the builder. Graph uses builder default denoise=0.72.",
            ],
        },
        {
            "id": "zimage_back_from_front",
            "filename": "character_zimage_back_from_front.json",
            "family": "Z-Image",
            "route": "Back from approved Front (I2I / pixel bind)",
            "workflowKey": "zimage.ref_edit",
            "builder": "build_zimage_ref_workflow",
            "builderPath": "studio-api/app/workflows/image_tools.py",
            "mode": "i2i",
            "prompt": BACK_GOAL,
            "negative": DEFAULT_NEGATIVE,
            "width": w,
            "height": h,
            "steps": int(settings.zimage_steps),
            "cfg": float(settings.zimage_cfg),
            "denoise": 0.35,
            "checkpoint": None,
            "image": FRONT_IMAGE,
            "dedicatedExisted": False,
            "notes": [
                "Same topology as Front I2I. LoadImage slot is the approved Front.",
                "Execute zimage.ref_edit does not pass job denoise into the builder. Graph uses builder default denoise=0.72.",
            ],
        },
        {
            "id": "illustrious_xl_front_t2i",
            "filename": "character_illustrious_xl_front_t2i.json",
            "family": "Illustrious XL (SDXL)",
            "route": "Front, no reference (text-to-image). This is Character Creator's SDXL path.",
            "workflowKey": "illustrious.txt2img",
            "builder": "build_txt2img_workflow",
            "builderPath": "studio-api/app/imagegen_workflows.py",
            "mode": "txt2img",
            "prompt": FRONT_GOAL,
            "negative": DEFAULT_NEGATIVE,
            "width": w,
            "height": h,
            "steps": int(settings.imagegen_illustrious_steps),
            "cfg": float(settings.imagegen_illustrious_cfg),
            "denoise": None,
            "checkpoint": settings.imagegen_illustrious_checkpoint,
            "image": None,
            "dedicatedExisted": False,
            "notes": [
                "There is no generic SDXL Character Creator adapter. Illustrious XL is the SDXL family.",
                "Front-with-reference and Back are Unavailable — no I2I workflow is routed.",
            ],
        },
    ]


def _write_json(path: Path, graph: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(graph, indent=2), encoding="utf-8")


def _parse_validate(raw: str) -> dict:
    try:
        verdict = json.loads(raw)
    except json.JSONDecodeError:
        return {"valid": None, "raw": raw[:4000]}
    if not isinstance(verdict, dict):
        return {"valid": None, "raw": str(verdict)[:4000]}
    return verdict


async def _mcp_validate(paths: dict[str, Path]) -> dict[str, dict]:
    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    params = StdioServerParameters(command=str(MCP_EXE), env={"COMFY_BIN": str(COMFY_BIN)})
    out: dict[str, dict] = {}
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            info = await session.call_tool("server_info", {})
            info_text = " ".join(getattr(block, "text", "") or "" for block in info.content)
            out["_server"] = {"server_info": info_text[:2000]}
            for name, path in paths.items():
                result = await session.call_tool("validate_workflow", {"workflow_path": str(path)})
                texts = [getattr(block, "text", "") for block in result.content]
                raw = texts[0] if texts else "{}"
                out[name] = _parse_validate(raw)
    return out


def _run_mcp_validate(paths: dict[str, Path]) -> dict[str, dict]:
    try:
        import mcp  # noqa: F401

        return asyncio.run(_mcp_validate(paths))
    except ImportError:
        pass
    mcp_py = REPO / "data" / "venvs" / "mcp" / "Scripts" / "python.exe"
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        manifest = Path(handle.name)
        json.dump({name: str(path) for name, path in paths.items()}, handle, indent=2)
    try:
        proc = subprocess.run(
            [str(mcp_py), str(Path(__file__).resolve()), "--validate-only", str(manifest)],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        manifest.unlink(missing_ok=True)
    if proc.returncode != 0:
        raise RuntimeError(
            "Comfy MCP validate subprocess failed:\n"
            f"{proc.stdout[-4000:]}\n{proc.stderr[-4000:]}"
        )
    return json.loads(proc.stdout)


def _validate_only(manifest_path: Path) -> int:
    paths = {k: Path(v) for k, v in json.loads(manifest_path.read_text(encoding="utf-8")).items()}
    print(json.dumps(asyncio.run(_mcp_validate(paths)), indent=2))
    return 0


def _unavailable_rows() -> list[dict]:
    return [
        {
            "family": "Illustrious XL (SDXL)",
            "route": "Front, reference attached",
            "workflowKey": None,
            "status": "Unavailable",
            "reason": "Character Creator has no Illustrious / SDXL I2I workflow. No graph was invented.",
        },
        {
            "family": "Illustrious XL (SDXL)",
            "route": "Back from approved Front",
            "workflowKey": None,
            "status": "Unavailable",
            "reason": "Back always requires I2I from Front pixels. Illustrious has no I2I path.",
        },
        {
            "family": "GPT Image",
            "route": "Hosted API Front / Back",
            "workflowKey": None,
            "status": "Not Comfy",
            "reason": "Hosted API adapter. No ComfyUI graph.",
        },
    ]


def _mapping_markdown(rows: list[dict], unavailable: list[dict], settings, comfy_url: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Character Creator ComfyUI Workflow Mapping",
        "",
        f"**Exported:** {now}",
        f"**Live Comfy:** `{comfy_url}` (Comfy MCP `validate_workflow`)",
        "**Prompting:** not modified. Graph text slots use the current Character Creator Front/Back goals. Live jobs still compile the Character Profile on top of these goals.",
        "**Certification:** not run. This is an owner-review export only.",
        "",
        "## What existed before this export",
        "",
        "Character Creator did **not** have dedicated stable Comfy workflow files.",
        "It reused Image Generator execute keys and built the graph at queue time:",
        "",
        "| Family | No-ref Front | With-ref Front | Back |",
        "|---|---|---|---|",
        "| FLUX | `flux.txt2img` | `flux.img2img` | `flux.img2img` |",
        "| Qwen Image 2512 | `qwen2512.txt2img` | `qwen2512.ref` | `qwen2512.ref` |",
        "| Z-Image | `zimage.txt2img` | `zimage.ref_edit` | `zimage.ref_edit` |",
        "| Illustrious XL (SDXL) | `illustrious.txt2img` | Unavailable | Unavailable |",
        "",
        "Comfy user workflows had no Character Creator graphs. Gallery templates named “character” are video/SCAIL, not these stills.",
        "",
        "This export **created** dedicated Character Creator API-format workflows from the exact live builders, then MCP-validated them against `:8188`.",
        "",
        "## Live settings used",
        "",
        f"- Frame: `2048 x 2048` (`crs_2k_view_pixels`, `sheet_layout=cc_v2`)",
        f"- FLUX UNET: `{settings.imagegen_flux_checkpoint}` + `{settings.imagegen_flux_clip_l}` + `{settings.imagegen_flux_t5}` + `{settings.imagegen_flux_vae}`",
        f"- Qwen UNET: `{settings.qwen_image_2512_unet}` + `{settings.qwen_image_2512_clip}` + `{settings.qwen_image_2512_vae}`",
        f"- Z-Image UNET: `{settings.zimage_unet}` + `{settings.zimage_clip}` + `{settings.zimage_vae}`",
        f"- Illustrious XL: `{settings.imagegen_illustrious_checkpoint}`",
        f"- Queue defaults before family remap: steps=`{settings.imagegen_default_steps}`, cfg=`{settings.imagegen_default_cfg}`",
        f"- Live SaveImage prefix on Adept jobs: `studio/{{projectId[:8]}}_imagegen`",
        f"- Dedicated export prefix: `{CC_PREFIX}/<route>`",
        "",
        "## Route → execute key → dedicated file",
        "",
        "| Family | Character Creator route | Execute key | Builder | Dedicated JSON | MCP valid | Graph steps/cfg/denoise | LoadImage |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        samp = row.get("sampler") or {}
        valid = row.get("mcpValid")
        valid_s = "PASS" if valid is True else ("FAIL" if valid is False else "UNKNOWN")
        samp_s = f"{samp.get('steps')}/{samp.get('cfg')}/{samp.get('denoise')}"
        lines.append(
            f"| {row['family']} | {row['route']} | `{row['workflowKey']}` | `{row['builder']}` | `{row['filename']}` | {valid_s} | {samp_s} | {'yes' if row.get('hasLoadImage') else 'no'} |"
        )
    lines.extend(
        [
            "",
            "## Unavailable / not Comfy",
            "",
            "| Family | Route | Status | Reason |",
            "|---|---|---|---|",
        ]
    )
    for row in unavailable:
        lines.append(
            f"| {row['family']} | {row['route']} | {row['status']} | {row['reason']} |"
        )
    lines.extend(
        [
            "",
            "## Per-file notes",
            "",
        ]
    )
    for row in rows:
        lines.append(f"### `{row['filename']}`")
        lines.append("")
        lines.append(f"- Route: {row['route']}")
        lines.append(f"- Execute key: `{row['workflowKey']}`")
        lines.append(f"- Builder: `{row['builder']}` in `{row['builderPath']}`")
        lines.append(f"- Class types: {', '.join(row.get('classTypes') or [])}")
        if row.get("image"):
            lines.append(f"- LoadImage filename slot: `{row['image']}`")
        mcp = row.get("mcp") or {}
        lines.append(f"- MCP `valid`: `{mcp.get('valid')}`")
        if mcp.get("errors"):
            lines.append(f"- MCP errors: `{json.dumps(mcp.get('errors'))[:1500]}`")
        if mcp.get("warnings"):
            lines.append(f"- MCP warnings: `{json.dumps(mcp.get('warnings'))[:1500]}`")
        for note in row.get("notes") or []:
            lines.append(f"- {note}")
        lines.append(f"- Review path: `{REVIEW_DIR / row['filename']}`")
        lines.append(f"- Artifact path: `{ARTIFACT_DIR / row['filename']}`")
        lines.append(f"- Comfy user copy: `{COMFY_USER_DIR / row['filename']}`")
        lines.append("")
    lines.extend(
        [
            "## How Character Creator uses these graphs",
            "",
            "1. Creator picks a family (or AUTO) and clicks Create Front / Create Back.",
            "2. `cc_v2.generate_view` resolves `t2iKey` or `refKey` from `cc_v2_generators.py`.",
            "3. `_enqueue_txt2img(..., sheet_layout='cc_v2')` sets 2048², `purpose=character`, and `taskType` `CC_V2_T2I` or `CC_V2_I2I`.",
            "4. Queue worker calls `build_leaf_graph` in `workflow_execute.py` with the execute key above.",
            "5. The graph in the matching JSON is what Comfy `:8188` receives (`/prompt` API format).",
            "",
            "Front I2I and Back I2I share topology per family. They differ by prompt goal and which pixels are bound (reference vs approved Front).",
            "",
            "Close-up uses the same I2I execute key as Back (approved Front pixels). A separate Close-up JSON was not requested.",
            "",
            "## Owner review files",
            "",
            f"- Mapping report: `{REVIEW_DIR.parent / 'CHARACTER_CREATOR_WORKFLOW_MAPPING.md'}`",
            f"- Downloadable JSON: `{REVIEW_DIR}`",
            f"- Local artifact copy: `{ARTIFACT_DIR}`",
            f"- Comfy Desktop copies: `{COMFY_USER_DIR}`",
            "",
            "No further prompt tuning or certification was run.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    _sys_path()
    from app.config import settings
    from app.image_runtime.workflow_execute import build_leaf_graph

    specs = _build_specs(settings)
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    COMFY_USER_DIR.mkdir(parents=True, exist_ok=True)

    built: list[dict] = []
    validate_paths: dict[str, Path] = {}
    for spec in specs:
        graph = build_leaf_graph(
            {"workflowKey": spec["workflowKey"]},
            settings=settings,
            prompt=spec["prompt"],
            negative=spec["negative"],
            width=spec["width"],
            height=spec["height"],
            seed=0,
            steps=spec["steps"],
            cfg=spec["cfg"],
            filename_prefix=f"{CC_PREFIX}/{spec['id']}",
            reference_image=spec["image"],
            source_image=spec["image"],
            checkpoint=spec["checkpoint"],
            denoise=spec["denoise"] if spec["denoise"] is not None else 0.45,
        )
        review_path = REVIEW_DIR / spec["filename"]
        _write_json(review_path, graph)
        _write_json(ARTIFACT_DIR / spec["filename"], graph)
        _write_json(COMFY_USER_DIR / spec["filename"], graph)
        row = dict(spec)
        row["classTypes"] = _class_types(graph)
        row["hasLoadImage"] = _has_load_image(graph)
        row["sampler"] = _sampler_fields(graph)
        row["nodeCount"] = len(graph)
        row["reviewPath"] = str(review_path)
        built.append(row)
        validate_paths[spec["id"]] = review_path

    mcp = _run_mcp_validate(validate_paths)
    server = mcp.pop("_server", {})
    for row in built:
        verdict = mcp.get(row["id"]) or {}
        row["mcp"] = {
            "valid": verdict.get("valid"),
            "errors": verdict.get("errors"),
            "warnings": verdict.get("warnings"),
        }
        row["mcpValid"] = verdict.get("valid") is True

    unavailable = _unavailable_rows()
    report = _mapping_markdown(built, unavailable, settings, "http://127.0.0.1:8188")
    report_path = REVIEW_DIR.parent / "CHARACTER_CREATOR_WORKFLOW_MAPPING.md"
    report_path.write_text(report, encoding="utf-8")
    (ARTIFACT_DIR / "CHARACTER_CREATOR_WORKFLOW_MAPPING.md").write_text(report, encoding="utf-8")
    shutil.copy2(report_path, COMFY_USER_DIR / "CHARACTER_CREATOR_WORKFLOW_MAPPING.md")

    index = {
        "exportedAt": datetime.now(timezone.utc).isoformat(),
        "comfy": "http://127.0.0.1:8188",
        "mcpServer": server,
        "reviewDir": str(REVIEW_DIR),
        "artifactDir": str(ARTIFACT_DIR),
        "comfyUserDir": str(COMFY_USER_DIR),
        "workflows": [
            {
                "id": r["id"],
                "filename": r["filename"],
                "family": r["family"],
                "route": r["route"],
                "workflowKey": r["workflowKey"],
                "mcpValid": r["mcpValid"],
                "sampler": r["sampler"],
                "hasLoadImage": r["hasLoadImage"],
            }
            for r in built
        ],
        "unavailable": unavailable,
    }
    (REVIEW_DIR / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    (ARTIFACT_DIR / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")

    print(json.dumps(index, indent=2))
    failed = [r["id"] for r in built if r["mcpValid"] is not True]
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--validate-only":
        sys.exit(_validate_only(Path(sys.argv[2])))
    sys.exit(main())
