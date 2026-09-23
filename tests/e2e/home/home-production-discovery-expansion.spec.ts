import {
  expect,
  test,
  type APIRequestContext,
  type ConsoleMessage,
  type Page,
  type Request,
} from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import {
  API,
  BETA_TARGET,
  createTempProject,
  deleteProject,
  resetLiveBetaTestSurface,
  waitForAppReady,
} from "../helpers/app";

const ARTIFACT_DIR = path.join(
  "docs",
  "release-gate",
  "home",
  "artifacts",
  "production-discovery",
);
const MANUAL_HANDOFF_ID = "77a4b96c-8e3f-4501-897c-51bab99bedb7";
const RUN_ID = `DISCOVERY-${new Date().toISOString().replace(/[:.]/g, "-")}`;

// Explore grid: 4×3 creator/tool roster. Timeline/MAGI remain Home feature cards.
const EXPECTED_IDS = [
  "imagegen",
  "txt2vid",
  "one",
  "three",
  "characters",
  "propcreator",
  "environmentcreator",
  "script",
  "scriptwriter",
  "voicestudio",
  "audiostudio",
  "library",
] as const;

const EXPECTED_TITLES = [
  "Image Generation",
  "Text to Video",
  "1 Frame",
  "3 Frame",
  "Character Creator",
  "Prop Creator",
  "Environment Creator",
  "Storyboard",
  "Scriptwriter",
  "Voice Studio",
  "Audio Studio",
  "Library",
] as const;

const EXPLORE_CARD_COUNT = EXPECTED_IDS.length;

type ProjectSummary = { id: string; name: string; archived?: number };

