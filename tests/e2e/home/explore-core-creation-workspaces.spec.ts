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
  "explore-core-creation",
);
const MANUAL_HANDOFF_ID = "77a4b96c-8e3f-4501-897c-51bab99bedb7";
const RUN_ID = `EXPLORE-CORE-${new Date().toISOString().replace(/[:.]/g, "-")}`;

/** Canonical 15-card Explore roster after core-creation expansion. */
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

const NEW_CORE_IDS = ["one", "three", "characters", "scriptwriter"] as const;

const NEW_CORE_ROUTES: ReadonlyArray<{
  id: (typeof NEW_CORE_IDS)[number];
  workspace: string;
  shell: string;
  imagePattern: RegExp;
}> = [
  { id: "one", workspace: "one", shell: "one-frame-panel", imagePattern: /ws-one-frame\.jpg/ },
  { id: "three", workspace: "three", shell: "three-frame-panel", imagePattern: /ws-three-frame\.jpg/ },
  {
    id: "characters",
    workspace: "characters",
    shell: "character-profile-workspace",
    imagePattern: /ws-character-creator\.jpg/,
  },
  {
    id: "scriptwriter",
    workspace: "scriptwriter",
    shell: "scriptwriter-studio",
    imagePattern: /ws-scriptwriter\.jpg/,
  },
];

const LEGACY_SPOT_CHECKS = [
  { id: "timeline", workspace: "timeline", shell: "timeline-editor-shell" },
  { id: "library", workspace: "library", shell: "library-filters" },
  { id: "posecraft", workspace: "posecraft", shell: "posecraft-workspace" },
] as const;

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
        ...consoleErrors.filter(
          (t) =>
            !/favicon|Download the React DevTools|WebGPU|BJS -|Failed to fetch/i.test(t),
        ),
        ...pageErrors.filter((t) => !/WebGPU|Failed to fetch/i.test(t)),
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

