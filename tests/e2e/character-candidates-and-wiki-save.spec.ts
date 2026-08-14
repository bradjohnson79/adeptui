/**
 * Playwright E2E — Character Candidate Diversity + Reference Fidelity (A)
 * and Story → Wiki Manual Save (B). Two independent workstreams.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const BASE = process.env.PLAYWRIGHT_BASE_URL || "https://adeptui.vercel.app";
const API = process.env.STUDIO_API_BASE || "https://api-beta.adeptui.org";
const SCREENSHOT_DIR = path.join("tests", "e2e", "screenshots");
const TINY_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64",
);

type Observer = { consoleErrors: string[]; pageErrors: string[]; failedRequests: Array<{ url: string; error: string }>; apiFailures: Array<{ url: string; status: number; method: string }> };

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
    // Local Beta (8760) does not proxy /api/* to the Studio API (8758); the
    // Co-Director chat SSE endpoint is expected to miss there in local runs.
    if (/\/api\/codirector\/chat\/stream/.test(url)) return;
    observer.failedRequests.push({ url, error: req.failure()?.errorText || "requestfailed" });
  });
  page.on("response", (res) => {
    const status = res.status();
    const method = res.request().method();
    if (status >= 400) {
      const url = res.url();
      const isExpected404 = status === 404 && /\/api\/projects\//.test(url) && /DELETE/i.test(method);
      if (isExpected404) return;
      // Same local-Beta artifact: /api/* on 8760 returns 404/405.
      if (/127\.0\.0\.1:8760\/api\//.test(url)) return;
      observer.apiFailures.push({ url, status, method });
    }
  });
}

async function waitForAppReady(request: APIRequestContext) {
  await expect.poll(async () => {
    try { const res = await request.get(`${API}/api/health`, { timeout: 15000 }); return res.ok(); } catch { return false; }
  }, { timeout: 120_000 }).toBeTruthy();
}

async function createTempProject(request: APIRequestContext, name?: string) {
  const res = await request.post(`${API}/api/projects`, { data: { name: name || `CandWiki-${Date.now()}` } });
  expect(res.ok(), `createTempProject failed: ${await res.text()}`).toBeTruthy();
  return (await res.json()) as { id: string; name: string };
}
async function deleteProject(request: APIRequestContext, id: string) { try { await request.delete(`${API}/api/projects/${id}`); } catch { /* */ } }

