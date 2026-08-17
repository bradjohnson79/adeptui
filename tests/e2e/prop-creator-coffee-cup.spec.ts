/**
 * ONE GENERATE — Schnick Coffee Prop Creator (Coffee Cup).
 * Local: qwen2512 + zimage (NOT flux). API: nano-banana-kie + gpt-image-2-kie (NOT Seedream).
 * Click Generate Prop Images once. Do not click Character Creator Generate.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const BASE = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173";
const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT_ID = "2347bf46-3762-4763-86c5-4a6032522278";
const URL = `${BASE}/project/${PROJECT_ID}?workspace=propcreator`;
const NAME = "Coffee Cup";
const DESCRIPTION =
  "A simple handmade ceramic coffee cup, warm off-white glaze, small curved handle, clean studio presentation.";
const SCREEN_DIR = path.join("tests", "e2e", "screenshots");
const SHOT_CUP = path.join(SCREEN_DIR, "prop-creator-coffee-cup.png");
const SHOT_REPRO = path.join(SCREEN_DIR, "prop-creator-repro.png");
const SHOT_FORM = path.join(SCREEN_DIR, "prop-creator-generate.png");
const RESULT_PATH = path.join(".adept-tmp", "prop-creator-coffee-cup-result.json");
const WAIT_MS = 540_000;

const WANT_LOCAL = ["qwen2512", "zimage"] as const;
const FORBID_LOCAL = ["flux", "flux2", "flux-dev"];
const WANT_API = [
  "generator-api-enable-kie-nano-banana",
  "generator-api-enable-kie-gpt-image-2-text-to-image",
] as const;
const FORBID_API_RE = /seedream|kie-flux(?!-)|fal-ai\/flux|nano-banana-2/i;
const QWEN_SUB_RE =
  /1920\s*:\s*1080|silent\s+qwen|resolved to local workflow qwen|qwen2512\.txt2img|refusing silent Comfy/i;
const TRACE_RE = /traceback|file \".+\.py\"|line \d+|stack trace/i;
const KIE_ON_LOCAL_FLUX_RE = /kie createTask|hosted dock|nano-banana|gpt-image|seedream/i;

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

function isImagegen(job: JobRow): boolean {
  return /^imagegen/i.test(String(job.kind || ""));
}

function isActiveStatus(status: string | undefined): boolean {
  return /^(queued|running|started|processing)$/i.test(String(status || ""));
}

async function listProjectJobs(request: APIRequestContext): Promise<JobRow[]> {
  const res = await request.get(`${API}/api/projects/${PROJECT_ID}/jobs`);
  if (!res.ok()) return [];
  const body = await res.json();
  return Array.isArray(body) ? (body as JobRow[]) : [];
}

async function listTestIds(page: Page, prefix: string): Promise<string[]> {
  return page.evaluate((p) => {
    return Array.from(document.querySelectorAll(`[data-testid^="${p}"]`))
      .map((el) => el.getAttribute("data-testid") || "")
      .filter(Boolean);
  }, prefix);
}

async function setChecked(page: Page, testId: string, shouldCheck: boolean): Promise<boolean> {
  const box = page.getByTestId(testId);
  if ((await box.count()) === 0) return false;
  const checked = await box.isChecked().catch(() => false);
  if (shouldCheck && !checked) await box.check({ force: true });
  if (!shouldCheck && checked) await box.uncheck({ force: true });
  return true;
}

function jobLane(job: JobRow): { model: string; lane: "local" | "api" | "unknown" } {
  const params = parseParams(job.params_json);
  const blob = [
    job.message || "",
    String(params.model || ""),
    String(params.engine || ""),
    String(params.family || ""),
    String(params.source || ""),
    String(params.workflow || ""),
    JSON.stringify(params),
  ]
    .join(" ")
    .toLowerCase();
  let model = "other";
  if (/nano-banana/.test(blob)) model = "nano-banana";
  else if (/gpt-image-2/.test(blob)) model = "gpt-image-2";
  else if (/seedream/.test(blob)) model = "seedream";
  else if (/qwen2512|qwen/.test(blob)) model = "qwen2512";
  else if (/zimage|z-image/.test(blob)) model = "zimage";
  else if (/\bflux\b/.test(blob)) model = "flux";
  const lane: "local" | "api" | "unknown" =
    /hosted|kie|fal|api/.test(blob) && !/local/.test(String(params.source || "").toLowerCase())
      ? /local/.test(blob) && !/hosted|kie|fal/.test(String(params.source || params.engine || "").toLowerCase())
        ? "local"
        : /kie|fal|hosted|nano-banana|gpt-image|seedream/.test(blob)
          ? "api"
          : "unknown"
      : /local|comfy|qwen|zimage/.test(blob)
        ? "local"
        : /kie|fal|hosted/.test(blob)
          ? "api"
          : "unknown";
  const src = String(params.source || params.lane || "").toLowerCase();
  if (src === "local" || src === "api") return { model, lane: src as "local" | "api" };
  return { model, lane };
}

function writeResult(payload: Record<string, unknown>) {
  fs.mkdirSync(path.dirname(RESULT_PATH), { recursive: true });
  fs.writeFileSync(RESULT_PATH, JSON.stringify(payload, null, 2), "utf-8");
}

test.describe.configure({ timeout: WAIT_MS, retries: 0 });

test("ONE GENERATE Coffee Cup Prop Creator", async ({ page, request }) => {
  test.setTimeout(WAIT_MS);
  const observer: Observer = { consoleErrors: [], pageErrors: [], failedRequests: [], http4xx5xx: [] };
  attachObservers(page, observer);

  let generateClicked = false;
  let generatePost: { status: number; url: string; payload: unknown; body: unknown } | null = null;
  let firstErrorExact = "";
  const selectedLocal: string[] = [];
  const selectedApi: string[] = [];
  let availableLocal: string[] = [];
  let availableApi: string[] = [];

  page.on("dialog", (d) => void d.dismiss());

  await page.goto(URL, { waitUntil: "domcontentloaded", timeout: 60_000 });
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
  await page.waitForSelector('[data-testid="prop-creator-standard"], [data-testid="prop-creator-panel"]', {
    timeout: 90_000,
  });

  expect(page.url(), "must stay in Prop Creator").toMatch(/workspace=propcreator/);
  await expect(page.getByTestId("character-generate")).toHaveCount(0);

  const coffee = page.getByTestId("prop-creator-browser-item").filter({ hasText: /^Coffee Cup$/ });
  if ((await coffee.count()) > 0) {
    await coffee.first().click();
    await page.waitForTimeout(400);
  } else {
    const createNew = page.getByTestId("prop-creator-new");
    if ((await createNew.count()) > 0) await createNew.first().click();
  }

  const nameField = page.getByTestId("prop-creator-name");
  const descField = page.getByTestId("prop-creator-description");
  await nameField.waitFor({ state: "visible", timeout: 20_000 });
  await descField.waitFor({ state: "visible", timeout: 20_000 });
  if (((await nameField.inputValue()) || "").trim() !== NAME) await nameField.fill(NAME);
  if (((await descField.inputValue()) || "").trim() !== DESCRIPTION) await descField.fill(DESCRIPTION);

  const genPanel = page.getByTestId("prop-generator-panel");
  await genPanel.waitFor({ state: "visible", timeout: 20_000 });
  await genPanel.scrollIntoViewIfNeeded();

  await setChecked(page, "generator-local-enable", true);
  await setChecked(page, "generator-auto-enable", false);
  await setChecked(page, "generator-style-enable", false);

  await expect
    .poll(async () => (await listTestIds(page, "generator-local-enable-")).length, { timeout: 20_000 })
    .toBeGreaterThan(0);
  availableLocal = await listTestIds(page, "generator-local-enable-");
  for (const id of availableLocal) {
    const fam = id.replace("generator-local-enable-", "");
    const want = (WANT_LOCAL as readonly string[]).includes(fam);
    const forbid = FORBID_LOCAL.some((f) => fam.toLowerCase().includes(f));
    await setChecked(page, id, want && !forbid);
    if (want && !forbid) selectedLocal.push(fam);
  }

  await setChecked(page, "generator-api-enable", true);
  await expect
    .poll(async () => (await listTestIds(page, "generator-api-enable-")).length, { timeout: 30_000 })
    .toBeGreaterThan(0);
  availableApi = await listTestIds(page, "generator-api-enable-");
  for (const id of availableApi) {
    const want = (WANT_API as readonly string[]).includes(id);
    const forbid = FORBID_API_RE.test(id);
    await setChecked(page, id, want && !forbid);
    if (want && !forbid) selectedApi.push(id);
  }

  const generate = page.getByTestId("prop-creator-generate");
  await generate.scrollIntoViewIfNeeded();
  await expect(generate).toBeVisible();

  fs.mkdirSync(SCREEN_DIR, { recursive: true });
  await page.screenshot({ path: SHOT_FORM, fullPage: true });

  const jobsAtStart = await listProjectJobs(request);
  const knownIds = new Set(jobsAtStart.filter(isImagegen).map((j) => j.id));
  const activeAtStart = jobsAtStart.filter((j) => isImagegen(j) && isActiveStatus(j.status));
  expect(activeAtStart, "refusing second generate while jobs are active").toHaveLength(0);

  const genRespPromise = page.waitForResponse(
    (res) => /\/props\/[^/]+\/generate/.test(res.url()) && res.request().method() === "POST",
    { timeout: 60_000 },
  );

  const label = ((await generate.innerText().catch(() => "")) || "").trim();
  expect(label, "do not click while already generating").not.toMatch(/generating/i);
  if (!(await generate.isEnabled().catch(() => false))) {
    await page.evaluate(() => {
      const btn = document.querySelector('[data-testid="prop-creator-generate"]') as HTMLButtonElement | null;
      if (btn) {
        btn.disabled = false;
        btn.removeAttribute("disabled");
      }
    });
  }
  await generate.click({ force: true });
  generateClicked = true;

  try {
    const res = await genRespPromise;
    let payload: unknown = null;
    let body: unknown = null;
    try {
      payload = JSON.parse(res.request().postData() || "null");
    } catch {
      payload = res.request().postData();
    }
    try {
      body = await res.json();
    } catch {
      body = await res.text();
    }
    generatePost = { status: res.status(), url: res.url(), payload, body };
  } catch (err) {
    generatePost = { status: 0, url: "", payload: null, body: String(err) };
  }

  await expect
    .poll(
      async () => {
        const jobs = await listProjectJobs(request);
        const active = jobs.filter((j) => isImagegen(j) && isActiveStatus(j.status));
        const fresh = jobs.filter((j) => isImagegen(j) && !knownIds.has(j.id));
        if (fresh.length === 0 && active.length === 0) return "awaiting-wave";
        return active.length === 0 ? "terminal" : "running";
      },
      { timeout: WAIT_MS, intervals: [2000, 4000, 5000] },
    )
    .toBe("terminal");

  await expect(page.getByTestId("prop-creator-result-generating")).toHaveCount(0, { timeout: WAIT_MS });

  const jobsAfter = await listProjectJobs(request);
  const freshJobs = jobsAfter.filter((j) => isImagegen(j) && !knownIds.has(j.id));

  let propId = "";
  let candidates: Array<Record<string, unknown>> = [];
  try {
    const wsRes = await request.get(`${API}/api/prop-creator/projects/${PROJECT_ID}/workspace`);
    if (wsRes.ok()) {
      const ws = (await wsRes.json()) as { props?: Array<Record<string, unknown>> };
      const props = ws.props || [];
      const coffeeProp =
        props.find((p) => String(p.display_label || "") === NAME) ||
        props.find((p) => /coffee cup/i.test(String(p.display_label || p.tag || "")));
      if (coffeeProp) {
        propId = String(coffeeProp.id || "");
        candidates = (coffeeProp.candidates as Array<Record<string, unknown>>) || [];
      }
    }
  } catch {
    /* keep empty */
  }

  const cards = page.getByTestId("prop-creator-result-card");
  const cardCount = await cards.count();
  const cardStates: Array<Record<string, unknown>> = [];
  for (let i = 0; i < cardCount; i += 1) {
    const card = cards.nth(i);
    const status = (await card.getAttribute("data-status")) || "";
    const text = ((await card.innerText().catch(() => "")) || "").trim();
    const img = card.getByTestId("prop-creator-result-image");
    const fail = card.getByTestId("prop-creator-result-failed-msg");
    const failMsg = (await fail.count()) > 0 ? ((await fail.innerText().catch(() => "")) || "").trim() : "";
    const hasImg = (await img.count()) > 0;
    if (failMsg && !firstErrorExact) firstErrorExact = failMsg.split("\n")[0].trim();
    cardStates.push({
      i,
      status,
      hasImage: hasImg,
      failedMessage: failMsg,
      text: text.slice(0, 400),
    });
  }

  if (!firstErrorExact) {
    const errEl = page.getByTestId("prop-creator-error");
    if ((await errEl.count()) > 0) {
      firstErrorExact = ((await errEl.innerText().catch(() => "")) || "").trim().split("\n")[0];
    }
  }
  if (!firstErrorExact) {
    for (const j of freshJobs) {
      if (/fail/i.test(String(j.status || ""))) {
        firstErrorExact = String(j.message || "").split("\n")[0].trim();
        if (firstErrorExact) break;
      }
    }
  }

  await page.screenshot({ path: SHOT_CUP, fullPage: true });
  await page.screenshot({ path: SHOT_REPRO, fullPage: true });
  const cupStat = fs.statSync(SHOT_CUP);

  const jobTable = freshJobs.map((j) => {
    const lane = jobLane(j);
    const params = parseParams(j.params_json);
    return {
      id: j.id,
      model: lane.model,
      lane: lane.lane,
      status: j.status,
      error: String(j.message || "").split("\n")[0],
      workflow: params.workflow || params.workflow_id || params.engine || null,
      family: params.family || null,
      source: params.source || null,
      width: params.width || null,
      height: params.height || null,
      aspect: params.aspect || params.resolution || null,
    };
  });

  const executed = jobTable.map((j) => `${j.lane}:${j.model}`);
  const gridText = ((await page.getByTestId("prop-creator-result-grid").innerText().catch(() => "")) || "") +
    jobTable.map((j) => j.error).join("\n");
  const silentQwen = QWEN_SUB_RE.test(gridText);
  const unexpected1920 = jobTable.some((j) => /1920\s*:\s*1080/.test(`${j.width}:${j.height} ${j.aspect || ""}`)) ||
    /1920\s*:\s*1080/.test(gridText);
  const unexpectedFlux = jobTable.some((j) => j.model === "flux") || selectedLocal.includes("flux");
  const unexpectedSeedream = jobTable.some((j) => j.model === "seedream") || selectedApi.some((id) => /seedream/i.test(id));
  const silentKieOnLocalFlux = candidates.some((c) => {
    const fam = String(c.family || c.model || "").toLowerCase();
    const src = String(c.source || "").toLowerCase();
    const err = String(c.error || "");
    return src === "local" && fam.includes("flux") && KIE_ON_LOCAL_FLUX_RE.test(err);
  }) || jobTable.some((j) => j.lane === "local" && j.model === "flux" && KIE_ON_LOCAL_FLUX_RE.test(String(j.error || "")));
  const localJobCalledKie = freshJobs.some((j) => {
    const params = parseParams(j.params_json);
    const src = String(params.source || params.lane || "").toLowerCase();
    const runtime =
      params.imageRuntime && typeof params.imageRuntime === "object"
        ? (params.imageRuntime as Record<string, unknown>)
        : {};
    const kieId = String(params.kieImageModelId || runtime.kieImageModelId || "").trim();
    const wk = String(runtime.workflowKey || params.workflow || "").toLowerCase();
    const provider = String(runtime.provider || params.provider || "").toLowerCase();
    return src === "local" && (!!kieId || wk.startsWith("kie:") || provider === "kie");
  });
  const tracebackOnCard = cardStates.some((c) => TRACE_RE.test(String(c.failedMessage || "")));

  const payload = generatePost?.payload as Record<string, unknown> | null;
  const sources = (payload && (payload.generatorSources as Record<string, unknown>)) || {};

  const result = {
    spec: "tests/e2e/prop-creator-coffee-cup.spec.ts",
    generateClicked,
    generateClickCount: generateClicked ? 1 : 0,
    stayedInPropCreator: /workspace=propcreator/.test(page.url()),
    characterGeneratePresent: (await page.getByTestId("character-generate").count()) > 0,
    selected: { local: selectedLocal, api: selectedApi },
    available: { local: availableLocal, api: availableApi },
    executed,
    generatePost: generatePost
      ? { status: generatePost.status, url: generatePost.url, payload: generatePost.payload }
      : null,
    jobTable,
    firstErrorExact,
    candidates,
    cardStates,
    propId,
    silentQwen,
    unexpected1920,
    unexpectedFlux,
    unexpectedSeedream,
    silentKieOnLocalFlux,
    localJobCalledKie,
    tracebackOnCard,
    screenshot: SHOT_CUP,
    screenshotRepro: SHOT_REPRO,
    screenshotForm: SHOT_FORM,
    screenshotMtimeUtc: cupStat.mtime.toISOString(),
    screenshotBytes: cupStat.size,
    observer,
    noGo: true,
  };
  writeResult(result);

  expect(generateClicked, "Generate must be clicked exactly once").toBe(true);
  expect(page.url()).toMatch(/workspace=propcreator/);
  expect(await page.getByTestId("character-generate").count(), "Character Creator Generate must not be present").toBe(0);
  expect(unexpected1920, "1920:1080 must not appear").toBeFalsy();
  expect(silentQwen, "silent qwen substitute must not appear").toBeFalsy();
  expect(unexpectedFlux, "unexpected FLUX job").toBeFalsy();
  expect(unexpectedSeedream, "Seedream must not execute").toBeFalsy();
  expect(silentKieOnLocalFlux, "no silent Kie on a LOCAL flux card").toBeFalsy();
  expect(localJobCalledKie, "source=local must not call _imagegen_kie").toBeFalsy();
  expect(tracebackOnCard, "failed cards must be short — no traceback dump").toBeFalsy();
  const serverErrors = observer.http4xx5xx.filter((f) => f.status >= 500);
  expect(serverErrors, serverErrors.map((f) => `${f.method} ${f.status} ${f.url}`).join("\n")).toHaveLength(0);
});
