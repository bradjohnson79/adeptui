import AxeBuilder from "@axe-core/playwright";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { API, resetLiveBetaTestSurface, waitForAppReady } from "../helpers/app";

const ARTIFACT_DIR = path.join("docs", "release-gate", "home", "artifacts");
const MANUAL_HANDOFF_ID = "77a4b96c-8e3f-4501-897c-51bab99bedb7";
const MANUAL_HANDOFF_NAME = "Manual Beta Handoff";

type ProjectSummary = {
  id: string;
  name: string;
  archived?: number;
};

function safeParseJson(raw: string) {
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

function uniqueIds(ids: Iterable<string>) {
  return Array.from(new Set(Array.from(ids).filter(Boolean)));
}

async function ensureArtifactDir() {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
}

async function gotoHome(page: Page) {
  await page.goto("/");
  await expect(page.getByTestId("generation-studio-home")).toBeVisible({ timeout: 30_000 });
}

async function goHomeInApp(page: Page) {
  await page.getByTestId("chrome-brand").click();
  await expect(page.getByTestId("generation-studio-home")).toBeVisible({ timeout: 30_000 });
}

async function listProjects(request: APIRequestContext): Promise<ProjectSummary[]> {
  const res = await request.get(`${API}/api/projects`);
  expect(res.ok()).toBeTruthy();
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
  expect(res.ok()).toBeTruthy();
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
  await expect(page.getByTestId("create-project-modal-panel")).toBeVisible();
}

async function expectProjectMenuIsLive(page: Page) {
  await page.getByRole("button", { name: /^Project$/ }).click();
  await expect(page.getByRole("menuitem", { name: "Browse all projects…" })).toBeVisible();
  await expect(page.getByRole("menuitem", { name: "Create project" })).toBeVisible();
}

async function createProjectFromModal(
  page: Page,
  request: APIRequestContext,
  opts: { name: string; doubleSubmit?: boolean; expectUrl?: RegExp },
) {
  const nameInput = page.locator("#np-name");
  await expect(nameInput).toBeVisible();
  await nameInput.fill(opts.name);
  const submit = page.getByTestId("create-project-submit");
  if (opts.doubleSubmit) {
    await submit.dblclick();
  } else {
    await submit.click();
  }
  if (opts.expectUrl) {
    await expect(page).toHaveURL(opts.expectUrl, { timeout: 30_000 });
  } else {
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
  expect(createdId).toBeTruthy();
  return createdId as string;
}

test.describe.serial("Home project creation audit @critical", () => {
  test.beforeAll(async () => {
    await ensureArtifactDir();
  });

  test("HOME-AUDIT-01 Create Project entry points complete a reliable creator workflow", async ({
    page,
    request,
  }) => {
    test.slow();

    const consoleLines: string[] = [];
    const createEvents: Array<Record<string, unknown>> = [];
    const createdIds = new Set<string>();

    page.on("console", (msg) => {
      consoleLines.push(`[console:${msg.type()}] ${msg.text()}`);
    });
    page.on("pageerror", (error) => {
      consoleLines.push(`[pageerror] ${error.stack || error.message}`);
    });
    page.on("response", async (response) => {
      try {
        const url = new URL(response.url());
        if (url.pathname !== "/api/projects" || response.request().method() !== "POST") return;
        createEvents.push({
          url: response.url(),
          status: response.status(),
          request:
            response.request().postDataJSON?.() ??
            response.request().postData() ??
            null,
          response: safeParseJson(await response.text()),
        });
      } catch (error) {
        createEvents.push({
          url: response.url(),
          status: response.status(),
          response: `capture failed: ${error instanceof Error ? error.message : String(error)}`,
        });
      }
    });

    await waitForAppReady(request);
    await resetLiveBetaTestSurface(request, page);

    const visibleBefore = await listProjects(request);

    try {
      await test.step("Scenario A: zero-project state shows the empty library", async () => {
        await withZeroEligibleProjects(page, async () => {
          await gotoHome(page);
          await expect(page.getByTestId("ds-empty-state")).toContainText("No Projects Yet");
          await page.screenshot({ path: path.join(ARTIFACT_DIR, "scenario-a-zero-project-state.png"), fullPage: true });
        });
      });

      await test.step("Scenario B: ai-guided setup with no projects opens the shared drawer instead of silently creating", async () => {
        const beforeCount = (await listProjects(request)).length;
        await withZeroEligibleProjects(page, async () => {
          await page.goto("/?setupMode=ai_guided&setupSource=workspace_launch");
          await expect(page.getByTestId("generation-studio-home")).toBeVisible({ timeout: 30_000 });
          await expect(page.getByTestId("create-project-modal-panel")).toBeVisible();
          await expect
            .poll(async () => (await listProjects(request)).length, { timeout: 10_000 })
            .toBe(beforeCount);
          await page.getByTestId("create-project-cancel").click();
          await gotoHome(page);
        });
      });

      await test.step("Scenario C: ai-guided setup with an existing project reuses it without opening create", async () => {
        const existing = await createProject(request, `Home Audit Existing ${Date.now()}`);
        createdIds.add(existing.id);
        let createPostCount = 0;
        const onRequest = (req: { method: () => string; url: () => string }) => {
          try {
            const url = new URL(req.url());
            if (req.method() === "POST" && url.pathname === "/api/projects") createPostCount += 1;
          } catch {
            /* ignore */
          }
        };
        page.on("request", onRequest);
        try {
          await page.goto("/?setupMode=ai_guided&setupSource=workspace_launch");
          await expect(page).toHaveURL(new RegExp(`/project/${existing.id.replace(/[-/\\^$*+?.()|[\]{}]/g, "\\$&")}\\?.*workspace=setup`), {
            timeout: 30_000,
          });
          await expect(page.getByTestId("create-project-modal-panel")).toBeHidden();
        } finally {
          page.off("request", onRequest);
        }
        expect(createPostCount).toBe(0);
      });

      await test.step("Scenario D: empty-state Create Project opens the shared drawer", async () => {
        await withZeroEligibleProjects(page, async () => {
          await gotoHome(page);
          await page.getByTestId("empty-state-create-project").click();
          await expect(page.getByTestId("create-project-modal-panel")).toBeVisible();
          await page.screenshot({ path: path.join(ARTIFACT_DIR, "scenario-b-empty-state-modal.png"), fullPage: true });
        });
      });

      await test.step("Scenario E: validation blocks blank project names", async () => {
        await withZeroEligibleProjects(page, async () => {
          await gotoHome(page);
          const nameInput = page.locator("#np-name");
          await page.getByTestId("empty-state-create-project").click();
          await nameInput.fill("");
          await expect(page.getByText("Give your project a name before creating it.")).toBeVisible();
          await expect(page.getByTestId("create-project-submit")).toBeDisabled();
          await page.getByTestId("create-project-cancel").click();
          await expect(page.getByTestId("create-project-modal-panel")).toBeHidden();
        });
      });

      await test.step("Scenario F/G/H: upper Create Project uses the same drawer and blocks duplicate submit", async () => {
        let createPostCount = 0;
        const onRequest = (req: { method: () => string; url: () => string }) => {
          try {
            const url = new URL(req.url());
            if (req.method() === "POST" && url.pathname === "/api/projects") createPostCount += 1;
          } catch {
            /* ignore */
          }
        };
        page.on("request", onRequest);
        try {
          await openChromeCreateProject(page);
          const projectId = await createProjectFromModal(page, request, {
            name: `Home Audit Alpha ${Date.now()}`,
            doubleSubmit: true,
          });
          createdIds.add(projectId);
        } finally {
          page.off("request", onRequest);
        }
        expect(createPostCount).toBe(1);
      });

      await test.step("Scenario I/J/K: post-create library, recent project menu, reload, and overflow menu all stay live", async () => {
        await goHomeInApp(page);
        const alphaCard = page.locator("[data-testid^='project-card-']").first();
        await expect(alphaCard).toBeVisible();
        await expect(page.getByTestId("ds-empty-state")).toHaveCount(0);
        const alphaName = (await alphaCard.locator("h3").textContent())?.trim() || "";
        expect(alphaName).toMatch(/Home Audit Alpha/i);
        await expectProjectMenuIsLive(page);
        await page.reload();
        await expect(alphaCard).toBeVisible();
        await alphaCard.getByTestId("project-menu-button").click();
        await expect(alphaCard.getByTestId("project-overflow-menu")).toBeVisible();
        await page.screenshot({ path: path.join(ARTIFACT_DIR, "scenario-g-library-after-create.png"), fullPage: true });
      });

      await test.step("Scenario L: failure keeps the drawer open and retry succeeds", async () => {
        await gotoHome(page);
        const failureName = `Home Audit Retry ${Date.now()}`;
        let failedOnce = false;
        const routeHandler = async (route: Parameters<Page["route"]>[1] extends infer T ? T : never) => {
          const req = route.request();
          const url = new URL(req.url());
          if (!failedOnce && req.method() === "POST" && url.pathname === "/api/projects") {
            failedOnce = true;
            await route.fulfill({
              status: 500,
              contentType: "application/json",
              body: JSON.stringify({ detail: { message: "Injected audit failure" } }),
            });
            return;
          }
          await route.continue();
        };
        await page.route("**/api/projects", routeHandler);
        await page.getByTestId("create-project-open").click();
        await page.locator("#np-name").fill(failureName);
        await page.getByTestId("create-project-submit").click();
        await expect(page.getByTestId("create-project-error")).toBeVisible();
        await expect(page.getByTestId("create-project-modal-panel")).toBeVisible();
        await page.screenshot({ path: path.join(ARTIFACT_DIR, "scenario-j-create-failure.png"), fullPage: true });
        await page.unroute("**/api/projects", routeHandler);
        const retryProjectId = await createProjectFromModal(page, request, { name: failureName });
        createdIds.add(retryProjectId);
      });

      await test.step("Scenario M: template cards stay wired to real creation", async () => {
        await gotoHome(page);
        await page.getByTestId("carousel-slide-narrative").click();
        await expect(page).toHaveURL(/\/project\//, { timeout: 30_000 });
        const templateProjectId = /\/project\/([^/?#]+)/.exec(page.url())?.[1];
        expect(templateProjectId).toBeTruthy();
        createdIds.add(templateProjectId as string);
      });

      await test.step("Scenario N: Explore cards, Co-Director entry, and responsive drawer remain usable", async () => {
        await gotoHome(page);
        await expect(page.locator("[data-testid^='project-card-']").first()).toBeVisible();
        const timelineCard = page.getByTestId("explore-workspace-timeline");
        await expect(timelineCard).toBeVisible();
        await timelineCard.click();
        await expect(page).toHaveURL(/workspace=timeline/, { timeout: 20_000 });

        await gotoHome(page);
        await page.getByTestId("enter-codirector").click();
        await expect(page).toHaveURL(/\/co-director/, { timeout: 20_000 });

        await gotoHome(page);
        await page.setViewportSize({ width: 390, height: 844 });
        await page.getByTestId("create-project-open").click();
        await expect(page.getByTestId("create-project-submit")).toBeVisible();
        await expect(page.getByTestId("create-project-cancel")).toBeVisible();
        const drawerA11y = await new AxeBuilder({ page })
          .include('[data-testid="create-project-modal-panel"]')
          .analyze();
        const severeDrawerViolations = drawerA11y.violations.filter((violation) =>
          ["serious", "critical"].includes(String(violation.impact || "")),
        );
        expect(severeDrawerViolations).toEqual([]);
        await page.screenshot({ path: path.join(ARTIFACT_DIR, "scenario-l-mobile-drawer.png"), fullPage: true });
      });
    } finally {
      for (const projectId of uniqueIds(createdIds)) {
        await deleteProjectIfPresent(request, projectId);
      }

      const finalVisibleProjects = await listProjects(request);
      fs.writeFileSync(path.join(ARTIFACT_DIR, "home-project-creation-console.log"), consoleLines.join("\n"));
      fs.writeFileSync(
        path.join(ARTIFACT_DIR, "home-project-create-events.json"),
        JSON.stringify(createEvents, null, 2),
      );
      fs.writeFileSync(
        path.join(ARTIFACT_DIR, "home-project-audit-state.json"),
        JSON.stringify(
          {
            manualHandoff: {
              id: MANUAL_HANDOFF_ID,
              name: MANUAL_HANDOFF_NAME,
              presentAfter: finalVisibleProjects.some((project) => project.id === MANUAL_HANDOFF_ID),
            },
            visibleBefore,
            createdIds: uniqueIds(createdIds),
            finalVisibleCount: finalVisibleProjects.length,
            finalVisibleProjects,
          },
          null,
          2,
        ),
      );
    }
  });
});
