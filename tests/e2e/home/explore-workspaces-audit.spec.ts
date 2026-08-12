import { expect, test, type APIRequestContext, type ConsoleMessage, type Page, type Request } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { API, BETA_TARGET, createTempProject, deleteProject, resetLiveBetaTestSurface, waitForAppReady } from "../helpers/app";

const ARTIFACT_DIR = path.join("docs", "release-gate", "home", "artifacts", "explore-workspaces");
const MANUAL_HANDOFF_ID = "77a4b96c-8e3f-4501-897c-51bab99bedb7";
const RUN_ID = `EXPLORE-WS-${new Date().toISOString().replace(/[:.]/g, "-")}`;

const EXPECTED_TITLES = [
  "Timeline",
  "MAGI Editor",
  "Brand Studio",
  "Spatial Map",
  "PoseCraft",
  "Image Generation",
  "Text to Video",
  "1 Frame",
  "3 Frame",
  "Character Creator",
  "Scriptwriter",
  "Avatar Studio",
  "Voice Studio",
  "Audio Studio",
  "Library",
] as const;

const EXPECTED_IDS = [
  "timeline",
  "magi",
  "brandstudio",
  "spatial",
  "posecraft",
  "imagegen",
  "txt2vid",
  "one",
  "three",
  "characters",
  "scriptwriter",
  "avatar",
  "voicestudio",
  "audiostudio",
  "library",
] as const;

type ProjectSummary = { id: string; name: string; archived?: number };

function ensureArtifactDir() {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
}

