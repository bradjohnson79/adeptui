/**
 * Live creator test — Script Writer simplification + Co-Director Story/Script access.
 *
 * Covers mission §17:
 *  Express: click "Untitled Script" → rename → save → reload → persists.
 *  Standard: simplified toolbar; Story routes to the Story workspace; add/edit/
 *    remove scene; revisions create/list; reload persistence.
 *  Co-Director Story/Script access + freshness + current-scene awareness are
 *  verified live against the running API by the mission probe
 *  (.runtime/_sw_codirector_live.json) and by
 *  studio-api/tests/test_codirector_story_script_access.py.
 *
 * Runs against the live Beta target (ADEPT_BETA_TARGET=1 → Vite :5173 + API :8758).
 */
import { expect, test } from "@playwright/test";

import { API, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";

const FOUNTAIN = [
  "INT. CLOCKWORK BRIDGE - DAY",
  "",
  "KORRI-X",
  "The compass spins toward NINEVOLTA.",
  "",
  "EXT. RUST DOCKS - NIGHT",
  "",
  "KORRI-X",
  "We sail at dawn.",
  "",
].join("\n");

test.describe("@mission @scriptwriter Script Writer simplification — live creator test", () => {
  test.beforeEach(async ({ request }) => {
    await waitForAppReady(request);
  });

  test("Express: title is editable inline and persists across reload", async ({ page, request }) => {
    const project = await createTempProject(request, `SW Express Title ${Date.now()}`);
    try {
      await page.goto(`/co-director?projectId=${project.id}&contentTab=scriptwriter`);
      await expect(page.getByTestId("scriptwriter-inline")).toBeVisible({ timeout: 45_000 });

      // Title shows the default and is an edit affordance, not static text.
      const display = page.getByTestId("sw-inline-title-display");
      await expect(display).toBeVisible();
      await expect(display).toContainText("Untitled Script");

      // Click → inline input; type; Enter saves. The click can land during
      // initial bundle hydration and be swallowed by a re-render, so confirm
      // the editor actually opened (retry the click once if needed).
      const input = page.getByTestId("sw-inline-title");
      for (let attempt = 0; attempt < 3; attempt++) {
        await display.click();
        try {
          await input.waitFor({ state: "visible", timeout: 4_000 });
          break;
        } catch {
          if (attempt === 2) throw new Error("Express title editor did not open after 3 clicks");
        }
      }
      await input.fill("The Adept Chronicles");
      const renameOk = page.waitForResponse(
        (r) => r.url().includes("/scriptwriter/documents/") && r.url().endsWith("/title") && r.status() === 200,
        { timeout: 15_000 },
      );
      await input.press("Enter");
      await renameOk;
      await expect(display).toContainText("The Adept Chronicles");
      await expect(page.getByTestId("sw-inline-save-state")).toHaveText("Saved", { timeout: 15_000 });

      // Canonical authority: the API bundle carries the new title.
      const bundle = await (await request.get(`${API}/api/projects/${project.id}/scriptwriter`)).json();
      expect(bundle.document.title).toBe("The Adept Chronicles");

      // Survives reload.
      await page.reload();
      await expect(page.getByTestId("scriptwriter-inline")).toBeVisible({ timeout: 45_000 });
      await expect(page.getByTestId("sw-inline-title-display")).toContainText("The Adept Chronicles");

      // Escape cancels an edit without saving.
      await page.getByTestId("sw-inline-title-display").click();
      const input2 = page.getByTestId("sw-inline-title");
      await input2.fill("Discarded Name");
      await input2.press("Escape");
      await expect(page.getByTestId("sw-inline-title-display")).toContainText("The Adept Chronicles");
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("Standard: simplified toolbar, Story routing, scenes, revisions, reload", async ({ page, request }) => {
    const project = await createTempProject(request, `SW Standard ${Date.now()}`);
    try {
      // Seed a two-scene screenplay through the canonical API.
      const created = await request.post(`${API}/api/projects/${project.id}/scriptwriter/documents`);
      expect(created.ok()).toBeTruthy();
      const docId = (await created.json()).document.id as string;
      const imported = await request.post(
        `${API}/api/projects/${project.id}/scriptwriter/documents/${docId}/import`,
        { data: { text: FOUNTAIN, format: "fountain" } },
      );
      expect(imported.ok()).toBeTruthy();

      await page.goto(`/project/${project.id}?workspace=scriptwriter`);
      await expect(page.getByTestId("scriptwriter-studio")).toBeVisible({ timeout: 45_000 });

      // ── Simplified toolbar: exactly the screenplay controls ──
      for (const id of [
        "scriptwriter-title-display",
        "scriptwriter-view-script",
        "scriptwriter-story",
        "scriptwriter-insert-scene",
        "scriptwriter-remove-scene",
        "scriptwriter-revisions",
        "scriptwriter-undo",
        "scriptwriter-redo",
      ]) {
        await expect(page.getByTestId(id)).toBeVisible();
      }
      // Removed planning clutter is gone from the DOM entirely.
      for (const id of [
        "scriptwriter-outline",
        "scriptwriter-cards",
        "scriptwriter-command-input",
        "scriptwriter-convert-beats",
      ]) {
        await expect(page.getByTestId(id)).toHaveCount(0);
      }

      // ── Title editing (shared authority with Express) ──
      const titleDisplay = page.getByTestId("scriptwriter-title-display");
      const titleInput = page.getByTestId("scriptwriter-title");
      for (let attempt = 0; attempt < 3; attempt++) {
        await titleDisplay.click();
        try {
          await titleInput.waitFor({ state: "visible", timeout: 4_000 });
          break;
        } catch {
          if (attempt === 2) throw new Error("Standard title editor did not open after 3 clicks");
        }
      }
      await titleInput.fill("The Adept Chronicles");
      const renameOk = page.waitForResponse(
        (r) => r.url().includes("/scriptwriter/documents/") && r.url().endsWith("/title") && r.status() === 200,
        { timeout: 15_000 },
      );
      await titleInput.press("Enter");
      await renameOk;
      await expect(titleDisplay).toContainText("The Adept Chronicles");
      const bundle = await (await request.get(`${API}/api/projects/${project.id}/scriptwriter`)).json();
      expect(bundle.document.title).toBe("The Adept Chronicles");

      // ── Story tab stays in Script Writer (canonical story document) ──
      await page.getByTestId("scriptwriter-story").click();
      await expect(page).toHaveURL(/workspace=scriptwriter/);
      await expect(page).not.toHaveURL(/\/co-director/);
      await expect(page.getByTestId("scriptwriter-story-document")).toBeVisible({ timeout: 20_000 });
      await expect(page.getByTestId("scriptwriter-navigator")).toBeHidden();
      await page.locator('[data-testid="scriptwriter-story-editor"] .ProseMirror').click();
      await page.keyboard.type("Native story document lives here.");
      await expect(page.getByTestId("scriptwriter-save-state")).toContainText(/^saved/i, { timeout: 20_000 });
      const entries = await (await request.get(`${API}/api/projects/${project.id}/story-entries`)).json();
      expect(JSON.stringify(entries)).toMatch(/Native story document lives here/i);
      await page.getByTestId("scriptwriter-view-script").click();
      await expect(page.getByTestId("scriptwriter-navigator")).toBeVisible();
      await expect(page.getByTestId("scriptwriter-story-document")).toHaveCount(0);

      // ── Scene management: add after active, edit, remove ──
      const navRows = page.locator("[data-testid^='scriptwriter-nav-']:not([data-testid*='-up-']):not([data-testid*='-down-'])");
      await expect(navRows).toHaveCount(2);
      await navRows.first().click(); // select scene 1 → Add Scene inserts after it
      await page.getByTestId("scriptwriter-insert-scene").click();
      await expect(navRows).toHaveCount(3);
      // Position, not just count: the new scene lands AFTER the active scene,
      // between CLOCKWORK BRIDGE and RUST DOCKS (never appended at the end).
      await expect(navRows.nth(0)).toContainText(/clockwork bridge/i);
      await expect(navRows.nth(1)).toContainText(/location/i);
      await expect(navRows.nth(2)).toContainText(/rust docks/i);

      // Edit the screenplay text (tiptap surface) and let autosave land.
      await page.locator(".sw-page .ProseMirror").first().click();
      await page.keyboard.press("End");
      await page.keyboard.type(" The crew cheers.");
      await expect(page.getByTestId("scriptwriter-save-state")).toContainText(/^saved/i, { timeout: 20_000 });

      // Remove the scene we just added (confirm accepted).
      page.on("dialog", (d) => void d.accept());
      await navRows.nth(1).click();
      await page.getByTestId("scriptwriter-remove-scene").click();
      await expect(navRows).toHaveCount(2);
      await expect(navRows.nth(0)).toContainText(/clockwork bridge/i);
      await expect(navRows.nth(1)).toContainText(/rust docks/i);

      // ── Revisions: first-class view, create + list, survives reload ──
      await page.getByTestId("scriptwriter-revisions").click();
      await expect(page.getByTestId("scriptwriter-revisions-view")).toBeVisible();
      await page.getByTestId("scriptwriter-create-revision").click();
      const revItems = page.locator("[data-testid='scriptwriter-revisions-list'] li");
      await expect(revItems).toHaveCount(1, { timeout: 15_000 });
      // Compare is folded under Revisions, not a top-level mode.
      await expect(page.getByTestId("scriptwriter-compare")).toBeVisible();

      // ── Reload: title, scenes, revision all persist ──
      await page.reload();
      await expect(page.getByTestId("scriptwriter-studio")).toBeVisible({ timeout: 45_000 });
      await expect(page.getByTestId("scriptwriter-title-display")).toContainText("The Adept Chronicles");
      await expect(navRows).toHaveCount(2);
      await page.getByTestId("scriptwriter-revisions").click();
      await expect(page.locator("[data-testid='scriptwriter-revisions-list'] li")).toHaveCount(1);
    } finally {
      await deleteProject(request, project.id);
    }
  });
});
