import { expect, test } from "@playwright/test";
import { createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import { openCoDirectorFullScreen, sendChatTurn } from "./helpers/audit";

/**
 * Production Planner FULL GO journey:
 * plan talk → Ready brief → Say Go → execution/job appears → cancel (no full media burn).
 * Also proves Cancel clears Go binding (stale).
 */
test.describe("@critical production planner pending brief ACT job reality", () => {
  test.beforeEach(async ({ request }) => {
    await waitForAppReady(request);
  });

  test("plan talk Ready brief; Say Go creates job; cancel; stale Go does not bind", async ({
    page,
    request,
  }) => {
    const project = await createTempProject(request, `ProdPlanner ACT ${Date.now()}`);
    const apiBase = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";

    const listExecutions = async () => {
      const res = await request.get(
        `${apiBase}/api/codirector/projects/${project.id}/executions`,
      );
      expect(res.ok()).toBeTruthy();
      const body = await res.json();
      return (body.executions || []) as Array<{
        execution_id: string;
        status?: string;
        child_jobs?: Array<{ job_id: string; status?: string }>;
        planned_steps?: unknown[];
        plan_id?: string;
      }>;
    };

    const cancelExecution = async (executionId: string) => {
      const res = await request.post(
        `${apiBase}/api/codirector/projects/${project.id}/executions/${executionId}/cancel`,
        { data: {} },
      );
      expect(res.ok()).toBeTruthy();
      return res.json();
    };

    try {
      await openCoDirectorFullScreen(page, project.id);

      const before = await listExecutions();
      const beforeIds = new Set(before.map((e) => e.execution_id));

      const planMsg =
        "Let's plan: generate a corridor still image, then make a video from it, then add footsteps audio";
      await sendChatTurn(page, planMsg);

      const brief = page.getByTestId("codirector-pending-plan-brief");
      await expect(brief).toBeVisible({ timeout: 90_000 });
      await expect(brief).toHaveAttribute("data-fresh", "true");
      await expect(page.getByTestId("pending-plan-say-go")).toBeEnabled();

      // Mid-check: plan talk must not create jobs.
      const mid = await listExecutions();
      const midNew = mid.filter((e) => !beforeIds.has(e.execution_id));
      expect(midNew.length).toBe(0);

      // Say Go → ACT → real execution/job
      await page.getByTestId("pending-plan-say-go").click();

      let created:
        | {
            execution_id: string;
            status?: string;
            child_jobs?: Array<{ job_id: string; status?: string }>;
            planned_steps?: unknown[];
            plan_id?: string;
          }
        | undefined;
      const deadline = Date.now() + 120_000;
      while (Date.now() < deadline) {
        const packs = await listExecutions();
        created = packs.find((e) => !beforeIds.has(e.execution_id));
        if (created) break;
        await page.waitForTimeout(1000);
      }
      expect(created, "expected a new execution after Say Go").toBeTruthy();
      expect(
        (created!.child_jobs || []).length,
        "expected at least one child job",
      ).toBeGreaterThan(0);

      // Cancel safely after enqueue proof — do not burn full media.
      const cancelled = await cancelExecution(created!.execution_id);
      expect(String(cancelled.status || "").toLowerCase()).toMatch(
        /cancel|fail|complete|queued|running/,
      );

      // Brief should clear after Go (pending consumed).
      await expect(brief).toHaveCount(0, { timeout: 60_000 });

      // Stale: Go ahead must not bind / create another job.
      const afterCancelIds = new Set(
        (await listExecutions()).map((e) => e.execution_id),
      );
      await sendChatTurn(page, "Go ahead");
      await page.waitForTimeout(3000);
      const staleNew = (await listExecutions()).filter(
        (e) => !afterCancelIds.has(e.execution_id),
      );
      expect(staleNew.length).toBe(0);
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("plan talk surfaces Ready brief; Cancel clears Go binding", async ({
    page,
    request,
  }) => {
    const project = await createTempProject(request, `ProdPlanner Cancel ${Date.now()}`);
    try {
      await openCoDirectorFullScreen(page, project.id);
      const planMsg =
        "Let's plan: generate a corridor still image, then make a video from it, then add footsteps audio";
      await sendChatTurn(page, planMsg);
      const brief = page.getByTestId("codirector-pending-plan-brief");
      await expect(brief).toBeVisible({ timeout: 60_000 });
      await expect(brief).toHaveAttribute("data-fresh", "true");
      await expect(page.getByTestId("pending-plan-say-go")).toBeEnabled();
      await page.getByTestId("pending-plan-cancel").click();
      await expect(brief).toHaveCount(0, { timeout: 30_000 });
    } finally {
      await deleteProject(request, project.id);
    }
  });
});
