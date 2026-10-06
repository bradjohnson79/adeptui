import { test } from "@playwright/test";

const PROJECT = "55a09a9e-c466-4116-a1f2-c363359810cc";
const SHOT = "C:/Users/bradj/agent-tools/observe_c_leftover_dulsc.png";

test("observe-only: C leftover JOB_NOT_FOUND DuLscPI7", async ({ page, context }) => {
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
  const isDuLscPI7 = scriptSrcs.some((s) => s.includes("index-DuLscPI7.js"));
  const staleBundle =
    scriptSrcs.some((s) => s.includes("index-ASRAMbmo.js")) ||
    scriptSrcs.some((s) => s.includes("index-DKiNh3YJ.js")) ||
    scriptSrcs.some((s) => s.includes("index-D_ERp0dY.js")) ||
    !isDuLscPI7;

  const body = await page.locator("body").innerText();
  const overlay = page.locator("[data-testid=agent-operation-overlay]");
  const packErr = page.locator("[data-testid=agent-work-pack-error]");
  const summaryCard = page.locator("[data-testid=execution-summary-card]");
  const otherCards = page.locator("[data-testid*=execution], [data-testid*=summary], [data-testid*=pack-error]");
  const otherTestids = await otherCards.evaluateAll((els) =>
    els.map((e) => e.getAttribute("data-testid"))
  );

  const summaryCount = await summaryCard.count();
  const packCount = await packErr.count();
  const overlayCount = await overlay.count();

  const report = {
    scriptSrcs,
    isDuLscPI7,
    staleBundle,
    staleFlag: staleBundle ? "FAIL-stale-bundle" : null,
    offline: /STUDIO_API_OFFLINE|Studio API Offline/i.test(body),
    bodyHasJobNotFound: /JOB_NOT_FOUND/i.test(body),
    summaryCardCount: summaryCount,
    summaryCardVisible: summaryCount > 0 && (await summaryCard.first().isVisible()),
    summaryCardText: summaryCount ? await summaryCard.first().innerText().catch(() => "") : "",
    packErrorCount: packCount,
    packErrorVisible: packCount > 0 && (await packErr.first().isVisible()),
    packErrorText: packCount ? await packErr.first().innerText().catch(() => "") : "",
    overlayCount,
    overlayVisible: overlayCount > 0 && (await overlay.first().isVisible()),
    otherTestids,
    generateClicked: false,
  };

  await page.screenshot({ path: SHOT, fullPage: true });
  console.log(JSON.stringify(report));
});
