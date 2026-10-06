import { describe, expect, it } from "vitest";
import {
  isPendingBriefFresh,
  pendingBriefFromDeliberationEvent,
  summarizePendingRoute,
} from "./pendingPlanBrief";

describe("pendingPlanBrief contract", () => {
  it("builds view from deliberation_decision SSE payload", () => {
    const view = pendingBriefFromDeliberationEvent({
      act: "TALK",
      reasonCodes: ["PRODUCTION_PLAN_ATTACHED", "PENDING_BRIEF_READY"],
      responsePlan: { purpose: "plan" },
      pendingBriefFresh: true,
      pendingBrief: {
        briefId: "brief-abc",
        planId: "plan-1",
        stepId: "step-image-1",
        summary: "Multi-step plan: image → video",
        state: "AWAITING_CONFIRMATION",
        expiresAt: new Date(Date.now() + 60_000).toISOString(),
      },
      productionPlan: {
        planId: "plan-1",
        goal: "Corridor still then video then footsteps",
        steps: [
          {
            stepId: "step-image-1",
            title: "Generate image",
            capabilityId: "image.generate",
            routeLock: { provider: "local", modelId: "x", level: "STRICT" },
          },
        ],
      },
      selectivePreflight: { required: true, multiStep: true, checks: ["multi_step_dependencies"] },
    });
    expect(view?.planId).toBe("plan-1");
    expect(view?.responsePurpose).toBe("plan");
    expect(isPendingBriefFresh(view)).toBe(true);
    expect(summarizePendingRoute(view!)).toContain("local");
  });

  it("stale pending must not bind Go", () => {
    const view = pendingBriefFromDeliberationEvent({
      pendingBriefFresh: false,
      pendingBrief: {
        briefId: "brief-old",
        planId: "plan-old",
        summary: "expired",
        state: "AWAITING_CONFIRMATION",
        expiresAt: new Date(Date.now() - 60_000).toISOString(),
      },
      productionPlan: { planId: "plan-old", goal: "old" },
    });
    expect(isPendingBriefFresh(view)).toBe(false);
  });

  it("expired expiresAt alone marks not fresh", () => {
    expect(
      isPendingBriefFresh({
        state: "AWAITING_CONFIRMATION",
        expiresAt: new Date(Date.now() - 5_000).toISOString(),
        fresh: true,
      }),
    ).toBe(false);
  });
});
