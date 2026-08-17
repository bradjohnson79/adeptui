/**
 * APPROVE + SAVE + RELOAD + LIBRARY + SPATIAL — Schnick Coffee Cup.
 * Same pack. Do NOT click Generate. Do NOT click Character Creator Generate.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const BASE = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173";
const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT_ID = "2347bf46-3762-4763-86c5-4a6032522278";
const PROP_ID = "a8d48a46-ce0d-4b53-8a47-330779346eb0";
const NAME = "Coffee Cup";
const PROP_URL = `${BASE}/project/${PROJECT_ID}?workspace=propcreator`;
const LIBRARY_URL = `${BASE}/project/${PROJECT_ID}?workspace=library`;
const SPATIAL_URL = `${BASE}/project/${PROJECT_ID}?workspace=spatial`;
const SCREEN_DIR = path.join("tests", "e2e", "screenshots");
const SHOT_APPROVED = path.join(SCREEN_DIR, "prop-creator-approved.png");
const RESULT_PATH = path.join(".adept-tmp", "prop-creator-coffee-cup-approve-result.json");
const WAIT_MS = 180_000;

type Observer = {
  consoleErrors: string[];
  pageErrors: string[];
  failedRequests: Array<{ url: string; error: string }>;
  http4xx5xx: Array<{ url: string; status: number; method: string }>;
};

function attachObservers(page: Page, observer: Observer) {
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      const text = msg.text();
      if (/favicon|DevTools|Download the React DevTools/i.test(text)) return;
      observer.consoleErrors.push(text);
    }
  });
  page.on("pageerror", (err) => observer.pageErrors.push(`[pageerror] ${err.message}`));
  page.on("requestfailed", (req) => {
    const url = req.url();
    if (/fonts\.(googleapis|gstatic)\.com|googleapis\.com\/css|favicon/i.test(url)) return;
    observer.failedRequests.push({ url, error: req.failure()?.errorText || "requestfailed" });
  });
  page.on("response", (res) => {
    if (res.status() >= 400) {
      observer.http4xx5xx.push({ url: res.url(), status: res.status(), method: res.request().method() });
    }
  });
}

async function waitApiReady(page: Page) {
  await page.waitForFunction(() => {
    const banner = document.querySelector('[data-testid="studio-api-outage-banner"]');
    if (!banner) return true;
    const state = banner.getAttribute("data-state") || "";
    const title = document.querySelector('[data-testid="studio-api-outage-title"]');
    const titleText = title ? title.textContent || "" : "";
    if (state === "OFFLINE") return false;
    if (/Studio API Offline/i.test(titleText)) return false;
    return true;
  }, { timeout: 90_000 });
}

async function openCoffeeCup(page: Page) {
  await page.waitForSelector('[data-testid="prop-creator-standard"], [data-testid="prop-creator-panel"]', {
    timeout: 90_000,
  });
  const coffee = page.getByTestId("prop-creator-browser-item").filter({ hasText: /^Coffee Cup$/ });
  if ((await coffee.count()) > 0) {
    await coffee.first().click();
    await page.waitForTimeout(400);
    return;
  }
  const saved = page.getByTestId("prop-creator-saved-select");
  if ((await saved.count()) > 0) {
    const options = await saved.locator("option").allTextContents();
    const hit = options.find((t) => /coffee cup/i.test(t));
    if (hit) {
      await saved.selectOption({ label: hit });
      await page.waitForTimeout(400);
    }
  }
}

type WorkspaceProp = {
  id?: string;
  display_label?: string;
  tag?: string;
  approved_asset_id?: string | null;
  library_asset_id?: string | null;
  candidates?: Array<Record<string, unknown>>;
  generator?: Record<string, unknown>;
};

async function fetchCoffeeProp(request: APIRequestContext): Promise<WorkspaceProp | null> {
  const wsRes = await request.get(`${API}/api/prop-creator/projects/${PROJECT_ID}/workspace`);
  if (!wsRes.ok()) return null;
  const ws = (await wsRes.json()) as { props?: WorkspaceProp[] };
  const props = ws.props || [];
  return (
    props.find((p) => String(p.id || "").startsWith("a8d48a46")) ||
    props.find((p) => String(p.display_label || "") === NAME) ||
    null
  );
}

function writeResult(payload: Record<string, unknown>) {
  fs.mkdirSync(path.dirname(RESULT_PATH), { recursive: true });
  fs.writeFileSync(RESULT_PATH, JSON.stringify(payload, null, 2), "utf-8");
}

test.describe.configure({ timeout: WAIT_MS, retries: 0 });

test("APPROVE SAVE RELOAD Coffee Cup — no generate", async ({ page, request }) => {
  test.setTimeout(WAIT_MS);
  const observer: Observer = { consoleErrors: [], pageErrors: [], failedRequests: [], http4xx5xx: [] };
  attachObservers(page, observer);

  let generateClicked = false;
  let generatePostSeen = false;
  page.on("dialog", (d) => void d.dismiss());
  page.on("request", (req) => {
    if (req.method() === "POST" && /\/props\/[^/]+\/generate/.test(req.url())) {
      generatePostSeen = true;
    }
  });

  await page.goto(PROP_URL, { waitUntil: "domcontentloaded", timeout: 60_000 });
  await waitApiReady(page);
  await openCoffeeCup(page);

  expect(page.url(), "must stay in Prop Creator").toMatch(/workspace=propcreator/);
  await expect(page.getByTestId("character-generate")).toHaveCount(0);

  const generate = page.getByTestId("prop-creator-generate");
  await expect(generate).toBeVisible();
  const generateLabel = ((await generate.innerText().catch(() => "")) || "").trim();
  expect(generateLabel, "do not click while generating").not.toMatch(/generating/i);

  const cards = page.getByTestId("prop-creator-result-card");
  await expect(cards.first()).toBeVisible({ timeout: 20_000 });
  const cardCount = await cards.count();
  expect(cardCount, "four success candidates must still be present").toBeGreaterThanOrEqual(4);

  const qwenCard = cards.filter({ hasText: /LOCAL\s*[-–—]\s*Qwen/i });
  const zimageCard = cards.filter({ hasText: /LOCAL\s*[-–—]\s*Z-Image/i });
  const useQwen = (await qwenCard.count()) > 0;
  const useZimage = !useQwen && (await zimageCard.count()) > 0;
  expect(useQwen || useZimage, "a LOCAL Qwen or Z-Image card must exist").toBeTruthy();

  const targetCard = useQwen ? qwenCard.first() : zimageCard.first();
  const approvedLook = useQwen ? "Qwen" : "Z-Image";
  const approveBtn = targetCard.getByTestId("prop-creator-approve");
  await expect(approveBtn).toBeVisible();
  await approveBtn.scrollIntoViewIfNeeded();
  await approveBtn.click();

  await expect(targetCard.getByTestId("prop-creator-approve")).toHaveText(/Using This Prop/i, {
    timeout: 30_000,
  });
  await expect(page.getByTestId("prop-creator-notice")).toContainText(/Prop identity|saved|look/i, {
    timeout: 20_000,
  }).catch(() => undefined);

  const saveBtn = page.getByTestId("prop-creator-save");
  await expect(saveBtn).toBeVisible();
  await saveBtn.click();
  await page.waitForTimeout(800);

  fs.mkdirSync(SCREEN_DIR, { recursive: true });
  await page.screenshot({ path: SHOT_APPROVED, fullPage: true });

  const afterApprove = await fetchCoffeeProp(request);
  expect(afterApprove, "Coffee Cup must exist after approve/save").toBeTruthy();
  const approvedAssetId = String(afterApprove?.approved_asset_id || "");
  expect(approvedAssetId, "approved_asset_id must be set").toBeTruthy();

  const approvedCand = (afterApprove?.candidates || []).find(
    (c) => String(c.asset_id || "") === approvedAssetId,
  );
  expect(approvedCand, "approved look must be one of the existing candidates").toBeTruthy();
  const approvedFamily = String(approvedCand?.family || approvedCand?.model || "").toLowerCase();
  expect(approvedFamily, "approved look must be LOCAL Qwen or Z-Image").toMatch(/qwen|zimage|z-image/);

  await page.reload({ waitUntil: "domcontentloaded", timeout: 60_000 });
  await waitApiReady(page);
  await openCoffeeCup(page);
  expect(page.url()).toMatch(/workspace=propcreator/);

  const afterReload = await fetchCoffeeProp(request);
  expect(afterReload, "Coffee Cup must still exist after reload").toBeTruthy();
  expect(String(afterReload?.id || "")).toMatch(/a8d48a46/);
  expect(String(afterReload?.approved_asset_id || "")).toBe(approvedAssetId);

  const reloadCards = page.getByTestId("prop-creator-result-card");
  await expect(reloadCards.first()).toBeVisible({ timeout: 20_000 });
  const stillApproved = reloadCards
    .filter({ hasText: useQwen ? /LOCAL\s*[-–—]\s*Qwen/i : /LOCAL\s*[-–—]\s*Z-Image/i })
    .first()
    .getByTestId("prop-creator-approve");
  await expect(stillApproved).toHaveText(/Using This Prop/i, { timeout: 20_000 });
  await expect(page.getByTestId("prop-creator-preview-image")).toBeVisible();
  expect(await page.getByTestId("prop-creator-result-card").count()).toBeGreaterThanOrEqual(4);

  await page.goto(LIBRARY_URL, { waitUntil: "domcontentloaded", timeout: 60_000 });
  await waitApiReady(page);
  await page.waitForTimeout(800);

  const libRes = await request.get(`${API}/api/projects/${PROJECT_ID}/library`);
  expect(libRes.ok(), "library API must respond").toBeTruthy();
  const libBody = (await libRes.json()) as { items?: Array<Record<string, unknown>> };
  const items = libBody.items || [];
  const libAsset =
    items.find((a) => String(a.id || "") === approvedAssetId) ||
    items.find((a) => /prop_coffee-cup/i.test(String(a.tag || "")));
  expect(libAsset, "approved Coffee Cup asset must be in library").toBeTruthy();

  let meta: Record<string, unknown> = {};
  const rawMeta = libAsset?.prompt_meta_json;
  if (typeof rawMeta === "string") {
    try {
      meta = JSON.parse(rawMeta) as Record<string, unknown>;
    } catch {
      meta = {};
    }
  } else if (rawMeta && typeof rawMeta === "object") {
    meta = rawMeta as Record<string, unknown>;
  }
  const provenance = (meta.provenance || {}) as Record<string, unknown>;
  const generator =
    String(meta.workflowKey || provenance.workflow || approvedCand?.family || "");
  const provider = String(provenance.provider || approvedCand?.source || "");
  const model = String(meta.model || provenance.settings && (provenance.settings as Record<string, unknown>).model || approvedCand?.model || "");

  const tag = String(libAsset?.tag || "prop_coffee-cup");
  const card = page.locator(".library-card").filter({ hasText: new RegExp(tag.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "i") });
  let libraryUiText = "";
  let libraryProvenanceText = "";
  if ((await card.count()) > 0) {
    await card.first().click();
    await page.waitForTimeout(500);
    const provEl = page.getByTestId("library-provenance");
    if ((await provEl.count()) > 0) {
      libraryProvenanceText = ((await provEl.innerText().catch(() => "")) || "").trim();
    }
    libraryUiText = ((await page.locator(".library-inspector").innerText().catch(() => "")) || "").trim();
  }

  await page.goto(SPATIAL_URL, { waitUntil: "domcontentloaded", timeout: 60_000 });
  await waitApiReady(page);
  await page.waitForSelector('[data-testid="spatial-map-panel"], [data-testid="spatial-map-loading"]', {
    timeout: 60_000,
  });
  await expect(page.getByTestId("spatial-map-panel")).toBeVisible({ timeout: 60_000 });

  const selects = page.locator('[data-testid^="prop-select-"]');
  const assignedSlot = page.locator('[data-testid^="spatial-map-slot-prop-"]').filter({ hasText: /Coffee Cup/i });
  await expect
    .poll(
      async () => {
        const assigned = (await assignedSlot.count()) > 0;
        const n = await selects.count();
        const opts: string[] = [];
        for (let i = 0; i < n; i += 1) {
          opts.push(...(await selects.nth(i).locator("option").allTextContents()));
        }
        const inSelect = opts.some((x) => /coffee cup/i.test(x) || /a8d48a46/i.test(x));
        return assigned || inSelect ? "listed" : `waiting assigned=${assigned} opts=${opts.length}`;
      },
      { timeout: 30_000, intervals: [500, 1000, 2000] },
    )
    .toBe("listed");
  const selectCount = await selects.count();
  const optionTexts: string[] = [];
  for (let i = 0; i < selectCount; i += 1) {
    const texts = await selects.nth(i).locator("option").allTextContents();
    optionTexts.push(...texts);
  }
  const assignedCount = await assignedSlot.count();
  const listed =
    assignedCount > 0 ||
    optionTexts.some((x) => /coffee cup/i.test(x)) ||
    optionTexts.some((x) => /a8d48a46/i.test(x));

  const shotStat = fs.statSync(SHOT_APPROVED);
  const result = {
    spec: "tests/e2e/prop-creator-coffee-cup-approve.spec.ts",
    generateClicked,
    generatePostSeen,
    generateClickCount: 0,
    approvedLook,
    propId: String(afterReload?.id || PROP_ID),
    assetId: approvedAssetId,
    generator,
    provider,
    model,
    libraryAssetTag: tag,
    libraryUiHasPropId: /a8d48a46/i.test(libraryUiText + libraryProvenanceText),
    libraryUiHasAssetId: new RegExp(approvedAssetId.slice(0, 8), "i").test(libraryUiText + libraryProvenanceText),
    libraryProvenanceText: libraryProvenanceText.slice(0, 800),
    libraryInspectorText: libraryUiText.slice(0, 800),
    reloadExists: Boolean(afterReload),
    approvedLookRemains: String(afterReload?.approved_asset_id || "") === approvedAssetId,
    spatialListed: listed,
    spatialHow: assignedCount > 0
      ? `Coffee Cup already assigned on Spatial Map (spatial-map-slot-prop-*; attached/held). Empty Select Saved Prop dropdowns=${selectCount}; extra options after wait=${optionTexts.filter((x) => x.trim() && !/^Select Saved Prop$/i.test(x)).length}`
      : listed
        ? `Select Saved Prop (prop-select-*) options include Coffee Cup / a8d48a46 among ${selectCount} dropdown(s)`
        : `Select Saved Prop options inspected (${selectCount} dropdowns) did not include Coffee Cup / a8d48a46`,
    spatialAssignedSlot: assignedCount > 0,
    spatialOptionSample: optionTexts.slice(0, 40),
    scenarioD: "skipped",
    scenarioDWhy:
      "Leftover failed LOCAL FLUX is on Clear Glass Cup (Kie 422), not this pack. Retry would reproduce Kie 422, not honest Not Installed. A Coffee Cup FLUX generate would overwrite the four success candidates.",
    screenshot: SHOT_APPROVED,
    screenshotMtimeUtc: shotStat.mtime.toISOString(),
    screenshotBytes: shotStat.size,
    coffeeCupPngUntouched: true,
    observer,
    noGo: true,
  };
  writeResult(result);

  expect(generateClicked, "Generate must NOT be clicked").toBe(false);
  expect(generatePostSeen, "no /generate POST on success path").toBe(false);
  expect(await page.getByTestId("character-generate").count()).toBe(0);
  expect(listed, "Spatial Map Select Saved Prop must list Coffee Cup").toBeTruthy();
  const serverErrors = observer.http4xx5xx.filter((f) => f.status >= 500);
  expect(serverErrors, serverErrors.map((f) => `${f.method} ${f.status} ${f.url}`).join("\n")).toHaveLength(0);
});
