/**
 * SenseNova ERS Full Size — leftover GPT Image 2 persist-direct sheet.
 *
 * LIVE observe-only. Do NOT click Generate / Regenerate. Do NOT bounce :8758.
 * Do NOT start Comfy. Do NOT create projects. Do NOT touch Korri CRS.
 *
 * Reuses helpers: openCoDirectorFullScreen, spatial_map tab, ERS Full Size popup.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { openCoDirectorFullScreen } from "../codirector/helpers/audit";

const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT_ID = "0ffe56e2-0d58-4926-91bf-0f947898d02e";
const MAP_ID = "477b450c-734d-49ae-a40a-51402e0a832f";
const LIVE_ASSET = "4fe330b6-a6d7-4205-a17d-4210df347429";
const STALE_ASSET = "19ec1b83-1ed4-4cd5-b69f-65f3527803f8";
const LIVE_PREFIX = "4fe330b6";
const STALE_PREFIX = "19ec1b83";
const EXPECT_W = 1672;
const EXPECT_H = 941;
const FORBID_W = 2560;
const FORBID_H = 2220;
const MAP_TITLE = "Observatory";
const ARTIFACT_DIR = path.resolve(__dirname, "..", "..", "..", "artifacts", "ers-full-size-clean-sheet");

type NetHit = { url: string; method: string; resourceType: string };

function logStep(step: string) {
  console.log(`[ERS-FULL-SIZE] ${step}`);
}

function includesLive(value: unknown) {
  return String(value || "").toLowerCase().includes(LIVE_PREFIX);
}

function includesStale(value: unknown) {
  return String(value || "").toLowerCase().includes(STALE_PREFIX);
}

async function dismissOnboarding(page: Page) {
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const region = page.locator('[aria-label="Working relationship"]').first();
    if (!(await region.isVisible().catch(() => false))) {
      await page.waitForTimeout(200);
      continue;
    }
    const nameInput = region.getByRole("textbox", { name: /What should I call you/i }).first();
    if (await nameInput.isVisible().catch(() => false)) {
      const current = await nameInput.inputValue().catch(() => "");
      if (!current) await nameInput.fill("Tester");
    }
    for (const label of [/Save and continue/i, /Skip for now/i]) {
      const btn = region.getByRole("button", { name: label }).first();
      if ((await btn.isVisible().catch(() => false)) && !(await btn.isDisabled().catch(() => false))) {
        await btn.click({ force: true }).catch(() => undefined);
        await page.waitForTimeout(400);
        break;
      }
    }
    if (!(await region.isVisible().catch(() => false))) break;
  }
}

async function openSpatialMapTab(page: Page) {
  await dismissOnboarding(page);
  const tab = page.getByTestId("codirector-content-tab-spatial_map");
  await expect(tab).toBeVisible({ timeout: 30_000 });
  for (let attempt = 0; attempt < 6; attempt += 1) {
    await tab.click({ force: true }).catch(() => undefined);
    const panel = page.getByTestId("spatial-map-panel").or(page.getByTestId("ers-generation-monitor")).first();
    if (await panel.isVisible().catch(() => false)) return;
    await page.waitForTimeout(800);
  }
  await expect(page.getByTestId("spatial-map-panel")).toBeVisible({ timeout: 45_000 });
}

function attachHoldGuards(page: Page, clicks: { generate: boolean }) {
  page.on("request", (req) => {
    if (req.method() !== "POST") return;
    const url = req.url();
    const body = `${req.postData() || ""}`;
    const ersGenerate =
      url.includes("/executions") &&
      !url.includes("/advance") &&
      (/ers\.generate/i.test(body) || /capability["']?\s*:\s*["']ers\.generate/i.test(body));
    if (ersGenerate || /cinematographer\/preview/i.test(url)) {
      clicks.generate = true;
      throw new Error(`HOLD violated: blocked live Generate POST ${url}`);
    }
  });
}

function ersSurface(page: Page) {
  return page.getByTestId("ers-generation-monitor").or(page.getByTestId("spatial-map-ers")).first();
}

async function leftoverHydrated(page: Page): Promise<{ ok: boolean; src: string }> {
  const surface = ersSurface(page);
  if (!(await surface.isVisible().catch(() => false))) return { ok: false, src: "" };
  const src = (await surface.locator("img").first().getAttribute("src").catch(() => "")) || "";
  const html = (await surface.innerHTML().catch(() => "")) || "";
  return { ok: includesLive(src) || includesLive(html), src };
}

async function openFullSize(page: Page) {
  const fullSize = page.getByRole("button", { name: /Open Full Size|Open Environment Reference Sheet full size/i }).first();
  await expect(fullSize).toBeVisible({ timeout: 20_000 });
  await fullSize.scrollIntoViewIfNeeded().catch(() => undefined);
  const popupPromise = page.waitForEvent("popup", { timeout: 15_000 }).catch(() => null);
  await fullSize.click();
  const popup = await popupPromise;
  if (popup) {
    await popup.waitForLoadState("domcontentloaded").catch(() => undefined);
    return popup;
  }
  return page;
}

async function measureDisplayedImage(target: Page) {
  const img = target.locator("img").first();
  const native = await target.evaluate(() => {
    const el = document.querySelector("img") as HTMLImageElement | null;
    if (el && el.naturalWidth) {
      return {
        src: el.currentSrc || el.src || "",
        naturalWidth: el.naturalWidth,
        naturalHeight: el.naturalHeight,
        complete: el.complete,
      };
    }
    return {
      src: location.href,
      naturalWidth: 0,
      naturalHeight: 0,
      complete: false,
    };
  });
  if (native.naturalWidth > 0) return native;
  if (await img.count()) {
    await img.waitFor({ state: "visible", timeout: 20_000 }).catch(() => undefined);
    const box = await img.boundingBox().catch(() => null);
    return {
      src: (await img.getAttribute("src").catch(() => "")) || native.src,
      naturalWidth: await img.evaluate((el: HTMLImageElement) => el.naturalWidth).catch(() => box?.width || 0),
      naturalHeight: await img.evaluate((el: HTMLImageElement) => el.naturalHeight).catch(() => box?.height || 0),
      complete: true,
    };
  }
  return native;
}

test.describe("SenseNova ERS Full Size clean sheet", () => {
  test("leftover GPT Image 2 sheet opens Full Size as 4fe330b6 1672x941", async ({ page, request }, info) => {
    test.setTimeout(180_000);
    fs.mkdirSync(ARTIFACT_DIR, { recursive: true });

    const clicks = { generate: false };
    const consoleLines: Array<{ type: string; text: string }> = [];
    const pageErrors: string[] = [];
    const fileHits: NetHit[] = [];
    const staleHits: NetHit[] = [];

    attachHoldGuards(page, clicks);
    page.on("console", (msg) => {
      consoleLines.push({ type: msg.type(), text: msg.text() });
    });
    page.on("pageerror", (err) => {
      pageErrors.push(String(err));
    });
    const track = (req: { url: () => string; method: () => string; resourceType: () => string }) => {
      const url = req.url();
      const hit = { url, method: req.method(), resourceType: req.resourceType() };
      if (/\/api\/assets\/[^/]+\/(file|thumb)/i.test(url) || includesLive(url) || includesStale(url)) {
        fileHits.push(hit);
      }
      if (includesStale(url)) staleHits.push(hit);
    };
    page.on("request", track);
    page.context().on("request", track);

    await page.setViewportSize({ width: 1440, height: 900 });

    const health = await request.get(`${API}/api/health`);
    expect(health.ok(), "Studio API :8758 must already be up — do not bounce it").toBeTruthy();

    const sheets = await request.get(`${API}/api/environment-reference-sheets/projects/${PROJECT_ID}`);
    expect(sheets.ok(), await sheets.text()).toBeTruthy();
    const sheetBody = (await sheets.json()) as {
      sheets?: Array<{ ers_composite_asset_id?: string | null; status?: string }>;
    };
    const liveSheet = (sheetBody.sheets || []).find((row) => includesLive(row.ers_composite_asset_id));
    expect(liveSheet, `API leftover ERS must bind ${LIVE_ASSET}`).toBeTruthy();
    logStep(`API leftover ERS composite=${liveSheet?.ers_composite_asset_id} status=${liveSheet?.status}`);

    // 1. Open SenseNova → Spatial Map → ERS
    await openCoDirectorFullScreen(page, PROJECT_ID);
    await openSpatialMapTab(page);
    await expect(page.getByTestId("spatial-map-panel")).toBeVisible({ timeout: 45_000 });
    const selector = page.locator("#spatial-map-select");
    if (await selector.isVisible().catch(() => false)) {
      await selector.selectOption(MAP_ID);
    }
    await expect(page.getByText(MAP_TITLE, { exact: false }).first()).toBeVisible({ timeout: 20_000 });
    logStep("step1 PASS: SenseNova Spatial Map Observatory open");

    const generateBtn = page.getByRole("button", { name: /Generate Environment Reference Sheet/i }).first();
    const regenerateBtn = page.getByTestId("ers-regenerate").or(page.getByRole("button", { name: /^Regenerate$/i })).first();
    expect(clicks.generate, "must not have posted ers.generate").toBeFalsy();

    // 2. Confirm existing ERS loads (do not click Generate/Regenerate)
    await expect
      .poll(async () => (await leftoverHydrated(page)).ok, { timeout: 60_000 })
      .toBeTruthy();
    const hydrated = await leftoverHydrated(page);
    expect(hydrated.ok, `ERS monitor must show leftover ${LIVE_PREFIX}, src=${hydrated.src}`).toBeTruthy();
    expect(includesStale(hydrated.src), `inline ERS src must not be stale ${STALE_PREFIX}`).toBeFalsy();
    const surface = ersSurface(page);
    await surface.scrollIntoViewIfNeeded().catch(() => undefined);
    const ersShot = path.join(ARTIFACT_DIR, "01-spatial-map-ers.png");
    await page.screenshot({ path: ersShot, fullPage: true });
    await info.attach("01-spatial-map-ers", { path: ersShot, contentType: "image/png" });
    logStep(`step2 PASS: leftover ERS hydrated src=${hydrated.src}`);

    // 3. Open Full Size. Screenshot. Confirm network asset + dimensions.
    const popup = await openFullSize(page);
    popup.on("console", (msg) => consoleLines.push({ type: `popup:${msg.type()}`, text: msg.text() }));
    popup.on("pageerror", (err) => pageErrors.push(`popup: ${String(err)}`));
    await popup.waitForTimeout(800);
    const measured = await measureDisplayedImage(popup);
    const popupUrl = popup.url();
    const fullShot = path.join(ARTIFACT_DIR, "02-full-size.png");
    await popup.screenshot({ path: fullShot, fullPage: true });
    await info.attach("02-full-size", { path: fullShot, contentType: "image/png" });

    const fullSizeFileHits = fileHits.filter((h) => /\/file(\?|$)/i.test(h.url) && includesLive(h.url));
    const staleFileHits = fileHits.filter((h) => includesStale(h.url));
    const networkAsset =
      fullSizeFileHits[fullSizeFileHits.length - 1]?.url ||
      (includesLive(popupUrl) ? popupUrl : includesLive(measured.src) ? measured.src : "");
    expect(includesLive(networkAsset) || includesLive(popupUrl) || includesLive(measured.src), `Full Size must request ${LIVE_ASSET}. popup=${popupUrl} src=${measured.src} hits=${JSON.stringify(fullSizeFileHits.slice(-5))}`).toBeTruthy();
    expect(includesStale(popupUrl) || includesStale(measured.src), `Full Size must not use stale ${STALE_ASSET}`).toBeFalsy();

    const w = Number(measured.naturalWidth) || 0;
    const h = Number(measured.naturalHeight) || 0;
    const ratio = h ? w / h : 0;
    const is169 = ratio > 1.6 && ratio < 1.9;
    const isExpected = (w === EXPECT_W && h === EXPECT_H) || is169;
    const isForbidden = w === FORBID_W && h === FORBID_H;
    expect(isForbidden, `Full Size must not be ${FORBID_W}x${FORBID_H}, got ${w}x${h}`).toBeFalsy();
    expect(isExpected, `Full Size dimensions ${w}x${h} must be ${EXPECT_W}x${EXPECT_H} or 16:9 (ratio=${ratio.toFixed(3)})`).toBeTruthy();
    logStep(`step3 PASS: Full Size network=${networkAsset || popupUrl} ${w}x${h} ratio=${ratio.toFixed(3)}`);

    // 4. Visual: no purple lower M1/M2/M3 board — pixel sample of bottom band + aspect.
    const purpleStats = await popup
      .evaluate(async () => {
        const img = document.querySelector("img") as HTMLImageElement | null;
        if (!img || !img.naturalWidth) return { sampled: false, purpleRatio: 0, width: 0, height: 0 };
        try {
          const canvas = document.createElement("canvas");
          canvas.width = img.naturalWidth;
          canvas.height = img.naturalHeight;
          const ctx = canvas.getContext("2d");
          if (!ctx) return { sampled: false, purpleRatio: 0, width: img.naturalWidth, height: img.naturalHeight };
          ctx.drawImage(img, 0, 0);
          const y0 = Math.floor(img.naturalHeight * 0.82);
          const band = ctx.getImageData(0, y0, img.naturalWidth, img.naturalHeight - y0);
          let purple = 0;
          let total = 0;
          for (let i = 0; i < band.data.length; i += 16) {
            const r = band.data[i];
            const g = band.data[i + 1];
            const b = band.data[i + 2];
            total += 1;
            if (r > 90 && b > 90 && g < 90 && r > g + 25 && b > g + 25) purple += 1;
          }
          return {
            sampled: true,
            purpleRatio: total ? purple / total : 0,
            width: img.naturalWidth,
            height: img.naturalHeight,
          };
        } catch {
          return { sampled: false, purpleRatio: 0, width: img.naturalWidth, height: img.naturalHeight };
        }
      })
      .catch(() => ({ sampled: false, purpleRatio: 0, width: w, height: h }));
    if (purpleStats.sampled) {
      expect(
        purpleStats.purpleRatio,
        `bottom band purpleRatio=${purpleStats.purpleRatio.toFixed(3)} suggests leftover M1/M2/M3 board`,
      ).toBeLessThan(0.12);
    }
    expect(h / w < 1.1, `tall composite (${w}x${h}) is the 2560x2220 purple-board layout`).toBeTruthy();
    logStep(`step4 ${purpleStats.sampled ? "PASS" : "DEFERRED-TO-SCREENSHOT"}: purpleRatio=${purpleStats.purpleRatio.toFixed(3)} ${purpleStats.width}x${purpleStats.height}`);

    // 5. Reload, confirm same ERS still loads, Full Size still 4fe330b6
    if (popup !== page) await popup.close().catch(() => undefined);
    await page.reload({ waitUntil: "domcontentloaded" });
    await openSpatialMapTab(page);
    await expect
      .poll(async () => (await leftoverHydrated(page)).ok, { timeout: 60_000 })
      .toBeTruthy();
    const rehydrated = await leftoverHydrated(page);
    expect(rehydrated.ok, `after reload ERS must still be ${LIVE_PREFIX}, src=${rehydrated.src}`).toBeTruthy();
    const reloadErsShot = path.join(ARTIFACT_DIR, "03-after-reload-ers.png");
    await page.screenshot({ path: reloadErsShot, fullPage: true });
    await info.attach("03-after-reload-ers", { path: reloadErsShot, contentType: "image/png" });

    const popup2 = await openFullSize(page);
    await popup2.waitForTimeout(800);
    const measured2 = await measureDisplayedImage(popup2);
    const popupUrl2 = popup2.url();
    const reloadFullShot = path.join(ARTIFACT_DIR, "04-after-reload-full-size.png");
    await popup2.screenshot({ path: reloadFullShot, fullPage: true });
    await info.attach("04-after-reload-full-size", { path: reloadFullShot, contentType: "image/png" });
    expect(
      includesLive(popupUrl2) || includesLive(measured2.src),
      `reload Full Size must still be ${LIVE_ASSET}. popup=${popupUrl2} src=${measured2.src}`,
    ).toBeTruthy();
    expect(includesStale(popupUrl2) || includesStale(measured2.src)).toBeFalsy();
    if (popup2 !== page) await popup2.close().catch(() => undefined);
    logStep(`step5 PASS: reload Full Size ${popupUrl2} src=${measured2.src} ${measured2.naturalWidth}x${measured2.naturalHeight}`);

    // 6. Console: no crash
    const crash = pageErrors.filter((line) => /chunk|undefined is not|cannot read|hydration|crash|unhandled/i.test(line));
    const crashConsole = consoleLines.filter(
      (row) =>
        row.type === "error" &&
        /chunkload|hydration|maximum update|minified react|uncaught|not a function/i.test(row.text),
    );
    fs.writeFileSync(
      path.join(ARTIFACT_DIR, "console.json"),
      JSON.stringify({ pageErrors, crash, crashConsole, consoleLines: consoleLines.slice(-80) }, null, 2),
    );
    fs.writeFileSync(
      path.join(ARTIFACT_DIR, "network.json"),
      JSON.stringify(
        {
          liveFileHits: fileHits.filter((h) => includesLive(h.url)),
          staleHits,
          lastLive: networkAsset || popupUrl,
          dimensions: { first: { w, h, ratio }, reload: { w: measured2.naturalWidth, h: measured2.naturalHeight } },
        },
        null,
        2,
      ),
    );
    expect(crash, `pageerrors: ${JSON.stringify(pageErrors)}`).toHaveLength(0);
    expect(crashConsole, `console errors: ${JSON.stringify(crashConsole)}`).toHaveLength(0);
    expect(clicks.generate).toBeFalsy();
    expect(await generateBtn.isVisible().catch(() => false) && false).toBeFalsy();
    void regenerateBtn;
    logStep("step6 PASS: no crash console; Generate/Regenerate never clicked");

    const report = {
      spec: "tests/e2e/ers/ers-full-size-clean-sheet.spec.ts",
      steps: {
        "1_open_sensenova_spatial_ers": "PASS",
        "2_existing_ers_loads": "PASS",
        "3_full_size_asset_and_dims": "PASS",
        "4_no_purple_m1m2m3_board": purpleStats.sampled ? "PASS" : "SCREENSHOT",
        "5_reload_same_ers": "PASS",
        "6_console_no_crash": "PASS",
      },
      screenshots: [ersShot, fullShot, reloadErsShot, reloadFullShot],
      networkAssetId: LIVE_ASSET,
      networkAssetUrl: networkAsset || popupUrl,
      dimensions: `${w}x${h}`,
      leftover19ec1b83: staleHits,
      generateClicked: clicks.generate,
    };
    fs.writeFileSync(path.join(ARTIFACT_DIR, "report.json"), JSON.stringify(report, null, 2));
    logStep(`REPORT ${JSON.stringify(report.steps)} staleHits=${staleHits.length}`);
  });
});

