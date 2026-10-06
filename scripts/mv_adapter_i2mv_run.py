"""Isolated MV-Adapter I2MV-SDXL 2D runner.

Does not import mvadapter.utils.mesh_utils (that package pulls nvdiffrast).
Camera math is vendored from official camera.py (Apache-2.0).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import torch
import torch.nn.functional as F
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME = REPO_ROOT / "data" / "runtimes" / "mv-adapter"
DEFAULT_MODELS = REPO_ROOT / "data" / "models" / "MV-Adapter"
AZIMUTHS = [0, 45, 90, 180, 270, 315]
SLOT_FOR_AZIMUTH = {
    0: "generated_front_discard",
    45: "three_quarter",
    90: "side",
    180: "back",
    270: "extra_profile",
    315: "extra_three_quarter",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _list_to_pt(x, dtype=None, device=None) -> torch.Tensor:
    if isinstance(x, list):
        return torch.tensor(x, dtype=dtype, device=device)
    return x.to(dtype=dtype)


def get_c2w(elevation_deg, distance, azimuth_deg, num_views=1, device=None):
    if azimuth_deg is None:
        azimuth_deg = torch.linspace(0, 360, num_views + 1, dtype=torch.float32, device=device)[:-1]
    else:
        num_views = len(azimuth_deg)
        azimuth_deg = _list_to_pt(azimuth_deg, dtype=torch.float32, device=device)
    elevation_deg = _list_to_pt(elevation_deg, dtype=torch.float32, device=device)
    camera_distances = _list_to_pt(distance, dtype=torch.float32, device=device)
    elevation = elevation_deg * math.pi / 180
    azimuth = azimuth_deg * math.pi / 180
    camera_positions = torch.stack(
        [
            camera_distances * torch.cos(elevation) * torch.cos(azimuth),
            camera_distances * torch.cos(elevation) * torch.sin(azimuth),
            camera_distances * torch.sin(elevation),
        ],
        dim=-1,
    )
    center = torch.zeros_like(camera_positions)
    up = torch.tensor([0, 0, 1], dtype=torch.float32, device=device)[None, :].repeat(num_views, 1)
    lookat = F.normalize(center - camera_positions, dim=-1)
    right = F.normalize(torch.cross(lookat, up, dim=-1), dim=-1)
    up = F.normalize(torch.cross(right, lookat, dim=-1), dim=-1)
    c2w3x4 = torch.cat([torch.stack([right, up, -lookat], dim=-1), camera_positions[:, :, None]], dim=-1)
    c2w = torch.cat([c2w3x4, torch.zeros_like(c2w3x4[:, :1])], dim=1)
    c2w[:, 3, 3] = 1.0
    return c2w


class Camera:
    def __init__(self, c2w, w2c, proj_mtx, mvp_mtx, cam_pos):
        self.c2w = c2w
        self.w2c = w2c
        self.proj_mtx = proj_mtx
        self.mvp_mtx = mvp_mtx
        self.cam_pos = cam_pos


def get_orthogonal_projection_matrix(batch_size, left, right, bottom, top, near=0.1, far=100.0, device=None):
    projection_matrix = torch.zeros(batch_size, 4, 4, dtype=torch.float32, device=device)
    projection_matrix[:, 0, 0] = 2 / (right - left)
    projection_matrix[:, 1, 1] = -2 / (top - bottom)
    projection_matrix[:, 2, 2] = -2 / (far - near)
    projection_matrix[:, 0, 3] = -(right + left) / (right - left)
    projection_matrix[:, 1, 3] = -(top + bottom) / (top - bottom)
    projection_matrix[:, 2, 3] = -(far + near) / (far - near)
    projection_matrix[:, 3, 3] = 1
    return projection_matrix


def get_orthogonal_camera(elevation_deg, distance, left, right, bottom, top, azimuth_deg=None, num_views=1, device=None):
    c2w = get_c2w(elevation_deg, distance, azimuth_deg, num_views, device)
    camera_positions = c2w[:, :3, 3]
    w2c = torch.linalg.inv(c2w)
    proj_mtx = get_orthogonal_projection_matrix(c2w.shape[0], left, right, bottom, top, device=device)
    return Camera(c2w=c2w, w2c=w2c, proj_mtx=proj_mtx, mvp_mtx=proj_mtx @ w2c, cam_pos=camera_positions)


def get_opencv_from_blender(matrix_world):
    opencv_world_to_cam = matrix_world.inverse()
    opencv_world_to_cam[1, :] *= -1
    opencv_world_to_cam[2, :] *= -1
    return opencv_world_to_cam[:3, :3], opencv_world_to_cam[:3, 3]


def get_plucker_embeds_from_cameras_ortho(c2w, ortho_scale, image_size):
    embeds = []
    for cam_matrix, _scale in zip(c2w, ortho_scale):
        r_mat, t_vec = get_opencv_from_blender(cam_matrix)
        cam_pos = -r_mat.T @ t_vec
        view_dir = r_mat.T @ torch.tensor([0, 0, 1]).float().to(cam_matrix.device)
        cam_pos = F.normalize(cam_pos, dim=0)
        plucker = torch.concat([view_dir, cam_pos])
        plucker = plucker.unsqueeze(-1).unsqueeze(-1).repeat(1, image_size, image_size)
        embeds.append(plucker)
    return torch.stack(embeds)


def preprocess_image(image: Image.Image, height: int, width: int) -> Image.Image:
    import numpy as np

    if image.mode != "RGBA":
        image = image.convert("RGB")
        arr = np.array(image)
        h, w, _ = arr.shape
        alpha = np.ones((h, w), dtype=np.uint8) * 255
        image = Image.fromarray(np.dstack([arr, alpha]))
    image_np = np.array(image)
    alpha = image_np[..., 3] > 0
    ys, xs = (alpha.nonzero() if alpha.any() else (None, None))
    if ys is None:
        rgb = image.convert("RGB").resize((width, height))
        return rgb
    y0, y1 = max(int(ys.min()) - 1, 0), min(int(ys.max()) + 1, alpha.shape[0])
    x0, x1 = max(int(xs.min()) - 1, 0), min(int(xs.max()) + 1, alpha.shape[1])
    center = image_np[y0:y1, x0:x1]
    h, w, _ = center.shape
    if h > w:
        w = int(w * (height * 0.9) / h)
        h = int(height * 0.9)
    else:
        h = int(h * (width * 0.9) / w)
        w = int(width * 0.9)
    center = np.array(Image.fromarray(center).resize((w, h)))
    canvas = np.zeros((height, width, 4), dtype=np.uint8)
    start_h = (height - h) // 2
    start_w = (width - w) // 2
    canvas[start_h : start_h + h, start_w : start_w + w] = center
    canvas_f = canvas.astype("float32") / 255.0
    rgb = canvas_f[:, :, :3] * canvas_f[:, :, 3:4] + (1 - canvas_f[:, :, 3:4]) * 0.5
    return Image.fromarray((rgb * 255).clip(0, 255).astype("uint8"))


def assert_no_nvdiffrast() -> None:
    if "nvdiffrast" in sys.modules:
        raise RuntimeError("nvdiffrast was imported; 2D isolation failed")


def run(args: argparse.Namespace) -> dict:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available in the isolated MV-Adapter venv")
    device = torch.device("cuda:0")
    probe = torch.zeros(1, device=device)
    if probe.device.type != "cuda":
        raise RuntimeError("tensor did not land on CUDA")
    gpu_name = torch.cuda.get_device_name(0)
    if "5090" not in gpu_name and "RTX" not in gpu_name.upper():
        raise RuntimeError(f"unexpected GPU: {gpu_name}")

    runtime = Path(args.runtime_root)
    sys.path.insert(0, str(runtime))

    from diffusers import AutoencoderKL
    from mvadapter.pipelines.pipeline_mvadapter_i2mv_sdxl import MVAdapterI2MVSDXLPipeline
    from mvadapter.schedulers.scheduling_shift_snr import ShiftSNRScheduler

    assert_no_nvdiffrast()

    vae = AutoencoderKL.from_pretrained(args.vae, torch_dtype=torch.float16)
    pipe = MVAdapterI2MVSDXLPipeline.from_pretrained(
        args.base,
        vae=vae,
        variant="fp16",
        torch_dtype=torch.float16,
        local_files_only=True,
    )
    pipe.scheduler = ShiftSNRScheduler.from_scheduler(
        pipe.scheduler, shift_mode="interpolated", shift_scale=8.0
    )
    pipe.init_custom_adapter(num_views=len(AZIMUTHS))
    pipe.load_custom_adapter(args.adapter_dir, weight_name="mvadapter_i2mv_sdxl.safetensors")
    pipe.to(device=device, dtype=torch.float16)
    pipe.cond_encoder.to(device=device, dtype=torch.float16)
    if hasattr(pipe, "enable_vae_slicing"):
        pipe.enable_vae_slicing()
    assert_no_nvdiffrast()

    cameras = get_orthogonal_camera(
        elevation_deg=[0] * len(AZIMUTHS),
        distance=[1.8] * len(AZIMUTHS),
        left=-0.55,
        right=0.55,
        bottom=-0.55,
        top=0.55,
        azimuth_deg=[x - 90 for x in AZIMUTHS],
        device=device,
    )
    plucker = get_plucker_embeds_from_cameras_ortho(cameras.c2w, [1.1] * len(AZIMUTHS), args.size)
    control_images = ((plucker + 1.0) / 2.0).clamp(0, 1)

    front = Image.open(args.image).convert("RGB")
    reference = preprocess_image(front.convert("RGBA"), args.size, args.size)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    started = time.time()
    torch.cuda.reset_peak_memory_stats()
    images = pipe(
        args.text,
        height=args.size,
        width=args.size,
        num_inference_steps=args.steps,
        guidance_scale=args.guidance,
        num_images_per_prompt=len(AZIMUTHS),
        control_image=control_images,
        control_conditioning_scale=1.0,
        reference_image=reference,
        reference_conditioning_scale=1.0,
        negative_prompt=args.negative,
        generator=torch.Generator(device=device).manual_seed(args.seed),
    ).images
    duration = time.time() - started
    peak_vram = int(torch.cuda.max_memory_allocated())
    assert_no_nvdiffrast()

    outputs = []
    for azimuth, image in zip(AZIMUTHS, images):
        slot = SLOT_FOR_AZIMUTH[azimuth]
        path = out_dir / f"{run_id}_{azimuth:03d}_{slot}.png"
        image.save(path)
        outputs.append(
            {
                "azimuth": azimuth,
                "elevation": 0,
                "slot": slot,
                "path": str(path),
                "sha256": _sha256(path),
                "width": image.width,
                "height": image.height,
            }
        )

    evidence = {
        "runId": run_id,
        "engine": "mv_adapter",
        "inputFront": str(Path(args.image).resolve()),
        "inputFrontSha256": _sha256(Path(args.image)),
        "adapter": str(Path(args.adapter_dir) / "mvadapter_i2mv_sdxl.safetensors"),
        "adapterSha256": _sha256(Path(args.adapter_dir) / "mvadapter_i2mv_sdxl.safetensors"),
        "base": args.base,
        "vae": args.vae,
        "python": sys.executable,
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "gpu": gpu_name,
        "seed": args.seed,
        "steps": args.steps,
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "durationSec": round(duration, 2),
        "peakVramBytes": peak_vram,
        "exitCode": 0,
        "nvdiffrastImported": "nvdiffrast" in sys.modules,
        "outputs": outputs,
    }
    (out_dir / f"{run_id}_evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    reference.save(out_dir / f"{run_id}_reference.png")
    print(json.dumps(evidence, indent=2))
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--runtime-root", default=str(DEFAULT_RUNTIME))
    parser.add_argument("--adapter-dir", default=str(DEFAULT_MODELS))
    parser.add_argument("--base", default=str(DEFAULT_MODELS / "stable-diffusion-xl-base-1.0"))
    parser.add_argument("--vae", default=str(DEFAULT_MODELS / "sdxl-vae-fp16-fix"))
    parser.add_argument("--text", default="high quality")
    parser.add_argument("--negative", default="watermark, ugly, deformed, noisy, blurry, low contrast, collage, text")
    parser.add_argument("--seed", type=int, default=21)
    parser.add_argument("--steps", type=int, default=50)
    parser.add_argument("--guidance", type=float, default=3.0)
    parser.add_argument("--size", type=int, default=768)
    args = parser.parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
