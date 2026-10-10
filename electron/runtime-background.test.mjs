import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { adeptControlAuthenticated, classifyControlPlane, chooseControlPort, writePackagedRuntimeConfig } = require("./runtime.cjs");
const { parseSsListenPids } = require("./platform/process.cjs");

test("a foreign listener on 8759 is left alone", () => {
  const plan = classifyControlPlane(
    { open: true, commands: [{ pid: 4, command: "node -e require('net').listen(8759)" }] },
    ["/opt/Adept UI/resources/python/bin/python", "/opt/Adept UI/resources/studio-api"],
  );
  assert.equal(plan.action, "leave");
  assert.equal(plan.collision, true);
  assert.equal(plan.owned, false);
});

test("the packaged runtime supervisor is the one owner and is reused", () => {
  const python = "/opt/Adept UI/resources/python/bin/python";
  const plan = classifyControlPlane(
    { open: true, commands: [{ pid: 9, command: `${python} -m runtime_supervisor serve` }] },
    [python, "/opt/Adept UI/resources/studio-api"],
  );
  assert.equal(plan.action, "reuse");
  assert.equal(plan.collision, false);
  assert.equal(plan.owned, true);
});

test("a foreign 8759 moves Background Services to the isolated port", () => {
  const chosen = chooseControlPort(
    [
      { port: 8759, open: true, commands: [{ pid: 4, command: "python scripts\\run_runtime_supervisor.py serve" }] },
      { port: 8779, open: false, commands: [] },
    ],
    ["/opt/Adept UI/resources/python/python.exe", "/opt/Adept UI/resources/studio-api"],
  );
  assert.equal(chosen.port, 8779);
  assert.equal(chosen.plan.action, "start");
  assert.equal(chosen.exhausted, false);
});

test("foreign listeners on both control ports are left alone", () => {
  const chosen = chooseControlPort(
    [
      { port: 8759, open: true, commands: [{ pid: 4, command: "dev supervisor" }] },
      { port: 8779, open: true, commands: [{ pid: 5, command: "unrelated" }] },
    ],
    ["/opt/Adept UI/resources/python/python.exe"],
  );
  assert.equal(chosen.exhausted, true);
  assert.equal(chosen.plan.collision, true);
});

test("ss output names the listening pid without lsof", () => {
  const text = 'LISTEN 0 128 127.0.0.1:8759 0.0.0.0:* users:(("python",pid=104296,fd=5))';
  assert.deepEqual(parseSsListenPids(text), [104296]);
});

test("an unidentified listener is left alone and is not selected", () => {
  const chosen = chooseControlPort(
    [
      { port: 8759, open: true, commands: [] },
      { port: 8779, open: false, commands: [] },
    ],
    ["/opt/Adept UI/resources/python/bin/python"],
  );
  assert.equal(chosen.port, 8779);
  assert.equal(chosen.plan.action, "start");
  assert.equal(chosen.plan.owned, false);
});

test("a listener with no command line is unidentified, including a pid ss could see", () => {
  const plan = classifyControlPlane(
    { open: true, commands: [{ pid: 104296, command: "" }] },
    ["/opt/Adept UI/resources/python/bin/python"],
  );
  assert.equal(plan.action, "unidentified");
  assert.equal(plan.owned, false);
  assert.equal(plan.collision, false);
});

test("only an authenticated Adept status identifies an otherwise unknown listener", () => {
  assert.equal(adeptControlAuthenticated(401, JSON.stringify({ ok: false, error: "invalid or missing control token" })), false);
  assert.equal(adeptControlAuthenticated(200, JSON.stringify({ ok: true })), false);
  assert.equal(adeptControlAuthenticated(200, JSON.stringify({ ok: true, managerPid: 104296, serviceState: "running" })), true);
  const chosen = chooseControlPort(
    [
      { port: 8759, open: true, commands: [], authenticated: true },
      { port: 8779, open: false, commands: [] },
    ],
    ["/opt/Adept UI/resources/python/bin/python"],
  );
  assert.equal(chosen.port, 8759);
  assert.equal(chosen.plan.action, "reuse");
  assert.equal(chosen.plan.authenticated, true);
});

test("packaged Linux does not load the host OpenSSL configuration", () => {
  const source = fs.readFileSync(fileURLToPath(new URL("./runtime.cjs", import.meta.url)), "utf8");
  assert.match(source, /process\.platform === "linux"\) env\.OPENSSL_CONF = "\/dev\/null"/);
});

test("a free control port starts Background Services", () => {
  const plan = classifyControlPlane({ open: false, commands: [] }, ["/opt/python"]);
  assert.equal(plan.action, "start");
  assert.equal(plan.collision, false);
});

test("packaged runtime config does not point at Comfy, the dev repo, or port 8760", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "adept-runtime-"));
  const layout = {
    runtimeHome: path.join(dir, "runtime"),
    comfyModels: path.join(dir, "models"),
    logs: path.join(dir, "logs"),
  };
  fs.mkdirSync(layout.comfyModels, { recursive: true });
  fs.mkdirSync(layout.runtimeHome, { recursive: true });
  const file = writePackagedRuntimeConfig(layout, "/opt/Adept UI/resources/python/bin/python", "/opt/Adept UI/resources/studio-api");
  const raw = JSON.parse(fs.readFileSync(file, "utf8"));
  assert.equal(raw.comfyRoot, "");
  assert.equal(raw.comfyPython, "");
  assert.equal(raw.repoRoot, "");
  assert.equal(raw.controlPort, 8759);
  assert.equal(raw.port, 8188);
  assert.equal(raw.studioApi.enabled, false);
  assert.equal(raw.studioApi.port, 8758);
  assert.equal(raw.modelRoot, layout.comfyModels);
  raw.comfyRoot = "C:\\kept";
  fs.writeFileSync(file, JSON.stringify(raw));
  writePackagedRuntimeConfig(layout, "/opt/Adept UI/resources/python/bin/python", "/opt/Adept UI/resources/studio-api", 8779);
  const updated = JSON.parse(fs.readFileSync(file, "utf8"));
  assert.equal(updated.controlPort, 8779);
  assert.equal(updated.comfyRoot, "C:\\kept");
  assert.equal(updated.studioApi.enabled, false);
});
