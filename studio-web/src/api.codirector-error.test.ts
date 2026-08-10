import assert from "node:assert/strict";
import test from "node:test";
import { ApiError, classifyCoDirectorError } from "./api.ts";

test("tool-not-found errors become creator-facing save failures", () => {
  const classified = classifyCoDirectorError(
    new ApiError("'record_production_decision' isn't a Co-Director tool.", 400, {
      code: "TOOL_NOT_FOUND",
      details: { toolId: "record_production_decision" },
      recoverable: true,
      recommendedAction: "retry",
    }),
  );

  assert.match(classified.message, /could not be saved yet/i);
  assert.equal(classified.details?.toolId, "record_production_decision");
  assert.equal(classified.details?.rawMessage, "'record_production_decision' isn't a Co-Director tool.");
});

