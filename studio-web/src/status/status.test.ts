import assert from "node:assert/strict";
import test from "node:test";
import { mapCapabilityStatus } from "./mapCapability.ts";
import { mapGenerationToolStatus } from "./mapGenerationTool.ts";
import { apiHealthLabel, gpuHealthLabel, mapGpuOk, providerHealthLabel } from "./mapHealth.ts";
import { mapJobStatus } from "./mapJob.ts";
import { mapStatusTone } from "./tones.ts";

test("maps capability readiness", () => {
  assert.equal(mapCapabilityStatus("production_ready"), "Ready");
  assert.equal(mapCapabilityStatus("blocked"), "Blocked");
  assert.equal(mapCapabilityStatus("not_configured"), "ConfigurationRequired");
});

test("maps tool and job statuses case-insensitively", () => {
  assert.equal(mapGenerationToolStatus("missing"), "InstallRequired");
  assert.equal(mapGenerationToolStatus("PARTIAL"), "Partial");
  assert.equal(mapGenerationToolStatus("DEFERRED"), "Deferred");
  assert.equal(mapGenerationToolStatus("CERTIFIED"), "Ready");
  assert.equal(mapJobStatus("COMPLETE"), "Complete");
  assert.equal(mapJobStatus("cancelled"), "Cancelled");
});

test("maps status tones", () => {
  assert.equal(mapStatusTone("Ready"), "positive");
  assert.equal(mapStatusTone("Blocked"), "danger");
  assert.equal(mapStatusTone("Unknown"), "muted");
});

test("health labels stay honest about probe scope", () => {
  assert.equal(apiHealthLabel(true, false), "Studio API Online");
  assert.equal(apiHealthLabel(true, true), "Studio API Degraded");
  assert.equal(apiHealthLabel(false, false), "Studio API Unavailable");
  assert.equal(providerHealthLabel(true), "Provider Connected");
  assert.equal(providerHealthLabel(false), "Provider Offline");
  assert.equal(gpuHealthLabel(true), "GPU Detected");
  assert.equal(gpuHealthLabel(false), "GPU Unavailable");
  assert.equal(mapGpuOk(true), "Connected");
});
