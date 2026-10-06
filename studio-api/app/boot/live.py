"""Read the running Adept stack and ask each existing owner for a dry check.

No process is started or stopped. Comfy is observed only.
"""

from __future__ import annotations

import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from .evaluate import BootFacts, evaluate

_HISTORY = Path(__file__).resolve().parents[3] / "data" / "boot" / "startup-history.json"
_CONTRACT_TTL_SEC = 45.0
_CONTRACT_FIELDS = (
    "codirector_tools",
    "codirector_unknown_closed",
    "codirector_error",
    "image_local",
    "image_hosted",
    "image_error",
    "storyboard_aspect",
    "storyboard_error",
    "h3_width",
    "h3_height",
    "h3_legal",
    "h3_base_optimized",
    "h3_reference_to_video",
    "h3_max_images",
    "h3_place_role",
    "timeline_error",
    "magi_2k_width",
    "magi_2k_height",
    "magi_2k_class",
    "magi_error",
    "library_ok",
    "library_error",
    "script_ok",
    "script_error",
    "voice_ok",
    "voice_error",
    "setup_components",
    "setup_error",
)
_contract_cache: tuple[float, dict[str, Any], dict[str, int]] | None = None


def _http(url: str, timeout: float = 3.0) -> tuple[int | None, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return int(resp.status), resp.read(8000).decode("utf-8", "replace")
    except Exception:
        return None, ""


def _commands(pids: list[int]) -> dict[int, str]:
    from runtime_supervisor.process import process_command_line

    out: dict[int, str] = {}
    for pid in pids:
        try:
            out[pid] = process_command_line(pid)
        except Exception:
            out[pid] = ""
    return out


def collect_facts(*, force: bool = False) -> tuple[BootFacts, dict[str, int]]:
    from runtime_supervisor.control_client import control_plane_reachable
    from runtime_supervisor.ports import listening_pids

    started = time.perf_counter()
    facts = BootFacts()
    durations: dict[str, int] = {}

    def mark(key: str, begin: float) -> None:
        durations[key] = int((time.perf_counter() - begin) * 1000)

    def runtime() -> None:
        begin = time.perf_counter()
        # A healthy status call already takes about 1.5s. Keep enough room
        # that a live manager is not recorded as unreachable.
        facts.supervisor_reachable = bool(control_plane_reachable(timeout=8.0))
        facts.api_pids = listening_pids(8758)
        facts.api_commands = _commands(facts.api_pids)
        facts.api_health_status, _body = _http("http://127.0.0.1:8758/api/healthz")
        facts.vite_pids = listening_pids(5173)
        facts.vite_commands = _commands(facts.vite_pids)
        facts.vite_status, facts.vite_body = _http("http://127.0.0.1:5173/")
        # Same owner as Comfy Manager. Observe only — never restart Comfy.
        from ..comfy_health import authoritative_comfy_health

        comfy_health_report = authoritative_comfy_health(timeout_sec=2.0)
        facts.comfy_pids = list(comfy_health_report.get("pids") or [])
        facts.comfy_healthy = bool(comfy_health_report.get("healthy"))
        mark("supervisor", begin)
        mark("studio_api_process", begin)
        mark("studio_api_owner", begin)
        mark("studio_api_health", begin)
        mark("duplicate_api", begin)
        mark("vite_process", begin)
        mark("vite_health", begin)
        mark("duplicate_vite", begin)
        mark("comfy", begin)

    def codirector() -> None:
        begin = time.perf_counter()
        try:
            from ..codirector.tools.registry import all_definitions, find

            facts.codirector_tools = len(all_definitions())
            facts.codirector_unknown_closed = find("boot-certification-unknown-tool") is None
        except Exception as exc:
            facts.codirector_error = str(exc)
        mark("codirector", begin)

    def images() -> None:
        begin = time.perf_counter()
        try:
            from ..production_control.model_registry import list_models

            local = [model for model in list_models("image") if str(getattr(model, "locality", "") or "") == "local"]
            facts.image_local = len(local)
        except Exception as exc:
            facts.image_error = str(exc)
        mark("image_generator", begin)
        begin_hosted = time.perf_counter()

        def hosted() -> None:
            from ..hosted_providers.discovery import dock_api_models

            payload = dock_api_models("image") or {}
            facts.image_hosted = len(payload.get("models") or [])

        try:
            with ThreadPoolExecutor(max_workers=1) as hosted_pool:
                hosted_pool.submit(hosted).result(timeout=2.0)
        except Exception:
            facts.image_hosted = None
        mark("image_hosted", begin_hosted)

    def storyboard() -> None:
        begin = time.perf_counter()
        try:
            from ..storyboard_studio.aspect import normalize_storyboard_aspect

            facts.storyboard_aspect = normalize_storyboard_aspect("16:9")
        except Exception as exc:
            facts.storyboard_error = str(exc)
        mark("storyboard", begin)

    def timeline() -> None:
        begin = time.perf_counter()
        try:
            from ..director_timeline_w46.generation.adapters.minimax_h3_base_optimized import (
                MiniMaxH3BaseOptimizedAdapter,
            )
            from ..film_timeline.references import generation_role
            from ..video_runtime.legal_canvas import check_h3_resolution

            checked = check_h3_resolution(1376, 768)
            facts.h3_legal = bool(checked.ok)
            facts.h3_width = 1376
            facts.h3_height = 768
            caps = MiniMaxH3BaseOptimizedAdapter().capabilities
            facts.h3_base_optimized = str(getattr(caps, "id", "") or "") == "minimax-h3-base-optimized"
            facts.h3_reference_to_video = bool(getattr(caps, "supportsReferenceToVideo", False))
            facts.h3_max_images = int(getattr(caps, "maximumReferenceImages", 0) or 0)
            facts.h3_place_role = generation_role("environment")
        except Exception as exc:
            facts.timeline_error = str(exc)
        mark("timeline", begin)

    def magi() -> None:
        begin = time.perf_counter()
        try:
            from ..magi.upscale_targets import resolve_apply_target

            width, height, label = resolve_apply_target(1376, 768, "2K")
            facts.magi_2k_width = int(width)
            facts.magi_2k_height = int(height)
            facts.magi_2k_class = str(label)
        except Exception as exc:
            facts.magi_error = str(exc)
        mark("magi", begin)

    def library() -> None:
        begin = time.perf_counter()
        try:
            from ..project_library.service import get_library_response

            facts.library_ok = callable(get_library_response)
        except Exception as exc:
            facts.library_error = str(exc)
        mark("library", begin)

    def script() -> None:
        begin = time.perf_counter()
        try:
            from ..scriptwriter.api import router

            facts.script_ok = router is not None
        except Exception as exc:
            facts.script_error = str(exc)
        mark("script_writer", begin)

    def voice() -> None:
        begin = time.perf_counter()
        try:
            from ..voice_performance.router import router

            facts.voice_ok = bool(getattr(router, "routes", None))
        except Exception as exc:
            facts.voice_error = str(exc)
        mark("voice", begin)

    def setup() -> None:
        begin = time.perf_counter()
        try:
            from ..setup.lifecycle.service import search_components

            payload = search_components("")
            facts.setup_components = len(payload.get("items") or [])
        except Exception as exc:
            facts.setup_error = str(exc)
        mark("setup", begin)

    global _contract_cache
    cached = _contract_cache
    use_cache = (
        not force
        and cached is not None
        and (time.time() - cached[0]) < _CONTRACT_TTL_SEC
    )
    if use_cache and cached is not None:
        runtime()
        for name, value in cached[1].items():
            setattr(facts, name, value)
        durations.update(cached[2])
    else:
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda fn: fn(), (runtime, codirector, images, storyboard, timeline, magi, library, script, voice, setup)))
        _contract_cache = (
            time.time(),
            {name: getattr(facts, name) for name in _CONTRACT_FIELDS},
            {key: value for key, value in durations.items() if key not in {"supervisor", "studio_api_process", "studio_api_owner", "studio_api_health", "duplicate_api", "vite_process", "vite_health", "duplicate_vite", "comfy"}},
        )
    durations["total"] = int((time.perf_counter() - started) * 1000)
    return facts, durations


def _remember(report: dict[str, Any]) -> None:
    try:
        _HISTORY.parent.mkdir(parents=True, exist_ok=True)
        prior: list[Any] = []
        if _HISTORY.is_file():
            loaded = json.loads(_HISTORY.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                prior = loaded
        prior.append(
            {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "verdict": report.get("verdict"),
                "durationMs": report.get("durationMs"),
                "failed": report.get("failed") or [],
            }
        )
        _HISTORY.write_text(json.dumps(prior[-12:], indent=2), encoding="utf-8")
    except Exception:
        return


def run_certification(*, force: bool = False) -> dict[str, Any]:
    facts, durations = collect_facts(force=force)
    report = evaluate(facts, durations=durations)
    report["durationMs"] = durations.get("total", 0)
    report["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    report["comfyRestarted"] = False
    _remember(report)
    return report
