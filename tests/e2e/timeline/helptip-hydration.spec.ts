/**
 * HelpTip sibling-control hydration smoke. Live :5173. Schnick / ADEPT_PROJECT_ID.
 * Never POST /api/projects. Does not run generator jobs.
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

async function openTimeline(page: Page, sceneId: string) {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/project/${PROJECT_ID}?workspace=timeline&scene=${sceneId}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
}

test.describe("HelpTip hydration + Preflight isolation", () => {
  test.beforeEach(async ({ request }) => {
    await waitApiReady(request);
  });

  test("Preflight and Help are sibling controls; Production menu stays clean", async ({ page, request }) => {
    test.setTimeout(180_000);
    const nestErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error" && /cannot be a descendant/i.test(msg.text())) {
        nestErrors.push(msg.text());
      }
    });

    const scene = await firstScene(request);
    let preflightCalls = 0;
    page.on("request", (req) => {
      if (req.method() === "POST" && /preflight/i.test(req.url())) {
        preflightCalls += 1;
      }
    });

    await openTimeline(page, scene.id);

    const preflight = page.getByTestId("timeline-toolbar-preflight");
    await expect(preflight).toBeVisible({ timeout: 30_000 });

    const nest = await preflight.evaluate((el) => Boolean(el.querySelector("button")));
    expect(nest, "Preflight must not wrap a HelpTip button").toBeFalsy();

    const help = page
      .locator(".action-with-help")
      .filter({ has: page.getByTestId("timeline-toolbar-preflight") })
      .locator("button.help-tip")
      .first();
    await expect(help).toBeVisible();

    const beforeClick = preflightCalls;
    await Promise.all([
      page.waitForRequest((req) => req.method() === "POST" && /preflight/i.test(req.url()), { timeout: 20_000 }),
      preflight.click(),
    ]);
    await expect.poll(() => preflightCalls).toBeGreaterThan(beforeClick);
    const afterPreflight = preflightCalls;

    await help.hover();
    await expect(page.getByRole("tooltip")).toBeVisible({ timeout: 8_000 });
    await help.evaluate((el) => (el as HTMLButtonElement).click());
    expect(preflightCalls, "Help must not fire Preflight").toBe(afterPreflight);

    await expect(page.getByTestId("timeline-video-generator")).toBeVisible();
    await expect(page.getByTestId("timeline-library-open")).toBeAttached();
    await expect(page.getByTestId("timeline-toolbar-zoom-slider")).toBeVisible();
    await expect(page.getByTestId("timeline-toolbar-snap")).toBeVisible();
    await expect(page.getByTestId("timeline-transport")).toBeVisible();

    const trigger = page.getByTestId("chrome-production-menu-button");
    await expect(trigger).toBeVisible();
    await trigger.click();
    const menu = page.getByTestId("production-menu");
    await expect(menu).toBeVisible({ timeout: 10_000 });
    const nestedMenu = await menu.evaluate((el) => {
      const items = Array.from(el.querySelectorAll('[role="menuitem"]'));
      return items.some((item) => item.querySelector("button"));
    });
    expect(nestedMenu, "Production menuitem must not wrap HelpTip").toBeFalsy();
    await trigger.click();

    expect(nestErrors, nestErrors.join("\n")).toEqual([]);
  });
});
