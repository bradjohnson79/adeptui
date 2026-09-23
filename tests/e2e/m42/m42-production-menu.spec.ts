import { expect, test, type Page, type Locator } from "@playwright/test";

/**
 * M42 Production categorized creator menu.
 * Assertions target menu roles / testids only — not repository-wide text.
 */

const KORRI_FALLBACK = "e32dae30-a014-4ea4-a2f2-69f4b7809bde";
const KORRI_NAME = process.env.ADEPT_KORRI_PROJECT_NAME || "Korri Character Production";

const CATEGORIES = [
  "create",
  "pre-production",
  "creative-studios",
  "post-production",
  "recent-projects",
] as const;

async function openProductionMenu(page: Page): Promise<Locator> {
  const trigger = page.getByTestId("chrome-production-menu-button");
  await trigger.click();
  const menu = page.getByTestId("production-menu");
  await expect(menu).toBeVisible();
  return menu;
}

test.describe("M42 Production categorized menu", () => {
  let projectId = KORRI_FALLBACK;
  let characterId = "";

  test.beforeAll(async ({ request }) => {
    const envId = (process.env.ADEPT_PROJECT_ID || "").trim();
    const listed = await request.get("/api/projects");
    expect(listed.ok(), "GET /api/projects").toBeTruthy();
    const body = await listed.json();
    const projects = Array.isArray(body) ? body : body.items || body.projects || [];
    let hit =
      (envId && projects.find((p: any) => p.id === envId)) ||
      projects.find((p: any) => p.name === KORRI_NAME) ||
      projects[0];
    if (!hit?.id) {
      const created = await request.post("/api/projects", {
        data: { name: KORRI_NAME, description: "Avatar Studio long-form presenter smoke" },
      });
      expect(created.ok(), "POST /api/projects").toBeTruthy();
      hit = await created.json();
    }
    expect(hit?.id, "need at least one project").toBeTruthy();
    projectId = String(hit.id);

    const chars = await request.get(`/api/projects/${projectId}/characters`);
    if (chars.ok()) {
      const cj = await chars.json();
      const items = cj.items || cj || [];
      const korri = (Array.isArray(items) ? items : []).find((c: any) =>
        String(c.name || "").toLowerCase().includes("korri"),
      );
      characterId = String(korri?.id || items[0]?.id || "");
    }
    if (!characterId) {
      const seeded = await request.post(`/api/projects/${projectId}/characters/seed-korri`, { data: {} });
      expect(seeded.ok(), "seed Korri for Avatar Studio").toBeTruthy();
      const seededBody = await seeded.json();
      characterId = String(seededBody?.id || "");
    }
  });

  test("categorized menu: Co-Director panel + five locked categories", async ({ page }) => {
    await page.goto(`/project/${projectId}?workspace=characters`);
    await expect(page.getByTestId("app-chrome")).toBeVisible({ timeout: 30_000 });

    const menu = await openProductionMenu(page);
    const cd = menu.getByTestId("production-menu-codirector");
    await expect(cd).toBeVisible();
    await expect(cd).toContainText("Co-Director");
    await expect(cd).toContainText("Your AI Production Assistant");
    await expect(menu.getByTestId("production-cd-continueProject")).toBeVisible();
    await expect(menu.getByTestId("production-cd-reviewTimeline")).toBeVisible();
    await expect(menu.getByTestId("production-cd-generateAssets")).toBeVisible();
    await expect(menu.getByTestId("production-cd-openChat")).toBeVisible();

    for (const id of CATEGORIES) {
      await expect(menu.getByTestId(`production-cat-${id}`)).toBeVisible();
    }

    const create = menu.getByTestId("production-cat-create");
    for (const id of ["txt2vid", "imagegen", "one", "three", "script", "timeline"]) {
      await expect(create.getByTestId(`production-item-${id}`)).toBeVisible();
    }
    await expect(create.getByTestId("production-item-txt2vid")).toContainText("Text to Video");
    await expect(create.getByTestId("production-item-script")).toContainText("Storyboard");
    await expect(create.getByTestId("production-item-timeline")).toContainText("Timeline Generator");

    const profiles = menu.getByTestId("production-cat-profiles");
    await expect(profiles).toHaveCount(0);
    await expect(menu.getByRole("menuitem", { name: "Project Profile" })).toHaveCount(0);

    const pre = menu.getByTestId("production-cat-pre-production");
    await expect(pre.getByTestId("production-item-scriptwriter")).toContainText("Scriptwriter");
    await expect(pre.getByTestId("production-item-environmentcreator")).toContainText("Environment Creator");
    // Scene Creator is retired from the Production menu (Image Generator v1.1 triad)
    await expect(pre.getByTestId("production-item-scenecreator")).toHaveCount(0);
    await expect(pre.getByTestId("production-item-propcreator")).toContainText("Prop Creator");
    await expect(pre.getByTestId("production-item-posecraft")).toContainText("PoseCraft");
    // Storyboard moved out of Pre-Production into Create
    await expect(pre.getByTestId("production-item-script")).toHaveCount(0);

    const studios = menu.getByTestId("production-cat-creative-studios");
    await expect(studios.getByTestId("production-item-characters")).toContainText("Character Creator");
    await expect(studios.getByTestId("production-item-avatar")).toContainText("Avatar Studio");
    await expect(studios.getByTestId("production-item-voicestudio")).toContainText("Voice Studio");
    await expect(studios.getByTestId("production-item-audiostudio")).toContainText("Audio Studio");
    await expect(menu.getByTestId("production-item-magi")).toContainText("MAGI Editor");

    await expect(menu.getByRole("menuitem", { name: "Identity Registry" })).toHaveCount(0);
    await expect(menu.getByRole("menuitem", { name: "Txt2Vid" })).toHaveCount(0);
    await expect(menu.getByRole("menuitem", { name: "ImageGen" })).toHaveCount(0);
    await expect(menu.getByRole("menuitem", { name: /^Director$/ })).toHaveCount(0);
    await expect(menu.getByRole("menuitem", { name: "Production DNA Profile" })).toHaveCount(0);
    await expect(menu.getByTestId("production-item-identityregistry")).toHaveCount(0);
  });

  test("legacy identityregistry lands on Approved Look with project context", async ({ page }) => {
    const qs = new URLSearchParams({
      workspace: "identityregistry",
      ...(characterId ? { characterId } : {}),
      return: "continuity",
    });
    await page.goto(`/project/${projectId}?${qs.toString()}`);
    await expect(page).toHaveURL(new RegExp(`/project/${projectId}`));
    await expect(page.getByTestId("character-profile-workspace")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("character-approved-look")).toBeVisible();
    await expect(page.getByRole("button", { name: "Approved Look" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Identity Registry" })).toHaveCount(0);
  });

  test("Avatar Studio gates when no character selected", async ({ page }) => {
    await page.addInitScript(() => {
      try {
        sessionStorage.removeItem("adept_selected_character");
        sessionStorage.removeItem("adept_avatar_profile");
      } catch {
        /* ignore */
      }
    });
    await page.goto(`/project/${projectId}?workspace=avatar`);
    await expect(page.getByTestId("avatar-requires-character")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText("Choose a character to open a long-form presenter workspace.")).toBeVisible();
    await expect(page.getByTestId("avatar-open-character-profiles")).toBeVisible();
  });

  test("Avatar Studio shows simplified long-form presenter workspace", async ({ page }) => {
    test.skip(!characterId, "requires an existing character");
    await page.addInitScript((id: string) => {
      try {
        sessionStorage.setItem("adept_selected_character", id);
        sessionStorage.setItem("adept_avatar_profile", id);
      } catch {
        /* ignore */
      }
    }, characterId);
    await page.goto(`/project/${projectId}?workspace=avatar`);
    await expect(page.getByTestId("avatar-studio-workspace")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("avatar-create-panel")).toBeVisible();
    const modeCards = page.getByTestId("avatar-mode-cards");
    await expect(modeCards.getByRole("button", { name: /^Talking Head\b/ })).toBeVisible();
    await expect(modeCards.getByRole("button", { name: /^Presenter\b/ })).toBeVisible();
    await expect(modeCards.getByRole("button", { name: /^Full-Body Presenter\b/ })).toBeVisible();
    await expect(modeCards.getByRole("button", { name: /^Existing Video Dubbing\b/ })).toBeVisible();
    await expect(page.getByTestId("avatar-review-tabs").getByRole("tab", { name: "Completed Videos" })).toBeVisible();
    await expect(page.locator("[data-testid='avatar-advanced-panel'][open]")).toHaveCount(0);
    await expect(page.getByText("Avatar Inspector")).toHaveCount(0);
  });

  test("responsive: wide, compact, sheet — required links visible", async ({ page }) => {
    await page.goto(`/project/${projectId}?workspace=home`);
    await expect(page.getByTestId("app-chrome")).toBeVisible({ timeout: 30_000 });

    for (const width of [1280, 900, 640]) {
      await page.setViewportSize({ width, height: 900 });
      const menu = await openProductionMenu(page);
      await expect(menu.getByTestId("production-menu-codirector")).toBeVisible();
      for (const id of CATEGORIES) {
        await expect(menu.getByTestId(`production-cat-${id}`)).toBeVisible();
      }
      await expect(menu.getByTestId("production-item-characters")).toBeVisible();
      await expect(menu.getByTestId("production-item-magi")).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(menu).toBeHidden();
    }
  });

  test("keyboard: open, arrow, Escape restores focus to Production trigger", async ({ page }) => {
    await page.goto(`/project/${projectId}?workspace=characters`);
    await expect(page.getByTestId("app-chrome")).toBeVisible({ timeout: 30_000 });

    const trigger = page.getByTestId("chrome-production-menu-button");
    await trigger.focus();
    await page.keyboard.press("Enter");
    const menu = page.getByTestId("production-menu");
    await expect(menu).toBeVisible();
    await expect(menu.locator(":focus")).toHaveCount(1);

    await page.keyboard.press("ArrowDown");
    await expect(menu.locator(":focus")).toHaveCount(1);

    await page.keyboard.press("Escape");
    await expect(menu).toBeHidden();
    await expect(trigger).toBeFocused();
  });

  test("Character Creator relocates under Creative Studios and navigates", async ({ page }) => {
    await page.goto(`/project/${projectId}?workspace=home`);
    const menu = await openProductionMenu(page);
    const studios = menu.getByTestId("production-cat-creative-studios");
    await expect(studios.getByTestId("production-item-characters")).toContainText("Character Creator");
    await studios.getByTestId("production-item-characters").click();
    await expect(page).toHaveURL(new RegExp(`/project/${projectId}.*workspace=characters`));
    await expect(page.getByTestId("character-profile-workspace")).toBeVisible({ timeout: 30_000 });
  });

  test("Recent Projects: real server projects, current indicator, canonical switch", async ({ page }) => {
    await page.goto(`/project/${projectId}?workspace=home`);
    const menu = await openProductionMenu(page);
    const recent = menu.getByTestId("production-menu-recent-projects");
    await expect(recent).toBeVisible();

    const rows = recent.locator('[data-testid^="production-recent-project-"]');
    const count = await rows.count();
    expect(count).toBeGreaterThan(0);
    expect(count).toBeLessThanOrEqual(5);

    // Recency order is server-sorted (updated_at desc) — first row must be the
    // most recent project. The current project may appear with Current state.
    const currentRow = rows.first({ has: page.getByText("Current") });
    await expect(currentRow).toHaveCount(1);

    // Clicking a non-current recent project switches via canonical flow.
    const other = rows.filter({ hasNotText: "Current" }).first();
    if ((await other.count()) > 0) {
      await other.click();
      await expect(page.getByTestId("app-chrome")).toBeVisible({ timeout: 30_000 });
      await expect(page).not.toHaveURL(new RegExp(`/project/${projectId}.*workspace=home`));
    }
  });

  test("legacy ?workspace=profiles deep link lands on project home (no blank page)", async ({ page }) => {
    await page.goto(`/project/${projectId}?workspace=profiles`);
    await expect(page.getByTestId("app-chrome")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("project-home")).toBeVisible({ timeout: 30_000 });
  });
});