test.describe.serial("Explore core creation workspaces @critical", () => {
  test.beforeAll(() => {
    ensureArtifactDir(RUN_ID);
  });

  test("HOME-EXPLORE-CORE-01 roster, routes, project-entry, responsive, a11y", async ({
    page,
    request,
  }) => {
    test.skip(!BETA_TARGET, "Set ADEPT_BETA_TARGET=1 for live Beta explore certification.");
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
      await test.step("Scenario 1: Explore roster is exactly 15 canonical workspaces in order", async () => {
        await gotoHome(page);
        const cards = page.getByTestId("explore-adept-ui").locator("[data-testid^='explore-workspace-']");
        await expect(cards).toHaveCount(15);
        for (const id of EXPECTED_IDS) {
          await expect(page.getByTestId(`explore-workspace-${id}`)).toBeVisible();
        }
        for (let i = 0; i < EXPECTED_IDS.length; i += 1) {
          await expect(
            page.getByTestId(`explore-workspace-${EXPECTED_IDS[i]}`).locator(".ds-workspace-card__title"),
          ).toHaveText(EXPECTED_TITLES[i]);
        }
        await page.screenshot({ path: path.join(artifactDir, "scenario-01-roster-1440.png"), fullPage: true });
      });

      await test.step("Scenario 2: four new cards have production JPG artwork and meaningful alt text", async () => {
        await gotoHome(page);
        for (const route of NEW_CORE_ROUTES) {
          const card = page.getByTestId(`explore-workspace-${route.id}`);
          const img = card.locator("img");
          await expect(img).toHaveAttribute("src", route.imagePattern);
          const alt = await img.getAttribute("alt");
          expect(alt && alt.trim().length > 0).toBeTruthy();
        }
        await page.screenshot({ path: path.join(artifactDir, "scenario-02-artwork.png"), fullPage: true });
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

      await test.step("Scenario 3: 1 Frame Home card opens one-frame workspace", async () => {
        await waitForActiveProjectContext(active);
        await page.getByTestId("explore-workspace-one").click();
        await assertWorkspaceShell(page, "one", "one-frame-panel", active.id);
        await page.screenshot({ path: path.join(artifactDir, "scenario-03-one-frame.png"), fullPage: true });
      });

      await test.step("Scenario 4: 3 Frame Home card opens three-frame workspace", async () => {
        await waitForActiveProjectContext(active);
        await page.getByTestId("explore-workspace-three").click();
        await assertWorkspaceShell(page, "three", "three-frame-panel", active.id);
        await page.screenshot({ path: path.join(artifactDir, "scenario-04-three-frame.png"), fullPage: true });
      });

      await test.step("Scenario 5: Character Creator Home card opens characters workspace", async () => {
        await waitForActiveProjectContext(active);
        await page.getByTestId("explore-workspace-characters").click();
        await assertWorkspaceShell(page, "characters", "character-profile-workspace", active.id);
        await page.screenshot({
          path: path.join(artifactDir, "scenario-05-character-creator.png"),
          fullPage: true,
        });
      });

      await test.step("Scenario 6: Scriptwriter Home card opens scriptwriter studio", async () => {
        await waitForActiveProjectContext(active);
        await page.getByTestId("explore-workspace-scriptwriter").click();
        await assertWorkspaceShell(page, "scriptwriter", "scriptwriter-studio", active.id);
        await page.screenshot({ path: path.join(artifactDir, "scenario-06-scriptwriter.png"), fullPage: true });
      });

      await test.step("Scenario 7: no-project entry opens centered Create Project modal", async () => {
        for (const project of await listProjects(request)) {
          if (project.name.startsWith(RUN_ID) && project.id !== active.id) {
            await deleteProject(request, project.id);
            createdIds.delete(project.id);
          }
        }
        const baseline = monitors.createCount();
        await withZeroEligibleProjects(page, async () => {
          await gotoHome(page);
          await page.getByTestId("explore-workspace-one").click();
          await expect(page.getByTestId("create-project-modal-panel")).toBeVisible({ timeout: 15_000 });
          expect(monitors.createCount()).toBe(baseline);
        });
      });

      await test.step("Scenario 8: cancel Create Project creates nothing", async () => {
        const cancelBaseline = monitors.createCount();
        await withZeroEligibleProjects(page, async () => {
          await gotoHome(page);
          await page.getByTestId("explore-workspace-characters").click();
          await expect(page.getByTestId("create-project-modal-panel")).toBeVisible({ timeout: 15_000 });
          await page.getByTestId("create-project-cancel").click();
          await expect(page.getByTestId("create-project-modal")).toBeHidden();
          expect(monitors.createCount()).toBe(cancelBaseline);
        });
        await expect
          .poll(async () => (await listProjects(request)).some((p) => p.name === `${RUN_ID} characters`))
          .toBeFalsy();
      });

      await test.step("Scenario 9: continue after create lands in selected workspace", async () => {
        const createBaseline = monitors.createCount();
        const name = `${RUN_ID} scriptwriter`;
        await withZeroEligibleProjects(page, async () => {
          await gotoHome(page);
          await page.getByTestId("explore-workspace-scriptwriter").click();
          await expect(page.getByTestId("create-project-modal-panel")).toBeVisible();
          await page.locator("#np-name").fill(name);
          await page.getByTestId("create-project-submit").click();
          await expect.poll(() => monitors.createCount(), { timeout: 30_000 }).toBe(createBaseline + 1);
          await assertWorkspaceShell(page, "scriptwriter", "scriptwriter-studio");
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
        await expect(page).toHaveURL(new RegExp(`workspace=scriptwriter`));
      });

      await test.step("Scenario 10: responsive layout — 15 cards, no overflow", async () => {
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
          for (const id of EXPECTED_IDS) {
            await expect(page.getByTestId(`explore-workspace-${id}`).getByText("Open →")).toBeVisible();
          }
          await page.screenshot({
            path: path.join(artifactDir, `scenario-10-layout-${viewport.label}.png`),
            fullPage: true,
          });
        }
        await page.setViewportSize({ width: 1440, height: 900 });
      });

      await test.step("Scenario 11: keyboard focus + Enter/Space opens workspace", async () => {
        await waitForActiveProjectContext(active);
        await page.getByTestId("explore-workspace-three").focus();
        await expect(page.getByTestId("explore-workspace-three")).toBeFocused();
        await page.keyboard.press("Enter");
        await assertWorkspaceShell(page, "three", "three-frame-panel", active.id);

        await waitForActiveProjectContext(active);
        await page.getByTestId("explore-workspace-one").focus();
        await page.keyboard.press(" ");
        await assertWorkspaceShell(page, "one", "one-frame-panel", active.id);
      });

      await test.step("Scenario 12: existing Explore cards still route correctly", async () => {
        for (const check of LEGACY_SPOT_CHECKS) {
          await waitForActiveProjectContext(active);
          await page.getByTestId(`explore-workspace-${check.id}`).click();
          await assertWorkspaceShell(page, check.workspace, check.shell, active.id);
        }
      });

      await test.step("Scenario 13: console and network clean; handoff project untouched", async () => {
        await waitForActiveProjectContext(active);
        await page.getByTestId("explore-workspace-one").click();
        await assertWorkspaceShell(page, "one", "one-frame-panel", active.id);
        monitors.assertClean("Explore core creation workspaces");
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
