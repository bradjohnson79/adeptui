"""Boot certification verdict. Evidence in, one GO or NO-GO out.

This does not start processes, load model weights, or write project data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BootFacts:
    supervisor_reachable: bool = False
    supervisor_port: int = 8759
    api_pids: list[int] = field(default_factory=list)
    api_commands: dict[int, str] = field(default_factory=dict)
    api_health_status: int | None = None
    api_port: int = 8758
    runtime_mode: str = "web-development"
    vite_pids: list[int] = field(default_factory=list)
    vite_commands: dict[int, str] = field(default_factory=dict)
    vite_status: int | None = None
    vite_body: str = ""
    comfy_healthy: bool = False
    comfy_pids: list[int] = field(default_factory=list)
    codirector_tools: int = 0
    codirector_unknown_closed: bool = False
    codirector_error: str = ""
    image_local: int = 0
    image_hosted: int | None = None
    image_error: str = ""
    storyboard_aspect: str = ""
    storyboard_error: str = ""
    h3_width: int = 0
    h3_height: int = 0
    h3_legal: bool = False
    h3_base_optimized: bool = False
    h3_reference_to_video: bool = False
    h3_max_images: int = 0
    h3_place_role: str = ""
    timeline_error: str = ""
    magi_2k_width: int = 0
    magi_2k_height: int = 0
    magi_2k_class: str = ""
    magi_error: str = ""
    library_ok: bool = False
    library_error: str = ""
    script_ok: bool = False
    script_error: str = ""
    voice_ok: bool = False
    voice_error: str = ""
    voice_provider_optional: str = ""
    setup_components: int = 0
    setup_error: str = ""
    update_source_online: bool | None = None
    timed_out: tuple[str, ...] = ()
    not_run: tuple[str, ...] = ()


def healthy_facts() -> BootFacts:
    return BootFacts(
        supervisor_reachable=True,
        api_pids=[100],
        api_commands={100: "python -m uvicorn app.main:app --port 8758"},
        api_health_status=200,
        vite_pids=[200],
        vite_commands={200: "node vite --port 5173 studio-web"},
        vite_status=200,
        vite_body="<!doctype html><title>Adept UI Studio</title><div id=\"root\">",
        comfy_healthy=True,
        comfy_pids=[300],
        codirector_tools=12,
        codirector_unknown_closed=True,
        image_local=2,
        image_hosted=4,
        storyboard_aspect="16:9",
        h3_width=1376,
        h3_height=768,
        h3_legal=True,
        h3_base_optimized=True,
        h3_reference_to_video=True,
        h3_max_images=9,
        h3_place_role="place",
        magi_2k_width=3670,
        magi_2k_height=2048,
        magi_2k_class="2K",
        library_ok=True,
        script_ok=True,
        voice_ok=True,
        setup_components=3,
        update_source_online=True,
    )


def _check(
    system: str,
    owner: str,
    name: str,
    result: str,
    detail: str,
    *,
    required: bool,
    classification: str,
    duration_ms: int = 0,
) -> dict[str, Any]:
    return {
        "system": system,
        "owner": owner,
        "check": name,
        "result": result,
        "detail": detail,
        "required": required,
        "classification": classification,
        "durationMs": duration_ms,
    }


def _expected_process(command: str, markers: tuple[str, ...]) -> bool:
    text = (command or "").lower()
    return bool(text) and any(marker in text for marker in markers)


def evaluate(facts: BootFacts, *, durations: dict[str, int] | None = None) -> dict[str, Any]:
    """Turn measured facts into the single startup verdict."""

    timing = durations or {}
    checks: list[dict[str, Any]] = []

    def add(check_id: str, row: dict[str, Any]) -> None:
        row["id"] = check_id
        row["durationMs"] = int(timing.get(check_id, row.get("durationMs") or 0))
        if check_id in facts.timed_out and row["required"]:
            row["result"] = "TIMEOUT"
            row["detail"] = "The check did not finish in time."
        elif check_id in facts.not_run and row["required"]:
            row["result"] = "NOT_RUN"
            row["detail"] = "The check did not run."
        checks.append(row)

    api_cmd = facts.api_commands.get(facts.api_pids[0], "") if len(facts.api_pids) == 1 else ""
    api_expected = len(facts.api_pids) == 1 and _expected_process(api_cmd, ("uvicorn", "app.main", "studio-api"))
    add(
        "studio_api_process",
        _check(
            "Studio API",
            "runtime supervisor",
            "process identity",
            "PASS" if api_expected else "FAIL",
            api_cmd or "No expected Studio API process is listening.",
            required=True,
            classification="BOOT_REQUIRED",
        ),
    )
    add(
        "studio_api_owner",
        _check(
            "Studio API",
            "runtime supervisor",
            "port owner",
            "PASS" if len(facts.api_pids) == 1 else "FAIL",
            f"{len(facts.api_pids)} listener(s) on {facts.api_port}",
            required=True,
            classification="BOOT_REQUIRED",
        ),
    )
    add(
        "studio_api_health",
        _check(
            "Studio API",
            "runtime supervisor",
            "healthz",
            "PASS" if facts.api_health_status == 200 else "FAIL",
            f"HTTP {facts.api_health_status}",
            required=True,
            classification="BOOT_REQUIRED",
        ),
    )
    api_duplicates = max(0, len(facts.api_pids) - 1) if facts.api_pids else 0
    add(
        "duplicate_api",
        _check(
            "Studio API",
            "runtime supervisor",
            "duplicate listeners",
            "PASS" if api_duplicates == 0 else "FAIL",
            str(api_duplicates),
            required=True,
            classification="BOOT_REQUIRED",
        ),
    )
    desktop = facts.runtime_mode == "electron-packaged"
    vite_cmd = facts.vite_commands.get(facts.vite_pids[0], "") if len(facts.vite_pids) == 1 else ""
    vite_expected = desktop or (len(facts.vite_pids) == 1 and _expected_process(vite_cmd, ("vite", "studio-web")))
    add(
        "vite_process",
        _check(
            "Creator UI",
            "Vite" if not desktop else "packaged renderer",
            "process identity",
            "PASS" if vite_expected else "FAIL",
            "Packaged renderer is the creator UI." if desktop else (vite_cmd or "No expected Creator UI process is listening."),
            required=not desktop,
            classification="BOOT_REQUIRED" if not desktop else "DESKTOP_RENDERER",
        ),
    )
    document_ok = desktop or (facts.vite_status == 200 and "Adept UI Studio" in (facts.vite_body or ""))
    add(
        "vite_health",
        _check(
            "Creator UI",
            "Vite" if not desktop else "packaged renderer",
            "document",
            "PASS" if document_ok else "FAIL",
            "Packaged renderer is the creator UI." if desktop else ("Adept UI Studio" if document_ok else f"HTTP {facts.vite_status}"),
            required=not desktop,
            classification="BOOT_REQUIRED" if not desktop else "DESKTOP_RENDERER",
        ),
    )
    vite_duplicates = max(0, len(facts.vite_pids) - 1) if facts.vite_pids else 0
    add(
        "duplicate_vite",
        _check(
            "Creator UI",
            "Vite",
            "duplicate listeners",
            "PASS" if vite_duplicates == 0 else "FAIL",
            str(vite_duplicates),
            required=not desktop,
            classification="BOOT_REQUIRED" if not desktop else "DESKTOP_RENDERER",
        ),
    )
    add(
        "supervisor",
        _check(
            "Runtime Supervisor",
            "Background Services",
            "control plane",
            "PASS" if facts.supervisor_reachable else "FAIL",
            f"{facts.supervisor_port} reachable" if facts.supervisor_reachable else "Background Services manager is not reachable.",
            required=True,
            classification="BOOT_REQUIRED",
        ),
    )
    add(
        "comfy",
        _check(
            "Creator Engine",
            "ComfyUI",
            "health",
            "PASS" if facts.comfy_healthy else "OPTIONAL",
            "8188 healthy" if facts.comfy_healthy else "ComfyUI is not healthy. Boot will not restart it.",
            required=False,
            classification="OPTIONAL",
        ),
    )
    codirector_ok = facts.codirector_tools > 0 and facts.codirector_unknown_closed and not facts.codirector_error
    add(
        "codirector",
        _check(
            "Co-Director",
            "codirector.tools.registry",
            "registry",
            "PASS" if codirector_ok else "FAIL",
            facts.codirector_error or f"{facts.codirector_tools} tools, unknown tool closed",
            required=True,
            classification="BOOT_REQUIRED",
        ),
    )
    image_ok = facts.image_local > 0 and not facts.image_error
    add(
        "image_generator",
        _check(
            "Image Generator",
            "image provider registry",
            "local registry",
            "PASS" if image_ok else "FAIL",
            facts.image_error or f"{facts.image_local} local providers",
            required=True,
            classification="BOOT_REQUIRED",
        ),
    )
    if facts.image_hosted is None:
        hosted_result, hosted_detail = "OPTIONAL", "Hosted catalog was not required for local planning."
    elif facts.image_hosted > 0:
        hosted_result, hosted_detail = "PASS", f"{facts.image_hosted} hosted models"
    else:
        hosted_result, hosted_detail = "OPTIONAL", "No hosted image provider is configured."
    add(
        "image_hosted",
        _check(
            "Image Generator",
            "hosted discovery",
            "hosted catalog",
            hosted_result,
            hosted_detail,
            required=False,
            classification="OPTIONAL",
        ),
    )
    story_ok = facts.storyboard_aspect == "16:9" and not facts.storyboard_error
    add(
        "storyboard",
        _check(
            "Storyboard",
            "storyboard_studio.aspect",
            "16:9 contract",
            "PASS" if story_ok else "FAIL",
            facts.storyboard_error or facts.storyboard_aspect or "aspect missing",
            required=True,
            classification="BOOT_REQUIRED",
        ),
    )
    timeline_ok = (
        facts.h3_legal
        and facts.h3_width == 1376
        and facts.h3_height == 768
        and facts.h3_base_optimized
        and facts.h3_reference_to_video
        and facts.h3_max_images >= 3
        and facts.h3_place_role == "place"
        and not facts.timeline_error
    )
    add(
        "timeline",
        _check(
            "Timeline",
            "legal canvas + H3 Base Optimized",
            "1.0 MP 16:9 reference contract",
            "PASS" if timeline_ok else "FAIL",
            facts.timeline_error or f"{facts.h3_width}x{facts.h3_height} place x{facts.h3_max_images}",
            required=True,
            classification="BOOT_REQUIRED",
        ),
    )
    magi_ok = (
        facts.magi_2k_class == "2K"
        and min(facts.magi_2k_width, facts.magi_2k_height) == 2048
        and not facts.magi_error
    )
    add(
        "magi",
        _check(
            "MAGI",
            "magi.upscale_targets",
            "2K plan",
            "PASS" if magi_ok else "FAIL",
            facts.magi_error or f"{facts.magi_2k_class} {facts.magi_2k_width}x{facts.magi_2k_height}",
            required=True,
            classification="BOOT_REQUIRED",
        ),
    )
    add(
        "library",
        _check(
            "Library",
            "project_library.service",
            "read contract",
            "PASS" if facts.library_ok and not facts.library_error else "FAIL",
            facts.library_error or "library service importable",
            required=True,
            classification="BOOT_REQUIRED",
        ),
    )
    add(
        "script_writer",
        _check(
            "Script Writer",
            "scriptwriter.api",
            "router",
            "PASS" if facts.script_ok and not facts.script_error else "FAIL",
            facts.script_error or "script router importable",
            required=True,
            classification="BOOT_REQUIRED",
        ),
    )
    add(
        "voice",
        _check(
            "Voice",
            "voice_performance.router",
            "routes",
            "PASS" if facts.voice_ok and not facts.voice_error else "FAIL",
            facts.voice_error or "voice routes importable",
            required=True,
            classification="BOOT_REQUIRED",
        ),
    )
    if facts.voice_provider_optional:
        add(
            "voice_provider",
            _check(
                "Voice",
                "external voice provider",
                "configuration",
                "OPTIONAL",
                facts.voice_provider_optional,
                required=False,
                classification="OPTIONAL",
            ),
        )
    add(
        "setup",
        _check(
            "Setup / Update",
            "setup.lifecycle",
            "catalog",
            "PASS" if facts.setup_components > 0 and not facts.setup_error else "FAIL",
            facts.setup_error or f"{facts.setup_components} components",
            required=True,
            classification="BOOT_REQUIRED",
        ),
    )
    if facts.update_source_online is False:
        add(
            "update_source",
            _check(
                "Setup / Update",
                "update metadata",
                "remote catalog",
                "OPTIONAL",
                "Update source is offline. Nothing will install during boot.",
                required=False,
                classification="OPTIONAL",
            ),
        )

    # Adept UI 1.1 Boot certifies 1.1 only. Cloud 1.2 is a separate version and
    # must not appear in checks, progress, optional rows, warnings, or GO/NO-GO.
    required = [row for row in checks if row["required"]]
    failed = [row for row in required if row["result"] != "PASS"]
    verdict = "NO-GO" if failed else "GO"
    passed = len(required) - len(failed)
    progress = round((passed / len(required)) * 100) if required else 0
    return {
        "verdict": verdict,
        "phase": "ready" if verdict == "GO" else "needs_attention",
        "headline": "ADEPT UI READY — GO" if verdict == "GO" else "ADEPT UI STARTUP — NO-GO",
        "studioApi": {
            "host": "127.0.0.1",
            "port": facts.api_port,
            "baseUrl": f"http://127.0.0.1:{facts.api_port}",
            "runtimeMode": facts.runtime_mode,
        },
        "progressPct": progress,
        "checks": checks,
        "failed": [{"system": row["system"], "check": row["check"], "detail": row["detail"], "result": row["result"]} for row in failed],
        "optional": [
            row
            for row in checks
            if not row["required"] and row["result"] != "PASS"
        ],
        "preloadPlan": {
            "preloaded": [
                "registries",
                "capability contracts",
                "legal canvas",
                "MAGI 2K target",
                "library read owner",
                "script and voice routers",
                "setup catalog",
            ],
            "lazy": [
                "model weights",
                "VRAM allocations",
                "image generation",
                "timeline render",
                "MAGI upscale",
                "voice synthesis",
                "downloads and installs",
            ],
        },
    }
