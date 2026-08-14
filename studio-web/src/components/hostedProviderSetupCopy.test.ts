import assert from "node:assert/strict";
import test from "node:test";
import {
  API_KEY_INPUT_TYPE,
  API_KEY_PROVIDER_BADGE,
  API_KEY_PROVIDER_IDS,
  API_KEY_PROVIDER_TITLES,
  API_KEY_PROVIDERS_CATEGORY,
  API_KEY_REMOVE_LABEL,
  API_KEY_SAVE_LABEL,
  API_KEY_UPDATE_LABEL,
  FORBIDDEN_GENERIC_LABELS,
  SETUP_PROVIDERS,
  STATUS,
  apiKeyProviderCardContract,
  apiKeyProviderStatusLabel,
  apiKeyRemovedCopy,
  apiKeyUpdatedCopy,
  catalogApiProvidersHiddenFromOptional,
  classifyProbeError,
  copyClaimsKeyUpdated,
  filterCloudProviders,
  isApiKeyCatalogComponent,
  isApiKeyCloudProvider,
  maskedKeyPlaceholder,
} from "./hostedProviderSetupCopy.ts";

test("API Providers accordion is the input surface, catalog category stays hidden", () => {
  assert.equal(API_KEY_PROVIDERS_CATEGORY, "API Providers");
  assert.equal(API_KEY_PROVIDER_BADGE, "API Key Provider");
  assert.equal(catalogApiProvidersHiddenFromOptional(), "API Providers");
});

test("three cards have password input + Update + Remove", () => {
  assert.deepEqual(API_KEY_PROVIDER_IDS, ["kie", "wavespeed", "fal"]);
  assert.deepEqual(API_KEY_PROVIDER_TITLES, ["Kie.ai", "WaveSpeed.ai", "fal.ai"]);
  assert.equal(SETUP_PROVIDERS.length, 3);
  const cards = apiKeyProviderCardContract();
  assert.equal(cards.length, 3);
  for (const card of cards) {
    assert.equal(card.inputType, "password");
    assert.equal(API_KEY_INPUT_TYPE, "password");
    assert.equal(card.updateLabel, "Update");
    assert.equal(card.removeLabel, "Remove");
    assert.equal(API_KEY_UPDATE_LABEL, "Update");
    assert.equal(API_KEY_SAVE_LABEL, "Update");
    assert.equal(API_KEY_REMOVE_LABEL, "Remove");
  }
});

test("Cloud Providers list excludes kie/fal/wavespeed and aliases", () => {
  const items = [
    { providerId: "kie" },
    { providerId: "Kie.ai" },
    { providerId: "fal" },
    { providerId: "fal.ai" },
    { providerId: "wavespeed" },
    { providerId: "wavespeed.ai" },
    { providerId: "openai" },
    { providerId: "replicate" },
    { id: "google_imagen" },
  ];
  const filtered = filterCloudProviders(items);
  assert.deepEqual(
    filtered.map((item) => item.providerId || item.id),
    ["openai", "replicate", "google_imagen"],
  );
  assert.equal(isApiKeyCloudProvider("kie"), true);
  assert.equal(isApiKeyCloudProvider("wavespeed.ai"), true);
  assert.equal(isApiKeyCloudProvider("openai"), false);
});

test("status-only catalog credential cards are hidden by id, group, and surface", () => {
  assert.equal(isApiKeyCatalogComponent({ id: "fal_key" }), true);
  assert.equal(isApiKeyCatalogComponent({ id: "kie_key" }), true);
  assert.equal(isApiKeyCatalogComponent({ id: "wavespeed_key" }), true);
  assert.equal(isApiKeyCatalogComponent({ id: "other", surfaceGroups: ["API Providers"] }), true);
  assert.equal(isApiKeyCatalogComponent({ id: "other", category: "API Providers" }), true);
  assert.equal(isApiKeyCatalogComponent({ id: "flux1_dev_local", category: "Still Image Models" }), false);
});

test("Update success copy", () => {
  assert.equal(apiKeyUpdatedCopy("WaveSpeed.ai"), "WaveSpeed.ai API key updated");
  assert.equal(apiKeyUpdatedCopy("Kie.ai"), "Kie.ai API key updated");
  assert.equal(apiKeyUpdatedCopy("fal.ai"), "fal.ai API key updated");
  assert.equal(apiKeyRemovedCopy(), "API key removed");
  assert.equal(copyClaimsKeyUpdated(apiKeyUpdatedCopy("fal.ai")), true);
});

test("invalid does not say updated", () => {
  const invalidCopy = "Provider rejected this API key.";
  assert.equal(copyClaimsKeyUpdated(invalidCopy), false);
  assert.equal(copyClaimsKeyUpdated("INVALID CREDENTIALS"), false);
  assert.equal(apiKeyProviderStatusLabel({ lastOutcome: "invalid" }), STATUS.INVALID_CREDENTIALS);
  assert.notEqual(STATUS.INVALID_CREDENTIALS, apiKeyUpdatedCopy("fal.ai"));
});

test("masked placeholder shows last4 never a full key", () => {
  assert.equal(maskedKeyPlaceholder("sk-1••••ab12"), "••••ab12");
  assert.equal(maskedKeyPlaceholder(null), "••••••••");
  assert.ok(!maskedKeyPlaceholder("sk-live-secret-ab12").includes("sk-live-secret"));
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
