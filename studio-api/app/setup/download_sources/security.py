"""Strict URL / host validation for Download Sources (SSRF-safe)."""

from __future__ import annotations

import ipaddress
import os
import socket
from urllib.parse import urlparse

ALLOWED_SCHEMES = frozenset({"https"})
DEV_LOCAL_SCHEMES = frozenset({"https", "http"})

ALLOWED_HOSTS = frozenset({
    "github.com",
    "www.github.com",
    "api.github.com",
    "objects.githubusercontent.com",
    "githubusercontent.com",
    "raw.githubusercontent.com",
    "codeload.github.com",
    "huggingface.co",
    "www.huggingface.co",
    "cdn-lfs.huggingface.co",
    "cdn-lfs-us-1.huggingface.co",
    "hf.co",
})

ALLOWED_HOST_SUFFIXES = (
    ".githubusercontent.com",
    ".hf.co",
    ".huggingface.co",
)


class SourceSecurityError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _dev_fixture_mode() -> bool:
    return os.environ.get("STUDIO_E2E", "").strip() in ("1", "true", "TRUE", "yes", "YES")


def _is_private_ip(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def host_allowed(host: str | None) -> bool:
    if not host:
        return False
    hostname = host.lower().strip(".")
    if hostname in ALLOWED_HOSTS:
        return True
    if any(hostname.endswith(suffix) for suffix in ALLOWED_HOST_SUFFIXES):
        return True
    if _dev_fixture_mode() and hostname in {"localhost", "127.0.0.1"}:
        return True
    return False


def validate_remote_url(url: str, *, allow_dev_http: bool | None = None) -> str:
    """Validate a user-supplied remote URL. Never follows redirects here."""
    raw = (url or "").strip()
    if not raw:
        raise SourceSecurityError("url_empty", "Source URL is required.")
    if raw.lower().startswith(("file:", "smb:", "\\\\", "//")):
        raise SourceSecurityError("url_scheme_rejected", "Local and SMB paths are not allowed as remote sources.")
    parsed = urlparse(raw)
    schemes = DEV_LOCAL_SCHEMES if (allow_dev_http if allow_dev_http is not None else _dev_fixture_mode()) else ALLOWED_SCHEMES
    if parsed.scheme.lower() not in schemes:
        raise SourceSecurityError(
            "url_scheme_rejected",
            f"URL scheme must be HTTPS{' or localhost HTTP in fixture mode' if _dev_fixture_mode() else ''}.",
        )
    host = (parsed.hostname or "").lower()
    if not host:
        raise SourceSecurityError("url_host_missing", "Source URL is missing a host.")
    if host in {"localhost", "127.0.0.1"} and not _dev_fixture_mode():
        raise SourceSecurityError("url_localhost_rejected", "Localhost URLs are not allowed.")
    if _is_private_ip(host):
        raise SourceSecurityError("url_private_ip_rejected", "Private or reserved IP addresses are not allowed.")
    # Block unresolved hostnames that resolve only to private IPs when looking up.
    if not host_allowed(host) and not _is_private_ip(host):
        # Non-allowlisted public hosts rejected (strict provider list).
        raise SourceSecurityError(
            "url_host_rejected",
            f"Host '{host}' is not an allowed download provider.",
        )
    if not host_allowed(host):
        raise SourceSecurityError("url_host_rejected", f"Host '{host}' is not an allowed download provider.")
    return raw


def validate_redirect_host(host: str | None) -> None:
    if not host_allowed(host):
        raise SourceSecurityError("redirect_host_rejected", "Redirect target host is not allowed.")
    if host and _is_private_ip(host):
        raise SourceSecurityError("redirect_private_ip_rejected", "Redirect to a private address was blocked.")


def resolve_host_ips(hostname: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except OSError:
        return []
    ips: list[str] = []
    for info in infos:
        addr = info[4][0]
        if addr not in ips:
            ips.append(addr)
    return ips


def assert_host_not_private_after_dns(hostname: str) -> None:
    for ip in resolve_host_ips(hostname):
        if _is_private_ip(ip):
            raise SourceSecurityError(
                "dns_private_ip_rejected",
                "Hostname resolved to a private or reserved address.",
            )
