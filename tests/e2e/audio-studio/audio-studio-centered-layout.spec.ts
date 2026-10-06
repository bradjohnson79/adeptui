/**
 * Audio Studio centered workspace. Reuses Korri Anadriya. No new project.
 */
import { expect, test } from "@playwright/test";

const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";

test.describe("Audio Studio centered layout", () => {
  test.use({ viewport: { width: 1600, height: 900 } });

  test("workspace is centered on a wide viewport", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(String(err)));
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });

    await page.goto(`/project/${PROJECT_ID}?workspace=audiostudio&audioTab=sfx`);
    const workspace = page.getByTestId("audio-studio-workspace");
    await expect(workspace).toBeVisible({ timeout: 30000 });
    await expect(page.getByTestId("audio-sfx-panel")).toBeVisible();

    const box = await workspace.boundingBox();
    const viewport = page.viewportSize();
    expect(box, "workspace bounding box").toBeTruthy();
    expect(viewport, "viewport").toBeTruthy();
    const mid = (box?.x || 0) + (box?.width || 0) / 2;
    const vpMid = (viewport?.width || 0) / 2;
    expect(Math.abs(mid - vpMid)).toBeLessThan(90);
    expect(box?.width || 0).toBeLessThan((viewport?.width || 1600) * 0.85);
    expect(box?.width || 0).toBeGreaterThan(640);

    await page.getByTestId("audio-sfx-preset-footsteps").click();
    await expect(page.getByTestId("audio-sfx-prompt")).toHaveValue(/metal grating/i);
    await expect(page.getByTestId("audio-sfx-strength")).toHaveValue("Normal");

    const leftover = errors.filter(
      (line) => !/favicon|ResizeObserver|fonts\.gstatic|fonts\.googleapis|x-adept-deny-owner-writes|net::ERR_FAILED/i.test(line),
    );
    expect(leftover, leftover.join("\n")).toEqual([]);
  });
});
