import fs from "node:fs";
import path from "node:path";
import { test, expect } from "@playwright/test";
import { API, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";

const OUT = path.join("artifacts", "brand-studio");

test.describe("Brand Studio Creative UX @DETERMINISTIC", () => {
  test.beforeAll(() => {
    fs.mkdirSync(OUT, { recursive: true });
  });

  test("creator-facing campaign canvas persists and generates", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `Brand Studio ${Date.now()}`);
    try {
      const png = Buffer.from(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
        "base64",
      );
      const upload = await request.post(`${API}/api/projects/${project.id}/assets`, {
        multipart: {
          file: { name: "brand-seed.png", mimeType: "image/png", buffer: png },
          tag: "brand-seed",
          kind: "image",
        },
      });
      expect(upload.ok()).toBeTruthy();
      const asset = await upload.json();

      await page.goto(`/project/${project.id}?workspace=brandstudio`);
      await expect(page.getByTestId("brand-studio")).toBeVisible({ timeout: 45_000 });
      await expect(page.getByTestId("brand-advanced")).not.toHaveAttribute("open", /true|open/i);
      await page.screenshot({ path: path.join(OUT, "brand-studio-workspace.png"), fullPage: true });

      await page.getByTestId("brand-campaign-type-social").click();
      await page.getByTestId("brand-direction-lifestyle").click();
      await page.getByTestId("brand-brief").fill(
        "Create a playful social launch with glossy product focus and easy-to-read headline space.",
      );
      await page.getByTestId(`brand-logo-lock-${asset.id}`).click();
      await page.getByTestId(`brand-product-lock-${asset.id}`).click();
      await page.getByTestId("brand-required-wording").fill("New summer sparkle");
      await page.getByTestId("brand-campaign-set-story-9-16").click();
      await page.getByTestId("brand-generate").click();
      await expect(page.getByText(/Queued .* brand-safe .*visual/i)).toBeVisible({ timeout: 30_000 });
      await page.screenshot({ path: path.join(OUT, "brand-studio-generated.png"), fullPage: true });

      await page.reload();
      await expect(page.getByTestId("brand-studio")).toBeVisible({ timeout: 45_000 });
      await expect(page.getByTestId("brand-brief")).toHaveValue(/playful social launch/i);
      await expect(page.getByTestId("brand-save-status")).toContainText(/Campaign|Saving/i);
    } finally {
      await deleteProject(request, project.id);
    }
  });
});
