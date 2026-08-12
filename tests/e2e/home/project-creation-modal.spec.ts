import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { API, BETA_TARGET, resetLiveBetaTestSurface, waitForAppReady } from "../helpers/app";

const ARTIFACT_DIR = path.join("docs", "release-gate", "home", "artifacts", "project-creation-modal");
const MANUAL_HANDOFF_ID = "77a4b96c-8e3f-4501-897c-51bab99bedb7";
const MANUAL_HANDOFF_NAME = "Manual Beta Handoff";
const RUN_ID = `PROJECT-CREATION-MODAL-${new Date().toISOString().replace(/[:.]/g, "-")}`;

type ProjectSummary = {
  id: string;
  name: string;
  archived?: number;
};

function ensureArtifactDir() {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
}

function uniqueIds(ids: Iterable<string>) {
  return Array.from(new Set(Array.from(ids).filter(Boolean)));
}

async function gotoHome(page: Page) {
  await page.goto("/");
  await expect(page.getByTestId("generation-studio-home")).toBeVisible({ timeout: 30_000 });
}

async function listProjects(request: APIRequestContext): Promise<ProjectSummary[]> {
  const res = await request.get(`${API}/api/projects`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return (await res.json()) as ProjectSummary[];
}

async function createProject(request: APIRequestContext, name: string): Promise<ProjectSummary> {
  const res = await request.post(`${API}/api/projects`, { data: { name } });
  expect(res.ok(), await res.text()).toBeTruthy();
  return (await res.json()) as ProjectSummary;
}

async function deleteProjectIfPresent(request: APIRequestContext, projectId: string) {
  const res = await request.delete(`${API}/api/projects/${projectId}`);
  if (res.status() === 404) return;
  expect(res.ok(), await res.text()).toBeTruthy();
}

async function getProject(request: APIRequestContext, projectId: string) {
  const res = await request.get(`${API}/api/projects/${projectId}`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return (await res.json()) as { id: string; name: string };
}

async function withZeroEligibleProjects(page: Page, run: () => Promise<void>) {
  const routeHandler = async (route: Parameters<Page["route"]>[1] extends infer T ? T : never) => {
    const req = route.request();
    const url = new URL(req.url());
    if (req.method() === "GET" && url.pathname === "/api/projects") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
      return;
    }
    await route.continue();
  };
  await page.route("**/api/projects", routeHandler);
  try {
    await run();
  } finally {
    await page.unroute("**/api/projects", routeHandler);
  }
}

async function openChromeCreateProject(page: Page) {
  await page.getByRole("button", { name: /^Project$/ }).click();
  await page.getByRole("menuitem", { name: "Create project" }).click();
  await expect(page.getByTestId("create-project-modal-panel")).toBeVisible({ timeout: 15_000 });
}

async function assertModalWithinViewport(page: Page) {
  const panel = page.getByTestId("create-project-modal-panel");
  const metrics = await panel.evaluate((node) => {
    const rect = node.getBoundingClientRect();
    return {
      top: rect.top,
      bottom: rect.bottom,
      left: rect.left,
      right: rect.right,
      viewportWidth: window.innerWidth,
      viewportHeight: window.innerHeight,
    };
  });
  expect(metrics.top).toBeGreaterThanOrEqual(-1);
  expect(metrics.left).toBeGreaterThanOrEqual(-1);
  expect(metrics.bottom).toBeLessThanOrEqual(metrics.viewportHeight + 1);
  expect(metrics.right).toBeLessThanOrEqual(metrics.viewportWidth + 1);
}

async function assertBodyScrollable(page: Page) {
  const body = page.getByTestId("create-project-modal-body");
  const metrics = await body.evaluate((el) => ({
    clientHeight: el.clientHeight,
    scrollHeight: el.scrollHeight,
    overflowY: getComputedStyle(el).overflowY,
  }));
  expect(metrics.scrollHeight).toBeGreaterThan(metrics.clientHeight);
  expect(["auto", "scroll"]).toContain(metrics.overflowY);
  return body;
}

async function assertFooterReachable(page: Page) {
  await expect(page.getByTestId("create-project-submit")).toBeVisible();
  await expect(page.getByTestId("create-project-cancel")).toBeVisible();
  const footerVisible = await page.getByTestId("create-project-submit").evaluate((el) => {
    const rect = el.getBoundingClientRect();
    return rect.top >= 0 && rect.bottom <= window.innerHeight + 1;
  });
  expect(footerVisible).toBeTruthy();
}

async function assertPageBackgroundLocked(page: Page) {
  const locked = await page.evaluate(() => ({
    bodyOverflow: getComputedStyle(document.body).overflow,
    bodyInlineOverflow: document.body.style.overflow,
  }));
  expect(locked.bodyInlineOverflow === "hidden" || locked.bodyOverflow === "hidden").toBeTruthy();
}

async function runExpandedContentScroll(page: Page, label: string) {
  const panel = page.getByTestId("create-project-modal-panel");
  await expect(panel).toBeVisible();
  const beforeBox = await panel.boundingBox();
  expect(beforeBox).toBeTruthy();
  await assertPageBackgroundLocked(page);

  await page.getByTestId("create-project-optional-toggle").click();
  await expect(page.getByTestId("create-project-optional-panel")).toBeVisible();
  await assertModalWithinViewport(page);
  const body = await assertBodyScrollable(page);

  await body.evaluate((el) => {
    el.scrollTop = el.scrollHeight;
  });
  await expect(page.getByTestId("create-project-optional-last-control")).toBeVisible();
  const lastControlVisible = await page.getByTestId("create-project-optional-last-control").evaluate((el) => {
    const rect = el.getBoundingClientRect();
    const bodyEl = document.querySelector('[data-testid="create-project-modal-body"]');
    if (!bodyEl) return false;
    const bodyRect = bodyEl.getBoundingClientRect();
    return rect.bottom <= bodyRect.bottom + 2 && rect.top >= bodyRect.top - 2;
  });
  expect(lastControlVisible).toBeTruthy();
  await assertFooterReachable(page);

  const maxScroll = await body.evaluate((el) => el.scrollHeight - el.clientHeight);
  expect(maxScroll).toBeGreaterThan(40);

  await body.evaluate((el) => {
    el.scrollTop = 0;
  });
  await body.focus();
  await page.keyboard.press("PageDown");
  const afterPageDown = await body.evaluate((el) => el.scrollTop);
  expect(afterPageDown).toBeGreaterThan(0);

  await body.evaluate((el) => {
    el.scrollTop = 0;
  });
  const box = await body.boundingBox();
  expect(box).toBeTruthy();
  const client = await page.context().newCDPSession(page);
  await client.send("Input.dispatchMouseEvent", {
    type: "mouseWheel",
    x: box!.x + box!.width / 2,
    y: box!.y + Math.min(80, box!.height / 3),
    deltaX: 0,
    deltaY: 320,
  });
  await client.detach();
  await expect
    .poll(async () => body.evaluate((el) => el.scrollTop), { timeout: 3_000 })
    .toBeGreaterThan(0);

  await page.getByTestId("create-project-optional-toggle").click();
  await expect(page.getByTestId("create-project-optional-panel")).toHaveCount(0);

  await page.getByTestId("create-project-templates-toggle").click();
  await expect(page.getByTestId("create-project-templates-panel")).toBeVisible();
  await assertModalWithinViewport(page);
  await assertBodyScrollable(page);
  await body.evaluate((el) => {
    el.scrollTop = el.scrollHeight;
  });
  await expect(page.locator('[data-testid^="create-project-template-"]').last()).toBeVisible();
  await assertFooterReachable(page);
  await assertPageBackgroundLocked(page);

  await page.screenshot({
    path: path.join(ARTIFACT_DIR, `expanded-content-scroll-${label}.png`),
    fullPage: true,
  });
}

async function createFromModal(
  page: Page,
  request: APIRequestContext,
  opts: { name: string; doubleSubmit?: boolean; expectUrl?: RegExp },
) {
  const nameInput = page.locator("#np-name");
  await expect(nameInput).toBeVisible({ timeout: 15_000 });
  await nameInput.fill(opts.name);
  const submit = page.getByTestId("create-project-submit");
  if (opts.doubleSubmit) {
    await submit.dblclick();
  } else {
    await nameInput.press("Enter");
  }
  if (opts.expectUrl) {
    await expect(page).toHaveURL(opts.expectUrl, { timeout: 30_000 });
  } else {
    await expect(page).toHaveURL(/\/$/, { timeout: 30_000 });
    await expect(page.getByTestId("create-project-modal")).toBeHidden({ timeout: 30_000 });
  }
  let createdId: string | null = null;
  await expect
    .poll(async () => {
      const created = (await listProjects(request)).find((project) => project.name === opts.name);
      createdId = created?.id || null;
      return createdId;
    }, { timeout: 30_000 })
    .not.toBeNull();
  return createdId as string;
}

async function captureHandoffSnapshot(request: APIRequestContext) {
  const res = await request.get(`${API}/api/projects/${MANUAL_HANDOFF_ID}`);
  if (res.status() === 404) {
    return {
      present: false,
      id: MANUAL_HANDOFF_ID,
      name: MANUAL_HANDOFF_NAME,
      sceneCount: 0,
      assetCount: 0,
    };
  }
  expect(res.status(), await res.text()).toBe(200);
  const project = (await res.json()) as { id: string; name: string; scene_count?: number; asset_count?: number };
  return {
    present: true,
    id: project.id,
    name: project.name,
    sceneCount: project.scene_count ?? 0,
    assetCount: project.asset_count ?? 0,
  };
}

test.describe.serial("Project creation modal @critical", () => {
  test.beforeAll(() => {
    ensureArtifactDir();
  });

  test("HOME-MODAL-01 modal create flow stays compact, explicit, and synchronized on Beta", async ({
    page,
    request,
  }) => {
    test.skip(!BETA_TARGET, "Set ADEPT_BETA_TARGET=1 for live Beta modal certification.");
    test.slow();

    const createdIds = new Set<string>();
    const monitorCreatePosts = () => {
      let count = 0;
      const handler = (req: { method: () => string; url: () => string }) => {
        try {
          const url = new URL(req.url());
          if (req.method() === "POST" && url.pathname === "/api/projects") count += 1;
        } catch {
          /* ignore */
        }
      };
      page.on("request", handler);
      return {
        count: () => count,
        dispose: () => page.off("request", handler),
      };
    };

    await waitForAppReady(request);
    await resetLiveBetaTestSurface(request, page);
    const handoffBefore = await captureHandoffSnapshot(request);

    try {
      await test.step("Scenario A: zero-project Home stays explicit", async () => {
        await withZeroEligibleProjects(page, async () => {
          await gotoHome(page);
          await expect(page.getByTestId("ds-empty-state")).toContainText("No Projects Yet");
          await page.getByTestId("empty-state-create-project").click();
          await expect(page.getByTestId("create-project-modal-panel")).toBeVisible();
        });
      });

      await test.step("Scenario B: ai-guided setup with no projects opens the shared modal", async () => {
        const beforeCount = (await listProjects(request)).length;
        await withZeroEligibleProjects(page, async () => {
          await page.goto("/?setupMode=ai_guided&setupSource=workspace_launch");
          await expect(page.getByTestId("generation-studio-home")).toBeVisible({ timeout: 30_000 });
          await expect(page.getByTestId("create-project-modal-panel")).toBeVisible();
          await expect.poll(async () => (await listProjects(request)).length, { timeout: 10_000 }).toBe(beforeCount);
        });
      });

      await test.step("Scenario C: ai-guided setup reuses an existing project", async () => {
        const existing = await createProject(request, `${RUN_ID} Existing`);
        createdIds.add(existing.id);
        await page.goto("/?setupMode=ai_guided&setupSource=workspace_launch");
        await expect(
          page,
        ).toHaveURL(
          new RegExp(`/project/${existing.id.replace(/[-/\\^$*+?.()|[\]{}]/g, "\\$&")}\\?.*workspace=setup`),
          { timeout: 30_000 },
        );
        await expect(page.getByTestId("create-project-modal")).toBeHidden();
      });

      await test.step("Scenario D: collapsed modal fits at 1440x900 without scrolling", async () => {
        await page.setViewportSize({ width: 1440, height: 900 });
        await gotoHome(page);
        await page.getByTestId("create-project-open").click();
        const panel = page.getByTestId("create-project-modal-panel");
        await expect(panel).toBeVisible();
        const metrics = await panel.evaluate((node) => ({
          clientHeight: node.clientHeight,
          scrollHeight: node.scrollHeight,
        }));
        expect(metrics.scrollHeight).toBeLessThanOrEqual(metrics.clientHeight + 1);
        for (const locator of [
          page.locator("#np-name"),
          page.getByText("Project type", { exact: true }),
          page.getByTestId("project-type-preview"),
          page.getByTestId("create-project-cancel"),
          page.getByTestId("create-project-submit"),
        ]) {
          await expect(locator).toBeVisible();
          const box = await locator.boundingBox();
          const panelBox = await panel.boundingBox();
          expect(box && panelBox && box.y + box.height <= panelBox.y + panelBox.height).toBeTruthy();
        }
        await page.screenshot({ path: path.join(ARTIFACT_DIR, "scenario-d-collapsed-modal-1440x900.png"), fullPage: true });
      });

      await test.step("Scenario E: cancel resets name, errors, and optional state", async () => {
        await page.locator("#np-name").fill("");
        await expect(page.getByText("Give your project a name before creating it.")).toBeVisible();
        await page.getByTestId("create-project-optional-toggle").click();
        await expect(page.getByTestId("create-project-optional-panel")).toBeVisible();
        await page.getByTestId("create-project-cancel").click();
        await expect(page.getByTestId("create-project-modal")).toBeHidden();
        await page.getByTestId("create-project-open").click();
        await expect(page.locator("#np-name")).toHaveValue("Untitled Project");
        await expect(page.getByText("Give your project a name before creating it.")).toHaveCount(0);
        await expect(page.getByTestId("create-project-optional-panel")).toHaveCount(0);
      });

      await test.step("Scenario F: Home create stays on Home and updates every surface together", async () => {
        const homeName = `${RUN_ID} Home Modal`;
        const projectId = await createFromModal(page, request, { name: homeName });
        createdIds.add(projectId);
        await expect(page.getByTestId("home-active-project-banner")).toContainText(homeName);
        await expect(page.getByTestId("codirector-project-context")).toContainText(homeName);
        const activeCard = page.locator(`[data-testid="project-card-${projectId}"]`);
        await expect(activeCard).toBeVisible();
        await expect(activeCard.getByTestId("project-active-badge")).toContainText("Active Project");
        await page.getByRole("button", { name: /^Project$/ }).click();
        await expect(page.getByRole("menuitem", { name: homeName })).toBeVisible();
        await expect(page).toHaveURL(/\/$/, { timeout: 10_000 });
        await page.screenshot({ path: path.join(ARTIFACT_DIR, "scenario-f-home-active-sync.png"), fullPage: true });
      });

      await test.step("Scenario G: chrome create still blocks duplicate submits", async () => {
        const monitor = monitorCreatePosts();
        try {
          await gotoHome(page);
          await openChromeCreateProject(page);
          const duplicateName = `${RUN_ID} Chrome Double`;
          const projectId = await createFromModal(page, request, {
            name: duplicateName,
            doubleSubmit: true,
          });
          createdIds.add(projectId);
          expect(monitor.count()).toBe(1);
        } finally {
          monitor.dispose();
        }
      });

      await test.step("Scenario H: pending Co-Director destinations complete, then clear cleanly", async () => {
        await page.goto("/co-director");
        await expect(page.getByTestId("app-chrome")).toBeVisible({ timeout: 30_000 });
        await openChromeCreateProject(page);
        await expect(page).toHaveURL(/[?&]create=1.*pendingKind=co-director/, { timeout: 10_000 });
        const routedName = `${RUN_ID} CoDirector Return`;
        const projectId = await createFromModal(page, request, {
          name: routedName,
          expectUrl: /\/co-director\?projectId=/,
        });
        createdIds.add(projectId);
        const project = await getProject(request, projectId);
        await expect(page.getByTestId("app-chrome")).toBeVisible();
        await gotoHome(page);
        await page.getByTestId("create-project-open").click();
        await expect(page.locator("#np-name")).toHaveValue("Untitled Project");
        await page.getByTestId("create-project-cancel").click();
        await expect(page).toHaveURL(/\/$/, { timeout: 10_000 });
        await expect(page.getByTestId("home-active-project-banner")).toContainText(project.name);
      });

      await test.step("Scenario I: failure stays visible, then closes cleanly without stale state", async () => {
        let failedOnce = false;
        const routeHandler = async (route: Parameters<Page["route"]>[1] extends infer T ? T : never) => {
          const req = route.request();
          const url = new URL(req.url());
          if (!failedOnce && req.method() === "POST" && url.pathname === "/api/projects") {
            failedOnce = true;
            await route.fulfill({
              status: 500,
              contentType: "application/json",
              body: JSON.stringify({ detail: { message: "Injected modal failure" } }),
            });
            return;
          }
          await route.continue();
        };
        await gotoHome(page);
        await page.route("**/api/projects", routeHandler);
        try {
          await page.getByTestId("create-project-open").click();
          await page.locator("#np-name").fill(`${RUN_ID} Failure Reset`);
          await page.getByTestId("create-project-submit").click();
          await expect(page.getByTestId("create-project-error")).toContainText("Injected modal failure");
          await expect(page.getByTestId("create-project-modal-panel")).toBeVisible();
          await page.getByTestId("create-project-cancel").click();
          await expect(page.getByTestId("create-project-modal")).toBeHidden();
        } finally {
          await page.unroute("**/api/projects", routeHandler);
        }
        await page.getByTestId("create-project-open").click();
        await expect(page.getByTestId("create-project-error")).toHaveCount(0);
        await expect(page.locator("#np-name")).toHaveValue("Untitled Project");
        await expect(page.getByTestId("create-project-optional-panel")).toHaveCount(0);
        await page.getByTestId("create-project-cancel").click();
        await expect(page.getByTestId("create-project-modal")).toBeHidden();
      });

      await test.step("Scenario J: Expanded Content Scroll keeps footer reachable", async () => {
        const viewports: Array<{ label: string; width: number; height: number; zoom?: number }> = [
          { label: "1440x900", width: 1440, height: 900 },
          { label: "1280x720", width: 1280, height: 720 },
          { label: "narrow-390x844", width: 390, height: 844 },
          { label: "1440x900-zoom-200", width: 1440, height: 900, zoom: 2 },
        ];

        for (const viewport of viewports) {
          await page.setViewportSize({ width: viewport.width, height: viewport.height });
          await page.evaluate((zoom) => {
            document.documentElement.style.zoom = String(zoom);
          }, viewport.zoom ?? 1);
          await gotoHome(page);
          await page.getByTestId("create-project-open").click();
          await runExpandedContentScroll(page, viewport.label);
          await page.getByTestId("create-project-cancel").click();
          await expect(page.getByTestId("create-project-modal")).toBeHidden();
        }

        await page.evaluate(() => {
          document.documentElement.style.zoom = "1";
        });
        await page.setViewportSize({ width: 1440, height: 900 });
      });
    } finally {
      for (const projectId of uniqueIds(createdIds)) {
        await deleteProjectIfPresent(request, projectId);
      }
      const handoffAfter = await captureHandoffSnapshot(request);
      fs.writeFileSync(
        path.join(ARTIFACT_DIR, "handoff-state.json"),
        JSON.stringify({ before: handoffBefore, after: handoffAfter }, null, 2),
      );
      expect(handoffAfter).toEqual(handoffBefore);
    }
  });
});
