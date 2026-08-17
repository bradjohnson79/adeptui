import assert from "node:assert/strict";
import test from "node:test";
import {
  canonicalGeneratorId,
  generatorOptionsFromPayload,
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
