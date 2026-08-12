import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { API, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";

type ViewportCase = { name: string; width: number; height: number };

const VIEWPORTS: ViewportCase[] = [
  { name: "desktop-1920", width: 1920, height: 1080 },
  { name: "desktop-2560", width: 2560, height: 1440 },
  { name: "desktop-1440", width: 1440, height: 900 },
  { name: "desktop-1280", width: 1280, height: 720 },
];

async function seedConversation(request: APIRequestContext, projectId: string) {
  const res = await request.post(`${API}/api/codirector/conversations/${projectId}`, {
    data: {
      messages: [{ id: "u1", role: "user", content: "Call this project The Dreamweaver and make it feel mythic." }],
      model: null,
      provider_id: null,
    },
  });
  expect(res.ok()).toBeTruthy();
}

async function seedRenameProposal(request: APIRequestContext, projectId: string) {
  const res = await request.post(`${API}/api/codirector/projects/${projectId}/tools/proposals`, {
    data: {
      toolId: "record_production_decision",
      arguments: {
        decision: "Project title confirmed as The Dreamweaver.",
        rationale: "The creator chose the final title during setup.",
        projectTitle: "The Dreamweaver",
      },
      requestId: `repair-${Date.now()}`,
      createdBy: "user",
    },
  });
  expect(res.ok()).toBeTruthy();
}

async function measureShell(page: Page) {
  return page.getByTestId("codirector-fullscreen-shell").evaluate((node) => {
    const rect = node.getBoundingClientRect();
    return {
      left: rect.left,
      right: window.innerWidth - rect.right,
      width: rect.width,
      viewportWidth: window.innerWidth,
      viewportHeight: window.innerHeight,
      scrollWidth: document.documentElement.scrollWidth,
    };
  });
}

async function expectFullscreenShell(page: Page, viewport: ViewportCase) {
  const metrics = await measureShell(page);
  const widthRatio = metrics.width / metrics.viewportWidth;
  const leftRatio = metrics.left / metrics.viewportWidth;
  const rightRatio = metrics.right / metrics.viewportWidth;

  if (viewport.width <= 768) {
    expect(widthRatio).toBeGreaterThanOrEqual(0.99);
    expect(leftRatio).toBeLessThanOrEqual(0.01);
    expect(rightRatio).toBeLessThanOrEqual(0.01);
  } else if (viewport.width <= 1439) {
    expect(widthRatio).toBeGreaterThanOrEqual(0.9);
    expect(widthRatio).toBeLessThanOrEqual(0.95);
    expect(leftRatio).toBeGreaterThanOrEqual(0.02);
    expect(leftRatio).toBeLessThanOrEqual(0.06);
    expect(rightRatio).toBeGreaterThanOrEqual(0.02);
    expect(rightRatio).toBeLessThanOrEqual(0.06);
  } else {
    expect(widthRatio).toBeGreaterThanOrEqual(0.88);
    expect(widthRatio).toBeLessThanOrEqual(0.92);
    expect(leftRatio).toBeGreaterThanOrEqual(0.04);
    expect(leftRatio).toBeLessThanOrEqual(0.06);
    expect(rightRatio).toBeGreaterThanOrEqual(0.04);
    expect(rightRatio).toBeLessThanOrEqual(0.06);
  }

  expect(metrics.scrollWidth).toBeLessThanOrEqual(metrics.viewportWidth + 2);
  await expect(page.getByLabel("Message Co-Director")).toBeVisible();
  await expect(page.getByTestId("codirector-project-content")).toBeVisible();
}

test.describe("@critical codirector runtime repair", () => {
  test.beforeEach(async ({ request }) => {
    await waitForAppReady(request);
  });

  for (const viewport of VIEWPORTS) {
    test(`fullscreen shell uses wide desktop layout (${viewport.name})`, async ({ page, request }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      const project = await createTempProject(request, `Runtime Repair ${viewport.name} ${Date.now()}`);
      const m214Plan404s: string[] = [];
      const consoleFailures: string[] = [];

      page.on("response", (response) => {
        if (response.status() === 404 && response.url().includes("/api/codirector/m214/plan")) {
          m214Plan404s.push(response.url());
        }
      });
      page.on("console", (msg) => {
        const text = msg.text();
        if (/record_production_decision|project\.get_summary|project\.list_blockers|isn't a Co-Director tool/i.test(text)) {
          consoleFailures.push(text);
        }
      });

      try {
        await seedConversation(request, project.id);
        await seedRenameProposal(request, project.id);

        await page.goto(`/co-director?projectId=${project.id}`);
        await expect(page.getByTestId("codirector-project-wiki")).toBeVisible({ timeout: 30_000 });
        await expect(page.getByTestId("codirector-project-wiki")).toContainText("Known Details");
        await expect(page.getByTestId("codirector-project-wiki")).toContainText("Creative Foundation");
        await expect(page.getByTestId("codirector-project-wiki")).not.toContainText(/project\.get_summary|project\.list_blockers/i);
        await expect(page.getByTestId("codirector-project-wiki")).not.toContainText(/project_service|session_context/i);
        await page.getByTestId("project-wiki-export-trigger").click();
        await expect(page.getByTestId("project-wiki-export-dialog")).toBeVisible();
        await page.getByTestId("project-wiki-export-html").click();
        const htmlExport = await request.post(`${API}/api/codirector/projects/${project.id}/wiki/export/html`, { data: {} });
        expect(htmlExport.ok()).toBeTruthy();

        await expectFullscreenShell(page, viewport);

        await page.getByTestId("codirector-content-tab-approvals").click();
        const card = page.locator(".codirector-proposal-card").first();
        await expect(card).toBeVisible({ timeout: 20_000 });
        await card.getByRole("button", { name: "Approve" }).click();
        await expect(page.locator(".codirector-msg.assistant .codirector-msg-bubble").last()).toContainText(
          /Dreamweaver/i,
          { timeout: 20_000 },
        );
        await expect(page.getByTestId("chrome-project-name")).toContainText("The Dreamweaver", { timeout: 20_000 });

        await page.getByTestId("codirector-content-tab-wiki").click();
        await expect(page.getByTestId("codirector-content-wiki")).toContainText("The Dreamweaver");
        await page.reload();
        await expect(page.getByTestId("chrome-project-name")).toContainText("The Dreamweaver", { timeout: 20_000 });
        await expect(page.getByTestId("codirector-project-wiki")).toContainText("The Dreamweaver");

        expect(m214Plan404s).toEqual([]);
        expect(consoleFailures).toEqual([]);
      } finally {
        await deleteProject(request, project.id);
      }
    });
  }

  test("compact popup remains narrower than fullscreen", async ({ page, request }) => {
    const project = await createTempProject(request, `Runtime Repair Compact ${Date.now()}`);
    try {
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto(`/project/${project.id}`);
      const launch = page.getByRole("button", { name: "Ask Co-Director" }).first();
      await expect(launch).toBeVisible({ timeout: 30_000 });
      await launch.click();
      const popupWidth = await page.getByTestId("codirector-shell").evaluate((node) => node.getBoundingClientRect().width);

      await page.goto(`/co-director?projectId=${project.id}`);
      const fullscreenWidth = (await measureShell(page)).width;
      expect(fullscreenWidth).toBeGreaterThan(popupWidth * 1.5);
    } finally {
      await deleteProject(request, project.id);
    }
  });
});

