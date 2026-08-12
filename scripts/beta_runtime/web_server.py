"""Production static SPA + reverse proxy for Adept UI Beta (no Vite).

Serves studio-web/dist on STUDIO_WEB_HOST:STUDIO_WEB_PORT and proxies
/api and /media to the Studio API so relative BASE=\"\" keeps working.
"""

from __future__ import annotations

import argparse
import asyncio
import mimetypes
import os
import sys
from pathlib import Path
from urllib.parse import urljoin

# Ensure repo scripts package imports work when launched as a file
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_ROOT / "scripts"))

from beta_runtime.envutil import load_beta_env, repo_root, runtime_dirs  # noqa: E402

try:
    import httpx
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import FileResponse, Response, StreamingResponse
    from starlette.routing import Route
    import uvicorn
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Beta web server requires starlette, uvicorn, and httpx in studio-api/.venv"
    ) from exc


def _api_base() -> str:
    host = os.environ.get("STUDIO_API_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = os.environ.get("STUDIO_API_PORT", "8758").strip() or "8758"
    return f"http://{host}:{port}"


def _proxy_error_response(code: str, message: str, status: int = 503) -> Response:
    import json as _json

    payload = {
        "detail": {
            "error_code": code,
            "code": code,
            "category": "runtime",
            "message": message,
            "recoverable": True,
            "retryable": True,
            "recommendedAction": "retry_or_check_service",
            "recommended_action": "retry_or_check_service",
            "details": {"proxyTarget": _api_base(), "boundary": "web_proxy"},
        }
    }
    return Response(
        _json.dumps(payload),
        status_code=status,
        media_type="application/json",
        headers={"X-Adept-Studio-Api-State": "OFFLINE", "Retry-After": "2"},
    )


async def _proxy(request: Request) -> Response:
    target = urljoin(_api_base() + "/", request.url.path.lstrip("/"))
    if request.url.query:
        target = f"{target}?{request.url.query}"
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in {"host", "content-length", "transfer-encoding", "connection"}
    }
    body = await request.body()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0), follow_redirects=False) as client:
            upstream = await client.request(
                request.method,
                target,
                headers=headers,
                content=body,
            )
    except httpx.ConnectError:
        return _proxy_error_response(
            "STUDIO_API_OFFLINE",
            "Studio API is offline. Co-Director and production services are paused until it reconnects.",
        )
    except httpx.ConnectTimeout:
        return _proxy_error_response(
            "STUDIO_API_OFFLINE",
            "Studio API did not accept the connection in time.",
        )
    except (httpx.ReadError, httpx.RemoteProtocolError, httpx.WriteError) as exc:
        msg = str(exc) or "connection reset"
        code = "STUDIO_API_CONNECTION_RESET"
        if "proxy" in msg.lower():
            code = "API_PROXY_UNAVAILABLE"
        return _proxy_error_response(
            code,
            "Studio API connection was reset while the request was in flight.",
        )
    except httpx.TimeoutException:
        import json as _json
        return Response(
            _json.dumps({
                "detail": {
                    "error_code": "STUDIO_API_TIMEOUT",
                    "code": "STUDIO_API_TIMEOUT",
                    "category": "runtime",
                    "message": "Studio API request timed out. The service may be temporarily slow under load.",
                    "recoverable": True,
                    "retryable": True,
                    "recommendedAction": "retry_or_check_service",
                    "recommended_action": "retry_or_check_service",
                    "details": {"proxyTarget": _api_base(), "boundary": "web_proxy"},
                }
            }),
            status_code=504,
            media_type="application/json",
            headers={"Retry-After": "5"},
        )
    except Exception as exc:  # noqa: BLE001
        return _proxy_error_response(
            "API_PROXY_UNAVAILABLE",
            f"Web proxy could not reach Studio API ({type(exc).__name__}).",
        )
    excluded = {"content-encoding", "content-length", "transfer-encoding", "connection"}
    out_headers = {k: v for k, v in upstream.headers.items() if k.lower() not in excluded}
    return Response(content=upstream.content, status_code=upstream.status_code, headers=out_headers)


def build_app(dist: Path, status_path: Path | None = None) -> Starlette:
    index = dist / "index.html"
    if not index.is_file():
        raise SystemExit(f"Production build missing: {index}. Run: npm --prefix studio-web run build")

    async def spa(request: Request) -> Response:
        path = request.url.path
        # Prefer supervisor status.json when adopted APIs predate /api/runtime/beta
        if request.method == "GET" and path.rstrip("/") == "/api/runtime/beta" and status_path and status_path.is_file():
            try:
                import json as _json

                data = _json.loads(status_path.read_text(encoding="utf-8"))
                data["active"] = True
                data["statusPath"] = str(status_path)
                data["servedBy"] = "beta-web"
                return Response(_json.dumps(data), media_type="application/json")
            except Exception:
                pass
        if path.startswith("/api/") or path == "/api" or path.startswith("/media/"):
            return await _proxy(request)
        # Prefer real files under dist
        rel = path.lstrip("/")
        if rel:
            candidate = (dist / rel).resolve()
            try:
                candidate.relative_to(dist.resolve())
            except ValueError:
                return FileResponse(index)
            if candidate.is_file():
                media = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
                return FileResponse(candidate, media_type=media)
        # SPA fallback
        return FileResponse(index)

    async def health(_: Request) -> Response:
        return Response('{"ok":true,"service":"adept-ui-beta-web"}', media_type="application/json")

    routes = [
        Route("/__beta_web_health", health, methods=["GET"]),
        Route("/{path:path}", spa, methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]),
        Route("/", spa, methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]),
    ]
    return Starlette(routes=routes)


def main() -> int:
    load_beta_env()
    dirs = runtime_dirs()
    parser = argparse.ArgumentParser(description="Adept UI Beta production web server")
    parser.add_argument("--host", default=os.environ.get("STUDIO_WEB_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("STUDIO_WEB_PORT", "8760")))
    parser.add_argument("--dist", type=Path, default=dirs["dist"])
    args = parser.parse_args()

    os.environ["ADEPT_UI_BETA_RUNTIME"] = "1"
    app = build_app(Path(args.dist), status_path=dirs["status"])
    print(
        f"[beta-web] serving {args.dist} on http://{args.host}:{args.port} "
        f"(proxy -> {_api_base()})",
        flush=True,
    )
    uvicorn.run(app, host=args.host, port=args.port, log_level="info", access_log=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

