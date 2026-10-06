from __future__ import annotations

import asyncio
import json
import logging
import shutil
import uuid
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

import httpx

from .config import settings

CancelCheck = Callable[[], bool]

# Wave 3B stall watchdog reconciliation:
# Do not mark Timeline/Comfy jobs failed while Comfy still has the prompt in
# queue_running/pending. Cap "running without history" at the job wall clock
# (default 3600s) rather than an early 900s abort. Fail early only when the
# prompt has vanished from queue+history (gone) or Comfy reports failure/cancel.
RUNNING_WITHOUT_HISTORY_STALL_SEC = 3600.0
PROMPT_GONE_GRACE_SEC = 45.0


class JobCancelledError(RuntimeError):
    """Raised when a Studio cancel request aborts a Comfy wait loop."""


class ComfyClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.comfy_url).rstrip("/")
        self.client_id = str(uuid.uuid4())
        self._object_info_cache: dict[str, Any] | None = None
        self._object_info_cached_at: float = 0.0

    def _read_json(self, path: str, timeout: float) -> tuple[int | None, dict[str, Any]]:
        """One HTTP reader for Comfy GET probes. Callers do not open their own /system_stats."""
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.get(f"{self.base_url}{path}")
                try:
                    body = response.json()
                except Exception:
                    body = {}
                return response.status_code, body if isinstance(body, dict) else {}
        except Exception as exc:
            return None, {"error": type(exc).__name__}

    def read_system_stats(self, timeout: float = 3.0) -> tuple[int | None, dict[str, Any]]:
        """Authoritative /system_stats read. Boot and Comfy Manager both use this."""
        return self._read_json("/system_stats", timeout)

    def read_queue(self, timeout: float = 3.0) -> tuple[int | None, dict[str, Any]]:
        return self._read_json("/queue", timeout)

    def read_history(self, prompt_id: str | None = None, timeout: float = 2.0) -> tuple[int | None, dict[str, Any]]:
        path = "/history?max_items=1" if not prompt_id else f"/history/{prompt_id}"
        return self._read_json(path, timeout)

    async def health(self) -> dict[str, Any]:
        status, body = await asyncio.to_thread(self.read_system_stats, 5.0)
        if status != 200:
            detail = body.get("error") if isinstance(body, dict) else None
            raise RuntimeError(detail or f"ComfyUI /system_stats returned {status}")
        return body

    async def object_info(self, node_class: str | None = None) -> dict[str, Any]:
        path = f"/object_info/{node_class}" if node_class else "/object_info"
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(f"{self.base_url}{path}")
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, dict) else {}

    async def get_object_info(
        self,
        *,
        force: bool = False,
        ttl_sec: float = 60.0,
        timeout_sec: float = 60.0,
    ) -> dict[str, Any]:
        """Fetch /object_info with a short in-memory cache."""
        import time

        now = time.monotonic()
        if (
            not force
            and self._object_info_cache is not None
            and (now - self._object_info_cached_at) < ttl_sec
        ):
            return self._object_info_cache
        async with httpx.AsyncClient(timeout=float(timeout_sec)) as client:
            r = await client.get(f"{self.base_url}/object_info")
            r.raise_for_status()
            data = r.json()
        self._object_info_cache = data
        self._object_info_cached_at = now
        return data

    async def _known_node_types(self, *, timeout_sec: float = 60.0) -> set[str] | None:
        """Live node type names, or None when the catalogue cannot be read.

        Retry once. Unknown is not treated as ready when a workflow_key is bound
        (Stability Cull Batch 2).
        """
        last_error: Exception | None = None
        for _attempt in range(2):
            try:
                catalogue = await self.get_object_info(timeout_sec=timeout_sec)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                continue
            if isinstance(catalogue, dict) and catalogue:
                return {str(key) for key in catalogue}
        _ = last_error
        return None

    async def queue_prompt(
        self,
        workflow: dict[str, Any],
        *,
        validate: bool = True,
        workflow_key: str | None = None,
        timeout_sec: float = 60.0,
    ) -> str:
        """Submit a graph. Refuses graphs whose required node types are provably absent.

        When ``workflow_key`` is provided, also runs ``ensure_queueable`` (models + registry).
        ``timeout_sec`` covers catalogue fetch and POST /prompt. Heavy H3 graphs
        can exceed the 60s default after a Qwen Omni pre-review (VRAM settle).
        """
        if validate:
            from .workflows.readiness import assert_graph_runnable

            known = await self._known_node_types(timeout_sec=max(60.0, float(timeout_sec)))
            if workflow_key:
                if known is None:
                    from .capabilities.errors import CapabilityError

                    raise CapabilityError(
                        code="WORKFLOW_READINESS_UNKNOWN",
                        message=(
                            f"ComfyUI node catalogue is unavailable; refusing to treat "
                            f"{workflow_key} as ready."
                        ),
                        details={"workflowId": workflow_key},
                        recoverable=True,
                        recommended_action="start_comfyui",
                    )
                from .video_runtime.preflight import ensure_local_queueable

                ensure_local_queueable(workflow_key, node_types=known)
            assert_graph_runnable(workflow, known)
        payload = {"prompt": workflow, "client_id": self.client_id}
        async with httpx.AsyncClient(timeout=float(timeout_sec)) as client:
            r = await client.post(f"{self.base_url}/prompt", json=payload)
            if r.status_code >= 400:
                detail = r.text
                raise RuntimeError(f"ComfyUI prompt rejected ({r.status_code}): {detail}")
            data = r.json()
            if "error" in data:
                raise RuntimeError(f"ComfyUI error: {data['error']}")
            prompt_id = str(data.get("prompt_id") or "").strip()
            if not prompt_id:
                raise RuntimeError("ComfyUI accepted the graph but returned no prompt_id")
            return prompt_id

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
        if not prompt_id:
            # Isolate: this job never owned a Comfy prompt. Do not interrupt a
            # sibling in-flight graph (CRS law-view vs leftover coverage).
            result["confirmedStopped"] = True
            result["confirmation"] = {"confirmed": True, "reason": "no_prompt_id"}
            return result
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
        on_preview_frame: Optional[Any] = None,
    ) -> dict[str, Any]:
        """Poll history/queue until complete. Observes cancel_check every poll cycle.
        When on_preview_frame is provided, a WebSocket latent-preview tap publishes
        low-res frames during sampling. Preview failure never fails the render."""
        from .video_runtime.progress import ProgressNormalizer

        timeout = timeout_sec or settings.job_timeout_sec
        elapsed = 0.0
        normalizer = ProgressNormalizer()
        running_without_history_sec = 0.0
        prompt_gone_sec = 0.0
        # Wave 3B: long-running Comfy (H3 etc.) may stay queue_running without
        # history for >15m. Do not early-abort at 900s while Comfy still owns
        # the prompt — align stall cap with overall timeout / 3600s wall.
        stall_limit_sec = min(RUNNING_WITHOUT_HISTORY_STALL_SEC, float(timeout))

        # Optional live preview tap (Comfy WebSocket → low-res latent previews).
        preview_task: asyncio.Task | None = None
        if on_preview_frame is not None:
            try:
                from .video_runtime.live_preview import tap_comfy_previews

                preview_task = asyncio.create_task(
                    tap_comfy_previews(
                        self.base_url,
                        self.client_id,
                        prompt_id,
                        on_preview_frame,
                    )
                )
            except Exception:
                logging.getLogger(__name__).debug("Preview tap unavailable", exc_info=True)

        try:
            return await self._wait_for_prompt_poll(
                prompt_id,
                timeout=timeout,
                elapsed=elapsed,
                normalizer=normalizer,
                running_without_history_sec=running_without_history_sec,
                stall_limit_sec=stall_limit_sec,
                prompt_gone_sec=prompt_gone_sec,
                on_progress=on_progress,
                cancel_check=cancel_check,
            )
        finally:
            # CRITICAL: never block finalize on preview WS teardown.
            # A hung websockets close after Comfy success previously stranded
            # MiniMax H3 at writing_output/message=done/progress=0.96 with the
            # MP4 on disk but no studio ingest (job 98db381c).
            if preview_task is not None:
                if not preview_task.done():
                    preview_task.cancel()
                try:
                    await asyncio.wait_for(preview_task, timeout=2.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    pass
                except Exception:
                    logging.getLogger(__name__).debug(
                        "Preview tap cleanup ended", exc_info=True
                    )

    async def _listen_comfy_progress(
        self,
        prompt_id: str,
        live: dict[str, Any],
        stop: asyncio.Event,
    ) -> None:
        """Primary live progress authority: Comfy WS progress / progress_state / executing."""
        try:
            import websockets
        except Exception:
            logging.getLogger(__name__).debug(
                "websockets missing — poll-only progress", exc_info=True
            )
            return

        from .video_runtime.progress import (
            extract_progress_state_fraction,
            live_fraction_from_comfy,
        )

        ws_url = self.base_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/ws?clientId={self.client_id}"
        wanted = (prompt_id or "").strip()
        try:
            async with websockets.connect(
                ws_url, max_size=32 * 1024 * 1024, open_timeout=10
            ) as ws:
                while not stop.is_set():
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    except asyncio.TimeoutError:
                        continue
                    except Exception:
                        break
                    if isinstance(raw, (bytes, bytearray)):
                        continue
                    try:
                        msg = json.loads(raw)
                    except Exception:
                        continue
                    if not isinstance(msg, dict):
                        continue
                    mtype = str(msg.get("type") or "")
                    data = msg.get("data") if isinstance(msg.get("data"), dict) else {}
                    pid = str(data.get("prompt_id") or "").strip()
                    if wanted and pid and pid != wanted:
                        continue
                    now = asyncio.get_running_loop().time()
                    if mtype == "progress":
                        value = float(data.get("value") or 0)
                        mx = float(data.get("max") or 0) or 1.0
                        frac = live_fraction_from_comfy(value, mx)
                        # Multi-step sampler ticks own the bar. Single-tick node
                        # completions (max<=1) are phase-only — never a fake %.
                        live["node"] = data.get("node")
                        live["live"] = True
                        live["updated_at"] = now
                        live["comfy_value"] = value
                        live["comfy_max"] = mx
                        if mx > 1:
                            live["fraction"] = frac
                            live["message"] = f"Sampling step {int(value)}/{int(mx)}"
                            live["grounded"] = True
                        else:
                            live["message"] = f"Node progress {int(value)}/{int(mx)}"
                            live["grounded"] = bool(live.get("grounded"))
                    elif mtype == "progress_state":
                        extracted = extract_progress_state_fraction(data)
                        if extracted:
                            frac, label = extracted
                            mx_guess = 1.0
                            try:
                                if "/" in label:
                                    mx_guess = float(label.rsplit("/", 1)[-1].split()[0])
                            except Exception:
                                mx_guess = 1.0
                            live["message"] = label
                            live["live"] = True
                            live["updated_at"] = now
                            if mx_guess > 1:
                                live["fraction"] = frac
                                live["grounded"] = True
                            else:
                                live["grounded"] = bool(live.get("grounded"))
                    elif mtype == "executing":
                        node = data.get("node")
                        if node is None:
                            live["message"] = live.get("message") or "finalizing ComfyUI"
                            live["updated_at"] = now
                            return
                        live["node"] = node
                        live["message"] = f"Executing node {node}"
                        live["live"] = True
                        live["updated_at"] = now
                        # Node change is a real runtime event, not a percent.
                    elif mtype == "execution_error":
                        return
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.getLogger(__name__).debug("Comfy progress WS ended", exc_info=True)

    async def _wait_for_prompt_poll(
        self,
        prompt_id: str,
        *,
        timeout: float,
        elapsed: float,
        normalizer: Any,
        running_without_history_sec: float,
        stall_limit_sec: float,
        prompt_gone_sec: float = 0.0,
        on_progress: Optional[Any],
        cancel_check: Optional[CancelCheck],
    ) -> dict[str, Any]:
        live: dict[str, Any] = {
            "fraction": None,
            "message": None,
            "node": None,
            "live": False,
            "grounded": False,
            "updated_at": 0.0,
        }
        stop = asyncio.Event()
        ws_task = asyncio.create_task(self._listen_comfy_progress(prompt_id, live, stop))
        last_mapped = 0.0
        last_force_elapsed = -999.0
        try:
            while elapsed < timeout:
                if cancel_check and cancel_check():
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
                        joined = json.dumps(msgs).lower()
                        if cancel_check and cancel_check():
                            raise JobCancelledError(
                                f"Cancelled by user — ComfyUI prompt {prompt_id} halted"
                            )
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
                            raise JobCancelledError(
                                f"Cancelled by user — ignoring late ComfyUI completion for {prompt_id}"
                            )
                        if on_progress:
                            stage, p = normalizer.map_comfy_message("done", 1.0, live=True)
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
                if in_running or in_pending:
                    # Comfy still owns the job — keep Timeline in rendering.
                    prompt_gone_sec = 0.0
                    if in_running and prompt_id not in history:
                        running_without_history_sec += settings.poll_interval_sec
                        # Only trip if wall-aligned stall_limit elapses while still
                        # running without history (typically == overall timeout).
                        if running_without_history_sec >= stall_limit_sec:
                            raise TimeoutError(
                                f"ComfyUI stall: prompt {prompt_id} has been queue_running "
                                f"for {int(running_without_history_sec)}s with no history "
                                f"(stall_limit={int(stall_limit_sec)}s)."
                            )
                    else:
                        running_without_history_sec = 0.0
                elif prompt_id not in history:
                    # Proven gone: not running, not pending, no history yet.
                    running_without_history_sec = 0.0
                    prompt_gone_sec += settings.poll_interval_sec
                    if prompt_gone_sec >= PROMPT_GONE_GRACE_SEC:
                        raise TimeoutError(
                            f"ComfyUI prompt gone: {prompt_id} missing from queue and "
                            f"history for {int(prompt_gone_sec)}s (unrecoverable)."
                        )
                else:
                    running_without_history_sec = 0.0
                    prompt_gone_sec = 0.0
                if on_progress:
                    live_frac = live.get("fraction")
                    live_msg = live.get("message")
                    is_live = bool(live.get("live"))
                    is_grounded = bool(live.get("grounded")) and live_frac is not None
                    node = live.get("node")
                    if is_grounded:
                        msg = str(live_msg or "running in ComfyUI")
                        prog = float(live_frac)
                        stage, mapped = normalizer.map_comfy_message(msg, prog, live=True)
                    elif in_running:
                        msg = str(live_msg or "running in ComfyUI")
                        prog = last_mapped
                        stage, mapped = normalizer.map_comfy_message(msg, prog, live=False)
                    elif in_pending:
                        msg = "queued in ComfyUI"
                        prog = last_mapped
                        stage, mapped = normalizer.map_comfy_message(msg, prog, live=False)
                    else:
                        msg = str(live_msg or "waiting for ComfyUI")
                        prog = last_mapped
                        stage, mapped = normalizer.map_comfy_message(msg, prog, live=False)
                    # Heartbeat every ~3s while Comfy owns the prompt — message/updated_at
                    # only. Never invent a percent from elapsed time.
                    force = False
                    if in_running and (elapsed - last_force_elapsed) >= 3.0 and not is_grounded:
                        force = True
                        if live_msg:
                            msg = f"{live_msg} · still running ({int(elapsed)}s)"
                        else:
                            msg = f"running in ComfyUI · still running ({int(elapsed)}s)"
                        last_force_elapsed = elapsed
                    stage_token = getattr(stage, "value", stage)
                    if node is not None:
                        from .video_runtime.progress_telemetry import infer_creator_phase

                        phase = infer_creator_phase(message=msg, stage=str(stage_token), node=node)
                        stage_name = phase or stage_token
                    else:
                        stage_name = stage_token
                    emitted = await normalizer.emit(
                        self._adapt_progress(on_progress),
                        progress=mapped,
                        message=msg,
                        stage=stage_name,
                        force=force,
                    )
                    if emitted and is_grounded:
                        last_mapped = mapped
                await asyncio.sleep(settings.poll_interval_sec)
                elapsed += settings.poll_interval_sec
            raise TimeoutError(f"Timed out waiting for ComfyUI prompt {prompt_id}")
        finally:
            stop.set()
            if not ws_task.done():
                ws_task.cancel()
            try:
                await asyncio.wait_for(ws_task, timeout=2.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
            except Exception:
                logging.getLogger(__name__).debug(
                    "Comfy progress WS cleanup ended", exc_info=True
                )

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
