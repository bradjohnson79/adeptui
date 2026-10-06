"use strict";

const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".gif": "image/gif",
  ".ico": "image/x-icon",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".mp4": "video/mp4",
  ".webm": "video/webm",
  ".wav": "audio/wav",
  ".mp3": "audio/mpeg",
};

function sendJson(res, status, body) {
  const raw = JSON.stringify(body);
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "content-length": Buffer.byteLength(raw),
    "cache-control": "no-store",
  });
  res.end(raw);
}

function safeFile(root, urlPath) {
  const decoded = decodeURIComponent(urlPath.split("?")[0]);
  const rel = decoded.replace(/^\/+/, "");
  const full = path.resolve(root, rel);
  const rootResolved = path.resolve(root);
  if (full !== rootResolved && !full.startsWith(rootResolved + path.sep)) return null;
  return full;
}

function proxyHttp(req, res, apiPort) {
  const headers = { ...req.headers, host: `127.0.0.1:${apiPort}` };
  const upstream = http.request(
    {
      host: "127.0.0.1",
      port: apiPort,
      method: req.method,
      path: req.url,
      headers,
    },
    (up) => {
      res.writeHead(up.statusCode || 502, up.headers);
      up.pipe(res);
    },
  );
  upstream.on("error", () => {
    if (!res.headersSent) sendJson(res, 502, { ok: false, code: "STUDIO_API_UNREACHABLE" });
    else res.end();
  });
  req.pipe(upstream);
}

function startRendererServer({ rendererRoot, apiPort, allowApi, onProxy, blockedMessage }) {
  const server = http.createServer((req, res) => {
    const urlPath = (req.url || "/").split("?")[0];
    if (urlPath === "/api" || urlPath.startsWith("/api/") || urlPath === "/media" || urlPath.startsWith("/media/")) {
      if (!allowApi()) {
        sendJson(res, 503, {
          ok: false,
          code: "STUDIO_API_PORT_IN_USE",
          message: blockedMessage || "Studio API is already in use by another process. Adept UI did not stop it.",
        });
        return;
      }
      if (onProxy) onProxy(urlPath.startsWith("/media") ? "media" : "api", apiPort);
      proxyHttp(req, res, apiPort);
      return;
    }
    if (req.method !== "GET" && req.method !== "HEAD") {
      sendJson(res, 405, { ok: false, code: "METHOD" });
      return;
    }
    const file = safeFile(rendererRoot, urlPath === "/" ? "/index.html" : urlPath);
    if (file && fs.existsSync(file) && fs.statSync(file).isFile()) {
      const ext = path.extname(file).toLowerCase();
      res.writeHead(200, {
        "content-type": MIME[ext] || "application/octet-stream",
        "cache-control": "no-cache",
        "content-security-policy":
          "default-src 'self'; connect-src 'self' http://127.0.0.1:* ws://127.0.0.1:*; img-src 'self' data: blob: http://127.0.0.1:*; media-src 'self' blob: http://127.0.0.1:*; font-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'",
      });
      if (req.method === "HEAD") res.end();
      else fs.createReadStream(file).pipe(res);
      return;
    }
    const index = path.join(rendererRoot, "index.html");
    res.writeHead(200, { "content-type": "text/html; charset=utf-8", "cache-control": "no-cache" });
    fs.createReadStream(index).pipe(res);
  });

  return new Promise((resolve, reject) => {
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      const port = typeof address === "object" && address ? address.port : 0;
      if (port === 5173) {
        server.close();
        reject(new Error("packaged renderer bound :5173"));
        return;
      }
      resolve({ server, port, origin: `http://127.0.0.1:${port}` });
    });
  });
}

module.exports = { startRendererServer };
