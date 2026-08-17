import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/**
 * CDX-088 (Phase 7) — legacy frontend plan/execute engine gate.
 *
 * The legacy browser-side plan/execute engine (planFromIntention / RECIPE_STUBS
 * in codirector/types.ts, the stubbed direct-action calls in execute.ts,
 * CoDirectorTaskStatus.tsx, and the runSteps executor in CoDirectorSession.tsx)
 * was a dormant bypass. Phase 7 removed it: no code path may set the session
 * plan state to a non-null ActionPlan in the live flow. These source-level
 * assertions lock that property so a future change cannot silently reintroduce
 * the bypass.
 */

const here = new URL(".", import.meta.url);

function src(file: string): string {
  return readFileSync(new URL(file, here), "utf8");
}

describe("legacy plan engine removed (CDX-088)", () => {
  it("planFromIntention / RECIPE_STUBS / RecipeStub are no longer defined in codirector/types.ts", () => {
    const types = src("../codirector/types.ts");
    expect(types).not.toMatch(/export function planFromIntention/);
    expect(types).not.toMatch(/export const RECIPE_STUBS/);
    expect(types).not.toMatch(/export type RecipeStub/);
    expect(types).not.toMatch(/export type RecipeStub =/);
  });

  it("no setPlan(non-null) path remains in CoDirectorSession.tsx", () => {
    const session = src("../components/CoDirector/CoDirectorSession.tsx");
    // Every setPlan call must be the permanent-null reset (setPlan(null)).
    const setPlanLines = session.split(/\r?\n/).filter((l) => l.includes("setPlan("));
    expect(setPlanLines.length).toBeGreaterThan(0);
    for (const line of setPlanLines) {
      expect(line.trim()).toBe("setPlan(null);");
    }
    // The legacy executor is gone entirely.
    expect(session).not.toMatch(/const runSteps/);
    expect(session).not.toMatch(/dismissPlan/);
    expect(session).not.toMatch(/executeStep/);
    expect(session).not.toMatch(/selectedSteps/);
  });

  it("execute.ts no longer contains the stubbed direct-action bypasses", () => {
    const execute = src("../codirector/execute.ts");
    for (const stubId of [
      "queueImageGeneration",
      "queueVideoGeneration",
      "renderIngredientsSheet",
      "createSpatialFromMasterSheet",
      "translateToSpatial",
      "saveMemorySuggestion",
    ]) {
      expect(execute).not.toMatch(new RegExp(`case "${stubId}"`));
      expect(execute).not.toMatch(new RegExp(`\b${stubId}\b`));
    }
    // The direct provider bypasses are gone (imageProduct.generate / txt2vid).
    expect(execute).not.toMatch(/imageProduct\.generate/);
    expect(execute).not.toMatch(/api\.txt2vid/);
  });

  it("CoDirectorTaskStatus.tsx is deleted", () => {
    expect(existsSync(fileURLToPath(new URL("../components/CoDirector/CoDirectorTaskStatus.tsx", here)))).toBe(false);
  });

  it("CoDirectorConversation.tsx no longer renders the legacy task status", () => {
    const conversation = src("../components/CoDirector/CoDirectorConversation.tsx");
    expect(conversation).not.toMatch(/CoDirectorTaskStatus/);
  });
});
