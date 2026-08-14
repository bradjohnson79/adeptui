import assert from "node:assert/strict";
import test from "node:test";
import { resolveProductionAvailability } from "./productionAvailability.ts";
import type { Health } from "../types.ts";

function makeHealth(over: Partial<Health> = {}): Health {
  return {
    ok: true,
    comfy_reachable: true,
    missing_models: [],
    message: "",
    ...over,
  } as Health;
}

test("runtime offline blocks generation", () => {
  const avail = resolveProductionAvailability(makeHealth({ comfy_reachable: false }), null);
  assert.equal(avail.textToVideo.status, "Local runtime offline");
  assert.equal(avail.imageGeneration.status, "Local runtime offline");
});

test("required-missing blocks generation with setup reason", () => {
  const avail = resolveProductionAvailability(
    makeHealth({
      comfy: {
        reachable: true,
        missingModelComponentIds: ["ltx_checkpoint"],
        missingRequiredModelComponentIds: ["ltx_checkpoint"],
        models: [{ componentId: "ltx_checkpoint", required: true, present: false }],
      },
    }),
    null,
  );
  assert.equal(avail.textToVideo.status, "Requires setup");
  assert.equal(avail.imageGeneration.status, "Requires setup");
});

test("optional-missing does NOT block generation (only affected generator gates)", () => {
  // LTX 2.5 text encoder is optional at the runtime level. A missing optional
  // component must not flip ALL generation to "Requires setup" — only the
  // affected generator's preflight should block.
  // Production leak: health.missing_models / missing_model_component_ids may list
  // optional krea2_models even when missingRequiredModelComponentIds is [].
  // An empty required array must NOT ||-fall-through into those all-missing IDs.
  const avail = resolveProductionAvailability(
    makeHealth({
      missing_model_component_ids: ["krea2_models"],
      missing_models: ["krea2_models"],
      comfy: {
        reachable: true,
        missingModelComponentIds: ["ltx_2_5_text_encoder", "krea2_models"],
        missingRequiredModelComponentIds: [],
        models: [{ componentId: "ltx_2_5_text_encoder", required: false, present: false }],
      },
    }),
    null,
  );
  assert.equal(avail.textToVideo.status, "Available", "optional-missing must not block textToVideo");
  assert.equal(avail.imageGeneration.status, "Available", "optional-missing must not block imageGeneration");
  assert.equal(avail.oneFrame.status, "Available");
  assert.equal(avail.threeFrame.status, "Available");
});

test("healthy runtime with no missing components is fully available", () => {
  const avail = resolveProductionAvailability(
    makeHealth({
      comfy: {
        reachable: true,
        missingModelComponentIds: [],
        missingRequiredModelComponentIds: [],
        models: [],
      },
    }),
    null,
  );
  assert.equal(avail.textToVideo.status, "Available");
  assert.equal(avail.imageGeneration.status, "Available");
});

test("timeline remains available even when comfy is offline", () => {
  const avail = resolveProductionAvailability(makeHealth({ comfy_reachable: false }), null);
  // Timeline planning UI does not depend on Comfy; generation steps gate later.
  assert.equal(avail.timeline.status, "Available");
});

test("legacy missing_model_component_ids without required split still blocks (conservative)", () => {
  // When the backend hasn't populated missingRequiredModelComponentIds, fall back
  // to the total missing count (conservative — better to over-block than under-block
  // when the required/optional split is unknown).
  const avail = resolveProductionAvailability(
    makeHealth({ missing_model_component_ids: ["ltx_checkpoint"] }),
    null,
  );
  assert.equal(avail.textToVideo.status, "Requires setup");
});