function ensureArtifactDir(runId: string) {
  const dir = path.join(ARTIFACT_DIR, runId);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

async function listProjects(request: APIRequestContext): Promise<ProjectSummary[]> {
  const res = await request.get(`${API}/api/projects`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return (await res.json()) as ProjectSummary[];
}

async function getProject(request: APIRequestContext, id: string) {
  const res = await request.get(`${API}/api/projects/${id}`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return (await res.json()) as {
    id: string;
    name: string;
    primary_project_type?: string;
    project_traits_json?: string;
  };
}

async function gotoHome(page: Page) {
  await page.goto("/");
  await expect(page.getByTestId("generation-studio-home")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("explore-adept-ui")).toBeVisible({ timeout: 15_000 });
}

async function withZeroEligibleProjects(page: Page, run: () => Promise<void>) {
  await page.evaluate(() => {
    try {
      localStorage.removeItem("adept_ui_recent_projects");
    } catch {
      /* ignore */
    }
  });
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

function attachMonitors(page: Page) {
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  const failedRequests: string[] = [];
  const createPosts: string[] = [];

  const onConsole = (msg: ConsoleMessage) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  };
  const onPageError = (err: Error) => pageErrors.push(err.message);
  const onRequestFailed = (req: Request) => {
    failedRequests.push(`${req.failure()?.errorText || "failed"} ${req.url()}`);
  };
  const onRequest = (req: Request) => {
    try {
      const url = new URL(req.url());
      if (req.method() === "POST" && url.pathname === "/api/projects") {
        createPosts.push(req.url());
      }
    } catch {
      /* ignore */
    }
  };
  const onResponse = async (res: Awaited<ReturnType<Page["waitForResponse"]>>) => {
    const status = res.status();
    if (status >= 400) {
      failedRequests.push(`${status} ${res.url()}`);
    }
  };

  page.on("console", onConsole);
  page.on("pageerror", onPageError);
  page.on("requestfailed", onRequestFailed);
  page.on("request", onRequest);
  page.on("response", onResponse);

  return {
    createCount: () => createPosts.length,
    assertClean: (label: string) => {
      const noise = [
        ...consoleErrors.filter((t) => !/favicon|Download the React DevTools/i.test(t)),
        ...pageErrors,
        ...failedRequests.filter((t) => !/favicon|\.map\b|net::ERR_ABORTED/i.test(t)),
      ];
      expect(noise, `${label} console/network failures:\n${noise.join("\n")}`).toEqual([]);
    },
    dispose: () => {
      page.off("console", onConsole);
      page.off("pageerror", onPageError);
      page.off("requestfailed", onRequestFailed);
      page.off("request", onRequest);
      page.off("response", onResponse);
    },
  };
}

async function openProductionItem(page: Page, itemId: string) {
  await page.getByRole("button", { name: /^Production$/ }).click();
  const item = page.getByTestId(`production-item-${itemId}`);
  await expect(item).toBeVisible({ timeout: 10_000 });
  await item.click();
}

async function assertWorkspaceShell(
  page: Page,
  workspace: string,
  shellTestId: string,
  projectId?: string,
) {
  const projectPart = projectId ? projectId : "[^/?#]+";
  await expect(page).toHaveURL(new RegExp(`/project/${projectPart}\\?.*workspace=${workspace}`), {
    timeout: 30_000,
  });
  await expect(page.getByTestId(shellTestId)).toBeVisible({ timeout: 45_000 });
}

test.describe.serial("Home + Production discovery expansion @critical", () => {
  test.beforeAll(() => {
    ensureArtifactDir(RUN_ID);
  });

  test("HOME-PRODUCTION-DISCOVERY-01 expanded roster, PoseCraft navigation, Brand route repair, templates, responsive, a11y", async ({
    page,
    request,
  }) => {
    test.skip(!BETA_TARGET, "Set ADEPT_BETA_TARGET=1 for live Beta discovery certification.");
    test.slow();

    const createdIds = new Set<string>();
    const monitors = attachMonitors(page);
    const artifactDir = ensureArtifactDir(RUN_ID);

    await waitForAppReady(request);
    await resetLiveBetaTestSurface(request);
    await page.goto("/");
    await page.evaluate(() => {
      try {
        localStorage.clear();
        sessionStorage.clear();
      } catch {
        /* ignore */
      }
    });
    const handoffBefore = await request.get(`${API}/api/projects/${MANUAL_HANDOFF_ID}`);

    try {
      await test.step("Scenario A: Explore roster is the v1.1 canonical workspaces (Spatial/3D shelved)", async () => {
        await gotoHome(page);
        const cards = page.getByTestId("explore-adept-ui").locator("[data-testid^='explore-workspace-']");
        await expect(cards).toHaveCount(EXPLORE_CARD_COUNT);
        for (const id of EXPECTED_IDS) {
          await expect(page.getByTestId(`explore-workspace-${id}`)).toBeVisible();
        }
        for (let i = 0; i < EXPECTED_IDS.length; i += 1) {
          await expect(
            page.getByTestId(`explore-workspace-${EXPECTED_IDS[i]}`).locator(".ds-workspace-card__title"),
          ).toHaveText(EXPECTED_TITLES[i]);
        }
        await expect(page.getByTestId("explore-workspace-posecraft")).toHaveCount(0);
        await expect(page.getByTestId("explore-workspace-spatial")).toHaveCount(0);
        await expect(page.getByTestId("explore-workspace-timeline")).toHaveCount(0);
        await expect(page.getByTestId("explore-workspace-magi")).toHaveCount(0);
        await expect(page.getByText("PoseCraft", { exact: true })).toHaveCount(0);
        await expect(page.getByText("Spatial Map", { exact: true })).toHaveCount(0);
        await page.screenshot({ path: path.join(artifactDir, "scenario-a-roster-1440.png"), fullPage: true });
      });

      const active = await createTempProject(request, `${RUN_ID} Active`);
      createdIds.add(active.id);
      await page.evaluate((project) => {
        localStorage.setItem(
          "adept_ui_recent_projects",
          JSON.stringify([{ id: project.id, name: project.name }]),
        );
      }, active);

      async function waitForActiveProjectContext(project: { id: string; name: string } = active) {
        await page.goto(`/project/${project.id}?workspace=library`);
        await expect(page).toHaveURL(new RegExp(`/project/${project.id}`), { timeout: 30_000 });
        await page.evaluate((entry) => {
          localStorage.setItem(
            "adept_ui_recent_projects",
            JSON.stringify([{ id: entry.id, name: entry.name }]),
          );
        }, project);
        await page.goto("/");
        await expect(page.getByTestId("generation-studio-home")).toBeVisible({ timeout: 30_000 });
        await expect(page.getByTestId("explore-adept-ui")).toBeVisible({ timeout: 15_000 });
        await expect(page.getByTestId("codirector-project-context")).toContainText(project.name, {
          timeout: 30_000,
        });
      }

      await test.step("Scenario B: stale PoseCraft URL silently opens Image Generator", async () => {
        await waitForActiveProjectContext(active);
        await page.goto(`/project/${active.id}?workspace=posecraft`);
        await assertWorkspaceShell(page, "imagegen", "cinematic-image-studio", active.id);
        await expect(page.getByTestId("posecraft-workspace")).toHaveCount(0);
        await page.screenshot({ path: path.join(artifactDir, "scenario-b-posecraft-stale-redirect.png"), fullPage: true });
      });

      await test.step("Scenario C: Pre-Production has no PoseCraft item; Spatial Map stale URL opens Environment Creator", async () => {
        await waitForActiveProjectContext(active);
        await page.getByRole("button", { name: /^Production$/ }).click();
        const preProd = page.getByTestId("production-cat-pre-production");
        await expect(preProd).toBeVisible({ timeout: 10_000 });
        await expect(preProd.getByTestId("production-item-posecraft")).toHaveCount(0);
        await expect(page.getByTestId("production-item-spatial")).toHaveCount(0);
        await page.keyboard.press("Escape");
        await page.goto(`/project/${active.id}?workspace=spatial`);
        await expect(page).toHaveURL(new RegExp(`/project/${active.id}\\?.*workspace=environmentcreator`), {
          timeout: 45_000,
        });
        await expect(page.getByTestId("environment-creator-surface")).toBeVisible({ timeout: 45_000 });
        await page.screenshot({ path: path.join(artifactDir, "scenario-c-spatial-stale-redirect.png"), fullPage: true });
      });

      await test.step("Scenario D: Brand Studio is retired — no Explore card, no Production item, stale route does not remount", async () => {
        await gotoHome(page);
        await expect(page.getByTestId("explore-workspace-brandstudio")).toHaveCount(0);
        await page.getByRole("button", { name: /^Production$/ }).click();
        await expect(page.getByTestId("production-item-brandstudio")).toHaveCount(0);
        await page.keyboard.press("Escape");
        await page.goto(`/project/${active.id}?workspace=brandstudio`);
        await expect(page).not.toHaveURL(/workspace=brandstudio/, { timeout: 45_000 });
        await expect(page.getByTestId("brand-studio")).toHaveCount(0);
        await page.screenshot({ path: path.join(artifactDir, "scenario-d-brand-retired.png"), fullPage: true });
      });

      await test.step("Scenario E: Voice Studio and Audio Studio routes still resolve (no regression)", async () => {
        await waitForActiveProjectContext(active);
        await page.getByTestId("explore-workspace-voicestudio").click();
        await assertWorkspaceShell(page, "voicestudio", "voice-studio-shell", active.id);

        await waitForActiveProjectContext(active);
        await openProductionItem(page, "voicestudio");
        await assertWorkspaceShell(page, "voicestudio", "voice-studio-shell", active.id);

        await waitForActiveProjectContext(active);
        await page.getByTestId("explore-workspace-audiostudio").click();
        await assertWorkspaceShell(page, "audiostudio", "audio-studio-workspace", active.id);

        await waitForActiveProjectContext(active);
        await openProductionItem(page, "audiostudio");
        await assertWorkspaceShell(page, "audiostudio", "audio-studio-workspace", active.id);
      });

      await test.step("Scenario F: Web Series and Brand Ad templates create correct project types", async () => {
        await gotoHome(page);
        await expect(page.getByTestId("browse-templates-card")).toBeVisible();
        await expect(page.getByTestId("carousel-slide-web-series")).toBeAttached();
        await expect(page.getByTestId("carousel-slide-brand-ad")).toBeAttached();

        const templates: Array<{ id: string; expectedType: string; expectedTrait: string }> = [
          // The resolve engine promotes the series+web_series trait to the concrete web_series subtype.
          { id: "web-series", expectedType: "web_series", expectedTrait: "web_series" },
          { id: "brand-ad", expectedType: "brand_ad", expectedTrait: "brand_ad" },
        ];

        for (const tpl of templates) {
          const baseline = monitors.createCount();
          await page.goto("/");
          await expect(page.getByTestId("generation-studio-home")).toBeVisible({ timeout: 30_000 });
          await page.getByTestId(`carousel-slide-${tpl.id}`).click({ force: true });
          await expect
            .poll(() => monitors.createCount(), { timeout: 30_000 })
            .toBe(baseline + 1);
          // Templates navigate to the project editor (home workspace is the default).
          await expect(page).toHaveURL(new RegExp(`/project/[^/?#]+`), {
            timeout: 30_000,
          });
          const url = page.url();
          const createdId = /\/project\/([^/?#]+)/.exec(url)?.[1] ?? "";
          expect(createdId.length).toBeGreaterThan(0);
          createdIds.add(createdId);

          const detail = await getProject(request, createdId);
          expect(detail.primary_project_type).toBe(tpl.expectedType);
          const traits = detail.project_traits_json || "";
          expect(traits).toContain(tpl.expectedTrait);
        }
      });

      await test.step("Scenario G: no-project Image Generator entry opens Create Project modal (no silent Untitled)", async () => {
        for (const project of await listProjects(request)) {
          if (project.name.startsWith(RUN_ID) && project.id !== active.id) {
            await deleteProject(request, project.id);
            createdIds.delete(project.id);
          }
        }

        const cancelBaseline = monitors.createCount();
        await withZeroEligibleProjects(page, async () => {
          await gotoHome(page);
          await page.getByTestId("explore-workspace-imagegen").click();
          await expect(page.getByTestId("create-project-modal-panel")).toBeVisible({ timeout: 15_000 });
          expect(monitors.createCount()).toBe(cancelBaseline);
          await page.getByTestId("create-project-cancel").click();
          await expect(page.getByTestId("create-project-modal")).toBeHidden();
          expect(monitors.createCount()).toBe(cancelBaseline);
        });
        await expect
          .poll(async () => (await listProjects(request)).some((p) => p.name === `${RUN_ID} imagegen`))
          .toBeFalsy();
      });

      await test.step("Scenario H: responsive layout — v1.1 cards, no overflow across viewports", async () => {
        const viewports = [
          { label: "1920x1080", width: 1920, height: 1080 },
          { label: "1440x900", width: 1440, height: 900 },
          { label: "1280x720", width: 1280, height: 720 },
          { label: "narrow-390x844", width: 390, height: 844 },
        ];
        for (const viewport of viewports) {
          await page.setViewportSize({ width: viewport.width, height: viewport.height });
          await gotoHome(page);
          const grid = page.getByTestId("explore-adept-ui");
          await expect(grid.locator("[data-testid^='explore-workspace-']")).toHaveCount(EXPLORE_CARD_COUNT);
          const overflow = await grid.evaluate((el) => {
            const section = el.closest("section") || el;
            return {
              sectionOverflowX: section.scrollWidth > section.clientWidth + 1,
              gridOverflowX: el.scrollWidth > el.clientWidth + 1,
            };
          });
          expect(overflow.sectionOverflowX, viewport.label).toBeFalsy();
          expect(overflow.gridOverflowX, viewport.label).toBeFalsy();
          for (const id of EXPECTED_IDS) {
            await expect(page.getByTestId(`explore-workspace-${id}`).getByText("Open →")).toBeVisible();
          }
          await page.screenshot({
            path: path.join(artifactDir, `scenario-h-layout-${viewport.label}.png`),
            fullPage: true,
          });
        }
        await page.setViewportSize({ width: 1440, height: 900 });
      });

      await test.step("Scenario I: keyboard/a11y + console/network clean; handoff project untouched", async () => {
        await waitForActiveProjectContext(active);
        await page.getByTestId("explore-workspace-imagegen").focus();
        await expect(page.getByTestId("explore-workspace-imagegen")).toBeFocused();
        await page.keyboard.press("Enter");
        await assertWorkspaceShell(page, "imagegen", "cinematic-image-studio", active.id);

        await waitForActiveProjectContext(active);
        await page.getByRole("button", { name: /^Production$/ }).focus();
        await page.keyboard.press("Enter");
        await expect(page.getByTestId("production-item-posecraft")).toHaveCount(0);
        await expect(page.getByTestId("production-item-imagegen")).toBeVisible();

        await waitForActiveProjectContext(active);
        for (const id of ["voicestudio", "audiostudio", "imagegen"] as const) {
          const alt = await page.getByTestId(`explore-workspace-${id}`).locator("img").getAttribute("alt");
          expect(alt && alt.trim().length > 0).toBeTruthy();
        }

        const noiseAllowed = /favicon|\.map\b|Download the React DevTools|net::ERR_ABORTED/i;
        const consoleErrors: string[] = [];
        await waitForActiveProjectContext(active);
        page.once("pageerror", (err) => consoleErrors.push(err.message));
        await page.getByTestId("explore-workspace-imagegen").click();
        await assertWorkspaceShell(page, "imagegen", "cinematic-image-studio", active.id);
        expect(consoleErrors.filter((t) => !noiseAllowed.test(t))).toEqual([]);

        monitors.assertClean("Image Generator + Brand/Voice/Audio discovery");
      });
    } finally {
      monitors.dispose();
      for (const projectId of createdIds) {
        await deleteProject(request, projectId);
      }
      const handoffAfter = await request.get(`${API}/api/projects/${MANUAL_HANDOFF_ID}`);
      fs.writeFileSync(
        path.join(artifactDir, "handoff-state.json"),
        JSON.stringify(
          {
            before: handoffBefore.status(),
            after: handoffAfter.status(),
            createdIds: Array.from(createdIds),
          },
          null,
          2,
        ),
      );
      expect(handoffAfter.status()).toBe(handoffBefore.status());
    }
  });
});

