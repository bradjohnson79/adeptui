import { expect, test } from "@playwright/test";
import { API, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";

const TINY_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC",
  "base64",
);

test.describe("Revision D Image Edit Studio", () => {
  test("Select and Remove Background controls exist", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, "Revision D Edit Studio");
    try {
      const upload = await request.post(`${API}/api/projects/${project.id}/assets`, {
        multipart: {
          file: { name: "still.png", mimeType: "image/png", buffer: TINY_PNG },
          tag: "edit_source",
          kind: "image",
        },
      });
      expect(upload.ok(), await upload.text()).toBeTruthy();
      await page.goto(`/project/${project.id}?workspace=image`, { waitUntil: "domcontentloaded", timeout: 60_000 });
      await expect(page.getByTestId("cinematic-image-studio")).toBeVisible({ timeout: 30_000 });
      await page.getByTestId("image-studio-edit-tab").click();
      await expect(page.getByTestId("image-edit-studio-title")).toBeVisible({ timeout: 30_000 });
      await expect(page.getByTestId("image-edit-select-subject")).toBeVisible();
      await expect(page.getByTestId("image-edit-remove-background")).toBeVisible();
      await expect(page.getByTestId("image-edit-protect")).toBeVisible();
      await expect(page.getByText(/SAM checkpoint|VGGT|JEPA embedding/i)).toHaveCount(0);
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("Timeline Inpaint discloses native video inpaint is unavailable", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, "Revision D Timeline Inpaint Disclosure");
    try {
      await page.goto(`/project/${project.id}?workspace=timeline`, { waitUntil: "domcontentloaded", timeout: 60_000 });
      await page.waitForTimeout(800);
      await page.evaluate(() => {
        window.dispatchEvent(
          new CustomEvent("adept-timeline-focus", { detail: { target: "viewer", openInpaint: true } }),
        );
      });
      await expect(page.getByTestId("timeline-inpaint-workspace")).toBeVisible({ timeout: 20_000 });
      await expect(page.getByTestId("timeline-inpaint-native-disclosure")).toContainText(/Native video inpaint is unavailable/i);
      await expect(page.getByTestId("timeline-inpaint-track")).toBeVisible();
    } finally {
      await deleteProject(request, project.id);
    }
  });
});
