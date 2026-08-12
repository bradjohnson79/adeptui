from __future__ import annotations

from .states import InstallState

# Canonical multi-phase install progress (UI stepper).
INSTALL_PHASES: list[dict[str, str]] = [
    {"id": "preparing", "label": "Preparing runtime"},
    {"id": "downloading", "label": "Downloading model"},
    {"id": "verifying_download", "label": "Verifying files"},
    {"id": "installing", "label": "Installing dependencies"},
    {"id": "configuring", "label": "Configuring provider"},
    {"id": "verifying_install", "label": "Final health check"},
]

_STATE_TO_PHASE_ID: dict[InstallState, str] = {
    InstallState.QUEUED: "preparing",
    InstallState.PREPARING: "preparing",
    InstallState.AWAITING_CONFIRMATION: "preparing",
    InstallState.DOWNLOADING: "downloading",
    InstallState.VERIFYING_DOWNLOAD: "verifying_download",
    InstallState.INSTALLING: "installing",
    InstallState.CONFIGURING: "configuring",
    InstallState.VERIFYING_INSTALL: "verifying_install",
    InstallState.READY: "verifying_install",
}


def phase_id_for_state(state: InstallState | str | None) -> str | None:
    if isinstance(state, InstallState):
        return _STATE_TO_PHASE_ID.get(state)
    value = str(state or "").strip().lower()
    for item in INSTALL_PHASES:
        if item["id"] == value:
            return value
    try:
        return _STATE_TO_PHASE_ID.get(InstallState(value))
    except ValueError:
        mapping = {
            "clone_repo": "preparing",
            "create_environment": "preparing",
            "install_dependencies": "installing",
            "import_probe": "verifying_install",
            "download_models": "downloading",
            "verify_runtime": "verifying_install",
            "extracting": "installing",
            "finalizing": "configuring",
            "validating": "verifying_install",
            "preflighting": "preparing",
            "resolving": "preparing",
            "verifying_source": "preparing",
            "restart_required": "configuring",
            "probing_nodes": "verifying_install",
        }
        return mapping.get(value)


def build_phase_steps(
    state: InstallState | str | None,
    *,
    phase: str | None = None,
    ready: bool = False,
    failed: bool = False,
) -> list[dict[str, str]]:
    current = phase_id_for_state(phase) or phase_id_for_state(state) or "preparing"
    current_index = next((i for i, item in enumerate(INSTALL_PHASES) if item["id"] == current), 0)
    steps: list[dict[str, str]] = []
    for index, item in enumerate(INSTALL_PHASES):
        if ready:
            status = "complete"
        elif failed and index == current_index:
            status = "failed"
        elif index < current_index:
            status = "complete"
        elif index == current_index:
            status = "active"
        else:
            status = "pending"
        steps.append({**item, "status": status})
    return steps


def overall_percent(
    *,
    state: InstallState | str | None,
    phase: str | None,
    download_percent: float | None,
    ready: bool,
) -> float | None:
    """Overall completion only reaches 100 after final health check passes."""
    if ready:
        return 100.0
    steps = build_phase_steps(state, phase=phase, ready=False)
    active_index = next((i for i, step in enumerate(steps) if step["status"] == "active"), 0)
    total = len(steps)
    if total <= 0:
        return None
    base = (active_index / total) * 100.0
    current_phase = phase_id_for_state(phase) or phase_id_for_state(state)
    if current_phase == "downloading" and download_percent is not None:
        span = 100.0 / total
        clamped = max(0.0, min(100.0, float(download_percent)))
        # Cap below 100 until health check completes.
        return min(99.0, base + (clamped / 100.0) * span)
    # Non-download phases: report phase progress without claiming completion.
    return min(99.0, base + (50.0 / total))
