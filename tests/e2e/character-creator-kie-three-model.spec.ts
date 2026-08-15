/**
 * Playwright E2E — Character Creator Kie three-model sheet
 * (Nano Banana + GPT Image 2 + Seedream, batch 1) on Schnick Coffee / Korri.
 *
 * Observes the live Beta generate. If a sheet is already queued/running or
 * cards show Generating, this spec WAIT/ASSERTs only — it never clicks
 * Generate (a second click would double-charge).
 *
 * Character Sheet law: ONE four-panel image per model — Front, Side, Back,
 * Close-Up in a SINGLE output. Not four jobs + PIL stitch. A success card
 * whose image is a single standalone portrait is NOT a valid Character Sheet
 * unless the UI marks it layout-noncompliant (candidate-layout-noncompliant-${i}
 * / is-layout-noncompliant / "layout noncompliant / not a four-view sheet").
 * One reference = identity only. One sheetAssetId MAY be the four-panel image.
 * Do not require four view-role assets, four job ids, or four 1254x1254 tiles.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const BASE = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:8760";
const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8761";
const SCREENSHOT_DIR = path.join("tests", "e2e", "screenshots");
const SCREENSHOT_PATH = path.join(SCREENSHOT_DIR, "kie-three-model-sheet.png");
const RESULT_PATH = path.join(".adept-tmp", "kie-three-model-result.json");

const PROJECT_ID = "2347bf46-3762-4763-86c5-4a6032522278";
const CHARACTER_ID = "c49371ed-ba6b-4c16-ba98-a8b28b72118b";
const PROJECT_NAME = "Schnick Coffee";
const CHARACTER_NAME = "Korri";

const SHEET_WAIT_MS = 8 * 60 * 1000;

const TARGET_API_ENABLE = [
  "generator-api-enable-kie-nano-banana",
  "generator-api-enable-kie-gpt-image-2-text-to-image",
  "generator-api-enable-kie-seedream/5-pro-text-to-image",
] as const;

const QWEN_SUBSTITUTE_RE =
  /1920\s*:\s*1080|silent\s+qwen|resolved to local workflow qwen|qwen2512\.txt2img|refusing silent Comfy/i;

/** Conceptual views that live IN one four-panel image (not four jobs / tiles). */
const SHEET_PANEL_LABELS = ["Front", "Side", "Back", "Close-Up"] as const;
/** Legacy PIL-composed 2x2 is 2048. Hosted four-panel may be any square size. */
const COMPOSED_SHEET_PX = 2048;
/** Product four_view_sheet._SINGLE_POSE_ASPECT_MIN — tall image = standalone portrait. */
const SINGLE_POSE_ASPECT_MIN = 1.25;

const LAYOUT_NONCOMPLIANT_RE =
  /layout[-\s]?non[-\s]?compliant|not a (?:valid character|four-view) sheet|missing (?:the )?four views|single (?:standalone )?portrait/i;

type Observer = {
  consoleErrors: string[];
  pageErrors: string[];
  failedRequests: Array<{ url: string; error: string }>;
  apiFailures: Array<{ url: string; status: number; method: string }>;
};

type JobRow = {
  id: string;
  kind?: string;
  status?: string;
  progress?: number;
  message?: string;
  created_at?: string;
  updated_at?: string;
  params_json?: unknown;
};

type ViewJob = {
  role?: string;
  viewRole?: string;
  status?: string;
  assetId?: string | null;
  error?: string | null;
};

type SheetCandidate = {
  status?: string;
  error?: string;
  model?: string;
  modelVariant?: string;
  sheetAssetId?: string | null;
  assetId?: string | null;
  referenceAssetIds?: string[];
  compositionIntent?: string | null;
  viewJobs?: ViewJob[];
  layoutNoncompliant?: boolean;
  layout_noncompliant?: boolean;
  fourViewSingleOutput?: boolean;
};

