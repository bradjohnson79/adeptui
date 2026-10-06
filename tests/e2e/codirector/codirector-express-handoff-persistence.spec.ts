import { expect, test } from "@playwright/test";
import { waitForAppReady } from "../helpers/app";
import { openCoDirectorFullScreen } from "./helpers/audit";

const PROJECT_ID = "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
const SCENE_ID = "ae8e5699-a5d8-4b9b-ad8e-0003d81d3639";

const EXPRESS_TABS: Array<{ tab: string; panel: string }> = [
  { tab: "wiki", panel: "codirector-content-wiki" },
  { tab: "notes", panel: "codirector-content-notes" },
  { tab: "story", panel: "codirector-content-story" },
  { tab: "scriptwriter", panel: "codirector-content-scriptwriter" },
  { tab: "characters", panel: "codirector-content-characters" },
  { tab: "voice_creator", panel: "codirector-content-voice-creator" },
  { tab: "prop_creator", panel: "codirector-content-prop-creator" },
  { tab: "spatial_map", panel: "codirector-content-spatial-map" },
  { tab: "scene_creator", panel: "codirector-content-scene-creator" },
  { tab: "timeline", panel: "codirector-content-timeline" },
  { tab: "library", panel: "codirector-content-library" },
];

test.use({
  video: "on",
  trace: "on",
});

async function expectBoundExpress(page: import("@playwright/test").Page) {
  const shell = page.getByTestId("codirector-fullscreen-shell");
  await expect(shell).toBeVisible({ timeout: 45_000 });
  await expect(shell).toHaveAttribute("data-project-id", PROJECT_ID, { timeout: 30_000 });
  await expect(shell).toHaveAttribute("data-session-status", /bound|Connected/i);
  await expect(page.getByTestId("codirector-no-project-banner")).toHaveCount(0);
}

test.describe("@critical Co-Director Express handoff + persistence", () => {
  test.beforeEach(async ({ request }) => {
    await waitForAppReady(request);
  });

  test("Korri Anadriya Express tabs, Standard handoffs, bound return, and reload", async ({ page }) => {
    await openCoDirectorFullScreen(page, PROJECT_ID, { sceneId: SCENE_ID, workspace: "timeline" });
    await expectBoundExpress(page);
    await expect(page.getByTestId("codirector-fullscreen-shell")).toHaveAttribute("data-scene-id", SCENE_ID);

    for (const { tab, panel } of EXPRESS_TABS) {
      await page.getByTestId(`codirector-content-tab-${tab}`).click();
      await expect(page.getByTestId(panel)).toBeVisible({ timeout: 30_000 });
      await expectBoundExpress(page);
      await expect(page.getByTestId("codirector-fullscreen-shell")).toHaveAttribute("data-project-id", PROJECT_ID);
    }

    await page.getByTestId("codirector-content-tab-scene_creator").click();
    await expect(page.getByTestId("scene-creator-open-standard")).toBeEnabled();
    await page.getByTestId("scene-creator-open-standard").click();
    await expect(page).toHaveURL(new RegExp(`/project/${PROJECT_ID}\\?.*workspace=scenecreator`), {
      timeout: 30_000,
    });
    await expect(page).toHaveURL(new RegExp(`sceneId=${SCENE_ID}`));
    const scenePopup = page.getByTestId("codirector-shell");
    await expect(scenePopup).toBeVisible({ timeout: 30_000 });
    await expect(scenePopup).toHaveAttribute("data-project-id", PROJECT_ID);
    await expect(page.getByTestId("codirector-no-project-banner")).toHaveCount(0);

    await page.getByTestId("codirector-expand-button").click();
    await expectBoundExpress(page);
    await expect(page).toHaveURL(new RegExp(`/co-director\\?.*projectId=${PROJECT_ID}`));

    await page.getByTestId("codirector-content-tab-timeline").click();
    await expect(page.getByTestId("timeline-open-standard")).toBeEnabled();
    await page.getByTestId("timeline-open-standard").click();
    await expect(page).toHaveURL(new RegExp(`/project/${PROJECT_ID}\\?.*workspace=timeline`), {
      timeout: 30_000,
    });
    await expect(page).toHaveURL(new RegExp(`sceneId=${SCENE_ID}`));
    const timelinePopup = page.getByTestId("codirector-shell");
    await expect(timelinePopup).toBeVisible({ timeout: 30_000 });
    await expect(timelinePopup).toHaveAttribute("data-project-id", PROJECT_ID);
    await expect(timelinePopup).toHaveAttribute("data-scene-id", SCENE_ID);
    await expect(page.getByTestId("codirector-no-project-banner")).toHaveCount(0);

    await page.getByTestId("codirector-expand-button").click();
    await expectBoundExpress(page);

    await page.getByTestId("codirector-content-tab-library").click();
    await expect(page.getByTestId("codirector-content-library")).toBeVisible({ timeout: 30_000 });
    await expectBoundExpress(page);

    await page.reload();
    await expectBoundExpress(page);
    await expect(page.getByTestId("codirector-fullscreen-shell")).toHaveAttribute("data-project-id", PROJECT_ID);
    await expect(page.getByTestId("codirector-fullscreen-shell")).toHaveAttribute("data-scene-id", SCENE_ID);
  });
});
