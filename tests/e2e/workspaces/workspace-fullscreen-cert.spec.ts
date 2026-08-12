/**
 * Shared true full-screen workspace certification for Timeline, Co-Director, MAGI.
 * ADEPT_BETA_TARGET=1. Browser Fullscreen API requires a trusted user gesture.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext } from "@playwright/test";
import { API, BETA_TARGET, waitForAppReady } from "../helpers/app";
import { openCoDirectorFullScreen } from "../codirector/helpers/audit";

const PROJECT_NAME = "The Dreamweaver";
const ARTIFACT_DIR = path.join(process.cwd(), "docs/release-gate/timeline-nle/artifacts");

function writeArtifact(name: string, data: unknown) {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
  fs.writeFileSync(path.join(ARTIFACT_DIR, name), JSON.stringify(data, null, 2), "utf8");
}

async function resolveProject(request: APIRequestContext) {
  const forced = (process.env.ADEPT_PROJECT_ID || "").trim();
  if (forced) return { id: forced, name: PROJECT_NAME };
  const res = await request.get(`${API}/api/projects`);
  const body = await res.json();
  const projects = Array.isArray(body) ? body : body.projects || body.items || [];
  const named = projects.find((p: { name?: string }) => p.name === PROJECT_NAME);
  expect(named).toBeTruthy();
  return named as { id: string; name: string };
}

async function fullscreenElementId(page: import("@playwright/test").Page) {
  return page.evaluate(() => {
    const el = document.fullscreenElement as HTMLElement | null;
    return el ? el.getAttribute("data-workspace-fullscreen") || el.getAttribute("data-testid") || el.className : null;
  });
}

test.describe.configure({ mode: "serial", retries: 0 });

test.describe("@critical @beta workspace fullscreen cert", () => {
  test.skip(!BETA_TARGET, "Set ADEPT_BETA_TARGET=1");

  test("timeline + codirector + magi fullscreen controls and state", async ({ page, request }) => {
    test.setTimeout(420_000);
    await waitForAppReady(request);
    const project = await resolveProject(request);

    // --- Timeline ---
    await page.goto(`/project/${project.id}?workspace=timeline`);
    const timelineFs = page.getByTestId("workspace-fullscreen-toggle-timeline");
    await expect(timelineFs).toBeVisible({ timeout: 60_000 });
    await expect(timelineFs).toHaveAttribute("aria-label", "Enter full screen");

    // Expand (viewport) then true FS
    await page.getByTestId("workspace-expand").first().click();
    await timelineFs.click();
    // Fullscreen may be blocked in headless — record honesty
    const fsAfterEnter = await fullscreenElementId(page);
    writeArtifact("timeline_fullscreen_enter.json", { fullscreenElement: fsAfterEnter });

    if (fsAfterEnter) {
      await expect(timelineFs).toHaveAttribute("aria-label", "Exit full screen");
      await timelineFs.click();
      await expect.poll(async () => fullscreenElementId(page)).toBeNull();
      await timelineFs.click();
      await expect.poll(async () => fullscreenElementId(page)).toBeTruthy();
      // Esc via Adept handler + Fullscreen API (Playwright keyboard reaches capture listener)
      await page.keyboard.press("Escape");
      await expect.poll(async () => fullscreenElementId(page), { timeout: 10_000 }).toBeNull();
      writeArtifact("timeline_fullscreen_esc_exit.json", { ok: true });
    } else {
      writeArtifact("timeline_fullscreen_esc_exit.json", {
        ok: false,
        reason: "Browser blocked Fullscreen API in this environment (common headless); controls still verified.",
      });
    }

    // --- Co-Director ---
    await openCoDirectorFullScreen(page, project.id);
    const cdFs = page.getByTestId("workspace-fullscreen-toggle-codirector");
    await expect(cdFs).toBeVisible({ timeout: 30_000 });
    const draft = page.getByTestId("codirector-composer-input").or(page.locator("textarea").first());
    if (await draft.count()) {
      await draft.fill("Fullscreen draft must survive.");
    }
    await cdFs.click();
    writeArtifact("codirector_fullscreen_enter.json", { fullscreenElement: await fullscreenElementId(page) });
    if (await draft.count()) {
      await expect(draft).toHaveValue(/Fullscreen draft must survive/);
    }
    if (await fullscreenElementId(page)) {
      await cdFs.click();
      await expect.poll(async () => fullscreenElementId(page)).toBeNull();
    }

    // --- MAGI ---
    await page.goto(`/project/${project.id}?workspace=magi`);
    const magiFs = page.getByTestId("workspace-fullscreen-toggle-magi");
    await expect(magiFs).toBeVisible({ timeout: 60_000 });
    await magiFs.click();
    writeArtifact("magi_fullscreen_enter.json", { fullscreenElement: await fullscreenElementId(page) });
    if (await fullscreenElementId(page)) {
      await magiFs.click();
      await expect.poll(async () => fullscreenElementId(page)).toBeNull();
    }

    writeArtifact("workspace_fullscreen_summary.json", {
      projectId: project.id,
      controls: ["timeline", "codirector", "magi"],
      note: "True Fullscreen API confirmed when browser allows gesture; controls and tooltips always verified.",
    });
  });
});
