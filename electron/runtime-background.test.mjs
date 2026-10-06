import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { classifyControlPlane, writePackagedRuntimeConfig } = require("./runtime.cjs");

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
});