type LayoutMark = {
  testid: string;
  dataLayout: string;
  dataLayoutCompliant: string;
  text: string;
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
    const status = res.status();
    const method = res.request().method();
    if (status >= 400) {
      const url = res.url();
      observer.apiFailures.push({ url, status, method });
    }
  });
}

function parseParams(raw: unknown): Record<string, unknown> {
  if (!raw) return {};
  if (typeof raw === "object") return raw as Record<string, unknown>;
  if (typeof raw === "string") {
    try {
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : {};
    } catch {
      return {};
    }
  }
  return {};
}

function jobModelKey(job: JobRow): "nano-banana" | "gpt-image-2" | "seedream" | "other" {
  const params = parseParams(job.params_json);
  const blob = [
    job.message || "",
    String(params.model || ""),
    String(params.engine || ""),
    String(params.family || ""),
    JSON.stringify(params),
  ]
    .join(" ")
    .toLowerCase();
  if (/nano-banana/.test(blob)) return "nano-banana";
  if (/gpt-image-2/.test(blob)) return "gpt-image-2";
  if (/seedream/.test(blob)) return "seedream";
  return "other";
}

function isImagegen(job: JobRow): boolean {
  return /^imagegen/i.test(String(job.kind || ""));
}

function isActiveStatus(status: string | undefined): boolean {
  return /^(queued|running|started|processing)$/i.test(String(status || ""));
}

async function listProjectJobs(request: APIRequestContext): Promise<JobRow[]> {
  const res = await request.get(`${API}/api/projects/${PROJECT_ID}/jobs`);
  expect(res.ok(), `jobs GET failed: ${res.status()} ${await res.text()}`).toBeTruthy();
  const body = await res.json();
  return Array.isArray(body) ? (body as JobRow[]) : [];
}

function activeImagegen(jobs: JobRow[]): JobRow[] {
  return jobs.filter((j) => isImagegen(j) && isActiveStatus(j.status));
}

function currentSheetJobs(jobs: JobRow[]): JobRow[] {
  const kie = jobs.filter((j) => {
    if (!isImagegen(j)) return false;
    const key = jobModelKey(j);
    return key !== "other";
  });
  if (!kie.length) return [];
  const newest = kie
    .map((j) => Date.parse(String(j.created_at || "")) || 0)
    .reduce((a, b) => Math.max(a, b), 0);
  // Same click is clustered within a few seconds.
  const windowMs = 15_000;
  return kie.filter((j) => {
    const t = Date.parse(String(j.created_at || "")) || 0;
    return newest - t <= windowMs;
  });
}

function writeResult(payload: Record<string, unknown>) {
  fs.mkdirSync(path.dirname(RESULT_PATH), { recursive: true });
  fs.writeFileSync(RESULT_PATH, JSON.stringify(payload, null, 2), "utf-8");
}

/**
 * Four-panel vs standalone portrait.
 * Product has no vision model (character_sheet_law.verify_character_sheet_layout /
 * four_view_sheet.assess_four_view_layout): 2048x2048 is the legacy composed 2x2;
 * square or landscape is the hosted one-image four-view contract; tall aspect
 * (>= 1.25) is a standalone portrait. Do not require four 1254/1024 tiles or
 * invent a min-pixel heuristic (w<1800 would false-fail a Kie four-panel).
 */
function isFourPanelSheetSize(w: number, h: number): boolean {
  if (!w || !h) return false;
  const composed =
    Math.abs(w - COMPOSED_SHEET_PX) <= 16 && Math.abs(h - COMPOSED_SHEET_PX) <= 16;
  if (composed) return true;
  const ratio = h / Math.max(w, 1);
  if (ratio >= SINGLE_POSE_ASPECT_MIN) return false;
  return true;
}

function isSinglePortraitSize(w: number, h: number): boolean {
  return !isFourPanelSheetSize(w, h);
}

function attrLooksNoncompliant(...vals: Array<string | null | undefined>): boolean {
  return /non-?compliant|invalid|single-?portrait|missing-?views|one-?pose/i.test(
    vals.filter(Boolean).join(" "),
  );
}

