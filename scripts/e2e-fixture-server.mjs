/**
 * Tiny local pack fixture HTTP server for Playwright / ADEPT_PACK_PROVIDER=fixture_http.
 * No real model weights. Scenarios are switched via POST /control/scenario.
 */
import http from "node:http";
import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const port = Number(process.env.E2E_FIXTURE_PORT || 8765);
const host = process.env.E2E_FIXTURE_HOST || "127.0.0.1";

/** @type {Record<string, any>} */
let scenario = {
  mode: "valid", // valid | no_releases | no_matching_asset | fail_download | slow_download | checksum_mismatch | corrupt
  slowMs: 8000,
};

function crc32(buf) {
  let c = ~0;
  for (let i = 0; i < buf.length; i++) {
    c ^= buf[i];
    for (let k = 0; k < 8; k++) c = c & 1 ? (c >>> 1) ^ 0xedb88320 : c >>> 1;
  }
  return ~c >>> 0;
}

function zipStore(files) {
  // Minimal ZIP (store method)
  const parts = [];
  const central = [];
  let offset = 0;
  for (const [name, content] of Object.entries(files)) {
    const nameBuf = Buffer.from(name, "utf8");
    const data = Buffer.isBuffer(content) ? content : Buffer.from(content, "utf8");
    const crc = crc32(data);
    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(20, 4);
    local.writeUInt16LE(0, 6);
    local.writeUInt16LE(0, 8);
    local.writeUInt16LE(0, 10);
    local.writeUInt16LE(0, 12);
    local.writeUInt32LE(crc, 14);
    local.writeUInt32LE(data.length, 18);
    local.writeUInt32LE(data.length, 22);
    local.writeUInt16LE(nameBuf.length, 26);
    local.writeUInt16LE(0, 28);
    const localFull = Buffer.concat([local, nameBuf, data]);
    parts.push(localFull);
    const cen = Buffer.alloc(46);
    cen.writeUInt32LE(0x02014b50, 0);
    cen.writeUInt16LE(20, 4);
    cen.writeUInt16LE(20, 6);
    cen.writeUInt16LE(0, 8);
    cen.writeUInt16LE(0, 10);
    cen.writeUInt16LE(0, 12);
    cen.writeUInt16LE(0, 14);
    cen.writeUInt32LE(crc, 16);
    cen.writeUInt32LE(data.length, 20);
    cen.writeUInt32LE(data.length, 24);
    cen.writeUInt16LE(nameBuf.length, 28);
    cen.writeUInt16LE(0, 30);
    cen.writeUInt16LE(0, 32);
    cen.writeUInt16LE(0, 34);
    cen.writeUInt16LE(0, 36);
    cen.writeUInt32LE(0, 38);
    cen.writeUInt32LE(offset, 42);
    central.push(Buffer.concat([cen, nameBuf]));
    offset += localFull.length;
  }
  const centralBuf = Buffer.concat(central);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  end.writeUInt16LE(0, 4);
  end.writeUInt16LE(0, 6);
  end.writeUInt16LE(Object.keys(files).length, 8);
  end.writeUInt16LE(Object.keys(files).length, 10);
  end.writeUInt32LE(centralBuf.length, 12);
  end.writeUInt32LE(offset, 16);
  end.writeUInt16LE(0, 20);
  return Buffer.concat([...parts, centralBuf, end]);
}

function packJson(packId, version = "1.0.0") {
  return JSON.stringify(
    {
      schemaVersion: 1,
      id: packId,
      name: packId,
      version,
      files: ["presets/sample.json"],
    },
    null,
    2,
  );
}

function buildZip(packId, kind = "valid") {
  if (kind === "corrupt") return Buffer.from("not-a-zip");
  if (kind === "missing_pack_json") {
    return zipStore({ "presets/sample.json": '{"ok":true}' });
  }
  if (kind === "wrong_id") {
    return zipStore({
      "pack.json": packJson("pack_essential_wrong", "1.0.0"),
      "presets/sample.json": '{"ok":true}',
    });
  }
  if (kind === "invalid_json") {
    return zipStore({
      "pack.json": "{not-json",
      "presets/sample.json": '{"ok":true}',
    });
  }
  if (kind === "missing_required") {
    return zipStore({ "pack.json": packJson(packId) });
  }
  return zipStore({
    "pack.json": packJson(packId),
    "presets/sample.json": '{"ok":true,"kind":"fixture"}',
  });
}

function sha256(buf) {
  return createHash("sha256").update(buf).digest("hex");
}

