import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { filterCloudProviders, isApiKeyCloudProvider } from "../../components/hostedProviderSetupCopy.ts";
import type { LifecycleCloudProvider } from "../types.ts";
import {
  CONNECTION_TEST_UNAVAILABLE,
  CREDENTIALS_STORED_ONLY,
  LEARN_MORE_FALLBACK,
  SETUP_NOT_YET_SUPPORTED,
  cloudProviderAiPrompt,
  cloudProviderCardContract,
  cloudProviderLearnMoreCopy,
  cloudProviderPrimaryAction,
  cloudProviderPrimaryLabel,
  cloudProviderStatusVocabulary,
  translateCapabilityChip,
} from "./cloudProviderCardCopy.ts";

const TEN = [
  "google_imagen",
  "openai",
  "replicate",
  "ideogram",
  "recraft",
  "leonardo",
  "runware",
  "together",
  "black_forest_labs",
  "stability",
] as const;

function provider(partial: Partial<LifecycleCloudProvider> & Pick<LifecycleCloudProvider, "providerId">): LifecycleCloudProvider {
  return {
    displayName: partial.displayName || partial.providerId,
    statusLabel: partial.statusLabel || "Requires Setup",
    configured: Boolean(partial.configured),
    setupSupported: partial.setupSupported ?? true,
    secretName: partial.secretName ?? `${partial.providerId}_api_key`,
    connectionTestAvailable: partial.connectionTestAvailable ?? false,
    ...partial,
  };
}

test("Cloud Providers filter still drops kie/fal/wavespeed", () => {
  const items = [
    ...TEN.map((providerId) => ({ providerId })),
    { providerId: "kie" },
    { providerId: "fal" },
    { providerId: "wavespeed" },
    { providerId: "kie.ai" },
    { providerId: "fal.ai" },
    { providerId: "wavespeed.ai" },
  ];
  const filtered = filterCloudProviders(items);
  assert.deepEqual(filtered.map((item) => item.providerId), [...TEN]);
  assert.equal(isApiKeyCloudProvider("kie"), true);
  assert.equal(isApiKeyCloudProvider("openai"), false);
});

test("cards have Set Up + Learn More when a secret path exists and no key is stored", () => {
  for (const providerId of TEN) {
    const card = cloudProviderCardContract(provider({ providerId, configured: false }));
    assert.equal(card.showSetUp, true, providerId);
    assert.equal(card.showManage, false, providerId);
    assert.equal(card.showLearnMore, true, providerId);
    assert.equal(card.showComingSoon, false, providerId);
    assert.equal(card.primaryLabel, "Set Up");
  }
});

test("configured cards show Manage + Learn More", () => {
  const card = cloudProviderCardContract(provider({ providerId: "openai", configured: true, state: "unverified" }));
  assert.equal(card.showManage, true);
  assert.equal(card.showSetUp, false);
  assert.equal(card.showLearnMore, true);
  assert.equal(card.primaryLabel, "Manage");
});

test("Learn More has fallback when catalog info is missing", () => {
  const copy = cloudProviderLearnMoreCopy(provider({ providerId: "unknown_vendor", summary: "", docsUrl: "", keysUrl: "" }));
  assert.equal(copy.fallback, LEARN_MORE_FALLBACK);
  assert.equal(copy.summary, "");
});

test("Learn More translates capability chips", () => {
  const copy = cloudProviderLearnMoreCopy(provider({
    providerId: "openai",
    summary: "Hosted OpenAI image models.",
    operations: ["image.generate", "image.edit"],
  }));
  assert.equal(copy.fallback, null);
  assert.deepEqual(copy.capabilities, ["Image Generation", "Image Editing"]);
  assert.equal(translateCapabilityChip("image.reference"), "Reference Images");
});

test("Set Up does not claim READY without a persisted verified secret", () => {
  const afterSave = cloudProviderStatusVocabulary({
    configured: true,
    state: "unverified",
    statusLabel: "Requires Setup",
  });
  assert.equal(afterSave.metaLabel, "Configured");
  assert.equal(afterSave.statusLabel, "Requires Setup");
  assert.equal(afterSave.claimsReady, false);
  const clickOnly = cloudProviderStatusVocabulary({
    configured: false,
    state: "missing",
    statusLabel: "Ready",
  });
  assert.equal(clickOnly.claimsReady, false);
  assert.equal(clickOnly.statusLabel, "Requires Setup");
  assert.equal(clickOnly.metaLabel, "Needs credentials");
});

test("coming soon when no secret mapping exists", () => {
  const card = cloudProviderCardContract(provider({
    providerId: "future_vendor",
    setupSupported: false,
    secretName: "",
  }));
  assert.equal(card.showComingSoon, true);
  assert.equal(card.showSetUp, false);
  assert.equal(card.showLearnMore, true);
  assert.equal(card.primaryLabel, SETUP_NOT_YET_SUPPORTED);
  assert.equal(cloudProviderPrimaryAction({ setupSupported: false, secretName: "" }), "coming_soon");
  assert.equal(cloudProviderPrimaryLabel({ setupSupported: false }), SETUP_NOT_YET_SUPPORTED);
});

test("Test Connection stays honest when no probe exists", () => {
  const card = cloudProviderCardContract(provider({ providerId: "openai", connectionTestAvailable: false }));
  assert.equal(card.testConnectionAvailable, false);
  assert.equal(card.testConnectionMessage, CONNECTION_TEST_UNAVAILABLE);
});

test("AI prompt scopes Co-Director and does not claim it can save the key", () => {
  const prompt = cloudProviderAiPrompt({ displayName: "OpenAI Images", providerId: "openai" });
  assert.match(prompt, /Help me set up OpenAI Images/);
  assert.match(prompt, /provider id: openai/);
  assert.match(prompt, /cannot save the key/i);
});

test("AiGuidedSetupPanel Cloud Provider cards emit Set Up, Manage, and Learn More", () => {
  const panel = readFileSync(new URL("./AiGuidedSetupPanel.tsx", import.meta.url), "utf8");
  const modal = readFileSync(new URL("./CloudProviderSetupModal.tsx", import.meta.url), "utf8");
  const copy = readFileSync(new URL("./cloudProviderCardCopy.ts", import.meta.url), "utf8");
  assert.match(panel, /filterCloudProviders\(cloudProviders\)/);
  assert.match(panel, /Learn More/);
  assert.match(panel, /SETUP_NOT_YET_SUPPORTED/);
  assert.match(panel, /cloudProviderPrimaryLabel/);
  assert.match(copy, /return "Set Up"/);
  assert.match(copy, /return "Manage"/);
  assert.doesNotMatch(panel, /hostedProvidersConnect/);
  assert.doesNotMatch(panel, /connect_and_verify/);
  assert.doesNotMatch(modal, /hostedProvidersConnect/);
  assert.match(modal, /setupLifecycleSetCloudProviderKey/);
  assert.match(modal, /CONNECTION_TEST_UNAVAILABLE/);
  assert.doesNotMatch(panel, /providerId === "kie"/);
});

test("credentials-stored-only copy never claims generation READY", () => {
  assert.doesNotMatch(CREDENTIALS_STORED_ONLY, /READY|Ready to generate|Connected/i);
});

