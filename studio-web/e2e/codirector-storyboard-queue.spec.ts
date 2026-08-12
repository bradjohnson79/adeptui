/**
 * Co-Director Storyboard Generation Queue — Playwright E2E certification.
 *
 * Tests E1–E7 covering the generation queue lifecycle:
 *   E1 — No false "Request failed" after stream interrupt with execution created
 *   E2 — Generation Queue card appears BEFORE any GPU work begins
 *   E3 — Refinement via chat updates queue without creating jobs
 *   E4 — Approve button triggers execution with GPU jobs
 *   E5 — Progress counts reflect real job state
 *   E6 — Result action buttons positioned below image grid
 *   E7 — Output/panel terminology correctness
 */

import { test, expect, type Page } from "@playwright/test";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Type a message and click Send. */
async function sendMessage(page: Page, text: string) {
  const textarea = page.getByLabel("Message Co-Director");
  await textarea.fill(text);
  await page.getByTestId("codirector-send-button").click();
}

/** Query the backend for the current GPU job count for a project. */
async function getGpuJobCount(request: any, projectId: string): Promise<number> {
  try {
    const res = await request.get(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/executions?active=true`,
    );
    if (!res.ok()) return -1;
    const body = (await res.json()) as { executions?: Array<{ child_jobs?: unknown[] }> };
    const jobs = body.executions?.flatMap((e) => e.child_jobs ?? []) ?? [];
    return jobs.length;
  } catch {
    return -1;
  }
}

// ---------------------------------------------------------------------------
// Suite
// ---------------------------------------------------------------------------

test.describe("Co-Director Storyboard Generation Queue", () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to a seeded test project
    await page.goto("/project/test-e2e-storyboard");
    // Open Co-Director via FAB
    const fab = page.locator("button.codirector-fab");
    await expect(fab).toBeVisible({ timeout: 30_000 });
    await fab.click();
    await expect(page.getByLabel("Message Co-Director")).toBeVisible({ timeout: 15_000 });
  });

  // =========================================================================
  // E1 — False Failure Test
  // =========================================================================
  test("E1: no 'Request failed' after stream interrupt when execution was created", async ({
    page,
  }) => {
    test.skip(true, "Requires mock Co-Director SSE scenario where execution is created then stream aborted");

    // Send a storyboard request that triggers execution creation during stream.
    await sendMessage(page, "Create a 4 image storyboard.");

    // Wait for the Stop button to appear (stream in progress).
    const stopButton = page.getByTestId("codirector-stop-button");
    await expect(stopButton).toBeVisible({ timeout: 15_000 });

    // Wait for AgentWorkSurface overlay to appear — evidence execution was created.
    await expect(page.getByTestId("agent-operation-overlay")).toBeVisible({ timeout: 20_000 });

    // Interrupt the stream.
    await stopButton.click();

    // Composer returns to normal.
    await expect(page.getByTestId("codirector-send-button")).toBeVisible({ timeout: 10_000 });

    // Verdict 1: NO "Request failed" text anywhere on the page.
    const body = page.locator("body");
    await expect(body).not.toContainText(/Request failed/i);

    // Verdict 2: NO send-error card visible.
    await expect(page.getByTestId("codirector-send-error")).toHaveCount(0);

    // Verdict 3: AgentWorkSurface overlay is STILL active (generation continues).
    const overlay = page.getByTestId("agent-operation-overlay");
    await expect(overlay).toBeVisible({ timeout: 5_000 });

    // Verdict 4: 4 output slots are shown in the storyboard frame grid.
    const frameGrid = page.getByTestId("storyboard-frame-grid");
    await expect(frameGrid).toBeVisible();
    const frameCards = frameGrid.locator("[data-testid^='frame-card-']");
    await expect(frameCards).toHaveCount(4);

    // Verdict 5: Generation jobs are still running (not failed/cancelled).
    for (let i = 0; i < 4; i++) {
      const card = page.getByTestId(`frame-card-${i}`);
      const state = await card.getAttribute("data-state");
      expect(state).not.toBe("failed");
      expect(state).not.toBe("cancelled");
    }

    // Verdict 6: The assistant bubble shows "interrupted" status.
    const interruptedLabels = page.locator(".codirector-msg-status");
    await expect(interruptedLabels.first()).toBeVisible({ timeout: 5_000 });
    await expect(interruptedLabels.first()).toContainText(/interrupted/i);

    // Verdict 7: Conversation is not stuck — composer is functional.
    const textarea = page.getByLabel("Message Co-Director");
    await expect(textarea).toBeEnabled({ timeout: 5_000 });
  });

  // =========================================================================
  // E2 — Generation Queue Appears Before GPU Jobs
  // =========================================================================
  test("E2: generation queue card appears before any GPU work begins", async ({
    page,
    request,
  }) => {
    test.skip(true, "Requires Co-Director mock provider with storyboard preview scenario");

    // Confirm zero GPU jobs at baseline.
    const initialJobs = await getGpuJobCount(request, "test-e2e-storyboard");
    expect(initialJobs).toBe(0);

    // Send the storyboard request.
    await sendMessage(page, "Create a 4 image storyboard.");

    // Verdict 1: Generation Queue card appears in the chat.
    const queueCard = page.getByTestId("generation-queue");
    await expect(queueCard).toBeVisible({ timeout: 20_000 });

    // Verdict 2: Card title contains "GENERATION QUEUE".
    const title = queueCard.locator(".codirector-gen-queue-title");
    await expect(title).toContainText(/GENERATION QUEUE/i);

    // Verdict 3: 4 outputs shown.
    const outputItems = queueCard.locator(".codirector-gen-queue-output");
    await expect(outputItems).toHaveCount(4);

    // Verdict 4: "Awaiting Approval" status badge visible.
    await expect(queueCard).toContainText(/Awaiting Approval/i);

    // Verdict 5: Approve and Refine buttons present.
    const approveBtn = page.getByTestId("generation-queue-approve");
    await expect(approveBtn).toBeVisible();
    await expect(approveBtn).toContainText(/Approve Generation/i);

    const refineBtn = page.getByTestId("generation-queue-refine");
    await expect(refineBtn).toBeVisible();
    await expect(refineBtn).toContainText(/Refine/i);

    // Verdict 6: NO AgentWorkSurface overlay active — execution hasn't started.
    await expect(page.getByTestId("agent-operation-overlay")).toHaveCount(0);

    // Verdict 7: Zero GPU jobs exist.
    const jobsAfter = await getGpuJobCount(request, "test-e2e-storyboard");
    expect(jobsAfter).toBe(0);

    // Verify each output is labeled "Output N".
    for (let i = 0; i < 4; i++) {
      const outputIndex = outputItems.nth(i).locator(".codirector-gen-queue-output-index");
      await expect(outputIndex).toHaveText(`Output ${i + 1}`);
    }
  });

  // =========================================================================
  // E3 — Refine Queue Through Chat
  // =========================================================================
  test("E3: refinement via chat updates queue without creating GPU jobs", async ({
    page,
    request,
  }) => {
    test.skip(true, "Requires Co-Director mock provider with storyboard refinement scenario");

    // Start with storyboard preview.
    await sendMessage(page, "Create a 4 image storyboard.");

    const queueCard = page.getByTestId("generation-queue");
    await expect(queueCard).toBeVisible({ timeout: 20_000 });

    // Send refinement request.
    await sendMessage(page, "Make all four outputs four-panel storyboard grids.");

    // Wait for the updated queue card.
    const updatedQueue = page.getByTestId("generation-queue");
    await expect(updatedQueue).toBeVisible({ timeout: 20_000 });

    // Verdict 1: All 4 outputs now show "4-Panel Storyboard" type.
    const updatedOutputs = updatedQueue.locator(".codirector-gen-queue-output");
    await expect(updatedOutputs).toHaveCount(4);
    const typeLabels = updatedOutputs.locator(".codirector-gen-queue-output-type");
    await expect(typeLabels).toHaveCount(4);
    for (let i = 0; i < 4; i++) {
      await expect(typeLabels.nth(i)).toHaveText(/4-Panel Storyboard/i);
    }

    // Verdict 2: Still 0 GPU jobs.
    const jobsAfter = await getGpuJobCount(request, "test-e2e-storyboard");
    expect(jobsAfter).toBe(0);

    // Verdict 3: Still "Awaiting Approval".
    await expect(updatedQueue).toContainText(/Awaiting Approval/i);
  });

  // =========================================================================
  // E4 — Approve Queue Triggers Execution
  // =========================================================================
  test("E4: approve generation triggers GPU job execution", async ({
    page,
    request,
  }) => {
    test.skip(true, "Requires real GPU backend (ComfyUI)");

    // Create storyboard preview.
    await sendMessage(page, "Create a 4 image storyboard.");
    const queueCard = page.getByTestId("generation-queue");
    await expect(queueCard).toBeVisible({ timeout: 20_000 });

    // Click "Approve Generation".
    const approveBtn = page.getByTestId("generation-queue-approve");
    await expect(approveBtn).toBeEnabled({ timeout: 10_000 });
    await approveBtn.click();

    // Verdict 1: Queue card is dismissed/replaced.
    await expect(queueCard).not.toBeVisible({ timeout: 15_000 });

    // Verdict 2: Exactly 4 GPU jobs created.
    await expect(async () => {
      const count = await getGpuJobCount(request, "test-e2e-storyboard");
      expect(count).toBe(4);
    }).toPass({ timeout: 30_000 });

    // Verdict 3: AgentWorkSurface overlay activates.
    const overlay = page.getByTestId("agent-operation-overlay");
    await expect(overlay).toBeVisible({ timeout: 10_000 });

    // Verdict 4: 4 output slots shown in the surface.
    const frameGrid = page.getByTestId("storyboard-frame-grid");
    await expect(frameGrid).toBeVisible({ timeout: 10_000 });
    const frameCards = frameGrid.locator("[data-testid^='frame-card-']");
    await expect(frameCards).toHaveCount(4);

    // Verdict 5: Progress reads "0 / 4".
    const progressCount = page.locator(".agent-work-surface__progress-count");
    await expect(progressCount).toContainText(/0 \/ 4/i);
  });

  // =========================================================================
  // E5 — Progress Truthfulness
  // =========================================================================
  test("E5: progress counts reflect real job state", async ({
    page,
    request,
  }) => {
    test.skip(true, "Requires real GPU backend (ComfyUI)");

    // Create and approve a 4-image storyboard.
    await sendMessage(page, "Create a 4 image storyboard.");
    await expect(page.getByTestId("generation-queue")).toBeVisible({ timeout: 20_000 });
    await page.getByTestId("generation-queue-approve").click();

    // Wait for AgentWorkSurface.
    const overlay = page.getByTestId("agent-operation-overlay");
    await expect(overlay).toBeVisible({ timeout: 15_000 });

    // Verdict 1: After first job completes, progress shows "1 / 4".
    const progress = page.locator(".agent-work-surface__progress-count");
    await expect(async () => {
      const text = (await progress.textContent()) ?? "";
      expect(text.trim()).toMatch(/^1 \/ 4/);
    }).toPass({ timeout: 120_000, intervals: [3_000] });

    // Verdict 2: Wait for all jobs to complete -> progress "4 / 4".
    await expect(async () => {
      const text = (await progress.textContent()) ?? "";
      expect(text.trim()).toMatch(/^4 \/ 4/);
    }).toPass({ timeout: 300_000, intervals: [3_000] });

    // Verdict 3: All 4 frame images are displayed.
    for (let i = 0; i < 4; i++) {
      const card = page.getByTestId(`frame-card-${i}`);
      const img = card.locator(".agent-work-surface__frame-image");
      await expect(img).toBeVisible({ timeout: 10_000 });
      const src = await img.getAttribute("src");
      expect(src).toBeTruthy();
    }
  });

  // =========================================================================
  // E6 — Action Row Position
  // =========================================================================
  test("E6: result action buttons appear below images in terminal state", async ({
    page,
    request,
  }) => {
    test.skip(true, "Requires real GPU backend (ComfyUI)");

    // Create, approve, and wait for completion.
    await sendMessage(page, "Create a 4 image storyboard.");
    await expect(page.getByTestId("generation-queue")).toBeVisible({ timeout: 20_000 });
    await page.getByTestId("generation-queue-approve").click();

    // Wait for AgentWorkSurface to enter terminal state (progress="4 / 4").
    const progress = page.locator(".agent-work-surface__progress-count");
    await expect(async () => {
      const text = (await progress.textContent()) ?? "";
      expect(text.trim()).toMatch(/^4 \/ 4/);
    }).toPass({ timeout: 300_000, intervals: [3_000] });

    const workSurface = page.getByTestId("agent-work-surface");

    // Verdict 1: "Regenerate All" button visible.
    const regenAllBtn = page.getByTestId("agent-work-regenerate-all");
    await expect(regenAllBtn).toBeVisible();

    // Verdict 2: "Open in Library" button visible.
    await expect(workSurface).toContainText(/Open in Library/i);

    // Verdict 3: "Close" button visible.
    const closeBtn = page.getByTestId("agent-work-close");
    await expect(closeBtn).toBeVisible();

    // Verdict 4: Buttons are in action-row, not inside the frame grid.
    const frameGrid = page.getByTestId("storyboard-frame-grid");
    const actionRow = workSurface.locator(".agent-work-surface__action-row");
    await expect(actionRow).toBeVisible();

    const actionRowInGrid = frameGrid.locator(".agent-work-surface__action-row");
    await expect(actionRowInGrid).toHaveCount(0);

    // Verdict 5: Action row is after the frame grid (lower y coordinate).
    const gridBox = await frameGrid.boundingBox();
    const rowBox = await actionRow.boundingBox();
    if (gridBox && rowBox) {
      expect(gridBox.y + gridBox.height).toBeLessThanOrEqual(rowBox.y + 1);
    }

    // Verdict 6: Each button is clickable.
    await expect(regenAllBtn).toBeEnabled();
    await expect(closeBtn).toBeEnabled();
  });

  // =========================================================================
  // E7 — Terminology
  // =========================================================================
  test("E7: output and panel terminology is correct", async ({
    page,
    request,
  }) => {
    test.skip(true, "Requires Co-Director mock provider with storyboard preview scenario");

    // Phase 1: Generation Queue terminology.
    await sendMessage(page, "Create a 4 image storyboard.");
    const queueCard = page.getByTestId("generation-queue");
    await expect(queueCard).toBeVisible({ timeout: 20_000 });

    // Verdict 1: Each output labeled "Output 1", "Output 2", etc.
    for (let i = 0; i < 4; i++) {
      const outputLabel = queueCard
        .locator(".codirector-gen-queue-output")
        .nth(i)
        .locator(".codirector-gen-queue-output-index");
      await expect(outputLabel).toHaveText(`Output ${i + 1}`);
    }

    // Verify the title says "STORYBOARD GENERATION QUEUE".
    const title = queueCard.locator(".codirector-gen-queue-title");
    await expect(title).toContainText(/STORYBOARD GENERATION QUEUE/i);

    // Phase 2: AgentWorkSurface terminology after approval.
    await page.getByTestId("generation-queue-approve").click();

    const overlay = page.getByTestId("agent-operation-overlay");
    await expect(overlay).toBeVisible({ timeout: 15_000 });

    // Verdict 2: Surface title says "STORYBOARD GENERATION".
    const surfaceTitle = page.locator(".agent-work-surface__title");
    await expect(surfaceTitle).toContainText(/STORYBOARD GENERATION/i);

    // Verdict 3: Frame card labels use "Output N" pattern.
    const frameGrid = page.getByTestId("storyboard-frame-grid");
    await expect(frameGrid).toBeVisible({ timeout: 10_000 });
    for (let i = 0; i < 4; i++) {
      const card = page.getByTestId(`frame-card-${i}`);
      const cardLabel = card.locator(".agent-work-surface__frame-label span");
      await expect(cardLabel).toContainText(`Output ${i + 1}`);
    }

    // Framing labels use human-readable text, not snake_case.
    const framingLabels = queueCard.locator(".codirector-gen-queue-output-framing");
    const framingCount = await framingLabels.count();
    for (let i = 0; i < framingCount; i++) {
      const text = (await framingLabels.nth(i).textContent()) ?? "";
      if (text.trim().length > 0) {
        expect(text).not.toContain("_");
        expect(text.trim()).toMatch(/^[A-Z]/);
      }
    }
  });
});