function releasePayload(packId) {
  const mode = scenario.mode;
  if (mode === "no_releases") {
    return {
      release: null,
      message: "No published fixture release was found for this pack.",
      diagnostics: {
        resolved_owner: "fixture",
        resolved_repository: "local",
        release_api_url: `http://${host}:${port}/releases/${packId}`,
        repository_found: true,
        releases_found: 0,
        draft_count: 0,
        prerelease_count: 0,
        selected_release_tag: null,
        available_asset_names: [],
        expected_asset_pattern: `${packId}-*.zip`,
        selection_reason: "no_published_releases",
      },
    };
  }
  if (mode === "no_matching_asset") {
    return {
      release: null,
      message: "Release exists but contains no matching asset.",
      diagnostics: {
        resolved_owner: "fixture",
        resolved_repository: "local",
        release_api_url: `http://${host}:${port}/releases/${packId}`,
        repository_found: true,
        releases_found: 1,
        draft_count: 0,
        prerelease_count: 0,
        selected_release_tag: "v1.0.0",
        available_asset_names: ["unrelated-notes.txt", "other-model.bin"],
        expected_asset_pattern: `${packId}-*.zip`,
        selection_reason: "no_matching_asset",
      },
    };
  }
  const zipKind =
    mode === "corrupt"
      ? "corrupt"
      : mode === "checksum_mismatch"
        ? "valid"
        : "valid";
  const zip = buildZip(packId, zipKind);
  const digest = mode === "checksum_mismatch" ? "0".repeat(64) : sha256(zip);
  const assetName = `${packId}-1.0.0.zip`;
  return {
    release: {
      pack_id: packId,
      version: "1.0.0",
      channel: "stable",
      tag_name: "v1.0.0",
      release_id: 1,
      published_at: new Date().toISOString(),
      minimum_studio_version: "0.0.0",
      archive_asset_name: assetName,
      archive_asset_id: 1,
      archive_format: "zip",
      expected_bytes: zip.length,
      checksum_algorithm: "sha256",
      checksum: digest,
      required_files: ["pack.json", "presets/sample.json"],
      metadata_asset_name: `${packId}-1.0.0.release.json`,
      repository: "fixture/local",
    },
    diagnostics: {
      resolved_owner: "fixture",
      resolved_repository: "local",
      release_api_url: `http://${host}:${port}/releases/${packId}`,
      repository_found: true,
      releases_found: 1,
      selected_release_tag: "v1.0.0",
      available_asset_names: [assetName],
      expected_asset_pattern: `${packId}-*.zip`,
      selection_reason: "matched_release_json",
    },
  };
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url || "/", `http://${host}:${port}`);
  const send = (code, body, type = "application/json") => {
    const data = typeof body === "string" || Buffer.isBuffer(body) ? body : JSON.stringify(body);
    res.writeHead(code, {
      "Content-Type": type,
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    });
    res.end(data);
  };

  if (req.method === "OPTIONS") return send(204, "");

  if (req.method === "POST" && url.pathname === "/control/scenario") {
    let raw = "";
    for await (const chunk of req) raw += chunk;
    try {
      const body = JSON.parse(raw || "{}");
      scenario = { ...scenario, ...body };
      return send(200, { ok: true, scenario });
    } catch {
      return send(400, { error: "invalid json" });
    }
  }

  if (req.method === "GET" && url.pathname === "/control/scenario") {
    return send(200, { scenario });
  }

  if (req.method === "GET" && url.pathname === "/health") {
    return send(200, { ok: true, scenario: scenario.mode });
  }

  const releaseMatch = url.pathname.match(/^\/releases\/([^/]+)$/);
  if (req.method === "GET" && releaseMatch) {
    return send(200, releasePayload(decodeURIComponent(releaseMatch[1])));
  }

  const assetMatch = url.pathname.match(/^\/assets\/([^/]+)\/([^/]+)$/);
  if (req.method === "GET" && assetMatch) {
    const packId = decodeURIComponent(assetMatch[1]);
    if (scenario.mode === "fail_download") {
      return send(500, { error: "simulated download failure" });
    }
    if (scenario.mode === "slow_download") {
      await new Promise((r) => setTimeout(r, Number(scenario.slowMs) || 8000));
    }
    const kind = scenario.mode === "corrupt" ? "corrupt" : "valid";
    const zip = buildZip(packId, kind);
    return send(200, zip, "application/zip");
  }

  // Direct ZIP for set_source_override happy path
  const zipMatch = url.pathname.match(/^\/direct\/([^/]+)\.zip$/);
  if (req.method === "GET" && zipMatch) {
    const packId = decodeURIComponent(zipMatch[1]);
    if (scenario.mode === "fail_download") return send(500, "fail");
    if (scenario.mode === "slow_download") {
      await new Promise((r) => setTimeout(r, Number(scenario.slowMs) || 8000));
    }
    return send(200, buildZip(packId, "valid"), "application/zip");
  }

  send(404, { error: "not found", path: url.pathname });
});

server.listen(port, host, () => {
  const base = `http://${host}:${port}`;
  const out = path.join(root, "artifacts", "functional-audit", "fixture-server.json");
  fs.mkdirSync(path.dirname(out), { recursive: true });
  fs.writeFileSync(out, JSON.stringify({ baseUrl: base, pid: process.pid }, null, 2));
  console.log(`[e2e-fixture] listening ${base}`);
});

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => {
    server.close(() => process.exit(0));
  });
}
