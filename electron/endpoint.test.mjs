import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { resolveStudioApiEndpoint, collisionMessage, COMFY_PORT } = require("./endpoint.cjs");

test("web and electron development stay on 8758", () => {
  for (const mode of ["web-development", "electron-development"]) {
    const endpoint = resolveStudioApiEndpoint(mode);
    assert.equal(endpoint.studioApiPort, 8758);
    assert.equal(endpoint.studioApiBaseUrl, "http://127.0.0.1:8758");
    assert.equal(endpoint.runtimeMode, mode);
  }
});

test("packaged electron uses 8760 and does not move Comfy", () => {
  const endpoint = resolveStudioApiEndpoint("electron-packaged");
  assert.equal(endpoint.studioApiPort, 8760);
  assert.equal(endpoint.studioApiBaseUrl, "http://127.0.0.1:8760");
  assert.equal(endpoint.comfyPort, 8188);
  assert.equal(COMFY_PORT, 8188);
  assert.equal(endpoint.controlPort, 8759);
  assert.equal(collisionMessage(endpoint.studioApiPort), "Adept UI could not start because local port 8760 is already in use.");
});

test("the endpoint contract is not a project record", () => {
  const sample = { projectId: "p", mediaUrl: "/media/assets/a.png", timeline: { clips: [] } };
  assert.equal(JSON.stringify(sample).includes("8760"), false);
  assert.equal(JSON.stringify(sample).includes("8758"), false);
});
