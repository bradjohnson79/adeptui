import { expect, test, type Page } from "@playwright/test";
import { createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";
import {
  TINY_MP4,
  TINY_PNG,
  TINY_WAV,
  openCoDirectorFullScreen,
  uploadProjectAsset,
} from "./helpers/audit";

async function openLibraryBrowser(page: Page) {
  await page.getByRole("button", { name: "Choose from Library" }).click();
  const dialog = page.getByRole("dialog", { name: /Select from Project Library/i });
  await expect(dialog).toBeVisible({ timeout: 20_000 });
  return dialog;
}

test.describe("@critical @isolated codirector library browser", () => {
  test.beforeEach(async ({ request }) => {
    await waitForAppReady(request);
  });

  test("empty project library opens as a large creator-friendly modal and closes on Escape", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    const project = await createTempProject(request, `CoDir Library Empty ${Date.now()}`);

    try {
      await openCoDirectorFullScreen(page, project.id);
      const dialog = await openLibraryBrowser(page);

      const box = await dialog.boundingBox();
      expect(box?.width ?? 0).toBeGreaterThanOrEqual(700);
      await expect(page.getByTestId("codirector-library-filter-all")).toHaveClass(/is-active/);
      await expect(page.getByTestId("codirector-library-selected-count")).toContainText(/No assets selected yet/i);
      await expect(dialog).toContainText(/No library items yet/i);
      await expect(dialog).toContainText(/Add images, video, audio, or documents/i);

      await page.keyboard.press("Escape");
      await expect(page.getByTestId("codirector-library-browser")).toHaveCount(0);

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("filters images, video, and audio and cancel leaves attachments empty", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    const project = await createTempProject(request, `CoDir Library Filters ${Date.now()}`);

    try {
      const imageAsset = await uploadProjectAsset(request, project.id, {
        name: "dreamweaver-library-image.png",
        mimeType: "image/png",
        kind: "image",
        buffer: TINY_PNG,
        tag: "Dreamweaver Image",
      });
      const videoAsset = await uploadProjectAsset(request, project.id, {
        name: "dreamweaver-library-video.mp4",
        mimeType: "video/mp4",
        kind: "video",
        buffer: TINY_MP4,
        tag: "Dreamweaver Video",
      });
      const audioAsset = await uploadProjectAsset(request, project.id, {
        name: "dreamweaver-library-audio.wav",
        mimeType: "audio/wav",
        kind: "audio",
        buffer: TINY_WAV,
        tag: "Dreamweaver Audio",
      });

      await openCoDirectorFullScreen(page, project.id);
      const dialog = await openLibraryBrowser(page);

      const imageCard = page.getByTestId(`codirector-library-asset-${imageAsset.id}`);
      const videoCard = page.getByTestId(`codirector-library-asset-${videoAsset.id}`);
      const audioCard = page.getByTestId(`codirector-library-asset-${audioAsset.id}`);

      await expect(imageCard).toBeVisible({ timeout: 20_000 });
      await expect(videoCard).toBeVisible({ timeout: 20_000 });
      await expect(audioCard).toBeVisible({ timeout: 20_000 });

      await page.getByTestId("codirector-library-filter-images").click();
      await expect(page.getByTestId("codirector-library-filter-images")).toHaveClass(/is-active/);
      await expect(imageCard).toBeVisible();
      await expect(videoCard).toHaveCount(0);
      await expect(audioCard).toHaveCount(0);

      await page.getByTestId("codirector-library-filter-video").click();
      await expect(page.getByTestId("codirector-library-filter-video")).toHaveClass(/is-active/);
      await expect(videoCard).toBeVisible();
      await expect(imageCard).toHaveCount(0);
      await expect(audioCard).toHaveCount(0);

      await page.getByTestId("codirector-library-filter-audio").click();
      await expect(page.getByTestId("codirector-library-filter-audio")).toHaveClass(/is-active/);
      await expect(audioCard).toBeVisible();
      await expect(imageCard).toHaveCount(0);
      await expect(videoCard).toHaveCount(0);

      await audioCard.click();
      await expect(page.getByTestId("codirector-library-selected-count")).toContainText(/1 asset selected/i);
      await page.getByTestId("codirector-library-cancel").click();

      await expect(page.getByTestId("codirector-library-browser")).toHaveCount(0);
      await expect(page.getByTestId("codirector-attachment-tray")).toHaveCount(0);
      await expect(dialog).toHaveCount(0);

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });
});