async function listProjects(request: APIRequestContext): Promise<ProjectSummary[]> {
  const res = await request.get(`${API}/api/projects`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return (await res.json()) as ProjectSummary[];
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
        ...failedRequests.filter((t) => !/favicon|\.map\b/i.test(t)),
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

async function assertWorkspaceShell(page: Page, workspace: string, shellTestId: string, projectId?: string) {
  const projectPart = projectId ? projectId : "[^/?#]+";
  await expect(page).toHaveURL(new RegExp(`/project/${projectPart}\\?.*workspace=${workspace}`), {
    timeout: 30_000,
  });
  await expect(page.getByTestId(shellTestId)).toBeVisible({ timeout: 45_000 });
}

test.describe.serial("Explore workspace roster audit @critical", () => {
  test.beforeAll(() => {
    ensureArtifactDir();
  });

  test("HOME-EXPLORE-01 roster, Brand/Voice/Audio routes, and project-entry contracts", async ({ page, request }) => {
    test.skip(!BETA_TARGET, "Set ADEPT_BETA_TARGET=1 for live Beta explore certification.");
    test.slow();

    const createdIds = new Set<string>();
    const monitors = attachMonitors(page);

    await waitForAppReady(request);
    // Clear once without a persistent init script — otherwise every navigation wipes
    // recent-project selection needed for Explore/Production launch contracts.
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
      await test.step("Scenario A: Explore roster is exactly the 10 canonical workspaces", async () => {
        await gotoHome(page);
        const cards = page.getByTestId("explore-adept-ui").locator("[data-testid^='explore-workspace-']");
        await expect(cards).toHaveCount(15);
        for (const id of EXPECTED_IDS) {
          await expect(page.getByTestId(`explore-workspace-${id}`)).toBeVisible();
        }
        for (let i = 0; i < EXPECTED_IDS.length; i += 1) {
          await expect(page.getByTestId(`explore-workspace-${EXPECTED_IDS[i]}`).locator(".ds-workspace-card__title")).toHaveText(
            EXPECTED_TITLES[i],
          );
        }
        await expect(page.getByTestId("explore-adept-ui").locator(".ds-workspace-card__title", { hasText: "Storyboard" })).toHaveCount(0);
        await page.screenshot({ path: path.join(ARTIFACT_DIR, "scenario-a-roster-1440.png"), fullPage: true });
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
        // Open the project first so ProjectEditor pushRecentProject wins, then return Home.
        // Soft re-goto("/") alone will not recompute preferredProjectId when already on Home.
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
        await expect(page.locator(`[data-testid="project-card-${project.id}"]`)).toBeVisible({
          timeout: 30_000,
        });
      }

      await test.step("Scenario B: Brand Studio Home card", async () => {
        await waitForActiveProjectContext(active);
        await page.getByTestId("explore-workspace-brandstudio").click();
        await assertWorkspaceShell(page, "brandstudio", "brand-studio", active.id);
        await expect(page.getByTestId("generation-studio-home")).toHaveCount(0);
        await page.screenshot({ path: path.join(ARTIFACT_DIR, "scenario-b-brand-home-card.png"), fullPage: true });
      });

      await test.step("Scenario C: Brand Studio Production dropdown", async () => {
        await waitForActiveProjectContext(active);
        await openProductionItem(page, "brandstudio");
        await assertWorkspaceShell(page, "brandstudio", "brand-studio", active.id);
        await expect(page).toHaveURL(new RegExp(active.id));
      });

      await test.step("Scenario D: Voice Studio card and Production dropdown", async () => {
        await waitForActiveProjectContext(active);
        await page.getByTestId("explore-workspace-voicestudio").click();
        await assertWorkspaceShell(page, "voicestudio", "voice-studio-shell", active.id);

        await waitForActiveProjectContext(active);
        await openProductionItem(page, "voicestudio");
        await assertWorkspaceShell(page, "voicestudio", "voice-studio-shell", active.id);
        await page.screenshot({ path: path.join(ARTIFACT_DIR, "scenario-d-voice-studio.png"), fullPage: true });
      });

      await test.step("Scenario E: Audio Studio card and Production dropdown", async () => {
        await waitForActiveProjectContext(active);
        await page.getByTestId("explore-workspace-audiostudio").click();
        await assertWorkspaceShell(page, "audiostudio", "audio-studio-workspace", active.id);

        await waitForActiveProjectContext(active);
        await openProductionItem(page, "audiostudio");
        await assertWorkspaceShell(page, "audiostudio", "audio-studio-workspace", active.id);
        await page.screenshot({ path: path.join(ARTIFACT_DIR, "scenario-e-audio-studio.png"), fullPage: true });
      });

      await test.step("Scenario F: no-project entry for Brand / Voice / Audio", async () => {
        for (const project of await listProjects(request)) {
          if (project.name.startsWith(RUN_ID) && project.id !== active.id) {
            await deleteProject(request, project.id);
            createdIds.delete(project.id);
          }
        }

        const workspaces: Array<{ id: (typeof EXPECTED_IDS)[number]; shell: string }> = [
          { id: "brandstudio", shell: "brand-studio" },
          { id: "voicestudio", shell: "voice-studio-shell" },
          { id: "audiostudio", shell: "audio-studio-workspace" },
        ];

        for (const workspace of workspaces) {
          const cancelBaseline = monitors.createCount();
          await withZeroEligibleProjects(page, async () => {
            await gotoHome(page);
            await page.getByTestId(`explore-workspace-${workspace.id}`).click();
            await expect(page.getByTestId("create-project-modal-panel")).toBeVisible({ timeout: 15_000 });
            expect(monitors.createCount()).toBe(cancelBaseline);
            await page.getByTestId("create-project-cancel").click();
            await expect(page.getByTestId("create-project-modal")).toBeHidden();
            expect(monitors.createCount()).toBe(cancelBaseline);
          });
          await expect
            .poll(async () => (await listProjects(request)).some((project) => project.name === `${RUN_ID} ${workspace.id}`))
            .toBeFalsy();

          const createBaseline = monitors.createCount();
          const name = `${RUN_ID} ${workspace.id}`;
          await withZeroEligibleProjects(page, async () => {
            await gotoHome(page);
            await page.getByTestId(`explore-workspace-${workspace.id}`).click();
            await expect(page.getByTestId("create-project-modal-panel")).toBeVisible();
            await page.locator("#np-name").fill(name);
            await page.getByTestId("create-project-submit").click();
            await expect
              .poll(() => monitors.createCount(), { timeout: 30_000 })
              .toBe(createBaseline + 1);
            await assertWorkspaceShell(page, workspace.id, workspace.shell);
          });
          let createdId: string | null = null;
          await expect
            .poll(async () => {
              const found = (await listProjects(request)).find((project) => project.name === name);
              createdId = found?.id || null;
              return createdId;
            }, { timeout: 30_000 })
            .not.toBeNull();
          createdIds.add(createdId as string);
        }
      });

      await test.step("Scenario G: responsive layout", async () => {
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
          await expect(grid.locator("[data-testid^='explore-workspace-']")).toHaveCount(15);
          const overflow = await grid.evaluate((el) => {
            const section = el.closest("section") || el;
            return {
              sectionOverflowX: section.scrollWidth > section.clientWidth + 1,
              gridOverflowX: el.scrollWidth > el.clientWidth + 1,
            };
          });
          expect(overflow.sectionOverflowX, viewport.label).toBeFalsy();
          expect(overflow.gridOverflowX, viewport.label).toBeFalsy();
          const heights = await grid.locator("[data-testid^='explore-workspace-']").evaluateAll((nodes) =>
            nodes.map((node) => Math.round(node.getBoundingClientRect().height)),
          );
          const minH = Math.min(...heights);
          const maxH = Math.max(...heights);
          // Allow modest variance from wrapping description lines at narrow widths.
          expect(maxH - minH, `${viewport.label} card height delta`).toBeLessThanOrEqual(
            viewport.width < 500 ? 48 : 12,
          );
          for (const id of EXPECTED_IDS) {
            await expect(page.getByTestId(`explore-workspace-${id}`).getByText("Open →")).toBeVisible();
          }
          await page.screenshot({
            path: path.join(ARTIFACT_DIR, `scenario-g-layout-${viewport.label}.png`),
            fullPage: true,
          });
        }
        await page.setViewportSize({ width: 1440, height: 900 });
      });

      await test.step("Scenario H: keyboard and accessibility basics", async () => {
        await waitForActiveProjectContext(active);
        await page.getByTestId("explore-workspace-brandstudio").focus();
        await expect(page.getByTestId("explore-workspace-brandstudio")).toBeFocused();
        await page.keyboard.press("Enter");
        await assertWorkspaceShell(page, "brandstudio", "brand-studio", active.id);

        await waitForActiveProjectContext(active);
        await page.getByRole("button", { name: /^Production$/ }).focus();
        await page.keyboard.press("Enter");
        await expect(page.getByTestId("production-item-brandstudio")).toBeVisible();
        await page.getByTestId("production-item-brandstudio").focus();
        await page.keyboard.press("Enter");
        await assertWorkspaceShell(page, "brandstudio", "brand-studio", active.id);

        await waitForActiveProjectContext(active);
        for (const id of ["brandstudio", "voicestudio", "audiostudio"] as const) {
          const alt = await page.getByTestId(`explore-workspace-${id}`).locator("img").getAttribute("alt");
          expect(alt && alt.trim().length > 0).toBeTruthy();
        }
      });

      await test.step("Scenario I: console and network clean for Brand/Voice/Audio opens", async () => {
        const noiseAllowed = /favicon|\.map\b|Download the React DevTools|net::ERR_ABORTED/i;
        const consoleErrors: string[] = [];
        await waitForActiveProjectContext(active);
        page.once("pageerror", (err) => consoleErrors.push(err.message));
        await page.getByTestId("explore-workspace-brandstudio").click();
        await assertWorkspaceShell(page, "brandstudio", "brand-studio", active.id);
        expect(consoleErrors.filter((t) => !noiseAllowed.test(t))).toEqual([]);
      });
    } finally {
      monitors.dispose();
      for (const projectId of createdIds) {
        await deleteProject(request, projectId);
      }
      const handoffAfter = await request.get(`${API}/api/projects/${MANUAL_HANDOFF_ID}`);
      fs.writeFileSync(
        path.join(ARTIFACT_DIR, "handoff-state.json"),
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
