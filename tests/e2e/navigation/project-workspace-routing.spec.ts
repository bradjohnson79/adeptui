/**
 * Project / Workspace Routing — NAV-1..NAV-7 Certification
 *
 * Certifies the routing contract from
 * docs/release-gate/timeline-full-audit/PROJECT_WORKSPACE_ROUTING_AUDIT.md:
 *
 *   1. Open Project (selector/list) → /project/<id> landing, NO workspace
 *      param, no silent resume — even when workspace memory exists.
 *   2. Open Timeline (explicit click) → /project/<id>?workspace=timeline.
 *   3. Return to Project → bare landing URL.
 *   4. Cross-project isolation: project A's workspace memory never
 *      contaminates project B; plain Open Project never resumes silently.
 *   5. Deep links honored exactly (bare → landing; ?workspace=timeline →
 *      Timeline).
 *   6. Refresh determinism: refresh never converts bare ↔ workspace URL.
 *   7. Back/Forward coherence: URL and visible workspace always agree.
 *
 * Runs against live Beta (ADEPT_BETA_TARGET=1). Serial, retries=0.
 */
import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { API, BETA_TARGET, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";

const RECENTS_KEY = "adept_ui_recent_projects";
const WORKSPACE_KEY = "adept_ui_last_workspace";
const ARTIFACT_DIR = path.join(process.cwd(), "docs/release-gate/timeline-full-audit/artifacts");

let pidA = "";
let nameA = "";
let pidB = "";
let nameB = "";

const navResults: Record<string, { ok: boolean; detail: string }> = {};
function navGate(id: string, ok: boolean, detail: string) {
  navResults[id] = { ok, detail };
}

function urlParts(page: Page) {
  const u = new URL(page.url());
  return { pathname: u.pathname, search: u.search };
}

async function seedStorage(
  page: Page,
  seed: { recents?: { id: string; name: string }[]; workspaces?: Record<string, string> },
) {
  await page.goto("/");
  await page.waitForLoadState("domcontentloaded");
  await page.evaluate(
    ([recentsKey, workspaceKey, recents, workspaces]) => {
      localStorage.clear();
      if (recents) localStorage.setItem(recentsKey, JSON.stringify(recents));
      if (workspaces) localStorage.setItem(workspaceKey, JSON.stringify(workspaces));
    },
    [RECENTS_KEY, WORKSPACE_KEY, seed.recents ?? null, seed.workspaces ?? null] as const,
  );
  await page.reload();
  await page.waitForLoadState("domcontentloaded");
}

async function openProjectViaMenu(page: Page, name: string) {
  await page.locator("button.ds-menu-trigger", { hasText: "Project" }).first().click();
  await page.locator('button[role="menuitem"]', { hasText: name }).first().click();
}

async function expectLanding(page: Page, pid: string) {
  await expect(page.locator(".project-dash-actions button.primary")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("timeline-editor-shell")).toHaveCount(0);
  const { pathname, search } = urlParts(page);
  expect(pathname, "landing path").toBe(`/project/${pid}`);
  expect(search, "landing URL must be bare (no workspace param)").toBe("");
}

async function expectTimeline(page: Page, pid: string) {
  await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 45_000 });
  const { pathname, search } = urlParts(page);
  expect(pathname, "timeline path").toBe(`/project/${pid}`);
  expect(search, "timeline URL carries explicit workspace param").toBe("?workspace=timeline");
}

test.describe.configure({ mode: "serial", retries: 0 });

