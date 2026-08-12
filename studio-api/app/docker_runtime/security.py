"""Security inspection for Adept Runtime Manifests — default deny dangerous configs."""

from __future__ import annotations

from .contracts import AdeptRuntimeManifest, RuntimeSecurityScanReport


_SOCKET_MARKERS = (
    "/var/run/docker.sock",
    "\\\\.\\pipe\\docker_engine",
    "docker.sock",
)


def scan_manifest(manifest: AdeptRuntimeManifest, *, compose_or_run_flags: dict | None = None) -> RuntimeSecurityScanReport:
    blocked: list[str] = []
    warnings: list[str] = []
    flags = compose_or_run_flags or {}

    if manifest.security.privileged or flags.get("privileged"):
        blocked.append("privileged_mode")
    if manifest.security.hostNetwork or flags.get("network_mode") == "host":
        blocked.append("host_network")
    if manifest.security.dockerSocket or flags.get("docker_socket"):
        blocked.append("docker_socket")

    for key, mount in (manifest.mounts or {}).items():
        path = (mount.containerPath or "").lower()
        host_hint = str(flags.get(f"mount_{key}") or "")
        combined = f"{path} {host_hint}".lower()
        if any(m in combined for m in _SOCKET_MARKERS):
            blocked.append("docker_socket_mount")
        if mount.access == "read_write" and mount.hostClass == "core":
            blocked.append("writable_core_mount")
        if "credential" in combined or ".ssh" in combined or "appdata\\adept" in combined:
            blocked.append("credential_path_mount")
        if mount.hostClass in ("job_inputs",) and mount.access == "read_write":
            warnings.append("job_inputs_should_be_read_only")

    image = manifest.image.image if manifest.image else ""
    if image.endswith(":latest") or (":" not in image and image):
        if not manifest.security.allowUnpinnedImages:
            blocked.append("unpinned_image_tag")
        else:
            warnings.append("unpinned_image_allowed_by_advanced_policy")

    if flags.get("env_inherit_all"):
        blocked.append("unrestricted_env_inheritance")

    return RuntimeSecurityScanReport(ok=not blocked, blocked=sorted(set(blocked)), warnings=sorted(set(warnings)))
