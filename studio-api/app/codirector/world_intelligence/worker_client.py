"""Spawn the isolated V-JEPA world intelligence worker. Never upload imagery."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

from .cache import compute_content_hash, get_cached_embedding, set_cached_embedding
from .compare import build_world_state_packet
from .contracts import (
    WORLD_INTELLIGENCE_MODEL_ID,
    EmbeddingReference,
    WorldStatePacket,
    WorldStateSource,
)
from .paths import (
    VJEPA2_MARKERS,
    VJEPA2_21_MARKERS,
    vjepa2_dir,
    vjepa2_21_dir,
    model_present,
    worker_python,
)


_STUB_MODES = ("stub", "1", "true", "yes")
_FORCE_FAIL_MODES = ("fail", "error")
_CUDA_TTL_SEC = 900.0
_CUDA_DISK_TTL_SEC = 24 * 3600.0
_cuda_probe_cache: tuple[float, dict] | None = None
_cuda_probe_thread_started = False


def _parse_worker_json(stdout: str) -> dict:
    """Accept a single JSON object, or the last JSON line if progress leaked."""
    text = (stdout or "").strip()
    if not text:
        raise json.JSONDecodeError("empty worker stdout", text, 0)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    raise json.JSONDecodeError("no JSON object in worker stdout", text, 0)


def stub_allowed() -> bool:
    if (os.environ.get("ADEPT_ALLOW_WORLD_STUB") or "").strip().lower() in ("1", "true", "yes"):
        return True
    return bool((os.environ.get("PYTEST_CURRENT_TEST") or "").strip())


def perception_mode() -> str:
    return (os.environ.get("ADEPT_WORLD_PERCEPTION_MODE") or "live").strip().lower()


def _select_model() -> tuple[Path, str, str]:
    """Select best available model. Prefers V-JEPA 2.1, falls back to V-JEPA 2."""
    if model_present(vjepa2_21_dir(), VJEPA2_21_MARKERS):
        return vjepa2_21_dir(), "vjepa2.1-vitl-384", VJEPA2_21_MARKERS
    if model_present(vjepa2_dir(), VJEPA2_MARKERS):
        return vjepa2_dir(), WORLD_INTELLIGENCE_MODEL_ID, VJEPA2_MARKERS
    raise RuntimeError("MODEL_NOT_INSTALLED")


def compare_images(
    image_a_path: str,
    image_b_path: str,
    *,
    asset_id_a: Optional[str] = None,
    asset_id_b: Optional[str] = None,
    project_id: str = "",
    use_cache: bool = True,
    timeout_sec: float = 300.0,
) -> WorldStatePacket:
    """Compare two images and return a world-state packet."""
    mode = perception_mode()
    model_dir, model_id, _ = _select_model()

    # Check cache if enabled
    if use_cache and asset_id_a and asset_id_b:
        hash_a = compute_content_hash(image_a_path)
        hash_b = compute_content_hash(image_b_path)
        cached_a = get_cached_embedding(
            asset_id_a, hash_a, model_id, "latest", "v1", project_id=project_id
        )
        cached_b = get_cached_embedding(
            asset_id_b, hash_b, model_id, "latest", "v1", project_id=project_id
        )
        if cached_a and cached_b:
            # Reconstruct packet from cached embeddings
            emb_a = cached_a["embedding"]
            emb_b = cached_b["embedding"]
            import math

            def _cosine_sim(a, b):
                dot = sum(x * y for x, y in zip(a, b))
                na = math.sqrt(sum(x * x for x in a))
                nb = math.sqrt(sum(y * y for y in b))
                return dot / (na * nb) if na * nb > 0 else 0.0

            similarity = _cosine_sim(emb_a, emb_b)
            return build_world_state_packet(
                source_asset_id=asset_id_b,
                reference_asset_ids=[asset_id_a],
                similarity=similarity,
                anomaly_score=1.0 - similarity,
                model_id=model_id,
                model_revision="latest",
                latency_ms=0,
            )

    # Run inference
    worker = Path(__file__).with_name("worker.py")
    cmd = [
        str(worker_python()),
        str(worker),
        "--mode", "compare",
        "--image-a", image_a_path,
        "--image-b", image_b_path,
        "--model-path", str(model_dir),
        "--model-id", model_id,
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired:
        return WorldStatePacket(
            availability="unavailable",
            reason="PERCEPTION_TIMEOUT",
            source=WorldStateSource(modelId=model_id, projectId=project_id),
        )

    if proc.returncode != 0:
        return WorldStatePacket(
            availability="unavailable",
            reason=f"WORKER_FAILED:{proc.stderr[:200] if proc.stderr else 'unknown'}",
            source=WorldStateSource(modelId=model_id, projectId=project_id),
        )

    try:
        data = _parse_worker_json(proc.stdout)
    except json.JSONDecodeError:
        return WorldStatePacket(
            availability="unavailable",
            reason="INVALID_WORKER_OUTPUT",
            source=WorldStateSource(modelId=model_id, projectId=project_id),
        )

    if not data.get("ok"):
        return WorldStatePacket(
            availability="unavailable",
            reason=data.get("error", "WORKER_FAILED"),
            source=WorldStateSource(modelId=model_id, projectId=project_id),
        )

    if use_cache and asset_id_a and asset_id_b:
        emb_a = data.get("embeddingA")
        emb_b = data.get("embeddingB")
        if isinstance(emb_a, list) and isinstance(emb_b, list):
            hash_a = compute_content_hash(image_a_path)
            hash_b = compute_content_hash(image_b_path)
            set_cached_embedding(
                asset_id=asset_id_a,
                content_hash=hash_a,
                model_id=model_id,
                model_revision="latest",
                preprocess_version="v1",
                embedding=emb_a,
                project_id=project_id,
            )
            set_cached_embedding(
                asset_id=asset_id_b,
                content_hash=hash_b,
                model_id=model_id,
                model_revision="latest",
                preprocess_version="v1",
                embedding=emb_b,
                project_id=project_id,
            )

    packet = build_world_state_packet(
        source_asset_id=asset_id_b,
        reference_asset_ids=[asset_id_a] if asset_id_a else [],
        similarity=data.get("similarity"),
        anomaly_score=data.get("anomalyScore"),
        model_id=model_id,
        model_revision="latest",
        latency_ms=round(data.get("totalTimeSec", 0) * 1000),
    )

    return packet


def encode_image(
    image_path: str,
    *,
    asset_id: Optional[str] = None,
    project_id: str = "",
    use_cache: bool = True,
    timeout_sec: float = 300.0,
) -> tuple[Optional[list[float]], Optional[str]]:
    """Encode a single image and return (embedding, cache_key)."""
    mode = perception_mode()
    model_dir, model_id, _ = _select_model()

    # Check cache
    if use_cache and asset_id:
        content_hash = compute_content_hash(image_path)
        cached = get_cached_embedding(asset_id, content_hash, model_id, "latest", "v1", project_id=project_id)
        if cached:
            return cached["embedding"], cached["cacheKey"]

    worker = Path(__file__).with_name("worker.py")
    cmd = [
        str(worker_python()),
        str(worker),
        "--mode", "encode",
        "--image", image_path,
        "--model-path", str(model_dir),
        "--model-id", model_id,
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired:
        return None, None

    if proc.returncode != 0:
        return None, None

    try:
        data = _parse_worker_json(proc.stdout)
    except json.JSONDecodeError:
        return None, None

    if not data.get("ok"):
        return None, None

    embedding = data.get("embedding")
    if not embedding:
        return None, None

    # Cache
    cache_key = None
    if use_cache and asset_id:
        content_hash = compute_content_hash(image_path)
        cache_key = set_cached_embedding(
            asset_id=asset_id,
            content_hash=content_hash,
            model_id=model_id,
            model_revision="latest",
            preprocess_version="v1",
            embedding=embedding,
            project_id=project_id,
        )

    return embedding, cache_key


def _disk_probe_path() -> Path:
    from .paths import world_intelligence_root

    return world_intelligence_root() / ".cuda-probe.json"


def _load_disk_probe() -> dict | None:
    path = _disk_probe_path()
    if not path.is_file():
        return None
    try:
        age = time.time() - path.stat().st_mtime
        if age > _CUDA_DISK_TTL_SEC:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict) or "ok" not in data:
        return None
    return {"ok": bool(data.get("ok")), "reason": data.get("reason")}


def _save_disk_probe(result: dict) -> None:
    path = _disk_probe_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"ok": bool(result.get("ok")), "reason": result.get("reason")}), encoding="utf-8")
    except Exception:
        return


def cached_cuda_probe(*, force: bool = False) -> dict | None:
    """Return the last CUDA probe without spawning a process."""
    global _cuda_probe_cache
    if _cuda_probe_cache is not None:
        return dict(_cuda_probe_cache[1])
    disk = _load_disk_probe()
    if disk is not None:
        _cuda_probe_cache = (time.monotonic(), disk)
        return dict(disk)
    return None


def schedule_cuda_probe() -> None:
    """Refresh CUDA readiness off the request thread. Never blocks callers."""
    global _cuda_probe_thread_started
    cached = cached_cuda_probe()
    if cached is not None and _cuda_probe_cache and time.monotonic() - _cuda_probe_cache[0] < _CUDA_TTL_SEC:
        return
    if _cuda_probe_thread_started:
        return
    _cuda_probe_thread_started = True

    def _run() -> None:
        global _cuda_probe_thread_started
        try:
            _probe_worker_cuda(force=True)
        finally:
            _cuda_probe_thread_started = False

    import threading

    threading.Thread(target=_run, name="world-intel-cuda-probe", daemon=True).start()


def _probe_worker_cuda(*, force: bool = False) -> dict:
    """Ask the isolated worker interpreter whether CUDA torch is present. No model load."""
    global _cuda_probe_cache
    now = time.monotonic()
    if not force:
        cached = cached_cuda_probe()
        if cached is not None and _cuda_probe_cache and now - _cuda_probe_cache[0] < _CUDA_TTL_SEC:
            return dict(cached)
    py = worker_python()
    if not Path(py).is_file():
        result = {"ok": False, "reason": "WORKER_PYTHON_MISSING"}
        _cuda_probe_cache = (now, result)
        _save_disk_probe(result)
        return dict(result)
    try:
        proc = subprocess.run(
            [str(py), "-c", "import torch; print('1' if torch.cuda.is_available() else '0')"],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except Exception as exc:
        result = {"ok": False, "reason": f"CUDA_PROBE_FAILED:{exc}"[:80]}
        _cuda_probe_cache = (now, result)
        _save_disk_probe(result)
        return dict(result)
    if proc.returncode != 0:
        result = {"ok": False, "reason": (proc.stderr or "TORCH_UNAVAILABLE")[:80]}
        _cuda_probe_cache = (now, result)
        _save_disk_probe(result)
        return dict(result)
    if (proc.stdout or "").strip() != "1":
        result = {"ok": False, "reason": "CPU_ONLY_TORCH"}
        _cuda_probe_cache = (now, result)
        _save_disk_probe(result)
        return dict(result)
    result = {"ok": True}
    _cuda_probe_cache = (now, result)
    _save_disk_probe(result)
    return dict(result)


def health() -> dict:
    """Live-ready only when weights exist AND the worker python has CUDA torch."""
    try:
        _, model_id, _ = _select_model()
    except RuntimeError:
        return {"ok": False, "installed": False, "reason": "MODEL_NOT_INSTALLED"}
    cuda = _probe_worker_cuda()
    return {
        "ok": bool(cuda.get("ok")),
        "installed": True,
        "modelId": model_id,
        "cuda": cuda,
        "reason": None if cuda.get("ok") else cuda.get("reason", "CPU_ONLY_TORCH"),
    }
