import { test } from "@playwright/test";

const PROJECT = "6456f12d-1a8a-495d-b5c5-a410bcc05196";
const SHOT = "C:/Users/bradj/agent-tools/observe_e2.png";

test("observe-only: E2 preview stays preview after hard refresh", async ({ page, context }) => {
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
  const report = {
    scriptSrcs,
    bundleHash: scriptSrcs.map((s) => {
      const m = s.match(/index-([A-Za-z0-9_-]+)\.js/);
      return m ? m[1] : s;
    }),
    offline: /STUDIO_API_OFFLINE|Studio API Offline/i.test(body),
    hasNoValidShots: /No valid shots were queued/i.test(body),
    overlayCount: await overlay.count(),
    overlayVisible: (await overlay.count()) > 0 && (await overlay.first().isVisible()),
    packErrorCount: await packErr.count(),
    packErrorText: (await packErr.count()) ? await packErr.first().innerText().catch(() => "") : "",
    generateClicked: false,
    approveClicked: false,
    cancelClicked: false,
    advanceClicked: false,
  };
  await page.screenshot({ path: SHOT, fullPage: true });
  console.log(JSON.stringify(report));
});
