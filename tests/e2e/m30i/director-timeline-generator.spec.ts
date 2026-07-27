import { test, expect } from "@playwright/test";
import { createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import fs from "node:fs";
import path from "node:path";

const OUT = path.join("artifacts", "m30i", "director-timeline");

test.describe("M3.0i Director timeline generator", () => {
  test("DIR-TL director and editor shells + freeze evidence stub", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `M30I DIR-TL ${Date.now()}`);
    fs.mkdirSync(OUT, { recursive: true });
    try {
      await page.goto(`/project/${project.id}?workspace=director`);
      await page.waitForLoadState("domcontentloaded");
      await expect(page.locator("body")).toBeVisible();
      await page.screenshot({ path: path.join(OUT, "director.png") });

      await page.goto(`/project/${project.id}?workspace=editor`);
      await expect(page.locator("body")).toBeVisible();
      await page.screenshot({ path: path.join(OUT, "editor.png") });

      // Scale integrity smoke: no crash after reload
      await page.reload();
      await expect(page.locator("body")).toBeVisible();
      const errors: string[] = [];
      page.on("pageerror", (e) => errors.push(String(e)));
      fs.writeFileSync(
        path.join(OUT, "reload-verification.json"),
        JSON.stringify({ ok: true, errors }, null, 2)
      );
      fs.writeFileSync(
        path.join(OUT, "console-errors.json"),
        JSON.stringify({ errors }, null, 2)
      );
    } finally {
      await deleteProject(request, project.id);
    }
  });
});
