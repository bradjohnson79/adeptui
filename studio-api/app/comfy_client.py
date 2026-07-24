from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from pathlib import Path
from typing import Any, Optional

import httpx

from .config import settings


class ComfyClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.comfy_url).rstrip("/")
        self.client_id = str(uuid.uuid4())
        self._object_info_cache: dict[str, Any] | None = None
        self._object_info_cached_at: float = 0.0

    async def health(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{self.base_url}/system_stats")
            r.raise_for_status()
            return r.json()

    async def object_info(self, node_class: str | None = None) -> dict[str, Any]:
        path = f"/object_info/{node_class}" if node_class else "/object_info"
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(f"{self.base_url}{path}")
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, dict) else {}

    async def get_object_info(self, *, force: bool = False, ttl_sec: float = 60.0) -> dict[str, Any]:
        """Fetch /object_info with a short in-memory cache."""
        import time

        now = time.monotonic()
        if (
            not force
            and self._object_info_cache is not None
            and (now - self._object_info_cached_at) < ttl_sec
        ):
            return self._object_info_cache
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.get(f"{self.base_url}/object_info")
            r.raise_for_status()
            data = r.json()
        self._object_info_cache = data
        self._object_info_cached_at = now
        return data

    async def _known_node_types(self) -> set[str] | None:
        """Live node type names, or None when the catalogue cannot be read."""
        try:
            catalogue = await self.get_object_info()
        except Exception:  # noqa: BLE001 - unknown must not be treated as invalid
            return None
        if not isinstance(catalogue, dict) or not catalogue:
            return None
        return {str(key) for key in catalogue}

    async def queue_prompt(self, workflow: dict[str, Any], *, validate: bool = True) -> str:
        """Submit a graph. Refuses graphs whose required node types are provably absent.

        Validation happens here so every producer is covered by one guard. It is skipped only
        when a caller explicitly opts out (`validate=False`), and it never blocks on missing
        evidence — an unreadable `/object_info` lets the submission through.
        """
        if validate:
            from .workflows.readiness import assert_graph_runnable

            assert_graph_runnable(workflow, await self._known_node_types())
        payload = {"prompt": workflow, "client_id": self.client_id}
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(f"{self.base_url}/prompt", json=payload)
            if r.status_code >= 400:
                detail = r.text
                raise RuntimeError(f"ComfyUI prompt rejected ({r.status_code}): {detail}")
            data = r.json()
            if "error" in data:
                raise RuntimeError(f"ComfyUI error: {data['error']}")
            return data["prompt_id"]

    async def get_history(self, prompt_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(f"{self.base_url}/history/{prompt_id}")
            r.raise_for_status()
            return r.json()

    async def get_queue(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(f"{self.base_url}/queue")
            r.raise_for_status()
            return r.json()

    async def interrupt(self) -> None:
        async with httpx.AsyncClient(timeout=15.0) as client:
            await client.post(f"{self.base_url}/interrupt")

    async def upload_image(self, src: Path, filename: str | None = None, subfolder: str = "studio") -> str:
        name = filename or src.name
        data = {"subfolder": subfolder, "type": "input", "overwrite": "true"}
        async with httpx.AsyncClient(timeout=120.0) as client:
            with src.open("rb") as f:
                files = {"image": (name, f, "application/octet-stream")}
                r = await client.post(f"{self.base_url}/upload/image", data=data, files=files)
                r.raise_for_status()
                result = r.json()
        # Prefer Comfy's returned name; include subfolder for LoadImage
        returned = result.get("name") or name
        folder = result.get("subfolder") or subfolder
        return f"{folder}/{returned}" if folder else returned

    async def upload_file_copy(self, src: Path, filename: str | None = None, subfolder: str = "studio") -> str:
        """Copy into Comfy input dir (audio/video friendly) and return relative path."""
        name = filename or src.name
        dest_dir = settings.comfy_input_dir / subfolder
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / name
        await asyncio.to_thread(shutil.copy2, src, dest)
        return f"{subfolder}/{name}"

    async def wait_for_prompt(
        self,
        prompt_id: str,
        timeout_sec: float | None = None,
        on_progress: Optional[Any] = None,
    ) -> dict[str, Any]:
        timeout = timeout_sec or settings.job_timeout_sec
        elapsed = 0.0
        while elapsed < timeout:
            history = await self.get_history(prompt_id)
            if prompt_id in history:
                entry = history[prompt_id]
                status = entry.get("status", {})
                if status.get("status_str") == "error" or status.get("completed") is False and status.get("messages"):
                    msgs = status.get("messages") or []
                    raise RuntimeError(f"ComfyUI job failed: {msgs}")
                if entry.get("outputs") is not None:
                    if on_progress:
                        await on_progress(1.0, "done")
                    return entry
            queue = await self.get_queue()
            running = queue.get("queue_running") or []
            pending = queue.get("queue_pending") or []
            in_running = any(item[1] == prompt_id for item in running if len(item) > 1)
            in_pending = any(item[1] == prompt_id for item in pending if len(item) > 1)
            if on_progress:
                if in_running:
                    await on_progress(0.55, "running in ComfyUI")
                elif in_pending:
                    await on_progress(0.2, "queued in ComfyUI")
            await asyncio.sleep(settings.poll_interval_sec)
            elapsed += settings.poll_interval_sec
        raise TimeoutError(f"Timed out waiting for ComfyUI prompt {prompt_id}")

    def find_output_files(self, history_entry: dict[str, Any]) -> list[Path]:
        outputs = history_entry.get("outputs") or {}
        found: list[Path] = []
        for node_out in outputs.values():
            for key in ("gifs", "videos", "images"):
                for item in node_out.get(key) or []:
                    filename = item.get("filename")
                    if not filename:
                        continue
                    sub = item.get("subfolder") or ""
                    folder = settings.comfy_output_dir / sub if sub else settings.comfy_output_dir
                    path = folder / filename
                    if path.exists():
                        found.append(path)
        return found


comfy = ComfyClient()
