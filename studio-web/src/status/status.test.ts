import assert from "node:assert/strict";
import test from "node:test";
import { mapCapabilityStatus } from "./mapCapability.ts";
import { mapGenerationToolStatus } from "./mapGenerationTool.ts";
import {
  apiHealthLabel,
  gpuHealthLabel,
  mapGpuOk,
  mapProviderStatus,
  providerHealthLabel,
  providerStatusLabel,
} from "./mapHealth.ts";
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
  assert.equal(providerHealthLabel(true), "Providers Ready");
  assert.equal(providerHealthLabel(false), "Required Provider Unavailable");
  assert.equal(providerStatusLabel({ status: "not_probed", reachable: false }), "Providers…");
  assert.equal(providerStatusLabel({ status: "skipped", reachable: false }), "Providers…");
  assert.equal(providerStatusLabel({ status: "not_probed" }, true), "Providers Ready");
  assert.equal(providerStatusLabel({ status: "ready", reachable: true }, false), "Required Provider Unavailable");
  assert.equal(mapProviderStatus({ status: "not_probed", reachable: false }), "Checking");
  assert.equal(mapProviderStatus({ status: "ready", reachable: true }, true), "Connected");
  assert.equal(gpuHealthLabel(true), "GPU Detected");
  assert.equal(gpuHealthLabel(false), "GPU Unavailable");
  assert.equal(mapGpuOk(true), "Connected");
});
