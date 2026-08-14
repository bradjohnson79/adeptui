import assert from "node:assert/strict";
import test from "node:test";
import {
  API_KEY_INPUT_TYPE,
  API_KEY_PROVIDER_BADGE,
  API_KEY_PROVIDER_IDS,
  API_KEY_PROVIDER_TITLES,
  API_KEY_PROVIDERS_CATEGORY,
  API_KEY_SAVE_LABEL,
  FORBIDDEN_GENERIC_LABELS,
  SETUP_PROVIDERS,
  STATUS,
  apiKeyProviderStatusLabel,
  catalogApiProvidersHiddenFromOptional,
  classifyProbeError,
} from "./hostedProviderSetupCopy.ts";

test("category name is API KEY PROVIDERS", () => {
  assert.equal(API_KEY_PROVIDERS_CATEGORY, "API KEY PROVIDERS");
  assert.equal(API_KEY_PROVIDER_BADGE, "API Key Provider");
  assert.equal(catalogApiProvidersHiddenFromOptional(), "API Providers");
});

test("three first-class API key provider cards", () => {
  assert.deepEqual(API_KEY_PROVIDER_IDS, ["kie", "wavespeed", "fal"]);
  assert.deepEqual(API_KEY_PROVIDER_TITLES, ["Kie.ai", "WaveSpeed.ai", "fal.ai"]);
  assert.equal(SETUP_PROVIDERS.length, 3);
});

test("masked input and Save action", () => {
  assert.equal(API_KEY_INPUT_TYPE, "password");
  assert.equal(API_KEY_SAVE_LABEL, "Save");
});

test("status labels: NOT CONFIGURED / CONNECTED / INVALID CREDENTIALS / UNREACHABLE", () => {
  assert.equal(apiKeyProviderStatusLabel({ card: { apiKeyStatus: { configured: false, state: "missing" } } }), STATUS.NOT_CONFIGURED);
  assert.equal(apiKeyProviderStatusLabel({ card: { apiKeyStatus: { configured: true, state: "verified" } } }), STATUS.CONNECTED);
  assert.equal(apiKeyProviderStatusLabel({ card: { apiKeyStatus: { configured: false, state: "invalid" } } }), STATUS.INVALID_CREDENTIALS);
  assert.equal(apiKeyProviderStatusLabel({ lastOutcome: "invalid" }), STATUS.INVALID_CREDENTIALS);
  assert.equal(apiKeyProviderStatusLabel({ card: { apiKeyStatus: { configured: true, state: "unverified" } } }), STATUS.UNREACHABLE);
  assert.equal(apiKeyProviderStatusLabel({ lastOutcome: "unreachable" }), STATUS.UNREACHABLE);
  assert.equal(apiKeyProviderStatusLabel({ lastOutcome: "rate_limited" }), STATUS.RATE_LIMITED);
});

test("configured-but-unverified is not CONNECTED", () => {
  assert.notEqual(
    apiKeyProviderStatusLabel({ card: { apiKeyStatus: { configured: true, state: "unverified" } } }),
    STATUS.CONNECTED,
  );
});

test("no generic Requires Setup / Needs API key copy for these three", () => {
  const labels = [
    API_KEY_PROVIDERS_CATEGORY,
    API_KEY_PROVIDER_BADGE,
    ...Object.values(STATUS),
    ...API_KEY_PROVIDER_TITLES,
  ];
  for (const forbidden of FORBIDDEN_GENERIC_LABELS) {
    for (const label of labels) {
      assert.notEqual(label, forbidden, `${label} must not be generic ${forbidden}`);
    }
  }
});

test("classifyProbeError maps reject vs network", () => {
  assert.equal(classifyProbeError("Kie.ai rejected this API key.", 400), "invalid");
  assert.equal(classifyProbeError("Could not reach WaveSpeed.ai to verify the key", 0), "unreachable");
  assert.equal(classifyProbeError("rate limited", 429), "rate_limited");
});