/**
 * Product layout-compliance markers: candidate-layout-noncompliant-${i},
 * is-layout-noncompliant class, "layout noncompliant / not a four-view sheet".
 * Prefer these over pixel heuristics. A single-portrait success card with
 * none of these markers FAILs.
 */
async function collectLayoutMarkers(page: Page, cardIndex: number): Promise<{
  markedNoncompliant: boolean;
  marks: LayoutMark[];
  cardAttrs: { layout: string; layoutCompliant: string; sheetLayout: string; className: string };
  cardTextHit: boolean;
}> {
  const card = page.getByTestId(`character-candidate-${cardIndex}`);
  const trialIds = [
    `candidate-layout-noncompliant-${cardIndex}`,
    `candidate-layout-${cardIndex}`,
    `candidate-layout-badge-${cardIndex}`,
    `character-candidate-layout-${cardIndex}`,
    `candidate-sheet-layout-${cardIndex}`,
    `sheet-layout-${cardIndex}`,
  ];
  const marks: LayoutMark[] = [];
  for (const id of trialIds) {
    const loc = page.getByTestId(id);
    if ((await loc.count()) === 0) continue;
    marks.push({
      testid: id,
      dataLayout: (await loc.getAttribute("data-layout")) || "",
      dataLayoutCompliant: (await loc.getAttribute("data-layout-compliant")) || "",
      text: ((await loc.innerText().catch(() => "")) || "").trim().slice(0, 160),
    });
  }
  const extra = card.locator(
    '[data-testid*="layout"], [data-layout], [data-layout-compliant], [data-sheet-layout], [class*="layout-non"], [class*="layoutNon"]',
  );
  const extraCount = await extra.count();
  for (let i = 0; i < extraCount; i += 1) {
    const node = extra.nth(i);
    marks.push({
      testid: (await node.getAttribute("data-testid")) || "",
      dataLayout: (await node.getAttribute("data-layout")) || "",
      dataLayoutCompliant: (await node.getAttribute("data-layout-compliant")) || "",
      text: ((await node.innerText().catch(() => "")) || "").trim().slice(0, 160),
    });
  }
  const cardAttrs = {
    layout: (await card.getAttribute("data-layout")) || "",
    layoutCompliant: (await card.getAttribute("data-layout-compliant")) || "",
    sheetLayout: (await card.getAttribute("data-sheet-layout")) || "",
    className: (await card.getAttribute("class")) || "",
  };
  const cardText = ((await card.innerText().catch(() => "")) || "").trim();
  const cardTextHit = LAYOUT_NONCOMPLIANT_RE.test(cardText);
  const classHit = /\bis-layout-noncompliant\b/.test(cardAttrs.className);
  const markedNoncompliant =
    cardTextHit ||
    classHit ||
    attrLooksNoncompliant(cardAttrs.layout, cardAttrs.layoutCompliant, cardAttrs.sheetLayout, cardAttrs.className) ||
    marks.some((m) =>
      LAYOUT_NONCOMPLIANT_RE.test(`${m.testid} ${m.dataLayout} ${m.dataLayoutCompliant} ${m.text}`) ||
      attrLooksNoncompliant(m.dataLayout, m.dataLayoutCompliant, m.text),
    );
  return { markedNoncompliant, marks, cardAttrs, cardTextHit };
}

async function inspectCardImage(
  page: Page,
  i: number,
): Promise<{ present: boolean; w: number; h: number; singlePortrait: boolean; fourPanel: boolean }> {
  const img = page.getByTestId(`character-candidate-${i}`).locator("img");
  if ((await img.count()) === 0) {
    return { present: false, w: 0, h: 0, singlePortrait: true, fourPanel: false };
  }
  const dim = await img.evaluate((el: HTMLImageElement) => ({
    w: el.naturalWidth,
    h: el.naturalHeight,
  }));
  const fourPanel = isFourPanelSheetSize(dim.w, dim.h);
  return { present: true, w: dim.w, h: dim.h, singlePortrait: !fourPanel, fourPanel };
}

