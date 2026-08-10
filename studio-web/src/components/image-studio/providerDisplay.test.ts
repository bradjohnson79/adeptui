import assert from "node:assert/strict";
import test from "node:test";
import {
  installComponentIdForProvider,
  installGuidanceHref,
  licenseShortName,
  providerSubLabel,
} from "./providerDisplay.ts";

const KREA2_TURBO_NOTE =
  "Krea 2 Community License — commercial use under $1M annual revenue; " +
  "gated HF download, license acceptance required";
const KREA2_RAW_NOTE =
  "Krea 2 Community License — RAW is the LoRA training base " +
  "(train on RAW, run on Turbo), not a creator default";

test("krea2 turbo carries the Recommended / Fast sub-label", () => {
  assert.equal(providerSubLabel({ id: "krea2-turbo-local" }), "Recommended / Fast");
  assert.equal(
    providerSubLabel({ id: "krea2-turbo-local", modelId: "krea2-turbo-local" }),
    "Recommended / Fast",
  );
});

test("krea2 raw carries the Advanced / LoRA Training Base sub-label", () => {
  assert.equal(providerSubLabel({ id: "krea2-raw-local" }), "Advanced / LoRA Training Base");
});

test("other providers have no sub-label", () => {
  assert.equal(providerSubLabel({ id: "zimage-local" }), null);
  assert.equal(providerSubLabel({ id: "qwen-image-2512-local" }), null);
});

test("license short name names the Krea 2 Community License", () => {
  assert.equal(licenseShortName(KREA2_TURBO_NOTE), "Krea 2 Community License");
  assert.equal(licenseShortName(KREA2_RAW_NOTE), "Krea 2 Community License");
});

test("license short name trims parenthetical and em-dash detail generically", () => {
  assert.equal(licenseShortName("Open-weight local (Qwen-Image-2512)"), "Open-weight local");
  assert.equal(licenseShortName("FLUX Dev — check local license terms"), "FLUX Dev");
  assert.equal(licenseShortName("Local certified Z-Image"), "Local certified Z-Image");
  assert.equal(licenseShortName(undefined), null);
  assert.equal(licenseShortName(""), null);
});

test("krea2 providers route install guidance to the krea2_models setup component", () => {
  assert.equal(installComponentIdForProvider({ id: "krea2-turbo-local" }), "krea2_models");
  assert.equal(installComponentIdForProvider({ id: "krea2-raw-local" }), "krea2_models");
  assert.equal(installComponentIdForProvider({ id: "flux-local" }), null);
});

test("install guidance href opens the AI-guided setup wizard from image studio", () => {
  const href = installGuidanceHref({ id: "krea2-turbo-local" });
  assert.ok(href);
  assert.match(href, /setupMode=ai_guided/);
  assert.match(href, /setupComponent=krea2_models/);
  assert.match(href, /setupSource=image_studio/);
  assert.equal(installGuidanceHref({ id: "zimage-local" }), null);
});
