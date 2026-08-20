"""Isolated V-JEPA world intelligence worker. Embedding comparisons only.

Usage:
  python worker.py --mode compare --image-a path.jpg --image-b path.jpg --out path.json
  python worker.py --mode encode --image path.jpg --out path.json
  python worker.py --mode health
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Optional


def _emit(payload: dict) -> None:
    # Progress must not share stdout with the final JSON result.
    print(json.dumps(payload), file=sys.stderr, flush=True)


def _refuse_cpu_only() -> None:
    try:
        import torch
        if not torch.cuda.is_available():
            _emit({"ok": False, "error": "CPU_ONLY_TORCH"})
            raise SystemExit(2)
    except SystemExit:
        raise
    except Exception as exc:
        _emit({"ok": False, "error": f"TORCH_UNAVAILABLE:{exc}"})
        raise SystemExit(2)


def _vram_used_gb() -> Optional[float]:
    try:
        import torch
        if not torch.cuda.is_available():
            return None
        free, total = torch.cuda.mem_get_info(0)
        return round((total - free) / (1024**3), 3)
    except Exception:
        return None


def _load_model(model_path: str):
    """Load V-JEPA 2 model from transformers."""
    import torch
    from transformers import VJEPA2Model, VJEPA2VideoProcessor

    _emit({"phase": "load", "modelPath": model_path})
    device = torch.device("cuda:0")
    
    model = VJEPA2Model.from_pretrained(
        model_path,
        torch_dtype=torch.float16,
        device_map={"": 0},
        trust_remote_code=True,
    )
    model.eval()
    
    from transformers import VJEPA2VideoProcessor
    processor = VJEPA2VideoProcessor.from_pretrained(
        model_path,
        trust_remote_code=True,
    )
    
    return model, processor, device


def _encode_image(
    image_path: str,
    model: Any,
    processor: Any,
    device: Any,
) -> dict:
    """Encode a single image and return embedding info."""
    import torch
    from PIL import Image
    
    image = Image.open(image_path).convert("RGB")
    inputs = processor(videos=[image], return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}
    
    with torch.no_grad():
        outputs = model(**inputs)
    
    # Use pooled output or mean-pool patch outputs
    if hasattr(outputs, "pooler_output") and outputs.pooler_output is not None:
        embedding = outputs.pooler_output
    elif hasattr(outputs, "last_hidden_state"):
        embedding = outputs.last_hidden_state.mean(dim=1)
    else:
        # Fallback: use the first output tensor
        for key in ("image_embeds", "embeddings", "hidden_states"):
            if hasattr(outputs, key):
                tensor = getattr(outputs, key)
                if isinstance(tensor, torch.Tensor):
                    if tensor.dim() > 2:
                        embedding = tensor.mean(dim=tuple(range(2, tensor.dim())))
                    else:
                        embedding = tensor
                    break
        else:
            raise RuntimeError("Could not extract embedding from model output")
    
    flat = embedding.reshape(-1).cpu().float()
    return {
        "ok": True,
        "embedding": flat.numpy().tolist(),
        "embeddingDim": int(flat.numel()),
        "device": str(device),
    }


def _compare_images(
    image_a: str,
    image_b: str,
    model_path: str,
) -> dict:
    """Compare two images and produce world-state similarity."""
    import torch
    import numpy as np
    
    t0 = time.time()
    model, processor, device = _load_model(model_path)
    load_time = time.time() - t0
    
    vram_before = _vram_used_gb()
    
    result_a = _encode_image(image_a, model, processor, device)
    result_b = _encode_image(image_b, model, processor, device)
    
    emb_a = torch.tensor(result_a["embedding"])
    emb_b = torch.tensor(result_b["embedding"])
    
    # Cosine similarity
    similarity = float(torch.nn.functional.cosine_similarity(emb_a.unsqueeze(0), emb_b.unsqueeze(0)).item())
    
    # L2 distance
    l2_distance = float(torch.dist(emb_a, emb_b, p=2).item())
    
    # Anomaly score: 1 - similarity (higher = more anomalous)
    anomaly = round(1.0 - similarity, 6)
    
    vram_peak = _vram_used_gb()
    
    # Clean up
    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    
    return {
        "ok": True,
        "mode": "live",
        "modelId": Path(model_path).name,
        "similarity": round(similarity, 6),
        "l2Distance": round(l2_distance, 6),
        "anomalyScore": max(0.0, anomaly),
        "embeddingDim": result_a["embeddingDim"],
        "loadTimeSec": round(load_time, 3),
        "inferTimeSec": round(time.time() - t0 - load_time, 3),
        "totalTimeSec": round(time.time() - t0, 3),
        "vramBeforeGb": vram_before,
        "vramPeakGb": vram_peak,
        "device": result_a["device"],
        "imageA": image_a,
        "imageB": image_b,
        "embeddingA": result_a["embedding"],
        "embeddingB": result_b["embedding"],
    }


def _encode_single(image_path: str, model_path: str) -> dict:
    """Encode a single image and return embedding."""
    import torch
    
    t0 = time.time()
    model, processor, device = _load_model(model_path)
    load_time = time.time() - t0
    
    result = _encode_image(image_path, model, processor, device)
    
    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    
    result["loadTimeSec"] = round(load_time, 3)
    result["totalTimeSec"] = round(time.time() - t0, 3)
    result["vramGb"] = _vram_used_gb()
    return result


def _health() -> dict:
    """Health check for the worker process."""
    try:
        import torch
    except Exception as exc:
        return {"ok": False, "error": f"TORCH_IMPORT_FAILED:{exc}"}
    
    if not torch.cuda.is_available():
        return {"ok": False, "error": "CPU_ONLY_TORCH"}
    
    try:
        from transformers import VJEPA2Model, VJEPA2VideoProcessor
        return {
            "ok": True,
            "cuda": True,
            "device": str(torch.cuda.get_device_name(0)),
            "vramGb": _vram_used_gb(),
            "modelAvailable": True,
        }
    except ImportError as exc:
        return {"ok": False, "error": f"VJEPA2_NOT_IN_TRANSFORMERS:{exc}"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=["compare", "encode", "health"])
    ap.add_argument("--image-a", default="")
    ap.add_argument("--image-b", default="")
    ap.add_argument("--image", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--model-path", default="")
    ap.add_argument("--model-id", default="vjepa2-vitl-fpc64-256")
    
    args = ap.parse_args()
    
    _refuse_cpu_only()
    
    if args.mode == "health":
        result = _health()
        print(json.dumps(result))
        return 0 if result.get("ok") else 1
    
    model_path = args.model_path or args.model_id
    
    if args.mode == "compare":
        if not args.image_a or not args.image_b:
            print(json.dumps({"ok": False, "error": "IMAGE_A_AND_B_REQUIRED"}))
            return 1
        result = _compare_images(args.image_a, args.image_b, model_path)
    elif args.mode == "encode":
        if not args.image:
            print(json.dumps({"ok": False, "error": "IMAGE_REQUIRED"}))
            return 1
        result = _encode_single(args.image, model_path)
    else:
        print(json.dumps({"ok": False, "error": f"UNKNOWN_MODE:{args.mode}"}))
        return 1
    
    print(json.dumps(result))
    
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