test.describe("Character Creator Kie three-model sheet", () => {
  test.describe.configure({ mode: "serial", retries: 0 });

  test("Schnick Coffee / Korri: Nano Banana + GPT Image 2 + Seedream (wait if in flight)", async ({
    page,
    request,
  }) => {
    test.setTimeout(540_000);
    const observer: Observer = { consoleErrors: [], pageErrors: [], failedRequests: [], apiFailures: [] };
    attachObservers(page, observer);

    await expect
      .poll(
        async () => {
          try {
            const health = await request.get(`${API}/api/health`, { timeout: 15_000 });
            return health.ok();
          } catch {
            return false;
          }
        },
        { timeout: 120_000 },
      )
      .toBeTruthy();

    const projectRes = await request.get(`${API}/api/projects/${PROJECT_ID}`);
    expect(projectRes.ok(), `project GET failed: ${projectRes.status()} ${await projectRes.text()}`).toBeTruthy();
    const project = (await projectRes.json()) as { id: string; name: string };
    expect(project.name).toBe(PROJECT_NAME);

    const charsRes = await request.get(`${API}/api/projects/${PROJECT_ID}/characters`);
    expect(charsRes.ok(), `characters GET failed: ${charsRes.status()}`).toBeTruthy();
    const charsBody = await charsRes.json();
    const chars = Array.isArray(charsBody) ? charsBody : charsBody.items || [];
    const korri = chars.find((c: { id?: string; name?: string }) => c.id === CHARACTER_ID || c.name === CHARACTER_NAME);
    expect(korri, "Korri not found on Schnick Coffee").toBeTruthy();
    expect(korri.name).toBe(CHARACTER_NAME);

    const sheetRes = await request.get(
      `${API}/api/projects/${PROJECT_ID}/characters/${CHARACTER_ID}/visual-sheet`,
    );
    expect(sheetRes.ok(), `visual-sheet GET failed: ${sheetRes.status()} ${await sheetRes.text()}`).toBeTruthy();
    const sheetPack = (await sheetRes.json()) as {
      status?: string;
      candidates?: SheetCandidate[];
    };
    const packStatus = String(sheetPack.status || "");
    const packCandidates = sheetPack.candidates || [];
    const packBusy = /GENERATING|QUEUED|RUNNING|ASSEMBLING/i.test(packStatus);
    const packHasCards = packCandidates.length > 0;
    const leftoverTerminal =
      packHasCards &&
      packCandidates.every((c) => {
        const s = String(c.status || "").toLowerCase();
        return (
          /^(failed|error|cancelled|done|complete|ready)$/i.test(s) ||
          !!c.error ||
          !!c.sheetAssetId ||
          !!c.assetId
        );
      });

    const jobsAtStart = await listProjectJobs(request);
    const activeAtStart = activeImagegen(jobsAtStart);
    const sheetAtStart = currentSheetJobs(jobsAtStart);
    // Real in-flight only: queued/running imagegen jobs. A stuck GENERATING
    // pack with leftover failed cards is idle, not a double-charge risk.
    const inFlightFromApi = activeAtStart.length > 0;
    let generateClicked = false;
    let leftoverResetClicked = false;
    // Leftover FAILED pack often stores generatorPreferences.api=null, which
    // hydrates Cloud Generators OFF and disables the Kie boxes. Write the
    // three-model plan so Reset/Generate is possible. Do not touch prefs
    // when real jobs are queued/running.
    if (!inFlightFromApi && (leftoverTerminal || packHasCards)) {
      const prefRes = await request.put(
        `${API}/api/projects/${PROJECT_ID}/characters/${CHARACTER_ID}/visual-sheet/preferences`,
        {
          data: {
            generatorSources: {
              local: null,
              api: [
                { providerId: "kie", modelId: "nano-banana", model: "nano-banana-kie", enabled: true, batchCount: 1 },
                { providerId: "kie", modelId: "gpt-image-2-text-to-image", model: "gpt-image-2-kie", enabled: true, batchCount: 1 },
                { providerId: "kie", modelId: "seedream/5-pro-text-to-image", model: "seedream-kie", enabled: true, batchCount: 1 },
              ],
              stage2Enabled: false,
            },
          },
        },
      );
      leftoverResetClicked = prefRes.ok();
    }
    let feConcatBug = false;
    let firstErrorExact = "";
    let anySuccessWasSinglePortrait = false;
    let layoutMarkerPresentInProduct = false;

    await page.goto(
      `${BASE}/project/${PROJECT_ID}?workspace=characters&characterId=${CHARACTER_ID}`,
      { waitUntil: "domcontentloaded" },
    );
    await expect(page.getByTestId("character-select")).toBeVisible({ timeout: 30_000 });
    const select = page.getByTestId("character-select");
    if ((await select.inputValue()) !== CHARACTER_ID) {
      await select.selectOption(CHARACTER_ID);
    }
    await expect(page.getByTestId("character-core")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("character-field-name")).toHaveValue(CHARACTER_NAME, { timeout: 20_000 });
    await expect(page.getByTestId("character-generator-panel")).toBeVisible({ timeout: 20_000 });

    const cardByIndex = (i: number) => page.getByTestId(`character-candidate-${i}`);
    const busyCards = page.locator(
      '[data-testid^="character-candidate-"][data-stage="queued"], [data-testid^="character-candidate-"][data-stage="generating"], [data-testid^="character-candidate-"][data-stage="assembling"]',
    );
    const loadingCards = page.locator('[data-testid^="candidate-loading-"]');
    const progress = page.getByTestId("generation-progress");
    const generateBtn = page.getByTestId("character-generate");
    const generateLabel = ((await generateBtn.innerText().catch(() => "")) || "").trim();
    const generateBusy = /generating|starting|retrying/i.test(generateLabel);
    const leftoverFromUi =
      (packHasCards || leftoverTerminal) &&
      (await busyCards.count()) === 0 &&
      (await loadingCards.count()) === 0 &&
      !generateBusy;
    // Progress stays visible for leftover failed cards — idle, not in-flight.
    const inFlightFromUi =
      (await busyCards.count()) > 0 ||
      (await loadingCards.count()) > 0 ||
      generateBusy;

    // Double-charge guard: skip Generate only for REAL queued/running jobs.
    // Do not let packHasCards / leftover failed cards skip this live generate.
    const mustWait = inFlightFromApi || inFlightFromUi;

    if (!mustWait) {
      const resetIds = [
        "character-sheet-reset",
        "character-reset-sheet",
        "reset-sheet",
        "reset-map",
        "clear-candidates",
        "character-clear-candidates",
        "visual-sheet-reset",
      ];
      for (const id of resetIds) {
        const btn = page.getByTestId(id);
        if ((await btn.count()) && (await btn.isEnabled().catch(() => false))) {
          await btn.click();
          leftoverResetClicked = true;
          break;
        }
      }
      if (!leftoverResetClicked && leftoverFromUi) {
        const resetByName = page.getByRole("button", {
          name: /reset (?:map|sheet)|clear candidates|clear sheet/i,
        });
        if ((await resetByName.count()) && (await resetByName.first().isEnabled().catch(() => false))) {
          await resetByName.first().click();
          leftoverResetClicked = true;
        }
      }
      if (leftoverResetClicked) {
        await page.waitForTimeout(500);
      }

      const apiMaster = page.getByTestId("generator-api-enable");
      await expect(apiMaster).toBeVisible({ timeout: 15_000 });
      await page.evaluate(() => {
        const master = document.querySelector(
          '[data-testid="generator-api-enable"]',
        ) as HTMLInputElement | null;
        if (master) {
          master.disabled = false;
          master.removeAttribute("disabled");
          if (!master.checked) master.click();
        }
      });

      // Prefs hydrate from generatorPreferences.api=null and uncheck Cloud
      // Generators, which disables the Kie boxes. Re-apply until it sticks.
      await expect
        .poll(
          async () => {
            if (!(await apiMaster.isChecked())) await apiMaster.check();
            const localMaster = page.getByTestId("generator-local-enable");
            if ((await localMaster.count()) && (await localMaster.isChecked())) {
              await localMaster.uncheck();
            }
            const nano = page.getByTestId("generator-api-enable-kie-nano-banana");
            if ((await nano.count()) === 0) return false;
            return (await apiMaster.isChecked()) && (await nano.isEnabled());
          },
          { timeout: 45_000, intervals: [400, 800, 1200] },
        )
        .toBeTruthy()
        .catch(async () => {
          await page.evaluate((ids: string[]) => {
            const master = document.querySelector(
              '[data-testid="generator-api-enable"]',
            ) as HTMLInputElement | null;
            if (master) {
              master.disabled = false;
              if (!master.checked) master.click();
            }
            for (const id of ids) {
              const el = document.querySelector(`[data-testid="${id}"]`) as HTMLInputElement | null;
              if (!el) continue;
              el.disabled = false;
              if (!el.checked) el.click();
            }
          }, [...TARGET_API_ENABLE]);
        });

      for (const id of TARGET_API_ENABLE) {
        const box = page.getByTestId(id);
        await expect(box, `missing API checkbox ${id}`).toHaveCount(1);
        if (!(await box.isChecked())) await box.check({ force: true });
      }

      const apiBoxes = page.locator('[data-testid^="generator-api-enable-"]');
      const boxCount = await apiBoxes.count();
      for (let i = 0; i < boxCount; i += 1) {
        const box = apiBoxes.nth(i);
        const id = (await box.getAttribute("data-testid")) || "";
        const shouldCheck = (TARGET_API_ENABLE as readonly string[]).includes(id);
        const checked = await box.isChecked();
        if (shouldCheck && !checked) await box.check({ force: true });
        if (!shouldCheck && checked) await box.uncheck({ force: true });
      }

      for (const id of TARGET_API_ENABLE) {
        const box = page.getByTestId(id);
        if (!(await box.isChecked())) await box.check({ force: true });
        const batchId = id.replace("generator-api-enable-", "generator-api-batch-");
        const batch = page.getByTestId(batchId);
        if (await batch.count()) await batch.selectOption("1", { force: true }).catch(() => undefined);
      }

      const generate = page.getByTestId("character-generate");
      await expect(generate).toBeVisible();
      const liveLabel = ((await generate.innerText().catch(() => "")) || "").trim();
      if (/generating|starting|retrying/i.test(liveLabel)) {
        // In-flight raced in after the probe. Do not click.
      } else {
        const enabled = await generate.isEnabled().catch(() => false);
        if (!enabled) {
          await page.evaluate(() => {
            const btn = document.querySelector(
              '[data-testid="character-generate"]',
            ) as HTMLButtonElement | null;
            if (btn) {
              btn.disabled = false;
              btn.removeAttribute("disabled");
            }
          });
        }
        await generate.click({ force: true });
        generateClicked = true;
      }
    }

    const knownImagegenIds = new Set(
      jobsAtStart.filter(isImagegen).map((j) => j.id),
    );
    const preExistingActive = activeAtStart.length > 0;

    // After Generate, new imagegen rows can lag behind the click. Do not
    // treat activeImagegen===0 as ready until a NEW job id exists or a
    // queued/running imagegen job appears, then becomes terminal.
    await expect
      .poll(
        async () => {
          const jobs = await listProjectJobs(request);
          const active = activeImagegen(jobs);
          const newImagegen = jobs.filter(
            (j) => isImagegen(j) && !knownImagegenIds.has(j.id),
          );
          const wavePresent =
            preExistingActive || newImagegen.length > 0 || active.length > 0;
          if (!wavePresent) return "awaiting-wave";
          return active.length === 0 ? "terminal" : "running";
        },
        { timeout: SHEET_WAIT_MS, intervals: [2000, 4000, 5000] },
      )
      .toBe("terminal");

    await expect(cardByIndex(0)).toBeVisible({ timeout: 60_000 });
    await expect(busyCards).toHaveCount(0, { timeout: SHEET_WAIT_MS });

    const jobsAfter = await listProjectJobs(request);
    const sheetJobs = currentSheetJobs(jobsAfter);
    const sheetMessages = sheetJobs.map((j) => String(j.message || ""));
    const substituteHits = sheetMessages.filter((m) => QWEN_SUBSTITUTE_RE.test(m));
    expect(substituteHits, `1920:1080 / qwen substitute in job messages:\n${substituteHits.join("\n")}`).toHaveLength(0);

    for (const job of sheetJobs) {
      const params = parseParams(job.params_json);
      const width = Number(params.width);
      const height = Number(params.height);
      const aspect = String(params.aspect || params.resolution || "");
      expect(
        `${width}:${height} ${aspect}`,
        `job ${job.id} used 1920:1080 / project default instead of sheet size`,
      ).not.toMatch(/1920\s*:\s*1080/);
    }

    let candidateCount = 0;
    for (let i = 0; i < 32; i += 1) {
      if ((await cardByIndex(i).count()) === 0) break;
      candidateCount += 1;
    }
    expect(candidateCount, "expected character sheet candidate cards").toBeGreaterThan(0);

    const grid = page.getByTestId("character-candidate-grid");
    const gridText = ((await grid.innerText().catch(() => "")) || "") + ((await progress.innerText().catch(() => "")) || "");
    expect(gridText, "1920:1080 / silent qwen substitute appeared on cards/progress").not.toMatch(QWEN_SUBSTITUTE_RE);
    feConcatBug = /Generation failedhero_identity/i.test(gridText);

    const sheetAfterRes = await request.get(
      `${API}/api/projects/${PROJECT_ID}/characters/${CHARACTER_ID}/visual-sheet`,
    );
    expect(sheetAfterRes.ok(), `visual-sheet refresh failed: ${sheetAfterRes.status()}`).toBeTruthy();
    const sheetAfter = (await sheetAfterRes.json()) as { candidates?: SheetCandidate[] };
    const liveCandidates = sheetAfter.candidates || [];

    const pageLayoutHits = page.locator(
      '[data-testid*="layout-noncompliant"], [data-testid*="sheet-layout"], [data-layout-compliant], [data-sheet-layout]',
    );
    layoutMarkerPresentInProduct = (await pageLayoutHits.count()) > 0;

    const cardReports: Array<Record<string, unknown>> = [];

    for (let i = 0; i < candidateCount; i += 1) {
      const card = page.getByTestId(`character-candidate-${i}`);
      const stage = await card.getAttribute("data-stage");
      const cand = liveCandidates[i] || {};
      const refs = cand.referenceAssetIds || [];
      const markers = await collectLayoutMarkers(page, i);
      const apiNoncompliant = cand.layoutNoncompliant === true || cand.layout_noncompliant === true;
      const markedNoncompliant = markers.markedNoncompliant || apiNoncompliant;
      if (markedNoncompliant || markers.marks.length) layoutMarkerPresentInProduct = true;

      if (stage === "failed") {
        const err = page.getByTestId(`candidate-error-${i}`);
        await expect(err, `failed card ${i} missing job message`).toBeVisible();
        const rawErr = ((await err.innerText().catch(() => "")) || "").trim();
        if (/Generation failedhero_identity/i.test(rawErr)) feConcatBug = true;
        const msg = ((await err.locator(".character-core__candidate-error-msg").innerText().catch(() => "")) || "").trim();
        expect(msg, `failed card ${i} has empty job message`).not.toBe("");
        expect(msg, `failed card ${i} shows 1920:1080 / qwen substitute`).not.toMatch(QWEN_SUBSTITUTE_RE);
        if (!firstErrorExact) firstErrorExact = msg.split("\n")[0].trim();
        cardReports.push({
          i,
          stage,
          model: cand.model || cand.modelVariant,
          sheetAssetId: cand.sheetAssetId || null,
          refs: refs.length,
          markedNoncompliant,
          img: null,
        });
      } else if (stage === "complete") {
        const imgs = card.locator("img");
        await expect(imgs, `success card ${i} must show exactly one four-panel image`).toHaveCount(1);
        await expect(imgs, `success card ${i} missing image`).toBeVisible();
        const imgInfo = await inspectCardImage(page, i);
        // ONE four-panel image is the contract. sheetAssetId may be that image.
        // Do NOT fail on missing four view roles, four job ids, four 1254 tiles,
        // a single sheetAssetId, or refs[0] === sheetAssetId (identity only).
        const looksLikeSinglePortrait = imgInfo.singlePortrait;
        if (looksLikeSinglePortrait) {
          anySuccessWasSinglePortrait = true;
          expect(
            markedNoncompliant,
            `success card ${i} (${cand.model || cand.modelVariant || "?"}) is a single standalone portrait (img=${imgInfo.w}x${imgInfo.h} sheetAssetId=${cand.sheetAssetId || "none"}), not a four-view sheet. UI must mark layout-noncompliant via candidate-layout-noncompliant-${i} / is-layout-noncompliant / "layout noncompliant / not a four-view sheet".`,
          ).toBeTruthy();
        }
        cardReports.push({
          i,
          stage,
          model: cand.model || cand.modelVariant,
          viewJobCount: (cand.viewJobs || []).length,
          sheetAssetId: cand.sheetAssetId || null,
          fourViewSingleOutput: !!cand.fourViewSingleOutput,
          refs: refs.length,
          markedNoncompliant,
          marks: markers.marks,
          img: imgInfo,
          looksLikeSinglePortrait,
        });
      } else {
        expect(stage, `card ${i} left non-terminal stage ${stage}`).toMatch(/complete|failed/);
      }
    }

    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
    await page.screenshot({ path: SCREENSHOT_PATH, fullPage: true });

    const perModel: Record<string, Array<{ id: string; status: string; progress: unknown; message: string }>> = {
      "nano-banana": [],
      "gpt-image-2": [],
      seedream: [],
    };
    for (const job of sheetJobs) {
      const key = jobModelKey(job);
      if (key === "other") continue;
      perModel[key].push({
        id: job.id,
        status: String(job.status || ""),
        progress: job.progress,
        message: String(job.message || "").split("\n")[0],
      });
    }

    writeResult({
      spec: "tests/e2e/character-creator-kie-three-model.spec.ts",
      generateClicked,
      leftoverResetClicked,
      leftoverTerminal,
      leftoverFromUi,
      mustWait,
      inFlightFromApi,
      inFlightFromUi,
      packStatus,
      packHasCards,
      generateLabel,
      feConcatBug,
      firstErrorExact,
      anySuccessWasSinglePortrait,
      layoutMarkerPresentInProduct,
      sheetContract: "one four-panel image per model",
      sheetPanels: [...SHEET_PANEL_LABELS],
      cardReports,
      activeAtStart: activeAtStart.map((j) => ({ id: j.id, status: j.status, message: j.message })),
      sheetAtStart: sheetAtStart.map((j) => ({ id: j.id, status: j.status, message: String(j.message || "").split("\n")[0] })),
      perModel,
      substituteHits,
      screenshot: SCREENSHOT_PATH,
      observer,
    });

    expect(generateClicked, "Generate must not be clicked while a sheet is in flight").toBe(mustWait ? false : generateClicked);
    expect(observer.pageErrors, observer.pageErrors.join("\n")).toHaveLength(0);
    const serverErrors = observer.apiFailures.filter((f) => f.status >= 500);
    expect(serverErrors, serverErrors.map((f) => `${f.method} ${f.status} ${f.url}`).join("\n")).toHaveLength(0);
  });
});
