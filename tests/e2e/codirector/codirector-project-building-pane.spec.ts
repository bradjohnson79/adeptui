import { expect, test } from "@playwright/test";
import { createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";
import {
  TINY_MP4,
  TINY_PNG,
  TINY_WAV,
  openCoDirectorFullScreen,
  uploadProjectAsset,
} from "./helpers/audit";

test.describe("@critical @isolated codirector project building pane", () => {
  test.beforeEach(async ({ request }) => {
    await waitForAppReady(request);
  });

  test("every project building tab renders a real interface (Story, Script Writer, Storyboard, Character Creator, Library)", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    const project = await createTempProject(request, `Project Building Pane ${Date.now()}`);

    try {
      const imageAsset = await uploadProjectAsset(request, project.id, {
        name: "storyboard-frame.png",
        mimeType: "image/png",
        kind: "image",
        buffer: TINY_PNG,
        tag: "Coffee Shop Reference",
      });
      const videoAsset = await uploadProjectAsset(request, project.id, {
        name: "scene-take.mp4",
        mimeType: "video/mp4",
        kind: "video",
        buffer: TINY_MP4,
        tag: "Scene Take 01",
      });
      const audioAsset = await uploadProjectAsset(request, project.id, {
        name: "voice-sample.wav",
        mimeType: "audio/wav",
        kind: "audio",
        buffer: TINY_WAV,
        tag: "Mieke Voice Sample",
      });

      await openCoDirectorFullScreen(page, project.id);

      // --- Story tab ---
      await page.getByTestId("codirector-content-tab-story").click();
      await expect(page.getByTestId("codirector-content-story")).toBeVisible({ timeout: 30_000 });
      await expect(page.locator(".story-editor, .tiptap, [contenteditable='true']").first()).toBeVisible({ timeout: 30_000 });

      // --- Script Writer tab ---
      await page.getByTestId("codirector-content-tab-scriptwriter").click();
      await expect(page.getByTestId("codirector-content-scriptwriter")).toBeVisible({ timeout: 30_000 });
      await expect(
        page
          .getByTestId("scriptwriter-compact")
          .or(page.getByTestId("scriptwriter-compact-empty"))
          .or(page.getByTestId("scriptwriter-compact-error"))
          .first(),
      ).toBeVisible({ timeout: 30_000 });
      // No raw JSON dump in script writer
      await expect(page.getByTestId("codirector-content-scriptwriter")).not.toContainText('"document"');

      // --- Storyboard tab (script) ---
      await page.getByTestId("codirector-content-tab-script").click();
      await expect(page.getByTestId("codirector-content-script")).toBeVisible({ timeout: 30_000 });
      await expect(
        page
          .getByTestId("storyboard-compact")
          .or(page.getByTestId("storyboard-compact-empty"))
          .or(page.getByTestId("storyboard-compact-error"))
          .first(),
      ).toBeVisible({ timeout: 30_000 });
      // No raw dark empty canvas (the compact view renders content or explicit empty state text)
      await expect(page.getByTestId("codirector-content-script")).toContainText(
        /Storyboard|Open Storyboard|No storyboard frames/i,
      );

      // --- Character Creator tab ---
      await page.getByTestId("codirector-content-tab-characters").click();
      await expect(page.getByTestId("codirector-content-characters")).toBeVisible({ timeout: 30_000 });
      await expect(
        page
          .getByTestId("character-compact")
          .or(page.getByTestId("character-compact-empty"))
          .or(page.getByTestId("character-compact-error"))
          .first(),
      ).toBeVisible({ timeout: 30_000 });

      // --- Library tab ---
      await page.getByTestId("codirector-content-tab-library").click();
      await expect(page.getByTestId("codirector-content-library")).toBeVisible({ timeout: 30_000 });
      await expect(page.getByTestId("library-media-grid")).toBeVisible({ timeout: 30_000 });

      // No raw JSON dump (the previous behavior).
      await expect(page.getByTestId("codirector-content-library")).not.toContainText('"items"');
      await expect(page.getByTestId("codirector-content-library")).not.toContainText("assetId");
      await expect(page.getByTestId("codirector-content-library")).not.toContainText("HashPreview");

      // Filter chips present.
      await expect(page.getByTestId("library-filter-all")).toHaveClass(/is-active/);
      for (const f of ["images", "video", "audio", "documents"] as const) {
        await expect(page.getByTestId(`library-filter-${f}`)).toBeVisible();
      }

      // The uploaded assets render as cards of the right kind.
      await expect(page.getByTestId("library-card-image").first()).toBeVisible({ timeout: 30_000 });
      await expect(page.getByTestId("library-card-video").first()).toBeVisible({ timeout: 30_000 });
      await expect(page.getByTestId("library-card-audio").first()).toBeVisible({ timeout: 30_000 });

      // Friendly tag names should be visible, not raw UUIDs.
      await expect(page.getByTestId("codirector-content-library")).toContainText("Coffee Shop Reference");
      await expect(page.getByTestId("codirector-content-library")).toContainText("Scene Take 01");
      await expect(page.getByTestId("codirector-content-library")).toContainText("Mieke Voice Sample");
      // UUIDs (8-4-4-4-12) should not be the visible label of a card.
      const uuidPattern = /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/i;
      const cardTitles = page.locator(".library-media-grid__meta strong");
      const count = await cardTitles.count();
      for (let i = 0; i < count; i += 1) {
        const text = await cardTitles.nth(i).innerText();
        expect(text, `card title "${text}" must not be a raw UUID`).not.toMatch(uuidPattern);
      }

      // Filter to images only.
      await page.getByTestId("library-filter-images").click();
      await expect(page.getByTestId("library-filter-images")).toHaveClass(/is-active/);
      await expect(page.getByTestId("library-card-image")).toBeVisible();
      await expect(page.getByTestId("library-card-video")).toHaveCount(0);
      await expect(page.getByTestId("library-card-audio")).toHaveCount(0);

      // Filter to video only.
      await page.getByTestId("library-filter-video").click();
      await expect(page.getByTestId("library-filter-video")).toHaveClass(/is-active/);
      await expect(page.getByTestId("library-card-video")).toBeVisible();
      await expect(page.getByTestId("library-card-image")).toHaveCount(0);

      // Filter back to all and open the image preview modal.
      await page.getByTestId("library-filter-all").click();
      await page.getByTestId("library-card-image").first().click();
      const preview = page.getByRole("dialog", { name: /preview/i });
      await expect(preview).toBeVisible({ timeout: 20_000 });
      await expect(preview.locator("img")).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(preview).toHaveCount(0);

      // Documents filter (none expected) shows the empty-filter state, not a blank.
      await page.getByTestId("library-filter-documents").click();
      await expect(
        page
          .getByTestId("library-empty-filter")
          .or(page.locator(".library-media-grid__state"))
          .first(),
      ).toBeVisible({ timeout: 10_000 });

      observer.assertHealthyBrowser();

      void imageAsset;
      void videoAsset;
      void audioAsset;
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });
});
