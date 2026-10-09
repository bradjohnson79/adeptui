import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import assert from "node:assert/strict";
import { evaluateSetupProbes, rendererShipsComfyPrerequisite, OFFICIAL_COMFY_DOWNLOAD } from "./setup-profile-smoke.mjs";

function status(profile, ids) {
  return {
    installationProfile: profile,
    firstRunScan: { essentialNeeded: ids.map((id) => ({ id })) },
  };
}

test("an API profile is not blocked by a missing ComfyUI", () => {
  const gates = evaluateSetupProbes({
    apiStatus: status("api", ["provider:validated"]),
    localStatus: status("local", ["comfyui"]),
    hybridStatus: status("hybrid", ["comfyui"]),
    prerequisite: { healthy: false, downloadUrl: OFFICIAL_COMFY_DOWNLOAD },
    rejectedStatus: 400,
    connected: { installed: true },
    connectedBytesSame: true,
    comfyJobStatus: 404,
  });
  assert.equal(gates["API PROFILE OMITS COMFY"], "PASS");
  assert.equal(gates["LOCAL REQUIREMENT MATCHES COMFY HEALTH"], "PASS");
  assert.equal(gates["HYBRID REQUIREMENT MATCHES COMFY HEALTH"], "PASS");
  assert.equal(gates["COMFY INSTALL NOT FABRICATED"], "PASS");
  assert.equal(gates["COMFY DETECTED WHEN REACHABLE"], "ABSENT");
});

test("a reachable ComfyUI is detected and a placeholder job still fails the gate", () => {
  const gates = evaluateSetupProbes({
    apiStatus: status("api", ["provider:validated"]),
    localStatus: status("local", ["zimage_models"]),
    hybridStatus: status("hybrid", ["zimage_models"]),
    prerequisite: { healthy: true, downloadUrl: OFFICIAL_COMFY_DOWNLOAD },
    rejectedStatus: 400,
    connected: { installed: true },
    connectedBytesSame: true,
    comfyJobStatus: 200,
  });
  assert.equal(gates["LOCAL REQUIREMENT MATCHES COMFY HEALTH"], "PASS");
  assert.equal(gates["COMFY DETECTED WHEN REACHABLE"], "PRESENT");
  assert.equal(gates["COMFY INSTALL NOT FABRICATED"], "FAIL");
});

test("the packaged renderer must contain the official download", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "adept-renderer-"));
  fs.writeFileSync(path.join(dir, "app.js"), `label ${OFFICIAL_COMFY_DOWNLOAD} Official ComfyUI Download`);
  assert.equal(rendererShipsComfyPrerequisite(dir), true);
  fs.writeFileSync(path.join(dir, "app.js"), "no download");
  assert.equal(rendererShipsComfyPrerequisite(dir), false);
});
