import { test } from "@playwright/test";

const PROJECT = "55a09a9e-c466-4116-a1f2-c363359810cc";
const SHOT = "C:/Users/bradj/agent-tools/observe_c_leftover.png";

test("observe-only: C leftover JOB_NOT_FOUND after API back", async ({ page, context }) => {
  test.setTimeout(50000);
  await context.clearCookies();
  await page.goto(`/co-director?projectId=${encodeURIComponent(PROJECT)}&_=${Date.now()}`, {
    waitUntil: "domcontentloaded",
  });
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.waitForTimeout(4000);
  const scriptSrcs = await page.locator("script[src]").evaluateAll((els) =>
    els.map((e) => (e as HTMLScriptElement).src)
  );
  const body = await page.locator("body").innerText();
  const overlay = page.locator("[data-testid=agent-operation-overlay]");
  const packErr = page.locator("[data-testid=agent-work-pack-error]");
  const cards = page.locator("[data-testid*=execution], [data-testid*=summary], [data-testid*=pack-error]");
  const cardIds = await cards.evaluateAll((els) => els.map((e) => e.getAttribute("data-testid")));
  const report = {
    scriptSrcs,
    isNew: scriptSrcs.some((s) => s.includes("index-ASRAMbmo.js")),
    offline: /STUDIO_API_OFFLINE|Studio API Offline/i.test(body),
    hasJobNotFound: /JOB_NOT_FOUND/i.test(body),
    hasFailed: /\bfailed\b/i.test(body),
    overlayCount: await overlay.count(),
    overlayVisible: (await overlay.count()) > 0 && (await overlay.first().isVisible()),
    packErrorCount: await packErr.count(),
    packErrorText: (await packErr.count()) ? await packErr.first().innerText().catch(() => "") : "",
    cardIds,
    generateClicked: false,
  };
  await page.screenshot({ path: SHOT, fullPage: true });
  console.log(JSON.stringify(report));
});
