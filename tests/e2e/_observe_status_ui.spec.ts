import { test } from "@playwright/test";

const PROJECT = "2347bf46-3762-4763-86c5-4a6032522278";
const SHOT = "C:/Users/bradj/agent-tools/observe_status_ui.png";

test("observe-only: Co-Director Status panel latest run", async ({ page, context }) => {
  test.setTimeout(90000);
  await context.clearCookies();
  await page.goto(`/co-director?projectId=${encodeURIComponent(PROJECT)}&_=${Date.now()}`, {
    waitUntil: "domcontentloaded",
  });
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.waitForTimeout(3500);

  const scriptSrcs = await page.locator("script[src]").evaluateAll((els) =>
    els.map((e) => (e as HTMLScriptElement).src)
  );
  const bundleHash = scriptSrcs.map((s) => {
    const m = s.match(/index-([A-Za-z0-9_-]+)\.js/);
    return m ? m[1] : s;
  });

  const clicks = { generateClicked: false, healthCheckClicked: false, recheckClicked: false, deepDiagnosticClicked: false };

  // Open overflow More if Status panel not already visible
  const panel = page.locator("[data-testid=codirector-status-panel]");
  if ((await panel.count()) === 0 || !(await panel.first().isVisible().catch(() => false))) {
    const more = page.getByTestId("codirector-overflow-button");
    if (await more.count()) {
      await more.first().click();
      await page.waitForTimeout(500);
    }
    // Click Status tab only (not Health Check / Re-check / Deep diagnostic)
    const statusTab = page.locator("#codirector-overflow-panel button, [data-testid=codirector-overflow-panel] button").filter({ hasText: /^Status$/ });
    if (await statusTab.count()) {
      await statusTab.first().click();
    } else {
      const statusBtn = page.getByRole("button", { name: /^Status$/ });
      if (await statusBtn.count()) await statusBtn.first().click();
    }
  }

  const panelVisible = await panel.first().isVisible({ timeout: 15000 }).catch(() => false);
  if (!panelVisible) {
    await page.screenshot({ path: SHOT, fullPage: true });
    const body = await page.locator("body").innerText();
    console.log(JSON.stringify({
      bundleHash,
      scriptSrcs,
      panelVisible: false,
      needHealthCheck: /Health Check|Re-check|Not Checked/i.test(body),
      bodySnippet: body.slice(0, 4000),
      ...clicks,
      STOP: "Status panel not visible without Health Check",
    }));
    return;
  }

  // Wait for latest-run rows (Degraded / score / check titles). Do not click Re-check.
  await page.waitForTimeout(2000);
  await page.locator(".codirector-status-hero, .codirector-status-categories, .codirector-status-gauge").first().waitFor({ timeout: 20000 }).catch(() => {});

  // Expand every category <details> so all check rows are visible (not a health check)
  const cats = page.locator("details.codirector-status-category");
  const catCount = await cats.count();
  for (let i = 0; i < catCount; i++) {
    const d = cats.nth(i);
    const open = await d.getAttribute("open");
    if (open === null) {
      await d.locator("summary").first().click();
      await page.waitForTimeout(150);
    }
  }

  const extracted = await page.evaluate(() => {
    const panelEl = document.querySelector("[data-testid=codirector-status-panel]") as HTMLElement | null;
    const hero = panelEl?.querySelector(".codirector-status-hero")?.textContent?.replace(/\s+/g, " ").trim() || "";
    const gaugeStrong = panelEl?.querySelector(".codirector-status-gauge strong")?.textContent?.trim() || "";
    const gaugeBand = panelEl?.querySelector(".codirector-status-gauge span")?.textContent?.trim() || "";
    const h3 = panelEl?.querySelector(".codirector-status-summary h3")?.textContent?.trim() || "";
    const help = panelEl?.querySelector("[data-testid=codirector-status-not-checked-help]")?.textContent?.trim() || "";
    const tallies = Array.from(panelEl?.querySelectorAll(".codirector-status-tallies > *") || []).map((n) =>
      (n.textContent || "").replace(/\s+/g, " ").trim()
    );
    const categorySummaries = Array.from(document.querySelectorAll("details.codirector-status-category > summary")).map((n) =>
      (n.textContent || "").replace(/\s+/g, " ").trim()
    );
    const rows = Array.from(document.querySelectorAll("details.codirector-status-category li")).map((li) => {
      const title = li.querySelector("strong")?.textContent?.trim() || "";
      const span = li.querySelector("span")?.textContent?.replace(/\s+/g, " ").trim() || "";
      const full = (li.textContent || "").replace(/\s+/g, " ").trim();
      return { title, span, full };
    });
    const highlights = (document.querySelector(".codirector-status-highlights")?.textContent || "")
      .replace(/\s+/g, " ")
      .trim();
    const allButtons = Array.from(panelEl?.querySelectorAll("button") || []).map((b) =>
      (b.textContent || "").replace(/\s+/g, " ").trim()
    );
    return { hero, gaugeStrong, gaugeBand, h3, help, tallies, categorySummaries, rows, highlights, allButtons };
  });

  await page.screenshot({ path: SHOT, fullPage: true });

  const runtimeLine = extracted.categorySummaries.find((s) => /runtime/i.test(s)) || null;
  const comfyRow = extracted.rows.find((r) => /comfy/i.test(r.title) || /comfy/i.test(r.full)) || null;

  console.log(JSON.stringify({
    bundleHash,
    scriptSrcs,
    panelVisible: true,
    overall: {
      statusIndicator: extracted.h3,
      score: extracted.gaugeStrong,
      band: extracted.gaugeBand,
      help: extracted.help,
      hero: extracted.hero,
      tallies: extracted.tallies,
    },
    runtimeLine,
    comfyRow,
    categorySummaries: extracted.categorySummaries,
    rows: extracted.rows,
    highlights: extracted.highlights,
    allButtons: extracted.allButtons,
    ...clicks,
  }, null, 2));
});
