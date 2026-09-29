/**
 * Timeline Turbo LoRA capability gating. Schnick / ADEPT_PROJECT_ID only.
 * Never POST /api/projects.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "2347bf46-3762-4763-86c5-4a6032522278";

async function waitApiReady(request: APIRequestContext) {
  await expect
    .poll(
      async () => {
        try {
          const res = await request.get(`${API}/api/health`, { timeout: 10_000 });
          return res.ok();
        } catch {
          return false;
        }
      },
      { timeout: 90_000 },
    )
    .toBeTruthy();
}

async function firstScene(request: APIRequestContext) {
  const res = await request.get(`${API}/api/projects/${PROJECT_ID}/scenes`);
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  const scenes = body.scenes || body.items || body || [];
  const scene = Array.isArray(scenes) ? scenes[0] : null;
  expect(scene?.id).toBeTruthy();
  return scene as { id: string };
}

async function getMaster(request: APIRequestContext, sceneId: string) {
  const res = await request.get(`${API}/api/director-timeline/projects/${PROJECT_ID}/scenes/${sceneId}/master`);
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  return (body.master || body) as Record<string, unknown> & {
    sceneGeneratorId?: string | null;
    turboLora?: boolean;
    batchBlocks?: Array<{ generatorId?: string | null }>;
  };
}

async function putMaster(
  request: APIRequestContext,
  sceneId: string,
  master: Record<string, unknown>,
) {
  const res = await request.put(`${API}/api/director-timeline/projects/${PROJECT_ID}/scenes/${sceneId}/master`, {
    data: { master },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
}

async function openTimeline(page: Page, sceneId: string) {
  await page.setViewportSize({ width: 1440, height: 900 });
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(String(err)));
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });
  await page.goto(`/project/${PROJECT_ID}?workspace=timeline&scene=${sceneId}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
  return errors;
}

async function openLeftDrawer(page: Page) {
  const handle = page.getByTestId("timeline-drawer-left-toggle");
  await expect(handle).toBeVisible({ timeout: 20_000 });
  for (let attempt = 0; attempt < 2; attempt++) {
    if ((await handle.getAttribute("aria-expanded")) !== "true") {
      const box = await handle.boundingBox();
      expect(box).toBeTruthy();
      await handle.click({ position: { x: Math.max(2, box!.width / 2), y: 16 } });
    }
    try {
      await expect(handle).toHaveAttribute("aria-expanded", "true", { timeout: 4_000 });
      break;
    } catch {
      /* click may have toggled a mid-open drawer closed */
    }
  }
  await expect(handle).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByTestId("timeline-drawer-left")).toHaveClass(/timeline-v2__drawer--open/);
}

async function waitGeneratorsLoaded(page: Page) {
  await expect
    .poll(async () => page.locator('[data-testid="timeline-video-generator-select"] option').count(), {
      timeout: 60_000,
    })
    .toBeGreaterThan(1);
}

function withGenerator(master: Record<string, unknown>, generatorId: string, turboLora: boolean) {
  const batches = Array.isArray(master.batchBlocks) ? (master.batchBlocks as Array<Record<string, unknown>>) : [];
  return {
    ...master,
    sceneGeneratorId: generatorId,
    turboLora,
    batchBlocks: batches.map((batch) => ({ ...batch, generatorId })),
  };
}

test.describe("Timeline Turbo LoRA", () => {
  test.beforeEach(async ({ request }) => {
    await waitApiReady(request);
  });

  test("capability-gated row, persist, switch-clear, Inspector sync", async ({ page, request }) => {
    test.setTimeout(180_000);
    const scene = await firstScene(request);
    const original = await getMaster(request, scene.id);
    try {
      await putMaster(request, scene.id, withGenerator(original, "minimax-h3", false));
      const errors = await openTimeline(page, scene.id);
      await openLeftDrawer(page);
      await waitGeneratorsLoaded(page);

      await expect(page.getByTestId("timeline-video-generator")).toBeVisible();
      await expect(page.getByTestId("timeline-turbo-lora")).toHaveCount(0);

      await putMaster(request, scene.id, withGenerator(await getMaster(request, scene.id), "ltx-2.5-full", false));
      await page.reload({ waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
      await openLeftDrawer(page);
      await waitGeneratorsLoaded(page);
      await expect(page.getByTestId("timeline-turbo-lora")).toBeVisible();
      await expect(page.getByTestId("timeline-turbo-lora-toggle")).not.toBeChecked();

      const turboHelp = page.locator('[data-testid="timeline-turbo-lora"] .help-tip');
      await expect(turboHelp).toHaveCount(1);
      await expect(page.locator('[data-testid="timeline-turbo-lora"] button .help-tip')).toHaveCount(0);

      await page.getByTestId("timeline-turbo-lora-toggle").check();
      await expect
        .poll(async () => Boolean((await getMaster(request, scene.id)).turboLora))
        .toBe(true);

      await page.reload({ waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
      await openLeftDrawer(page);
      await waitGeneratorsLoaded(page);
      await expect(page.getByTestId("timeline-turbo-lora-toggle")).toBeChecked();

      const inspectorToggle = page.getByTestId("timeline-drawer-right-toggle");
      if ((await inspectorToggle.getAttribute("aria-expanded")) !== "true") {
        const box = await inspectorToggle.boundingBox();
        if (box) await inspectorToggle.click({ position: { x: Math.max(2, box.width / 2), y: 16 } });
      }
      const inspectorRow = page.getByTestId("timeline-inspector-turbo-lora");
      if (await inspectorRow.count()) {
        await expect(inspectorRow).toContainText("On");
        await expect(page.getByTestId("timeline-inspector-turbo-lora-toggle")).toBeChecked();
      }

      const select = page.getByTestId("timeline-video-generator-select");
      const ltxDistilledEnabled = await select.locator('option[value="ltx-2.5-distilled"]:not([disabled])').count();
      if (ltxDistilledEnabled) {
        await select.selectOption("ltx-2.5-distilled");
        await expect.poll(async () => Boolean((await getMaster(request, scene.id)).turboLora)).toBe(false);
        await expect(page.getByTestId("timeline-turbo-lora")).toHaveCount(0);
      }

      await putMaster(request, scene.id, withGenerator(await getMaster(request, scene.id), "minimax-h3", false));
      await page.reload({ waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
      await openLeftDrawer(page);
      await waitGeneratorsLoaded(page);
      await expect(page.getByTestId("timeline-turbo-lora")).toHaveCount(0);

      const nested = errors.filter((line) => /hydrat|nested.*button|<button/i.test(line));
      expect(nested, nested.join("\n")).toEqual([]);
    } finally {
      await putMaster(request, scene.id, original);
    }
  });
});