test.describe("@critical @beta project workspace routing (NAV)", () => {
  test.skip(!BETA_TARGET, "Set ADEPT_BETA_TARGET=1");

  test.beforeAll(async ({ request }) => {
    await waitForAppReady(request);
    const stamp = Date.now();
    const a = await createTempProject(request, `NAV-A-${stamp}`);
    const b = await createTempProject(request, `NAV-B-${stamp}`);
    pidA = a.id;
    nameA = a.name;
    pidB = b.id;
    nameB = b.name;
  });

  test.afterAll(async ({ request }) => {
    fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
    fs.writeFileSync(
      path.join(ARTIFACT_DIR, "nav-routing-cert.json"),
      JSON.stringify(
        {
          spec: "tests/e2e/navigation/project-workspace-routing.spec.ts",
          ranAt: new Date().toISOString(),
          gates: navResults,
          allPassed: Object.values(navResults).every((g) => g.ok),
        },
        null,
        2,
      ),
      "utf8",
    );
    if (pidA) await deleteProject(request, pidA);
    if (pidB) await deleteProject(request, pidB);
  });

  test("NAV-1: project selector opens the landing page — never a silent workspace resume", async ({ page }) => {
    // Seed: project A is recent AND has a remembered Timeline workspace. A
    // plain Open Project must still land on the project landing page.
    await seedStorage(page, {
      recents: [
        { id: pidA, name: nameA },
        { id: pidB, name: nameB },
      ],
      workspaces: { [pidA]: "timeline" },
    });
    await openProjectViaMenu(page, nameA);
    await expectLanding(page, pidA);
    navGate("NAV-1", true, "selector opened bare landing despite seeded timeline memory");
  });

  test("NAV-2: explicit Timeline click navigates to ?workspace=timeline", async ({ page }) => {
    await seedStorage(page, {});
    await page.goto(`/project/${pidA}`);
    await expectLanding(page, pidA);
    await page.getByRole("button", { name: "View Timeline" }).click();
    await expectTimeline(page, pidA);
    navGate("NAV-2", true, "explicit Timeline click → ?workspace=timeline");
  });

  test("NAV-3: return to Project from Timeline restores the bare landing URL", async ({ page }) => {
    await seedStorage(page, {});
    await page.goto(`/project/${pidA}?workspace=timeline`);
    await expectTimeline(page, pidA);
    await page.locator('[data-testid="chrome-breadcrumbs"] button', { hasText: "Project" }).click();
    await expectLanding(page, pidA);
    navGate("NAV-3", true, "breadcrumb Project → bare landing URL");
  });

  test("NAV-4: cross-project isolation — A's workspace memory never contaminates B", async ({ page }) => {
    await seedStorage(page, {
      recents: [
        { id: pidA, name: nameA },
        { id: pidB, name: nameB },
      ],
    });
    // Put A into Timeline explicitly — the app persists A→timeline memory.
    await page.goto(`/project/${pidA}?workspace=timeline`);
    await expectTimeline(page, pidA);
    await expect
      .poll(async () =>
        page.evaluate(
          ([key, pid]) => {
            const raw = localStorage.getItem(key);
            const map = raw ? (JSON.parse(raw) as Record<string, string>) : {};
            return map[pid] ?? null;
          },
          [WORKSPACE_KEY, pidA] as const,
        ),
      )
      .toBe("timeline");

    // Open B via the selector: bare landing, no inherited workspace state.
    await openProjectViaMenu(page, nameB);
    await expectLanding(page, pidB);

    // B must not have inherited A's memory, and A's memory stays intact.
    const memory = await page.evaluate((key) => {
      const raw = localStorage.getItem(key);
      return raw ? (JSON.parse(raw) as Record<string, string>) : {};
    }, WORKSPACE_KEY);
    expect(memory[pidA], "A's memory preserved").toBe("timeline");
    expect(memory[pidB], "B has no resume memory (landing is never persisted)").toBeUndefined();

    // Re-open A via the selector: still the landing page — memory only feeds
    // the intentional Continue affordance, never plain Open Project.
    await openProjectViaMenu(page, nameA);
    await expectLanding(page, pidA);
    navGate("NAV-4", true, "A's timeline memory never contaminated B; no silent resume for A");
  });

  test("NAV-5: deep links honored exactly (bare → landing; ?workspace=timeline → Timeline)", async ({ page }) => {
    await seedStorage(page, { workspaces: { [pidA]: "timeline" } });
    await page.goto(`/project/${pidA}`);
    await expectLanding(page, pidA);

    await page.goto(`/project/${pidA}?workspace=timeline`);
    await expectTimeline(page, pidA);
    navGate("NAV-5", true, "bare → landing; ?workspace=timeline → Timeline (memory ignored)");
  });

  test("NAV-6: refresh determinism — refresh never converts bare ↔ workspace URL", async ({ page }) => {
    await seedStorage(page, { workspaces: { [pidA]: "timeline" } });

    await page.goto(`/project/${pidA}`);
    await expectLanding(page, pidA);
    await page.reload();
    await expectLanding(page, pidA);

    await page.goto(`/project/${pidA}?workspace=timeline`);
    await expectTimeline(page, pidA);
    await page.reload();
    await expectTimeline(page, pidA);
    navGate("NAV-6", true, "reload preserves bare and workspace URLs exactly");
  });

  test("NAV-7: Back/Forward coherence — URL and visible workspace always agree", async ({ page }) => {
    await seedStorage(page, {});
    await page.goto(`/project/${pidA}`);
    await expectLanding(page, pidA);

    await page.getByRole("button", { name: "View Timeline" }).click();
    await expectTimeline(page, pidA);

    await page.goBack();
    await expectLanding(page, pidA);

    await page.goForward();
    await expectTimeline(page, pidA);
    navGate("NAV-7", true, "Back → landing, Forward → Timeline; URL and view agree");
  });
});