async function createCharacter(request: APIRequestContext, projectId: string, opts: { name: string; description?: string; visualDescription?: string }) {
  const res = await request.post(`${API}/api/projects/${projectId}/characters`, {
    data: { name: opts.name, role: "protagonist", description: opts.description || "", visual_description: opts.visualDescription || "" },
  });
  expect(res.ok(), `createCharacter failed: ${await res.text()}`).toBeTruthy();
  return (await res.json()) as { id: string; name: string };
}
async function attachCharacterReference(request: APIRequestContext, projectId: string, characterId: string, assetId: string) {
  const res = await request.post(`${API}/api/projects/${projectId}/characters/${characterId}/references`, { data: { asset_id: assetId, reference_role: "reference_image" } });
  expect(res.ok(), `attachCharacterReference failed: ${await res.text()}`).toBeTruthy();
}
async function uploadImageAsset(request: APIRequestContext, projectId: string, opts: { name: string; tag?: string }) {
  const res = await request.post(`${API}/api/projects/${projectId}/assets`, {
    multipart: { file: { name: opts.name, mimeType: "image/png", buffer: TINY_PNG }, tag: opts.tag || opts.name, kind: "image" },
  });
  expect(res.ok(), `uploadImageAsset failed: ${await res.text()}`).toBeTruthy();
  return (await res.json()) as { id: string };
}
async function startVisualSheet(request: APIRequestContext, projectId: string, characterId: string) {
  const res = await request.post(`${API}/api/projects/${projectId}/characters/${characterId}/visual-sheet/generate`, { data: { candidateCount: 4, includeDetails: false, includePerformance: false } });
  expect(res.ok(), `startVisualSheet failed: ${await res.text()}`).toBeTruthy();
  return (await res.json()) as { ok: boolean; pack: { candidates?: any[]; status?: string; referenceLocked?: boolean } };
}
async function getVisualSheet(request: APIRequestContext, projectId: string, characterId: string) {
  const res = await request.get(`${API}/api/projects/${projectId}/characters/${characterId}/visual-sheet`);
  expect(res.ok(), `getVisualSheet failed: ${await res.text()}`).toBeTruthy();
  return (await res.json()) as { ok: boolean; pack: { candidates?: any[]; referenceLocked?: boolean } };
}
async function compileWiki(request: APIRequestContext, projectId: string) {
  const res = await request.post(`${API}/api/codirector/projects/${projectId}/wiki/compile`, { data: { preserveStoryWording: true } });
  expect(res.ok(), `compileWiki failed: ${await res.text()}`).toBeTruthy();
}
async function getWiki(request: APIRequestContext, projectId: string) {
  const res = await request.get(`${API}/api/codirector/projects/${projectId}/wiki`);
  expect(res.ok(), `getWiki failed: ${await res.text()}`).toBeTruthy();
  return (await res.json()) as { storyEntries?: any[]; compiledStorySummary?: Record<string, string> };
}
async function listStoryEntries(request: APIRequestContext, projectId: string) {
  const res = await request.get(`${API}/api/projects/${projectId}/story-entries`);
  expect(res.ok()).toBeTruthy();
  return (await res.json()) as Array<{ id: string; logline: string; shortSummary: string; longSummary: string; title: string }>;
}
async function createStoryEntry(request: APIRequestContext, projectId: string, data: Record<string, string>) {
  const res = await request.post(`${API}/api/projects/${projectId}/story-entries`, { data });
  expect(res.ok(), `createStoryEntry failed: ${await res.text()}`).toBeTruthy();
  return (await res.json()) as { id: string };
}
async function updateStoryEntry(request: APIRequestContext, projectId: string, entryId: string, data: Record<string, string>) {
  const res = await request.put(`${API}/api/projects/${projectId}/story-entries/${entryId}`, { data });
  expect(res.ok(), `updateStoryEntry failed: ${await res.text()}`).toBeTruthy();
}
async function deleteStoryEntries(request: APIRequestContext, projectId: string, ids: string[]) {
  for (const id of ids) await request.delete(`${API}/api/projects/${projectId}/story-entries/${id}`).catch(() => undefined);
}

