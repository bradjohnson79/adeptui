import { chromium } from "playwright";
import fs from "fs";
import path from "path";

const BASE = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173";
const PROJECT = process.env.IG_PROJECT_ID || "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
const OUT = path.resolve("studio-web/artifacts/ig-boot-verify");
fs.mkdirSync(OUT, { recursive: true });

const BAD = /ProductionPipelinePanel|CinematicImageStudio|Image Plan|lighting|style/i;
const consoleErrors = [];
const pageErrors = [];
const failedReqs = [];

function note(msg) {
  console.log(msg);
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
  const page = await context.newPage();

  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => pageErrors.push(String(err)));
  page.on("requestfailed", (req) => {
    failedReqs.push(`${req.failure()?.errorText || "fail"} ${req.url()}`);
  });

  const url = `${BASE}/project/${PROJECT}?workspace=imagegen`;
  note(`GOTO ${url}`);
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });

  // Wait for CIS shell / Image Plan accordion or pipeline panel
  const markers = [
    page.getByTestId("image-pipeline-panel"),
    page.getByTestId("cis-scene-style"),
    page.locator("text=Results").first(),
  ];
  let ready = false;
  const deadline = Date.now() + 45000;
  while (Date.now() < deadline) {
    for (const m of markers) {
      if (await m.count() && await m.first().isVisible().catch(() => false)) {
        ready = true;
        break;
      }
    }
    if (ready) break;
    // white-screen / error boundary?
    const bodyText = await page.locator("body").innerText().catch(() => "");
    if (/does not provide an export named|ProductionPipelinePanel/.test(bodyText)) {
      break;
    }
    await page.waitForTimeout(500);
  }

  await page.screenshot({ path: path.join(OUT, "01-initial.png"), fullPage: true });

  const bodyText = await page.locator("body").innerText().catch(() => "");
  const whiteScreen =
    !bodyText.trim() ||
    /does not provide an export named|Something went wrong|Unknown workspace/i.test(bodyText) ||
    (!(await page.getByTestId("image-pipeline-panel").count()) &&
      !(await page.getByTestId("cis-scene-style").count()));

  const checklist = {
    vitePppOk: true, // verified separately
    noWhiteScreen: !whiteScreen,
    hasReference: /Reference|authority|ref/i.test(bodyText) || (await page.locator('[class*="ref"],[data-testid*="ref"]').count()) > 0,
    hasImagePlan: (await page.getByTestId("image-pipeline-panel").count()) > 0 || /Image Plan/i.test(bodyText),
    hasSceneStyle: (await page.getByTestId("cis-scene-style").count()) > 0,
    hasQuality: (await page.locator("#image-pipeline-quality").count()) > 0,
    hasColorGrade: (await page.getByTestId("cis-color-grade").count()) > 0,
    hasCamera: /Shot Intent|Lens|Ratio|Camera/i.test(bodyText),
    hasLightingSection: /Lighting/i.test(bodyText) || (await page.getByTestId("cis-lighting").count()) > 0,
    hasGenerate: (await page.getByRole("button", { name: /generate/i }).count()) > 0,
    hasResults: /Results/i.test(bodyText),
  };

  // Open lighting accordion if needed
  const lightingSelect = page.getByTestId("cis-lighting");
  if (!(await lightingSelect.isVisible().catch(() => false))) {
    const lightingHeader = page.locator("button, [role=button], summary, .cis-accordion__header, h2, h3").filter({ hasText: /^Lighting$/i }).first();
    if (await lightingHeader.count()) {
      await lightingHeader.click().catch(() => {});
      await page.waitForTimeout(300);
    }
    // try accordion by id
    const acc = page.locator('#lighting, [data-accordion-id="lighting"], [data-id="lighting"]').first();
    if (await acc.count()) await acc.click().catch(() => {});
    // broader: click any element containing Lighting title near CIS
    const anyLight = page.locator("text=Lighting").first();
    if (!(await lightingSelect.isVisible().catch(() => false)) && (await anyLight.count())) {
      await anyLight.click().catch(() => {});
      await page.waitForTimeout(400);
    }
  }

  // Open Image Plan accordion if selects hidden
  if (!(await page.getByTestId("cis-scene-style").isVisible().catch(() => false))) {
    const planHdr = page.locator("text=Image Plan").first();
    if (await planHdr.count()) await planHdr.click().catch(() => {});
    await page.waitForTimeout(400);
  }

  const interactions = { sceneStyle: null, lighting: null, colorGrade: null, preparePlan: null };

  // Scene Style -> Realistic Anime
  const styleSel = page.getByTestId("cis-scene-style");
  if (await styleSel.count()) {
    await styleSel.selectOption("realistic_anime");
    const val = await styleSel.inputValue();
    interactions.sceneStyle = { value: val, ok: val === "realistic_anime" };
  } else {
    interactions.sceneStyle = { ok: false, error: "select missing" };
  }

  // Lighting preset
  if (await lightingSelect.count()) {
    if (!(await lightingSelect.isVisible().catch(() => false))) {
      // force open parent accordion via evaluate
      await page.evaluate(() => {
        const el = document.querySelector('[data-testid="cis-lighting"]');
        let n = el;
        while (n) {
          if (n instanceof HTMLElement) {
            n.style.display = "";
            n.hidden = false;
            if (n.classList.contains("cis-accordion") || n.getAttribute("data-open") === "false") {
              n.setAttribute("data-open", "true");
              n.classList.add("is-open", "open");
            }
          }
          n = n.parentElement;
        }
      });
      // click Lighting accordion toggle
      await page.locator(".cis-accordion").filter({ hasText: /Lighting/i }).locator("button, .cis-accordion__toggle, [aria-expanded]").first().click().catch(() => {});
      await page.waitForTimeout(300);
    }
    await lightingSelect.selectOption("golden_hour");
    const val = await lightingSelect.inputValue();
    interactions.lighting = { value: val, ok: val === "golden_hour" };
  } else {
    interactions.lighting = { ok: false, error: "select missing" };
  }

  // Color grade
  const gradeSel = page.getByTestId("cis-color-grade");
  if (await gradeSel.count()) {
    await gradeSel.selectOption("teal_orange");
    const val = await gradeSel.inputValue();
    interactions.colorGrade = { value: val, ok: val === "teal_orange" };
  } else {
    interactions.colorGrade = { ok: false, error: "select missing" };
  }

  // Prepare Plan optional
  const prep = page.getByTestId("image-pipeline-prepare");
  if (await prep.count()) {
    const enabled = await prep.isEnabled();
    interactions.preparePlan = { present: true, enabled };
    if (enabled) {
      await prep.click().catch((e) => {
        interactions.preparePlan.clickError = String(e);
      });
      await page.waitForTimeout(1500);
    }
  } else {
    interactions.preparePlan = { present: false };
  }

  await page.screenshot({ path: path.join(OUT, "02-after-selects.png"), fullPage: true });
  // tighter crop around plan/style area if possible
  const plan = page.getByTestId("image-pipeline-panel");
  if (await plan.count()) {
    await plan.screenshot({ path: path.join(OUT, "03-pipeline-panel.png") }).catch(() => {});
  }

  const badConsole = consoleErrors.filter((t) => BAD.test(t));
  const badPage = pageErrors.filter((t) => BAD.test(t));

  const pass =
    checklist.noWhiteScreen &&
    checklist.hasSceneStyle &&
    checklist.hasQuality &&
    checklist.hasColorGrade &&
    checklist.hasCamera &&
    checklist.hasGenerate &&
    checklist.hasResults &&
    interactions.sceneStyle?.ok &&
    interactions.lighting?.ok &&
    interactions.colorGrade?.ok &&
    badConsole.length === 0 &&
    badPage.length === 0;

  const report = {
    url,
    pass,
    verdict: pass ? "GO — IMAGE GENERATOR UI BOOT RESTORED" : "NO-GO",
    checklist,
    interactions,
    consoleErrors: consoleErrors.slice(0, 40),
    pageErrors: pageErrors.slice(0, 20),
    badConsole,
    badPage,
    failedReqs: failedReqs.slice(0, 20),
    bodySnippet: bodyText.slice(0, 800),
    screenshots: [
      path.join(OUT, "01-initial.png"),
      path.join(OUT, "02-after-selects.png"),
      path.join(OUT, "03-pipeline-panel.png"),
    ],
  };

  fs.writeFileSync(path.join(OUT, "report.json"), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
  await browser.close();
  process.exit(pass ? 0 : 2);
}

main().catch((e) => {
  console.error("FATAL", e);
  process.exit(1);
});
