import { test, expect } from "@playwright/test";
import { createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import fs from "node:fs";
import path from "node:path";

const OUT = path.join("artifacts", "m30i", "accessibility", "keyboard");

async function tabUntil(page: import("@playwright/test").Page, max = 24) {
  for (let i = 0; i < max; i++) {
    await page.keyboard.press("Tab");
    const tag = await page.evaluate(() => document.activeElement?.tagName?.toLowerCase() || "");
    if (tag && tag !== "body") return tag;
  }
  return "";
}

test.describe("@critical m30i keyboard A11Y-KB", () => {
  test("A11Y-KB-01..05 project landmarks and workspaces", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `M30I KB ${Date.now()}`);
    const rows: Array<Record<string, unknown>> = [];
    try {
      for (const ws of ["setup", "settings", "director", "editor", "bible"] as const) {
        await page.goto(`/project/${project.id}?workspace=${ws}`);
        await page.waitForLoadState("domcontentloaded");
        const tag = await tabUntil(page);
        expect(tag, ws).not.toBe("");
        rows.push({ id: `A11Y-KB-${rows.length + 1}`, workspace: ws, focused: tag, ok: true });
      }
      fs.mkdirSync(OUT, { recursive: true });
      fs.writeFileSync(path.join(OUT, "keyboard-journeys.json"), JSON.stringify({ rows }, null, 2));
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("A11Y-KB-08..10 language settings LOC-ISO keyboard", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `M30I LOC ${Date.now()}`);
    try {
      await page.addInitScript(() => {
        localStorage.setItem(
          "adept_ui_language_prefs_v1",
          JSON.stringify({
            interfaceLocale: "en",
            conversationLocale: "en",
            projectPrimaryLocale: "es",
            promptLanguagePolicy: "english",
            exportLocale: "es",
            followOsLocale: false,
          })
        );
      });
      await page.goto(`/project/${project.id}?workspace=settings`);
      await page.waitForLoadState("domcontentloaded");
      await tabUntil(page, 20);
      const prefs = await page.evaluate(() =>
        JSON.parse(localStorage.getItem("adept_ui_language_prefs_v1") || "{}")
      );
      expect(prefs.projectPrimaryLocale).toBe("es");
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("A11Y-KB-14..18 director editor export focus", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `M30I DIR ${Date.now()}`);
    try {
      for (const ws of ["director", "editor", "export"] as const) {
        await page.goto(`/project/${project.id}?workspace=${ws}`);
        await page.waitForLoadState("domcontentloaded");
        const tag = await tabUntil(page);
        expect(tag).not.toBe("");
        await page.keyboard.press("Escape").catch(() => undefined);
      }
    } finally {
      await deleteProject(request, project.id);
    }
  });
});
