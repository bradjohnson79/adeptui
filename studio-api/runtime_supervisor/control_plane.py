"""Loopback-only control plane. Token required. Studio API is a client."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import urlparse

from .constants import CONTROL_PORT
from .control_token import TOKEN_HEADER, token_matches

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


class ControlPlaneError(ValueError):
    pass


def assert_loopback_bind(host: str) -> str:
    raw = (host or "").strip()
    if raw not in LOOPBACK_HOSTS:
        raise ControlPlaneError("control plane must bind 127.0.0.1 only")
    if raw in {"0.0.0.0", "::", ""}:
        raise ControlPlaneError("control plane refuses non-loopback bind")
    return "127.0.0.1" if raw == "localhost" else raw


def peer_is_loopback(addr: str | None) -> bool:
    host = (addr or "").split("%")[0]
    return host in LOOPBACK_HOSTS


HandlerFn = Callable[[dict[str, Any]], dict[str, Any]]


class ControlPlane:
    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = CONTROL_PORT,
        on_status: HandlerFn | None = None,
        on_start: HandlerFn | None = None,
        on_stop: HandlerFn | None = None,
        on_restart: HandlerFn | None = None,
        on_request_qwen: HandlerFn | None = None,
        on_start_api: HandlerFn | None = None,
        on_stop_api: HandlerFn | None = None,
        on_restart_api: HandlerFn | None = None,
        on_start_comfy: HandlerFn | None = None,
        on_stop_comfy: HandlerFn | None = None,
        on_restart_comfy: HandlerFn | None = None,
        on_start_route_a: HandlerFn | None = None,
        on_stop_route_a: HandlerFn | None = None,
        on_restart_route_a: HandlerFn | None = None,
        on_start_ollama: HandlerFn | None = None,
        on_stop_ollama: HandlerFn | None = None,
        on_restart_ollama: HandlerFn | None = None,
        on_repair: HandlerFn | None = None,
    ):
        self.host = assert_loopback_bind(host)
        self.port = int(port)
        self.on_status = on_status
        self.on_start = on_start
        self.on_stop = on_stop
        self.on_restart = on_restart
        self.on_request_qwen = on_request_qwen
        self.on_start_api = on_start_api
        self.on_stop_api = on_stop_api
        self.on_restart_api = on_restart_api
        self.on_start_comfy = on_start_comfy
        self.on_stop_comfy = on_stop_comfy
        self.on_restart_comfy = on_restart_comfy
        self.on_start_route_a = on_start_route_a
        self.on_stop_route_a = on_stop_route_a
        self.on_restart_route_a = on_restart_route_a
        self.on_start_ollama = on_start_ollama
        self.on_stop_ollama = on_stop_ollama
        self.on_restart_ollama = on_restart_ollama
        self.on_repair = on_repair
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def authorize(self, token: str | None, client_host: str | None) -> tuple[int, str]:
        if not peer_is_loopback(client_host):
            return 403, "loopback only"
        if not token_matches(token):
            return 401, "invalid or missing control token"
        return 200, "ok"


def _json_bytes(payload: dict[str, Any], status: int = 200) -> tuple[int, bytes]:
    return status, json.dumps(payload).encode("utf-8")


def make_handler(plane: ControlPlane) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: object) -> None:
            return

        def _token(self) -> str | None:
            return self.headers.get(TOKEN_HEADER) or self.headers.get(TOKEN_HEADER.lower())

        def _gate(self) -> bool:
            code, reason = plane.authorize(self._token(), self.client_address[0] if self.client_address else "")
            if code != 200:
                self._write(code, {"ok": False, "error": reason})
                return False
            return True

        def _write(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _dispatch(self, fn: HandlerFn | None, default_error: str) -> None:
            if fn is None:
                self._write(501, {"ok": False, "error": default_error})
                return
            try:
                result = fn({})
            except Exception as exc:
                self._write(500, {"ok": False, "error": str(exc)})
                return
            ok = bool(result.get("ok", True))
            self._write(200 if ok else 409, result)

        def do_GET(self) -> None:  # noqa: N802
            if not self._gate():
                return
            path = urlparse(self.path).path
            if path in {"/status", "/"}:
                self._dispatch(plane.on_status, "status unavailable")
                return
            self._write(404, {"ok": False, "error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            if not self._gate():
                return
            path = urlparse(self.path).path
            mapping = {
                "/start": (plane.on_start, "start unavailable"),
                "/stop": (plane.on_stop, "stop unavailable"),
                "/restart": (plane.on_restart_comfy or plane.on_restart, "restart unavailable"),
                "/request-qwen": (plane.on_request_qwen, "request-qwen unavailable"),
                "/start-api": (plane.on_start_api, "start-api unavailable"),
                "/stop-api": (plane.on_stop_api, "stop-api unavailable"),
                "/restart-api": (plane.on_restart_api, "restart-api unavailable"),
                "/start-comfy": (plane.on_start_comfy, "start-comfy unavailable"),
                "/stop-comfy": (plane.on_stop_comfy, "stop-comfy unavailable"),
                "/restart-comfy": (plane.on_restart_comfy or plane.on_restart, "restart-comfy unavailable"),
                "/start-route-a": (plane.on_start_route_a, "start-route-a unavailable"),
                "/stop-route-a": (plane.on_stop_route_a, "stop-route-a unavailable"),
                "/restart-route-a": (plane.on_restart_route_a, "restart-route-a unavailable"),
                "/start-ollama": (plane.on_start_ollama, "start-ollama unavailable"),
                "/stop-ollama": (plane.on_stop_ollama, "stop-ollama unavailable"),
                "/restart-ollama": (plane.on_restart_ollama, "restart-ollama unavailable"),
                "/repair": (plane.on_repair, "repair unavailable"),
            }
            pair = mapping.get(path)
            if not pair:
                self._write(404, {"ok": False, "error": "not found"})
                return
            self._dispatch(pair[0], pair[1])

    return Handler


def start_control_plane(plane: ControlPlane) -> ControlPlane:
    handler = make_handler(plane)
    httpd = ThreadingHTTPServer((plane.host, plane.port), handler)
    httpd.daemon_threads = True
    httpd.allow_reuse_address = True
    bound_host, bound_port = httpd.server_address[:2]
    if str(bound_host) not in LOOPBACK_HOSTS:
        httpd.server_close()
        raise ControlPlaneError("control plane bound a non-loopback interface")
    plane._httpd = httpd
    thread = threading.Thread(target=httpd.serve_forever, name="adept-runtime-control", daemon=True)
    plane._thread = thread
    thread.start()
    return plane


def stop_control_plane(plane: ControlPlane) -> None:
    if plane._httpd is not None:
        plane._httpd.shutdown()
        plane._httpd.server_close()
        plane._httpd = None
