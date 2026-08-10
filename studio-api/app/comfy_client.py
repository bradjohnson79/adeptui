from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

import httpx

from .config import settings

CancelCheck = Callable[[], bool]


class JobCancelledError(RuntimeError):
    """Raised when a Studio cancel request aborts a Comfy wait loop."""


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

    async def queue_prompt(
        self,
        workflow: dict[str, Any],
        *,
        validate: bool = True,
        workflow_key: str | None = None,
    ) -> str:
        """Submit a graph. Refuses graphs whose required node types are provably absent.

        When ``workflow_key`` is provided, also runs ``ensure_queueable`` (models + registry).
        """
        if validate:
            from .workflows.readiness import assert_graph_runnable

            known = await self._known_node_types()
            if workflow_key:
                from .video_runtime.preflight import ensure_local_queueable

                ensure_local_queueable(workflow_key, node_types=known)
            assert_graph_runnable(workflow, known)
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

    async def delete_queue_prompt(self, prompt_id: str) -> dict[str, Any]:
        """Remove a pending (and best-effort running) prompt from Comfy's queue."""
        payload = {"delete": [prompt_id]}
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(f"{self.base_url}/queue", json=payload)
            if r.status_code >= 400:
                return {"ok": False, "status": r.status_code, "body": r.text[:500]}
            try:
                return r.json() if r.content else {"ok": True}
            except Exception:  # noqa: BLE001
                return {"ok": True, "raw": r.text[:200]}

    async def prompt_queue_presence(self, prompt_id: str) -> dict[str, Any]:
        """Return whether prompt_id is in Comfy running or pending queues."""
        try:
            queue = await self.get_queue()
        except Exception as exc:  # noqa: BLE001
            return {
                "reachable": False,
                "running": False,
                "pending": False,
                "error": str(exc)[:200],
            }
        running = queue.get("queue_running") or []
        pending = queue.get("queue_pending") or []
        in_running = any(item[1] == prompt_id for item in running if len(item) > 1)
        in_pending = any(item[1] == prompt_id for item in pending if len(item) > 1)
        return {
            "reachable": True,
            "running": in_running,
            "pending": in_pending,
            "active": in_running or in_pending,
        }

    async def confirm_prompt_stopped(
        self,
        prompt_id: str,
        *,
        timeout_sec: float = 20.0,
        poll_sec: float = 0.4,
    ) -> dict[str, Any]:
        """Poll until prompt is absent from running+pending, or timeout."""
        elapsed = 0.0
        last: dict[str, Any] = {"reachable": False, "active": True}
        while elapsed <= timeout_sec:
            last = await self.prompt_queue_presence(prompt_id)
            if last.get("reachable") and not last.get("active"):
                return {
                    "confirmed": True,
                    "elapsedSec": round(elapsed, 2),
                    "presence": last,
                }
            await asyncio.sleep(poll_sec)
            elapsed += poll_sec
        return {
            "confirmed": False,
            "elapsedSec": round(elapsed, 2),
            "presence": last,
            "errorCode": "COMFY_CANCEL_NOT_CONFIRMED",
        }

    async def halt_prompt(
        self,
        prompt_id: str | None,
        *,
        confirm_timeout_sec: float = 20.0,
        request_free_memory: bool = True,
    ) -> dict[str, Any]:
        """Deep cancel: interrupt, delete pending, confirm stopped, optional free.

        Does **not** claim cancelled until the prompt is confirmed absent from
        Comfy running and pending queues (when a prompt_id is known).
        ``free_memory`` is requested but never treated as proof that all models
        unloaded or VRAM returned to idle.
        """
        result: dict[str, Any] = {
            "interrupt": False,
            "deleted": False,
            "freedRequested": False,
            "confirmedStopped": False,
            "errorCode": None,
        }
        try:
            await self.interrupt()
            result["interrupt"] = True
        except Exception as exc:  # noqa: BLE001
            result["interruptError"] = str(exc)[:200]

        if prompt_id:
            try:
                deleted = await self.delete_queue_prompt(prompt_id)
                result["deleted"] = bool(deleted.get("ok", True))
                result["deleteResponse"] = deleted
            except Exception as exc:  # noqa: BLE001
                result["deleteError"] = str(exc)[:200]

            # Re-issue interrupt after delete in case execution was mid-node.
            try:
                await self.interrupt()
                result["interrupt"] = True
            except Exception:  # noqa: BLE001
                pass

            confirmation = await self.confirm_prompt_stopped(
                prompt_id, timeout_sec=confirm_timeout_sec
            )
            result["confirmation"] = confirmation
            result["confirmedStopped"] = bool(confirmation.get("confirmed"))
            if not result["confirmedStopped"]:
                result["errorCode"] = "COMFY_CANCEL_NOT_CONFIRMED"
        else:
            # No prompt bound yet — interrupt is best-effort; treat as confirmed
            # for pre-submit cancel (nothing active to observe).
            result["confirmedStopped"] = True
            result["confirmation"] = {"confirmed": True, "reason": "no_prompt_id"}

        if request_free_memory:
            try:
                freed = await self.free_memory()
                result["freedRequested"] = True
                result["freeResponse"] = freed
                # Honesty: request ≠ all models unloaded / GPU idle.
                result["vramFullyReleased"] = False
                result["vramReleaseNote"] = (
                    "free_memory was requested; cached CUDA/models/encoders may remain. "
                    "Success is measured by prompt stop + job reservation release, not full unload."
                )
            except Exception as exc:  # noqa: BLE001
                result["freeError"] = str(exc)[:200]
        return result

    async def free_memory(self, *, unload_models: bool = True, free_memory: bool = True) -> dict[str, Any]:
        """Ask ComfyUI to unload models and free VRAM/RAM before heavy graphs (WAN CLIP)."""
        payload = {"unload_models": unload_models, "free_memory": free_memory}
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(f"{self.base_url}/free", json=payload)
            if r.status_code >= 400:
                return {"ok": False, "status": r.status_code, "body": r.text[:500]}
            try:
                return r.json() if r.content else {"ok": True}
            except Exception:  # noqa: BLE001
                return {"ok": True, "raw": r.text[:200]}

    async def upload_image(self, src: Path, filename: str | None = None, subfolder: str = "studio") -> str:
        name = filename or src.name
        data = {"subfolder": subfolder, "type": "input", "overwrite": "true"}
        async with httpx.AsyncClient(timeout=120.0) as client:
            with src.open("rb") as f:
                files = {"image": (name, f, "application/octet-stream")}
                r = await client.post(f"{self.base_url}/upload/image", data=data, files=files)
                r.raise_for_status()
                result = r.json()
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
        cancel_check: Optional[CancelCheck] = None,
    ) -> dict[str, Any]:
        """Poll history/queue until complete. Observes cancel_check every poll cycle."""
        from .video_runtime.progress import ProgressNormalizer

        timeout = timeout_sec or settings.job_timeout_sec
        elapsed = 0.0
        normalizer = ProgressNormalizer()
        while elapsed < timeout:
            if cancel_check and cancel_check():
                # Interrupt promptly; full confirm/transition is owned by JobQueue.cancel_and_halt.
                try:
                    await self.interrupt()
                    await self.delete_queue_prompt(prompt_id)
                except Exception:  # noqa: BLE001
                    pass
                raise JobCancelledError(
                    f"Cancel observed — waiting for confirmed ComfyUI stop of prompt {prompt_id}"
                )
            history = await self.get_history(prompt_id)
            if prompt_id in history:
                entry = history[prompt_id]
                status = entry.get("status", {})
                if status.get("status_str") == "error" or (
                    status.get("completed") is False and status.get("messages")
                ):
                    msgs = status.get("messages") or []
                    # Treat interrupt as cancellation when cancel was requested
                    joined = json.dumps(msgs).lower()
                    if cancel_check and cancel_check():
                        raise JobCancelledError(
                            f"Cancelled by user — ComfyUI prompt {prompt_id} halted"
                        )
                    # Honest cancel signal: execution_interrupted — not the word
                    # "interrupt" appearing inside stack frames (allow_interrupt=True).
                    interrupted = any(
                        isinstance(m, (list, tuple))
                        and len(m) >= 1
                        and str(m[0]).lower()
                        in {"execution_interrupted", "execution_cached_interrupted"}
                        for m in msgs
                    ) or (
                        "execution_interrupted" in joined
                        or '"interrupted": true' in joined
                        or "prompt interrupted" in joined
                    )
                    if interrupted:
                        raise JobCancelledError(
                            f"ComfyUI interrupted for prompt {prompt_id}"
                        )
                    # Surface the real exception_message when present
                    err_msg = None
                    for m in msgs:
                        if (
                            isinstance(m, (list, tuple))
                            and len(m) >= 2
                            and str(m[0]) == "execution_error"
                            and isinstance(m[1], dict)
                        ):
                            err_msg = m[1].get("exception_message") or m[1].get(
                                "exception_type"
                            )
                            break
                    raise RuntimeError(
                        f"ComfyUI job failed: {err_msg or msgs}"
                    )
                if status.get("completed") is True or status.get("status_str") == "success":
                    if cancel_check and cancel_check():
                        # Late completion after cancel — do not treat as success
                        raise JobCancelledError(
                            f"Cancelled by user — ignoring late ComfyUI completion for {prompt_id}"
                        )
                    if on_progress:
                        stage, p = normalizer.map_comfy_message("done", 1.0)
                        await normalizer.emit(
                            self._adapt_progress(on_progress),
                            progress=p,
                            message="done",
                            stage=stage,
                            force=True,
                        )
                    return entry
            queue = await self.get_queue()
            running = queue.get("queue_running") or []
            pending = queue.get("queue_pending") or []
            in_running = any(item[1] == prompt_id for item in running if len(item) > 1)
            in_pending = any(item[1] == prompt_id for item in pending if len(item) > 1)
            if on_progress:
                if in_running:
                    msg = "running in ComfyUI"
                    prog = 0.55
                elif in_pending:
                    msg = "queued in ComfyUI"
                    prog = 0.2
                else:
                    msg = "waiting for ComfyUI"
                    prog = 0.3
                stage, mapped = normalizer.map_comfy_message(msg, prog)
                await normalizer.emit(
                    self._adapt_progress(on_progress),
                    progress=mapped,
                    message=msg,
                    stage=stage,
                )
            # Best-effort WebSocket progress enrichment (non-blocking short attempt)
            await asyncio.sleep(settings.poll_interval_sec)
            elapsed += settings.poll_interval_sec
        raise TimeoutError(f"Timed out waiting for ComfyUI prompt {prompt_id}")

    @staticmethod
    def _adapt_progress(on_progress: Any) -> Any:
        """Support both legacy (p, msg) and new (p, msg, stage) callbacks."""

        async def _wrapped(progress: float, message: str, stage: str) -> None:
            try:
                result = on_progress(progress, message, stage)
            except TypeError:
                result = on_progress(progress, message)
            if hasattr(result, "__await__"):
                await result

        return _wrapped

    @staticmethod
    def _candidate_output_dirs() -> list[Path]:
        """Resolve possible Comfy output roots (Shared vs install dir divergence)."""
        primary = Path(settings.comfy_output_dir)
        dirs: list[Path] = [primary]
        # Comfy Desktop often writes to the install output while Studio is configured
        # for ComfyUI-Shared/output. Prefer finding the real file over failing closed.
        parent = primary.parent
        if parent.name.lower() == "comfyui-shared":
            alt = parent.parent / "ComfyUI-Installs" / "ComfyUI" / "ComfyUI" / "output"
            if alt.is_dir():
                dirs.append(alt)
        # Deduplicate while preserving order
        seen: set[str] = set()
        out: list[Path] = []
        for d in dirs:
            key = str(d.resolve()) if d.exists() else str(d)
            if key in seen:
                continue
            seen.add(key)
            out.append(d)
        return out

    def find_output_files(self, history_entry: dict[str, Any]) -> list[Path]:
        outputs = history_entry.get("outputs") or {}
        found: list[Path] = []
        roots = self._candidate_output_dirs()
        for node_out in outputs.values():
            for key in ("gifs", "videos", "images"):
                for item in node_out.get(key) or []:
                    full = item.get("fullpath")
                    if full:
                        full_path = Path(full)
                        if full_path.is_file():
                            found.append(full_path)
                            continue
                    filename = item.get("filename")
                    if not filename:
                        continue
                    sub = item.get("subfolder") or ""
                    for root in roots:
                        folder = root / sub if sub else root
                        path = folder / filename
                        if path.exists():
                            found.append(path)
                            break
            # PreviewAny / LatentSync often return absolute paths under "text".
            for item in node_out.get("text") or []:
                if not isinstance(item, str):
                    continue
                text_path = Path(item.strip().strip('"'))
                if text_path.is_file():
                    found.append(text_path)
        return found


comfy = ComfyClient()
