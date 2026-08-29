import assert from "node:assert/strict";
import test from "node:test";
import {
  canonicalGeneratorId,
  generatorOptionsFromPayload,
  joinProductionControlVideoOptions,
  resolveGeneratorOption,
  supportsVideoMotionReferences,
} from "./draftCapabilities.ts";

const payload = {
  timelineAdapters: [
    {
      id: "minimax-h3-t2v-local",
      label: "MiniMax H3 Text-to-Video (Local)",
      aliases: ["minimax-h3", "minimax-h3-local"],
      supportsVideoReferences: false,
      maximumReferenceVideos: 0,
    },
    {
      id: "seedance-api",
      label: "Seedance",
      aliases: ["seedance-kie"],
      supportsVideoReferences: true,
      maximumReferenceVideos: 1,
    },
  ],
};

test("canonicalGeneratorId maps MiniMax scene engine to the T2V adapter", () => {
  assert.equal(canonicalGeneratorId("minimax-h3"), "minimax-h3-t2v-local");
  assert.equal(canonicalGeneratorId("minimax-h3-local"), "minimax-h3-t2v-local");
  assert.equal(canonicalGeneratorId("seedance-api"), "seedance-api");
});

test("resolveGeneratorOption accepts scene-engine aliases", () => {
  const options = generatorOptionsFromPayload(payload);
  const minimax = resolveGeneratorOption(options, "minimax-h3");
  assert.equal(minimax?.id, "minimax-h3-t2v-local");
  assert.equal(supportsVideoMotionReferences(minimax), false);
  const seedance = resolveGeneratorOption(options, undefined, "seedance-kie");
  assert.equal(seedance?.id, "seedance-api");
  assert.equal(supportsVideoMotionReferences(seedance), true);
});

test("supportsVideoMotionReferences requires both the flag and a video slot", () => {
  const options = generatorOptionsFromPayload({
    timelineAdapters: [
      { id: "flag-without-slot", supportsVideoReferences: true, maximumReferenceVideos: 0 },
    ],
  });
  assert.equal(supportsVideoMotionReferences(options[0]), false);
});

test("joinProductionControlVideoOptions uses PC identity and adapter capability", () => {
  const joined = joinProductionControlVideoOptions(
    {
      models: [
        {
          id: "ltx-local",
          modality: "video",
          label: "LTX 2.3 (Local)",
          locality: "local",
          executable: true,
          capabilityLabel: "Certified",
          supports: ["image_to_video"],
          doesNotSupport: [],
          gpuCompatible: true,
        },
        {
          id: "minimax-h3",
          modality: "video",
          label: "MiniMax H3",
          locality: "local",
          executable: false,
          capabilityLabel: "Requires Setup",
          supports: ["text_to_video"],
          doesNotSupport: [],
          gpuCompatible: true,
        },
        {
          id: "wan-local",
          modality: "video",
          label: "WAN 2.2 I2V (Local)",
          locality: "local",
          executable: true,
          capabilityLabel: "Certified",
          supports: ["image_to_video"],
          doesNotSupport: [],
          gpuCompatible: true,
        },
      ],
    },
    {
      timelineAdapters: [
        {
          id: "ltx-local",
          label: "LTX 2.5 (Local)",
          aliases: ["ltx-2.5-full"],
          executable: true,
          maxDurationSec: 20,
          supportedDurations: [5, 20],
          supportsImageToVideo: true,
          supportsTextToVideo: false,
        },
        {
          id: "minimax-h3-t2v-local",
          label: "MiniMax H3 Text-to-Video (Local)",
          aliases: ["minimax-h3", "minimax-h3-local"],
          executable: true,
          maxDurationSec: 5,
        },
      ],
    },
  );
  assert.deepEqual(
    joined.map((item) => ({ id: item.id, label: item.label, executable: item.executable, adapterId: item.adapterId })),
    [
      { id: "ltx-local", label: "LTX 2.3 (Local)", executable: true, adapterId: "ltx-local" },
      { id: "minimax-h3", label: "MiniMax H3", executable: false, adapterId: "minimax-h3-t2v-local" },
    ],
  );
  assert.equal(resolveGeneratorOption(joined, "ltx")?.id, "ltx-local");
  assert.equal(joined.find((item) => item.id === "ltx-local")?.maxDurationSec, 20);
});

test("supportsTemperature is the live catalog boolean when present", () => {
  const options = generatorOptionsFromPayload({
    timelineAdapters: [
      { id: "explicit-false", supportsTemperature: false },
      { id: "explicit-true", supportsTemperature: true },
      { id: "missing-flag" },
      { id: "non-boolean-flag", supportsTemperature: "true" },
    ],
  });
  const byId = Object.fromEntries(options.map((item) => [item.id, item]));
  assert.equal(byId["explicit-false"].supportsTemperature, false);
  assert.equal(byId["explicit-true"].supportsTemperature, true);
  assert.equal(byId["missing-flag"].supportsTemperature, undefined);
  assert.equal(byId["non-boolean-flag"].supportsTemperature, undefined);
});
