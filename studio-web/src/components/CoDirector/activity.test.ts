import assert from "node:assert/strict";
import test from "node:test";
import {
  applyToolEvent,
  createActivityState,
  labelForTool,
  shouldShowActivity,
  summarizeActivity,
} from "./activity.ts";

test("activity uses creator-safe tool labels", () => {
  assert.equal(labelForTool("production_plan.get"), "the active plan");
  assert.equal(labelForTool("production_bible.get_summary"), "saved project notes");
  assert.equal(labelForTool("asset.search"), "your project media");
});

test("longer-task preference shows while running, then richer activity after", () => {
  const base = createActivityState({
    requestId: "req-1",
    hasProject: true,
    hasContext: false,
    attachmentsCount: 0,
  });
  // Creators must see Processing feedback while a turn is in flight.
  assert.equal(shouldShowActivity(base, "longer_tasks"), true);
  const completed = { ...base, status: "completed" as const };
  assert.equal(shouldShowActivity(completed, "longer_tasks"), false);
  const withPlan = applyToolEvent(base, "production_plan.get", "completed");
  assert.equal(shouldShowActivity({ ...withPlan, status: "completed" }, "longer_tasks"), true);
});

test("activity summary reports actual context facts", () => {
  const activity = applyToolEvent(
    createActivityState({
      requestId: "req-2",
      hasProject: true,
      hasContext: true,
      attachmentsCount: 2,
    }),
    "production_bible.get_summary",
    "completed",
  );
  const facts = summarizeActivity({
    uiContext: {
      projectId: "proj-1",
      sceneName: "Opening Scene",
      workspaceId: "story",
    },
    manifest: {
      projectId: "proj-1",
      bibleVersionId: "v1",
      includedEntityKeys: [],
      includedFactIds: [],
      tokenBudget: 1000,
      estimatedTokens: 250,
      truncated: false,
    },
    attachmentsCount: 2,
    stages: activity.stages,
  });
  assert.ok(facts.includes("Used the current project context."));
  assert.ok(facts.includes('Focused on scene "Opening Scene".'));
  assert.ok(facts.includes("Checked saved project notes."));
  assert.ok(facts.includes("Included 2 attached references."));
});
