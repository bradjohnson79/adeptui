import AxeBuilder from "@axe-core/playwright";
import { test, expect } from "@playwright/test";
import { createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import fs from "node:fs";
import path from "node:path";

const WORKSPACES = [
  { qs: "workspace=setup", label: "setup" },
  { qs: "workspace=settings", label: "settings" },
  { qs: "workspace=director", label: "director" },
  { qs: "workspace=editor", label: "editor" },
  { qs: "workspace=bible", label: "bible" },
  { qs: "workspace=jobs", label: "jobs" },
  { qs: "workspace=export", label: "export" },
] as const;

const OUT_DIR = path.join("artifacts", "m30g", "accessibility");

async function analyze(page: import("@playwright/test").Page) {
  return new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
}

test.describe("@critical m30g a11y", () => {
  test("A11Y production workspaces: 0 critical axe violations", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `A11y M30G ${Date.now()}`);
    const report: Record<string, unknown> = {
      startedAt: new Date().toISOString(),
      browser: "chromium",
      viewport: page.viewportSize(),
      pages: [] as unknown[],
    };
    try {
      for (const ws of WORKSPACES) {
        await page.goto(`/project/${project.id}?${ws.qs}`);
        await page.waitForLoadState("domcontentloaded");
        await expect(page.locator("body")).toBeVisible();
        const results = await analyze(page);
        const critical = results.violations.filter((v) => v.impact === "critical");
        const serious = results.violations.filter((v) => v.impact === "serious");
        (report.pages as unknown[]).push({
          label: ws.label,
          critical: critical.length,
          serious: serious.length,
          violations: results.violations.map((v) => ({
            id: v.id,
            impact: v.impact,
            help: v.help,
            nodes: v.nodes.length,
          })),
        });
        expect(critical, `${ws.label}: ${JSON.stringify(critical, null, 2)}`).toEqual([]);
      }
      report.finishedAt = new Date().toISOString();
      report.verdict = "NO_CRITICAL_VIOLATIONS";
      fs.mkdirSync(OUT_DIR, { recursive: true });
      fs.writeFileSync(path.join(OUT_DIR, "axe-m30g-production.json"), JSON.stringify(report, null, 2));
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("A11Y keyboard: settings language tab reachable", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `A11y KB ${Date.now()}`);
    try {
      await page.goto(`/project/${project.id}?workspace=settings`);
      await page.waitForLoadState("domcontentloaded");
      for (let i = 0; i < 12; i++) await page.keyboard.press("Tab");
      const focused = page.locator(":focus");
      await expect(focused).toBeVisible({ timeout: 5000 });
    } finally {
      await deleteProject(request, project.id);
    }
  });
});
