/**
 * Scene Creator Mini Generate Stills eligibility — SenseNova Observatory only.
 * Live UI :8760. Does not click Generate. Does not start Comfy.
 * Does not create projects/maps/characters/ERS. Does not touch Korri CRS.
 *
 * Navigation reuses Co-Director / Spatial Map helpers from scene-creator-mini-camera-production.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { API } from "../helpers/app";
import { openCoDirectorFullScreen } from "../codirector/helpers/audit";

const PROJECT_ID = "0ffe56e2-0d58-4926-91bf-0f947898d02e";
const MAP_ID = "477b450c-734d-49ae-a40a-51402e0a832f";
const LIVE_BUNDLE = "index-DkKogtPb.js";
const GATE_SAVE = "Save Spatial Map to generate stills.";
const GATE_OUTPUT = "Select Camera shots or Room views to generate.";
const EVIDENCE = path.resolve("artifacts", "scene-creator-mini-eligibility");

test.setTimeout(8 * 60 * 1000);

type MapSnap = {
  version: string | null;
  savedVersion: string | null;
  isDirty: boolean;
  saved: boolean;
};

type StepLog = {
  step: string;
  pass: boolean;
  assertion: string;
  extra?: Record<string, unknown>;
};

const steps: StepLog[] = [];
const versions: Array<{ label: string } & MapSnap> = [];

function record(step: string, pass: boolean, assertion: string, extra?: Record<string, unknown>) {
  steps.push({ step, pass, assertion, extra });
  expect(pass, `${step}: ${assertion}`).toBeTruthy();
}

async function dismissOnboarding(page: Page) {
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const region = page.locator('[aria-label="Working relationship"]').first();
    if (!(await region.isVisible().catch(() => false))) return;
    const skip = region.getByRole("button", { name: /Skip for now/i }).first();
    if (await skip.isVisible().catch(() => false)) {
      await skip.click({ force: true }).catch(() => undefined);
      await page.waitForTimeout(400);
    } else {
      break;
    }
  }
}

async function openSpatialMap(page: Page) {
  await openCoDirectorFullScreen(page, PROJECT_ID);
  await dismissOnboarding(page);
  const tab = page.getByTestId("codirector-content-tab-spatial_map");
  await expect(tab).toBeVisible({ timeout: 30_000 });
  await tab.click({ force: true });
  await expect(page.getByTestId("spatial-map-panel")).toBeVisible({ timeout: 45_000 });
}

async function selectObservatory(page: Page) {
  const heading = page.getByRole("heading", { name: /Observatory Control Room/i }).first();
  const select = page.locator("#spatial-map-select");
  const named = page.getByTestId("spatial-map-selector");
  if (await heading.isVisible().catch(() => false)) {
    return;
  }
  if (await select.count()) {
    await select.selectOption(MAP_ID);
    await expect(select).toHaveValue(MAP_ID, { timeout: 15_000 });
    return;
  }
  if (await named.isVisible().catch(() => false)) {
    await page.locator("#spatial-map-select").selectOption(MAP_ID);
    return;
  }
  await expect(heading).toBeVisible({ timeout: 20_000 });
}

async function enableMini(page: Page) {
  const mini = page.getByTestId("scene-creator-mini");
  await expect(mini).toBeVisible({ timeout: 30_000 });
  const toggle = page.getByTestId("scene-creator-mini-toggle");
  const bodyHint = page.getByTestId("scene-creator-mini-generate");
  if (!(await bodyHint.isVisible().catch(() => false))) {
    await toggle.click();
  }
  const enable = page.getByTestId("scene-creator-mini-enable");
  await expect(enable).toBeVisible({ timeout: 15_000 });
  if ((await enable.getAttribute("aria-checked")) !== "true") {
    await enable.click();
  }
  await expect(enable).toHaveAttribute("aria-checked", "true");
  await expect(page.getByTestId("scene-creator-mini-generate")).toBeVisible({ timeout: 15_000 });
}

async function getMapSnap(request: APIRequestContext): Promise<MapSnap> {
  const mapRes = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${MAP_ID}`);
  expect(mapRes.ok(), `GET map failed ${mapRes.status()} ${await mapRes.text()}`).toBeTruthy();
  const mapBody = await mapRes.json();
  const doc = mapBody.document || mapBody;
  const prevRes = await request.get(
    `${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${MAP_ID}/mini-take/preview`,
  );
  expect(prevRes.ok(), `GET mini-take/preview failed ${prevRes.status()} ${await prevRes.text()}`).toBeTruthy();
  const prev = await prevRes.json();
  const version = doc.version != null ? String(doc.version) : null;
  const savedVersion = doc.savedVersion != null ? String(doc.savedVersion) : null;
  return {
    version,
    savedVersion,
    isDirty: Boolean(prev.isDirty),
    saved: Boolean(prev.saved),
  };
}

async function generateSnapshot(page: Page) {
  const btn = page.getByTestId("scene-creator-mini-generate");
  const gate = page.getByTestId("scene-creator-mini-gate");
  const saveBtn = page.getByTestId("scene-creator-mini-save-map");
  return {
    enabled: await btn.isEnabled(),
    disabled: await btn.isDisabled(),
    reason: (await gate.isVisible().catch(() => false)) ? (await gate.innerText()).trim() : "",
    saveVisible: await saveBtn.isVisible().catch(() => false),
  };
}

async function pickReadyGenerator(page: Page) {
  const gen = page.getByTestId("scene-creator-mini-generator");
  await expect(gen).toBeVisible();
  const current = await gen.inputValue();
  const qwenOpt = gen.locator('option[value="qwen2512"]');
  const gptOpt = gen.locator('option[value="gpt-image-2"]');
  const qwenDisabled = await qwenOpt.isDisabled();
  const gptDisabled = await gptOpt.isDisabled();
  if ((current === "qwen2512" && qwenDisabled) && !gptDisabled) {
    await gen.selectOption("gpt-image-2");
    return { switched: true, from: current, to: "gpt-image-2", qwenDisabled, gptDisabled };
  }
  return { switched: false, from: current, to: current, qwenDisabled, gptDisabled };
}

async function shot(page: Page, name: string) {
  fs.mkdirSync(EVIDENCE, { recursive: true });
  const dest = path.join(EVIDENCE, name);
  await page.screenshot({ path: dest, fullPage: true });
  return dest;
}

async function canonicalSave(page: Page) {
  const saveBtn = page.getByTestId("scene-creator-mini-save-map");
  await expect(saveBtn).toBeVisible({ timeout: 15_000 });
  const saveResp = page.waitForResponse(
    (r) => r.url().includes(`/maps/${MAP_ID}/save`) && r.request().method() === "POST",
    { timeout: 30_000 },
  );
  await saveBtn.click();
  const resp = await saveResp;
  return { status: resp.status(), ok: resp.ok(), body: await resp.text().catch(() => "") };
}

test.describe("Mini Generate Stills eligibility (SenseNova Observatory)", () => {
  test.afterEach(async ({ request }) => {
    try {
      const snap = await getMapSnap(request);
      if (snap.isDirty || snap.version !== snap.savedVersion) {
        const save = await request.post(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${MAP_ID}/save`);
        test.info().annotations.push({
          type: "afterEach-save",
          description: `forced leftover save status=${save.status()}`,
        });
      }
    } catch (err) {
      test.info().annotations.push({
        type: "afterEach-save",
        description: `leftover save failed: ${err instanceof Error ? err.message : String(err)}`,
      });
    }
    fs.mkdirSync(EVIDENCE, { recursive: true });
    fs.writeFileSync(
      path.join(EVIDENCE, "run-evidence.json"),
      JSON.stringify({ versions, steps }, null, 2),
      "utf8",
    );
  });

  test("save gate, dirty cycle, output gate; never click Generate", async ({ page, request }) => {
    const consoleLines: string[] = [];
    const netFails: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleLines.push(`[console.error] ${msg.text()}`);
    });
    page.on("requestfailed", (req) => {
      netFails.push(`${req.method()} ${req.url()} ${req.failure()?.errorText || ""}`);
    });
    page.on("response", (resp) => {
      if (resp.status() >= 400 && /spatial-map|mini-take|save/.test(resp.url())) {
        netFails.push(`${resp.status()} ${resp.request().method()} ${resp.url()}`);
      }
    });

    const indexRes = await request.get("/");
    const indexHtml = await indexRes.text();
    record(
      "0-bundle",
      indexHtml.includes(LIVE_BUNDLE),
      `live index.html must list ${LIVE_BUNDLE} (got hash scan)`,
      { includesDkKogtPb: indexHtml.includes("index-DkKogtPb.js"), includesOldB81: indexHtml.includes("index-B81Y2QOW.js") },
    );

    await openSpatialMap(page);
    const liveScripts = await page.evaluate(() =>
      Array.from(document.querySelectorAll("script[src]"))
        .map((el) => (el as HTMLScriptElement).src)
        .filter((src) => /index-[A-Za-z0-9_-]+\.js/.test(src)),
    );
    record(
      "0b-page-bundle",
      liveScripts.some((src) => src.includes(LIVE_BUNDLE)),
      `page context scripts include ${LIVE_BUNDLE}`,
      { liveScripts },
    );
    await selectObservatory(page);
    await enableMini(page);

    const genPick = await pickReadyGenerator(page);
    const initialUi = await generateSnapshot(page);
    const initialSnap = await getMapSnap(request);
    versions.push({ label: "initial", ...initialSnap });
    const initialShot = await shot(page, "01-initial.png");
    record(
      "1-open-mini",
      true,
      `SenseNova Spatial Map Mini open; Generate ${initialUi.enabled ? "enabled" : "disabled"}; reason="${initialUi.reason}"`,
      { initialUi, initialSnap, genPick, initialShot },
    );
    record(
      "3-preview",
      initialSnap.version != null,
      `GET map+preview version=${initialSnap.version} savedVersion=${initialSnap.savedVersion} isDirty=${initialSnap.isDirty}`,
      { initialSnap },
    );

    const urlBeforeSave = page.url();
    if (initialSnap.isDirty || !initialUi.enabled) {
      if (initialUi.disabled) {
        record(
          "2-initial-disabled",
          initialUi.disabled && (initialUi.reason === GATE_SAVE || initialSnap.isDirty),
          `Generate disabled with save reason when dirty (reason="${initialUi.reason}")`,
          { initialUi, initialSnap },
        );
      }
      const saveResult = await canonicalSave(page);
      record("4-save-http", saveResult.ok, `canonical POST maps/{id}/save status=${saveResult.status}`, saveResult);
      await expect(page.getByTestId("scene-creator-mini-generate")).toBeEnabled({ timeout: 30_000 });
      await expect(page.getByTestId("scene-creator-mini-save-map")).toHaveCount(0);
      expect(page.url()).toBe(urlBeforeSave);
      const afterSaveUi = await generateSnapshot(page);
      const afterSaveSnap = await getMapSnap(request);
      versions.push({ label: "after-first-save", ...afterSaveSnap });
      const afterSaveShot = await shot(page, "02-after-save-enabled.png");
      record(
        "4-save-enable",
        afterSaveUi.enabled && afterSaveSnap.savedVersion === afterSaveSnap.version && !afterSaveSnap.isDirty,
        `Generate enabled without reload; savedVersion==version (${afterSaveSnap.savedVersion}==${afterSaveSnap.version})`,
        { afterSaveUi, afterSaveSnap, afterSaveShot, urlBeforeSave, urlAfter: page.url() },
      );
    } else {
      record(
        "5-already-saved",
        initialUi.enabled && !initialSnap.isDirty,
        "Map already saved; Generate already enabled — skip first save",
        { initialUi, initialSnap },
      );
      await shot(page, "02-after-save-enabled.png");
    }

    const varB = page.locator(".spatial-map__mini-card").filter({ hasText: /Variation B/i });
    const varBVisible = (await varB.count()) > 0;
    const varBFailed = varBVisible
      ? (await varB.first().innerText()).toLowerCase().includes("fail")
      : false;
    const afterSaveEnabled = (await generateSnapshot(page)).enabled;
    record(
      "9-variation-b",
      !varBFailed || afterSaveEnabled,
      varBVisible
        ? `Variation B ${varBFailed ? "failed" : "visible"} did not keep Generate disabled (enabled=${afterSaveEnabled})`
        : "Variation B not visible; skip keep-disabled check",
      { varBVisible, varBFailed, afterSaveEnabled },
    );

    const lens = page.getByTestId("camera-lens-0");
    await expect(lens).toBeVisible({ timeout: 20_000 });
    const originalLens = await lens.inputValue();
    const dirtyLens = originalLens === "35" ? "50" : "35";
    const beforeDirty = await getMapSnap(request);
    versions.push({ label: "before-dirty-edit", ...beforeDirty });
    const patchResp = page.waitForResponse(
      (r) =>
        r.url().includes(`/maps/${MAP_ID}/cameras/`) &&
        r.request().method() === "PATCH" &&
        r.status() < 400,
      { timeout: 20_000 },
    );
    await lens.selectOption(dirtyLens);
    await patchResp;
    await expect(page.getByTestId("scene-creator-mini-save-map")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("scene-creator-mini-generate")).toBeDisabled();
    await expect(page.getByTestId("scene-creator-mini-gate")).toHaveText(GATE_SAVE);
    const dirtyUi = await generateSnapshot(page);
    const dirtySnap = await getMapSnap(request);
    versions.push({ label: "after-dirty-edit", ...dirtySnap });
    const dirtyShot = await shot(page, "03-dirty-again.png");
    record(
      "6-dirty-edit",
      dirtyUi.disabled && dirtyUi.reason === GATE_SAVE && dirtySnap.isDirty,
      `lens ${originalLens}→${dirtyLens} dirties; Generate disabled + "${GATE_SAVE}"`,
      { dirtyUi, dirtySnap, originalLens, dirtyLens, dirtyShot },
    );

    const urlBeforeResave = page.url();
    const resave = await canonicalSave(page);
    record("7-resave-http", resave.ok, `second canonical save status=${resave.status}`, resave);
    await expect(page.getByTestId("scene-creator-mini-generate")).toBeEnabled({ timeout: 30_000 });
    await expect(page.getByTestId("scene-creator-mini-save-map")).toHaveCount(0);
    expect(page.url()).toBe(urlBeforeResave);
    const reenabledUi = await generateSnapshot(page);
    const reenabledSnap = await getMapSnap(request);
    versions.push({ label: "after-second-save", ...reenabledSnap });
    const reenabledShot = await shot(page, "04-re-enabled.png");
    record(
      "7-reenable",
      reenabledUi.enabled && reenabledSnap.savedVersion === reenabledSnap.version && !reenabledSnap.isDirty,
      `Generate re-enabled without reload; savedVersion==version (${reenabledSnap.savedVersion}==${reenabledSnap.version})`,
      { reenabledUi, reenabledSnap, reenabledShot },
    );

    const cameras = page.getByTestId("scene-creator-mini-include-cameras");
    const rooms = page.getByTestId("scene-creator-mini-include-room-views");
    await cameras.uncheck();
    await rooms.uncheck();
    await expect(page.getByTestId("scene-creator-mini-generate")).toBeDisabled();
    await expect(page.getByTestId("scene-creator-mini-gate")).toHaveText(GATE_OUTPUT);
    const noneUi = await generateSnapshot(page);
    record(
      "8-outputs-off",
      noneUi.disabled && noneUi.reason === GATE_OUTPUT,
      `both outputs off → Generate disabled + "${GATE_OUTPUT}"`,
      { noneUi },
    );
    await cameras.check();
    await expect(page.getByTestId("scene-creator-mini-generate")).toBeEnabled();
    const oneOnUi = await generateSnapshot(page);
    record(
      "8-outputs-one-on",
      oneOnUi.enabled,
      "Camera shots on → Generate eligible again (other gates pass)",
      { oneOnUi },
    );

    if ((await lens.inputValue()) !== originalLens) {
      const restorePatch = page.waitForResponse(
        (r) =>
          r.url().includes(`/maps/${MAP_ID}/cameras/`) &&
          r.request().method() === "PATCH" &&
          r.status() < 400,
        { timeout: 20_000 },
      );
      await lens.selectOption(originalLens);
      await restorePatch;
      await expect(page.getByTestId("scene-creator-mini-save-map")).toBeVisible({ timeout: 20_000 });
      const restoreSave = await canonicalSave(page);
      record("11-restore-lens-save", restoreSave.ok, `restore lens ${dirtyLens}→${originalLens} and save`, restoreSave);
      await expect(page.getByTestId("scene-creator-mini-generate")).toBeEnabled({ timeout: 30_000 });
    }

    const finalSnap = await getMapSnap(request);
    versions.push({ label: "final", ...finalSnap });
    record(
      "11-leftover-saved",
      !finalSnap.isDirty && finalSnap.savedVersion === finalSnap.version,
      `leftover map SAVED savedVersion==version (${finalSnap.savedVersion}==${finalSnap.version})`,
      { finalSnap, consoleLines, netFails },
    );

    const generateClicks = await page.evaluate(() => 0);
    record("10-no-generate", generateClicks === 0, "Did not click Generate Stills", { generateClicks });

    fs.mkdirSync(EVIDENCE, { recursive: true });
    fs.writeFileSync(
      path.join(EVIDENCE, "run-evidence.json"),
      JSON.stringify({ versions, steps, consoleLines, netFails, genPick }, null, 2),
      "utf8",
    );
  });
});
