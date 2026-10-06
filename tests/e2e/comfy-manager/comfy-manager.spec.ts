import { expect, test } from "@playwright/test";

const SNAPSHOT = {
  header: {
    state: "BUSY",
    label: "Busy",
    host: "127.0.0.1:8188",
    pid: 31048,
    running: 1,
    queued: 0,
    vramTotal: 34190917632,
    vramFree: 12000000000,
    gpu: "NVIDIA GeForce RTX 5090",
    submissionsPaused: false,
    checkedAt: "2026-10-06T03:20:00Z",
  },
  active: [
    {
      adeptJobId: "job-1",
      projectId: "proj-1",
      projectName: "Production Test",
      sceneId: "scene-1",
      source: "Timeline",
      workspace: "timeline",
      model: "MiniMax H3 Base Optimized",
      status: "running",
      progress: 0.63,
      elapsedSec: 272,
      width: 1376,
      height: 768,
      durationSec: 15,
      megapixels: 1,
      stall: "none",
      comfyPromptId: "prompt-1",
    },
  ],
  queue: [
    { lane: "running", promptId: "prompt-1", ownership: "adept", label: "Adept", source: "Timeline", projectName: "Production Test" },
    { lane: "pending", promptId: "other", ownership: "external", label: "External / Unknown" },
  ],
  history: [
    {
      adeptJobId: "job-old",
      projectId: "proj-1",
      projectName: "Production Test",
      source: "Image Generator",
      workspace: "imagegen",
      status: "failed",
      model: "local",
    },
  ],
  problems: [],
  diagnostics: { healthHttp: 200, queueHttp: 200, pid: 31048, progressChannel: "stored on the job" },
  cleanup: { items: [], bytes: 0, note: "No temporary file was proven safe to remove. Nothing will be deleted." },
};

test("Comfy Manager shows Adept work and leaves external jobs alone", async ({ page }) => {
  await page.route("**/api/comfy-manager/snapshot", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(SNAPSHOT) }),
  );
  await page.route("**/api/comfy-manager/cleanup/preview", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [], bytes: 0, note: "No temporary file was proven safe to remove. Nothing will be deleted." }),
    }),
  );
  await page.goto("/setup/comfy", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("comfy-manager-status")).toHaveText("Busy");
  await expect(page.getByTestId("comfy-active-job")).toContainText("Production Test");
  await expect(page.getByTestId("comfy-active-job")).toContainText("1376×768");
  await page.getByTestId("comfy-tab-queue").click();
  await expect(page.getByText("External / Unknown")).toBeVisible();
  await expect(page.getByText("will not be cancelled")).toBeVisible();
  await page.getByTestId("comfy-manager-cleanup").click();
  await expect(page.getByTestId("comfy-manager-notice")).toContainText("Nothing will be deleted");
});

test("Comfy Manager follows a job without a manual refresh", async ({ page }) => {
  const started = Date.now();
  await page.route("**/api/comfy-manager/snapshot", (route) => {
    const age = Date.now() - started;
    const phase = age < 4000 ? "queued" : age < 8000 ? "running" : "done";
    const active =
      phase === "done"
        ? []
        : [
            {
              adeptJobId: "job-live",
              projectId: "proj-1",
              projectName: "Production Test",
              source: "Image Generator",
              workspace: "imagegen",
              model: "qwen2512",
              status: phase === "queued" ? "queued" : "running",
              statusLabel: phase === "queued" ? "Queued" : "Running",
              progress: phase === "queued" ? 0 : 0.4,
              elapsedSec: phase === "queued" ? 1 : 8,
              comfyPromptId: "prompt-live",
              stall: "none",
            },
          ];
    const history =
      phase === "done"
        ? [
            {
              adeptJobId: "job-live",
              projectId: "proj-1",
              projectName: "Production Test",
              source: "Image Generator",
              workspace: "imagegen",
              status: "done",
              statusLabel: "Completed",
              model: "qwen2512",
              comfyPromptId: "prompt-live",
            },
          ]
        : [];
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ...SNAPSHOT,
        header: { ...SNAPSHOT.header, label: phase === "done" ? "Healthy" : "Busy", running: phase === "running" ? 1 : 0 },
        active,
        history,
        diagnostics: { ...SNAPSHOT.diagnostics, historyHttp: 200 },
      }),
    });
  });
  await page.goto("/setup/comfy", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("comfy-active-job")).toContainText("Queued");
  await expect(page.getByTestId("comfy-active-job")).toContainText("Running", { timeout: 15000 });
  await expect(page.getByTestId("comfy-active-job")).toContainText("40%");
  await page.getByTestId("comfy-tab-history").click();
  await expect(page.getByText("Image Generator · Completed")).toBeVisible({ timeout: 15000 });
  await page.getByTestId("comfy-tab-diagnostics").click();
  await expect(page.getByTestId("comfy-history-read")).toContainText("History response: 200");
});

test("Comfy Manager surfaces state mismatch and a missing result", async ({ page }) => {
  const mismatch = {
    ...SNAPSHOT.active[0],
    adeptJobId: "job-mismatch",
    status: "running",
    statusLabel: "Running",
    reconciliation: "mismatch",
    reconciliationLabel: "State mismatch — awaiting reconciliation",
    resultMissing: false,
  };
  const missing = {
    ...SNAPSHOT.active[0],
    adeptJobId: "job-missing",
    status: "running",
    statusLabel: "Running",
    reconciliation: "result_missing",
    reconciliationLabel: "Generation completed without the expected output",
    resultMissing: true,
    progress: 1,
  };
  await page.route("**/api/comfy-manager/snapshot", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ...SNAPSHOT, active: [mismatch, missing], queue: [] }),
    }),
  );
  await page.goto("/setup/comfy", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("comfy-state-mismatch")).toHaveText("State mismatch — awaiting reconciliation");
  await expect(page.getByTestId("comfy-result-missing")).toHaveText("Generation completed without the expected output");
  await expect(page.getByTestId("comfy-reconcile").first()).toBeVisible();
});