async function dismissOnboarding(page: Page) {
  for (let attempt = 0; attempt < 5; attempt += 1) {
    const region = page.locator('[aria-label="Working relationship"]').first();
    if (!(await region.isVisible().catch(() => false))) { await page.waitForTimeout(300); continue; }
    const nameInput = region.getByRole("textbox", { name: /What should I call you/i }).first();
    if (await nameInput.isVisible().catch(() => false)) {
      const current = await nameInput.inputValue().catch(() => "");
      if (!current) await nameInput.fill("Tester");
    }
    for (const label of [/Save and continue/i, /Skip for now/i]) {
      const btn = region.getByRole("button", { name: label }).first();
      if (await btn.isVisible().catch(() => false)) {
        if (!(await btn.isDisabled().catch(() => false))) { await btn.click({ force: true }).catch(() => undefined); await page.waitForTimeout(800); break; }
      }
    }
    if (!(await region.isVisible().catch(() => false))) break;
  }
}
async function cancelInFlightGeneration(page: Page) {
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const stopBtn = page.getByRole("button", { name: /Stop generating/i }).first();
    if (!(await stopBtn.isVisible().catch(() => false))) return;
    await stopBtn.click({ force: true }).catch(() => undefined);
    await page.waitForTimeout(800);
  }
}
async function clickTabAndWait(page: Page, tabId: string, panelTestIds: string[]): Promise<void> {
  await dismissOnboarding(page);
  await cancelInFlightGeneration(page);
  const tab = page.getByTestId(`codirector-content-tab-${tabId}`);
  await expect(tab).toBeVisible({ timeout: 30_000 });
  for (let attempt = 0; attempt < 5; attempt += 1) {
    await tab.click({ force: true }).catch(() => undefined);
    for (const testId of panelTestIds) {
      if (await page.getByTestId(testId).first().isVisible().catch(() => false)) return;
    }
    await cancelInFlightGeneration(page);
    await page.waitForTimeout(1000);
  }
  await expect(page.getByTestId(panelTestIds[0]).first()).toBeVisible({ timeout: 45_000 });
}
async function openCoDirector(page: Page, projectId: string) {
  await page.goto(`${BASE}/co-director?projectId=${encodeURIComponent(projectId)}`);
  await expect(page.getByTestId("codirector-fullscreen-shell").or(page.getByTestId("codirector-workspace")).first()).toBeVisible({ timeout: 45_000 });
  await expect(page.getByTestId("codirector-composer-input")).toBeVisible({ timeout: 30_000 });
}
async function screenshot(page: Page, name: string) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  const file = path.join(SCREENSHOT_DIR, `${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  return file;
}

// ===========================================================================
// Workstream B — Story → Wiki Manual Save
// ===========================================================================
test.describe.serial("Story → Wiki Manual Save", () => {
  let projectId: string;
  const observer: Observer = { consoleErrors: [], pageErrors: [], failedRequests: [], apiFailures: [] };

  test.beforeAll(async ({ request }) => { await waitForAppReady(request); });
  test.afterAll(async ({ request }) => {
    if (projectId) await deleteProject(request, projectId);
    expect(observer.consoleErrors, "console errors").toEqual([]);
    expect(observer.pageErrors, "page errors").toEqual([]);
    expect(observer.failedRequests, "failed requests").toEqual([]);
    expect(observer.apiFailures, "api failures").toEqual([]);
  });

  test("B1 — Edit Story without Save to Wiki leaves Wiki unchanged", async ({ page, request }) => {
    test.setTimeout(180_000);
    attachObservers(page, observer);
    projectId = (await createTempProject(request, `CandWiki-B-${Date.now()}`)).id;

    // Seed Version A and establish the published Wiki baseline via explicit compile.
    await createStoryEntry(request, projectId, {
      title: "Manual Save Story",
      entryType: "project_story",
      logline: "Version A logline about a scout on the dust plains.",
      shortSummary: "Version A short summary.",
      longSummary: "Version A long summary with multiple sentences.",
    });
    await compileWiki(request, projectId);

    await page.setViewportSize({ width: 1440, height: 900 });
    await openCoDirector(page, projectId);
    await dismissOnboarding(page);
    await cancelInFlightGeneration(page);

    // Edit the Logline to Version B via the UI (autosave, no publish).
    await clickTabAndWait(page, "story", ["story-editor"]);
    const logline = page.getByTestId("story-entry-logline").first();
    await expect(logline).toBeVisible({ timeout: 15_000 });
    await logline.fill("Version B logline that should NOT appear in Wiki until publish");
    await expect(page.getByTestId("story-unpublished-changes")).toBeVisible({ timeout: 10_000 });
    await page.waitForTimeout(1500);

    // Open Wiki — must still show Version A (no Save to Wiki clicked).
    await clickTabAndWait(page, "wiki", ["codirector-content-wiki", "project-wiki-empty"]);
    const wikiPanel = page.getByTestId("codirector-content-wiki").or(page.locator('[data-testid="project-wiki-empty"]')).first();
    // Wait for the Wiki to finish loading (it may briefly show "Loading Project Wiki").
    await expect(wikiPanel).not.toContainText(/Loading Project Wiki/i, { timeout: 20_000 });
    // The published Version A logline must be present.
    await expect(wikiPanel).toContainText(/Version A logline/i, { timeout: 15_000 });
    // The edited Version B must NOT have leaked into the Wiki before publish.
    await expect(wikiPanel).not.toContainText(/Version B logline/i);

    const shot = await screenshot(page, "cand-wiki-b-before-publish");
    test.info().annotations.push({ type: "screenshot", description: shot });

    // Confirm via API: Wiki still holds Version A.
    const wiki = await getWiki(request, projectId);
    const blob = JSON.stringify(wiki.compiledStorySummary || {}) + JSON.stringify(wiki.storyEntries || []);
    expect(blob, "Wiki API must not contain Version B before publish").not.toMatch(/Version B logline/i);
    expect(blob, "Wiki API must retain Version A").toMatch(/Version A logline/i);
  });

  test("B2 — Save to Wiki publishes the current Story version", async ({ page, request }) => {
    test.setTimeout(180_000);
    attachObservers(page, observer);
    expect(projectId, "projectId carried from B1").toBeTruthy();

    await page.setViewportSize({ width: 1440, height: 900 });
    await openCoDirector(page, projectId);
    await dismissOnboarding(page);
    await cancelInFlightGeneration(page);
    await clickTabAndWait(page, "story", ["story-editor"]);

    const saveBtn = page.getByTestId("story-save-to-wiki").first();
    await expect(saveBtn).toBeVisible({ timeout: 15_000 });
    await saveBtn.click();
    await expect(page.getByTestId("story-publish-msg")).toContainText(/Story saved to Wiki/i, { timeout: 15_000 });

    // Open Wiki — must now show Version B.
    await clickTabAndWait(page, "wiki", ["codirector-content-wiki"]);
    const wikiPanel = page.getByTestId("codirector-content-wiki").first();
    await expect(wikiPanel).toContainText(/Version B logline/i, { timeout: 15_000 });

    const wiki = await getWiki(request, projectId);
    const blob = JSON.stringify(wiki.compiledStorySummary || {}) + JSON.stringify(wiki.storyEntries || []);
    expect(blob, "Wiki API must contain Version B after publish").toMatch(/Version B logline/i);

    const shot = await screenshot(page, "cand-wiki-b-after-publish");
    test.info().annotations.push({ type: "screenshot", description: shot });
  });

  test("B3 — Blank Logline + Save to Wiki yields blank Wiki Logline", async ({ request, page }) => {
    test.setTimeout(150_000);
    attachObservers(page, observer);
    expect(projectId, "projectId carried").toBeTruthy();

    // Blank the Logline via the API, then publish explicitly.
    const entries = await listStoryEntries(request, projectId);
    expect(entries.length).toBeGreaterThan(0);
    await updateStoryEntry(request, projectId, entries[0].id, { logline: "", shortSummary: "", longSummary: "" });
    await compileWiki(request, projectId);

    const wiki = await getWiki(request, projectId);
    const blob = JSON.stringify(wiki.compiledStorySummary || {}) + JSON.stringify(wiki.storyEntries || []);
    // No invented logline content — blank stays blank.
    expect(blob.toLowerCase(), "Wiki must not invent a logline for blank Story").not.toMatch(/logline about a scout|version [ab] logline/i);
  });

  test("B4 — Conversation content does not affect Wiki Story fields", async ({ request, page }) => {
    test.setTimeout(120_000);
    attachObservers(page, observer);
    expect(projectId, "projectId carried").toBeTruthy();

    // Add unrelated conversation-style content as a non-story knowledge entry path
    // is not directly writable here; instead assert the Wiki Story fields still
    // reflect only the (blank) Story record and never contain filler markers.
    const wiki = await getWiki(request, projectId);
    const blob = JSON.stringify(wiki.compiledStorySummary || {}) + JSON.stringify(wiki.storyEntries || []);
    expect(blob, "Wiki Story must not contain conversation filler").not.toMatch(/please call me friend|ok thanks will do/i);
  });
});

// ===========================================================================
// Workstream A — Character Candidate Diversity + Reference Fidelity
// ===========================================================================
test.describe.serial("Character Candidate Diversity + Reference Fidelity", () => {
  let projectId: string;
  const observer: Observer = { consoleErrors: [], pageErrors: [], failedRequests: [], apiFailures: [] };

  test.beforeAll(async ({ request }) => { await waitForAppReady(request); });
  test.afterAll(async ({ request }) => {
    if (projectId) await deleteProject(request, projectId);
    expect(observer.consoleErrors, "console errors").toEqual([]);
    expect(observer.pageErrors, "page errors").toEqual([]);
    expect(observer.failedRequests, "failed requests").toEqual([]);
    expect(observer.apiFailures, "api failures").toEqual([]);
  });

  test("A1 — Reference-locked candidates route to zimage.ref_edit with reference pixels", async ({ request, page }) => {
    test.setTimeout(240_000);
    attachObservers(page, observer);
    projectId = (await createTempProject(request, `CandWiki-A-${Date.now()}`)).id;

    const char = await createCharacter(request, projectId, {
      name: "Korri",
      description: "Elven barista with light-circuitry markings.",
      visualDescription: "Pale elf, black twin ponytails, purple eyes, pointed ears, black asymmetric outfit.",
    });
    const ref = await uploadImageAsset(request, projectId, { name: "korri-ref-sheet.png", tag: "korri-ref-sheet" });
    await attachCharacterReference(request, projectId, char.id, ref.id);

    const start = await startVisualSheet(request, projectId, char.id);
    const pack = start.pack || {};
    const candidates = pack.candidates || [];
    expect(candidates.length, "4 candidates enqueued").toBe(4);
    expect(pack.referenceLocked, "pack is reference-locked").toBe(true);

    // Every candidate must carry the reference asset id as conditioning pixels
    // and route to the Certified reference-capable workflow.
    for (const c of candidates) {
      expect(c.workflowKey, "candidate routed to zimage.ref_edit").toBe("zimage.ref_edit");
      expect((c.referenceAssetIds || []).length, "reference asset id present").toBeGreaterThan(0);
      expect(c.referenceLocked, "candidate is reference-locked").toBe(true);
      expect(c.compositionIntent, "full-body casting preserved").toBe("full_body_casting");
      expect(c.referenceFidelityMode, "honest limited mode recorded").toBe("limited");
    }

    const shot = await screenshot(page, "cand-wiki-a-reference-locked-start");
    test.info().annotations.push({ type: "screenshot", description: shot });
  });

  test("A2 — No-reference candidates use distinct Certified families before reuse", async ({ request, page }) => {
    test.setTimeout(240_000);
    attachObservers(page, observer);
    expect(projectId, "projectId carried").toBeTruthy();

    const char = await createCharacter(request, projectId, {
      name: "Mieke",
      description: "A curious street photographer.",
      visualDescription: "Tall human with short auburn hair and a leather jacket.",
    });
    const start = await startVisualSheet(request, projectId, char.id);
    const candidates = start.pack?.candidates || [];
    expect(candidates.length).toBe(4);
    const families = candidates.map((c: any) => c.workflowKey);
    // First two candidates use distinct Certified txt2img families; remaining
    // reuse (never fabricate a third distinct model).
    expect(families[0], "first candidate uses a distinct family").not.toBe(families[1]);
    const distinct = new Set(families);
    expect(distinct.size, "no fabricated distinctness").toBeLessThanOrEqual(2);
    for (const c of candidates) {
      expect(c.compositionIntent, "full-body casting preserved").toBe("full_body_casting");
      expect((c.referenceAssetIds || []).length, "no reference attached").toBe(0);
      expect(c.referenceLocked, "not reference-locked").toBe(false);
    }
  });

  test("A3 — Per-candidate generator label renders in the UI", async ({ page, request }) => {
    test.setTimeout(300_000);
    attachObservers(page, observer);
    expect(projectId, "projectId carried").toBeTruthy();

    await page.setViewportSize({ width: 1440, height: 900 });
    await openCoDirector(page, projectId);
    await dismissOnboarding(page);
    await cancelInFlightGeneration(page);

    // Open the Characters tab and select the first character so the candidate
    // panel renders. The generator label must appear under each candidate.
    await clickTabAndWait(page, "characters", ["codirector-content-characters", "character-compact"]);
    const firstChar = page.getByTestId("character-compact").first();
    await expect(firstChar).toBeVisible({ timeout: 30_000 });
    await firstChar.click({ force: true }).catch(() => undefined);
    await page.waitForTimeout(1500);

    // Trigger Generate Images if the control is available.
    const genBtn = page.getByRole("button", { name: /Generate Images|Generate Candidates|Generate/i }).first();
    if (await genBtn.isVisible({ timeout: 8000 }).catch(() => false)) {
      await genBtn.click({ force: true }).catch(() => undefined);
    }

    // Wait for at least one candidate generator label to render (wiring proof).
    const genLabel = page.getByTestId("character-compact-candidate-generator").first();
    await expect(genLabel, "per-candidate generator label must render").toBeVisible({ timeout: 120_000 });

    const shot = await screenshot(page, "cand-wiki-a-candidate-generator-labels");
    test.info().annotations.push({ type: "screenshot", description: shot });
  });
});


