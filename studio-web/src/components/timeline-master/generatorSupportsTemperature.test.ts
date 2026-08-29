import assert from "node:assert/strict";
import test from "node:test";
import { generatorSupportsTemperature } from "./generatorSupportsTemperature.ts";

test("missing or unknown capability is fail-closed", () => {
  assert.equal(generatorSupportsTemperature(), false);
  assert.equal(generatorSupportsTemperature("seedance-api"), false);
  assert.equal(generatorSupportsTemperature("seedance-api", {}), false);
  assert.equal(generatorSupportsTemperature("seedance-api", { supportsTemperature: undefined }), false);
  assert.equal(generatorSupportsTemperature("seedance-api", { supportsTemperature: "true" as unknown as boolean }), false);
});

test("live catalog boolean is used when present", () => {
  assert.equal(generatorSupportsTemperature("seedance-api", { supportsTemperature: false }), false);
  assert.equal(generatorSupportsTemperature("seedance-api", { supportsTemperature: true }), true);
});

test("MiniMax H3 stays false even if the catalog flag is forgotten or true", () => {
  assert.equal(generatorSupportsTemperature("minimax-h3"), false);
  assert.equal(generatorSupportsTemperature("minimax-h3-t2v-local"), false);
  assert.equal(generatorSupportsTemperature("minimax-h3-t2v-local", {}), false);
  assert.equal(generatorSupportsTemperature("minimax-h3-t2v-local", { supportsTemperature: true }), false);
  assert.equal(generatorSupportsTemperature("minimax-h3-i2v-local", { supportsTemperature: false }), false);
});
