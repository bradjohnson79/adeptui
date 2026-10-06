import { test } from "@playwright/test";
import fs from "fs";

const PROJECT = "2347bf46-3762-4763-86c5-4a6032522278";
const ART = "C:/Users/bradj/agent-tools";
const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";

function pickCheck(results: any[], id: string) {
  return (results || []).find((r: any) => r.checkId === id) || null;
}

function slimCheck(r: any) {
  if (!r) return null;
  return {
    checkId: r.checkId,
    title: r.title,
    status: r.status,
    durationMs: r.durationMs,
    summary: r.summary,
    message: r.message,
    blockers: r.blockers || [],
    warnings: r.warnings || [],
  };
}

test("ASSIGNED: three Status Health Checks only", async ({ page, context }) => {
  test.setTimeout(420000);
  await context.clearCookies();
  await page.goto(`/co-director?projectId=${encodeURIComponent(PROJECT)}&_=${Date.now()}`, {
    waitUntil: "domcontentloaded",
  });
  await page.waitForTimeout(2500);

  const scriptSrcs = await page.locator("script[src]").evaluateAll((els) =>
    els.map((e) => (e as HTMLScriptElement).src)
  );
  const bundleHash = scriptSrcs.map((s) => {
    const m = s.match(/index-([A-Za-z0-9_-]+)\.js/);
    return m ? m[1] : s;
  });

  const generateClicked = false;
  const approveClicked = false;
  const deepClicked = false;

  const panel = page.locator("[data-testid=codirector-status-panel]");
  if ((await panel.count()) === 0 || !(await panel.first().isVisible().catch(() => false))) {
    const more = page.getByTestId("codirector-overflow-button");
    if (await more.count()) {
      await more.first().click();
      await page.waitForTimeout(500);
    }
    const statusTab = page
      .locator("#codirector-overflow-panel button, [data-testid=codirector-overflow-panel] button")
      .filter({ hasText: /^Status$/ });
    if (await statusTab.count()) {
      await statusTab.first().click();
    } else {
      const statusBtn = page.getByRole("button", { name: /^Status$/ });
      if (await statusBtn.count()) await statusBtn.first().click();
    }
  }

  await panel.first().waitFor({ state: "visible", timeout: 20000 });

  const allRuns: any[] = [];

  for (let n = 1; n <= 3; n++) {
    const checkBtn = page
      .locator("[data-testid=codirector-status-panel] button")
      .filter({ hasText: /^(Health Check|Re-check)$/ })
      .first();
    await checkBtn.waitFor({ state: "visible", timeout: 15000 });
    await checkBtn.click();

    await page.waitForFunction(() => {
      const hero = document.querySelector(".codirector-status-hero")?.textContent || "";
      return /Checking studio readiness/i.test(hero);
    }, null, { timeout: 20000 }).catch(() => {});

    await page.waitForFunction(() => {
      const hero = document.querySelector(".codirector-status-hero")?.textContent || "";
      if (/Checking studio readiness/i.test(hero)) return false;
      const h3 = document.querySelector(".codirector-status-summary h3")?.textContent || "";
      const gauge = document.querySelector(".codirector-status-gauge strong")?.textContent || "";
      return Boolean(h3 || gauge);
    }, null, { timeout: 120000 });

    await page.waitForTimeout(1500);

    const cats = page.locator("details.codirector-status-category");
    const catCount = await cats.count();
    for (let i = 0; i < catCount; i++) {
      const d = cats.nth(i);
      const open = await d.getAttribute("open");
      if (open === null) {
        await d.locator("summary").first().click();
        await page.waitForTimeout(80);
      }
    }

    const ui = await page.evaluate(() => {
      const panelEl = document.querySelector("[data-testid=codirector-status-panel]") as HTMLElement | null;
      const hero = panelEl?.querySelector(".codirector-status-hero")?.textContent?.replace(/\s+/g, " ").trim() || "";
      const gaugeStrong = panelEl?.querySelector(".codirector-status-gauge strong")?.textContent?.trim() || "";
      const gaugeBand = panelEl?.querySelector(".codirector-status-gauge span")?.textContent?.trim() || "";
      const h3 = panelEl?.querySelector(".codirector-status-summary h3")?.textContent?.trim() || "";
      const categorySummaries = Array.from(document.querySelectorAll("details.codirector-status-category > summary")).map((el) =>
        (el.textContent || "").replace(/\s+/g, " ").trim()
      );
      const rows = Array.from(document.querySelectorAll("details.codirector-status-category li")).map((li) => {
        const title = li.querySelector("strong")?.textContent?.trim() || "";
        const span = li.querySelector("span")?.textContent?.replace(/\s+/g, " ").trim() || "";
        const full = (li.textContent || "").replace(/\s+/g, " ").trim();
        return { title, span, full };
      });
      const allButtons = Array.from(panelEl?.querySelectorAll("button") || []).map((b) =>
        (b.textContent || "").replace(/\s+/g, " ").trim()
      );
      return { hero, gaugeStrong, gaugeBand, h3, categorySummaries, rows, allButtons };
    });

    await page.screenshot({ path: `${ART}/observe_status_hc${n}.png`, fullPage: true });

    const latestUrl = `${API}/api/codirector/status/latest?projectId=${PROJECT}`;
    const apiRes = await page.request.get(latestUrl);
    const apiJson = await apiRes.json();
    const run = apiJson.run || apiJson;
    const summary = run.summary || {};
    const results = run.results || [];
    const categories = run.categories || [];
    const runtimeCat = categories.find((c: any) => c.category === "runtime") || null;

    const blocked = results
      .filter((r: any) => r.status === "blocked" || (r.blockers && r.blockers.length))
      .map((r: any) => ({ checkId: r.checkId, title: r.title, status: r.status, blockers: r.blockers || [] }));
    const timedSlowWarn = results
      .filter((r: any) =>
        r.status === "timed_out" ||
        r.status === "slow" ||
        r.status === "warning" ||
        /slow/i.test(String(r.summary || "")) ||
        (r.warnings && r.warnings.length)
      )
      .map((r: any) => ({
        checkId: r.checkId,
        title: r.title,
        status: r.status,
        durationMs: r.durationMs,
        summary: r.summary,
        warnings: r.warnings || [],
      }));

    const payload = {
      runIndex: n,
      bundleHash,
      scriptSrcs,
      runId: run.runId,
      startedAt: run.startedAt,
      completedAt: run.completedAt,
      score: summary.score,
      overallStatusIndicator: summary.statusIndicator,
      band: summary.band,
      runtimeCategory: runtimeCat,
      image_runtime: slimCheck(pickCheck(results, "image_runtime.readiness")),
      comfy: slimCheck(pickCheck(results, "comfy.health")),
      production_control: slimCheck(pickCheck(results, "production_control.status")),
      tools_registry: slimCheck(pickCheck(results, "tools.registry")),
      blocked,
      timed_out_slow_warning: timedSlowWarn,
      ui,
      generateClicked,
      approveClicked,
      deepClicked,
      healthCheckClicked: true,
    };

    fs.writeFileSync(`${ART}/status_hc${n}.json`, JSON.stringify({ api: apiJson, extract: payload }, null, 2));
    allRuns.push(payload);
    console.log(JSON.stringify(payload, null, 2));
  }

  fs.writeFileSync(`${ART}/status_hc123_compare.json`, JSON.stringify({ bundleHash, allRuns }, null, 2));
});
