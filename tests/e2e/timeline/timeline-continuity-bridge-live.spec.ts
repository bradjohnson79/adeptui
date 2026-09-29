/**
 * Live Schnick continuity-bridge chips (ORDER 2).
 * Live state: B1 bb_44ff590bff48 approved take_6b538159c562;
 * B2 bb_5ba6fb2cc740 CandidateReady cand_14f17e967f91 NOT approved;
 * bridge cbr_cade5f7097dc.
 * Does NOT click Approve, un-approve, or generate
 * (New take / Update later shots / Retry / Continue without matching).
 * Keep existing is persist-only and only when stale is actually showing.
 * No ContinuityBadge. No mocks. No JEPA. No Korri canon / CRS mutation.
 *
 * Live chips only: timeline-continuity-chip-*, timeline-batch-continuity,
 * timeline-batch-stale.
 *
 * Navigation helpers match tests/e2e/timeline/timeline-v2-layout.spec.ts
 * and tests/e2e/timeline/timeline-master-snap-zoom-generator.spec.ts.
 */
import { expect, test, type Page } from "@playwright/test";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const PROJECT_ID = "2347bf46-3762-4763-86c5-4a6032522278";
const SCENE_ID = "e4550745-f0ef-44c8-99a5-ef9e20bd47d2";
const B1_ID = "bb_44ff590bff48";
const B1_APPROVED_TAKE_ID = "take_6b538159c562";
const B1_APPROVED_CAND_ID = "cand_f4f997daa4aa";
const B2_ID = "bb_5ba6fb2cc740";
const B2_CAND_ID = "cand_14f17e967f91";
const B2_BRIDGE_ID = "cbr_cade5f7097dc";
const EXPECTED_INDEX_HASH = "index-DTD-QGrr.js";
const CHIP_LABELS = ["Matched", "Needs update"] as const;
const STILLS_DIR = path.join("test-results", "timeline-continuity-bridge-live");
const MASTER_PATH = `/api/director-timeline/projects/${PROJECT_ID}/scenes/${SCENE_ID}/master`;

type MasterPayload = {
  master?: {
    batchBlocks?: Array<{
      id: string;
      status?: string;
      downstreamStale?: boolean;
      staleFromTakeId?: string | null;
      activeTakeId?: string | null;
      incomingBridgeId?: string | null;
      approvedClip?: { assetId?: string; candidateId?: string } | null;
      candidateVersions?: Array<{
        id: string;
        approved?: boolean;
        takeId?: string;
        label?: string;
        assetId?: string;
      }>;
      generationJobs?: Array<{ id: string; status?: string; createdAt?: string }>;
    }>;
    continuityBridges?: Array<{
      bridgeId?: string;
      targetBatchId?: string;
      status?: string;
    }>;
  };
};

async function openTimeline(page: Page, sceneId: string) {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/project/${PROJECT_ID}?workspace=timeline&scene=${sceneId}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
  await expect(page.locator(".timeline-v2")).toBeVisible();
  await expect(page.getByTestId("timeline-v2-label-batches")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("timeline-v2-label-visual")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("timeline-playhead")).toBeVisible({ timeout: 30_000 });
}

async function openLeftDrawer(page: Page) {
  const leftToggle = page.getByTestId("timeline-drawer-left-toggle");
  await expect(leftToggle).toBeVisible();
  if ((await leftToggle.getAttribute("aria-expanded")) !== "true") {
    await leftToggle.click();
  }
  await expect(leftToggle).toHaveAttribute("aria-expanded", "true");
}

async function closeLeftDrawer(page: Page) {
  const leftToggle = page.getByTestId("timeline-drawer-left-toggle");
  await expect(leftToggle).toBeVisible();
  if ((await leftToggle.getAttribute("aria-expanded")) === "true") {
    const box = await leftToggle.boundingBox();
    if (box) await leftToggle.click({ position: { x: Math.max(2, box.width / 2), y: 16 } });
  }
  await expect(leftToggle).toHaveAttribute("aria-expanded", "false", { timeout: 10_000 });
}

async function shot(page: Page, name: string) {
  await mkdir(STILLS_DIR, { recursive: true });
  const dest = path.join(STILLS_DIR, name);
  await page.screenshot({ path: dest, fullPage: true });
  return dest.replace(/\\/g, "/");
}

async function getMaster(page: Page): Promise<MasterPayload> {
  const res = await page.request.get(MASTER_PATH);
  expect(res.ok(), `GET master ${res.status()}`).toBeTruthy();
  return (await res.json()) as MasterPayload;
}

function findBatch(payload: MasterPayload, id: string) {
  return (payload.master?.batchBlocks || []).find((batch) => batch.id === id);
}

function jobIds(payload: MasterPayload): string[] {
  return (payload.master?.batchBlocks || [])
    .flatMap((batch) => (batch.generationJobs || []).map((job) => job.id))
    .sort();
}

async function openRightInspector(page: Page) {
  const rightToggle = page.getByTestId("timeline-drawer-right-toggle");
  await expect(rightToggle).toBeVisible();
  if ((await rightToggle.getAttribute("aria-expanded")) !== "true") {
    await rightToggle.click();
  }
  await expect(rightToggle).toHaveAttribute("aria-expanded", "true");
  const tab = page.getByTestId("timeline-tab-inspector");
  if (await tab.isVisible().catch(() => false)) await tab.click();
  await expect(page.getByTestId("timeline-inspector")).toBeVisible({ timeout: 20_000 });
}

async function openRetakeAccordion(page: Page) {
  const retake = page.getByTestId("timeline-inspector-retake");
  await expect(retake).toBeVisible({ timeout: 20_000 });
  await retake.evaluate((el) => {
    const details = el as HTMLDetailsElement;
    details.scrollIntoView({ block: "nearest", inline: "nearest" });
    if (details.open) return;
    const summary = details.querySelector("summary") as HTMLElement | null;
    if (summary) summary.click();
    if (!details.open) {
      details.open = true;
      details.dispatchEvent(new Event("toggle", { bubbles: true }));
    }
  });
}

async function revealKeepExisting(page: Page) {
  const keep = page.getByTestId("timeline-keep-existing-downstream");
  await openRightInspector(page);
  if (await page.getByTestId("timeline-inspector-retake").isVisible().catch(() => false)) {
    await openRetakeAccordion(page);
    if (await keep.count()) return;
  }
  await openLeftDrawer(page);
  const active = page.locator(".timeline-v2__scenes-list .scene-block.active").first();
  await expect(active).toBeVisible({ timeout: 20_000 });
  await active.click();
  await expect(page.getByTestId("timeline-inspector-scene")).toBeVisible({ timeout: 20_000 });
  await closeLeftDrawer(page);
  await openRightInspector(page);
  await openRetakeAccordion(page);
  if ((await keep.count()) === 0) {
    console.log("[ORDER2] Keep existing not in DOM after reveal");
    return;
  }
  await keep.evaluate((el) => el.scrollIntoView({ block: "center", inline: "nearest" }));
}

test.describe("timeline continuity bridge live (Schnick)", () => {
  test("B2 CandidateReady chip, Keep existing persist-only if stale, temperature after library close", async ({
    page,
  }) => {
    test.setTimeout(180_000);
    const screenshots: string[] = [];
    let chipLabel = "";
    let chipHeight = 0;
    let inspectorDetails = "";
    let staleDetails = "";
    let b2Approved = false;
    let b2StatusText = "";
    let b1StatusText = "";
    let indexHash = "";
    let b2CandText = "";
    let keepExistingClicked = false;
    let keepExistingSkipped = false;
    let staleShowing = false;
    let staleCleared = false;
    let reloadPersist = false;
    let generateCountDelta = -1;
    const generatePosts: string[] = [];
    const approvePosts: string[] = [];
    const phase1 = {
      temperature: false,
      library: false,
      scenePrompt: false,
      schnick: false,
    };

    page.on("request", (req) => {
      if (req.method() !== "POST") return;
      const url = req.url();
      if (/keep-existing-downstream/.test(url)) return;
      if (/\/approve/.test(url)) approvePosts.push(url);
      if (
        /\/(generate-batch|generate\b|retake|reconcile-downstream|retry-bridge|continue-without)/.test(url)
      ) {
        generatePosts.push(url);
      }
    });

    await openTimeline(page, SCENE_ID);

    indexHash = await page.evaluate(() => {
      const scripts = [...document.querySelectorAll("script[src]")].map((el) => (el as HTMLScriptElement).src);
      const hit = scripts.find((src) => /index-[A-Za-z0-9_-]+\.js/.test(src));
      return hit?.match(/index-[A-Za-z0-9_-]+\.js/)?.[0] || "";
    });
    expect(indexHash, "INDEX_HASH").toBe(EXPECTED_INDEX_HASH);
    await expect(page.getByTestId("continuity-badge")).toHaveCount(0);

    await expect(page.getByText(/Schnick/i).first()).toBeVisible({ timeout: 60_000 });
    phase1.schnick = true;

    const scenePrompt = page.getByTestId("timeline-scene-prompt");
    await expect(scenePrompt).toBeVisible({ timeout: 30_000 });
    phase1.scenePrompt = true;

    await openLeftDrawer(page);
    const library = page
      .getByTestId("timeline-library-open")
      .or(page.locator(".timeline-v2__dock--library"))
      .or(page.getByText(/^Library$/i));
    await expect(library.first()).toBeVisible({ timeout: 20_000 });
    phase1.library = true;
    await closeLeftDrawer(page);

    const promptClip = page.locator('[data-testid^="track-clip-prompt-"]').first();
    if (await promptClip.isVisible().catch(() => false)) {
      await promptClip.click({ force: true });
    }
    const temp = page
      .getByTestId("timeline-temperature-control")
      .or(page.getByTestId("timeline-temperature-unavailable"))
      .or(page.getByTestId("timeline-temperature-tooltip"));
    await expect(temp.first()).toBeVisible({ timeout: 15_000 });
    phase1.temperature = true;
    screenshots.push(await shot(page, "01-phase1-timeline.png"));

    const b1 = page.getByTestId(`timeline-batch-${B1_ID}`);
    await expect(b1).toBeVisible({ timeout: 30_000 });
    const b1Status = page.getByTestId(`timeline-batch-status-${B1_ID}`);
    if (await b1Status.isVisible().catch(() => false)) {
      b1StatusText = ((await b1Status.textContent()) || "").trim();
    }
    console.log(`[ORDER2] b1Status=${b1StatusText || "(none)"}`);
    await b1.click({ force: true });
    await expect(page.getByTestId("timeline-batch-inspector")).toBeVisible({ timeout: 20_000 });
    const b1ApprovedTake = page.getByTestId(`timeline-take-${B1_APPROVED_CAND_ID}`);
    await expect(b1ApprovedTake, `B1 approved take ${B1_APPROVED_TAKE_ID} visible`).toBeVisible({
      timeout: 20_000,
    });
    await expect(b1ApprovedTake).toHaveClass(/active/);
    await expect(b1ApprovedTake).toContainText(/\(active\)/i);
    screenshots.push(await shot(page, "02-b1-approved.png"));

    const b2 = page.getByTestId(`timeline-batch-${B2_ID}`);
    await expect(b2).toBeVisible({ timeout: 30_000 });
    const chip = page.getByTestId(`timeline-continuity-chip-${B2_ID}`);
    await expect(chip).toBeVisible({ timeout: 30_000 });
    const chipBox = await chip.boundingBox();
    chipHeight = chipBox?.height ?? 0;
    chipLabel = ((await chip.textContent()) || "").trim();
    console.log(`[ORDER2] chipLabel=${chipLabel}`);
    console.log(`[ORDER2] chipHeight=${chipHeight}`);
    expect(chipHeight, `B2 chip height seen label=${chipLabel}`).toBeGreaterThan(0);
    expect(CHIP_LABELS as readonly string[], `B2 chip live string: ${chipLabel}`).toContain(chipLabel);

    await b2.click({ force: true });
    const inspector = page.getByTestId("timeline-inspector");
    await expect(inspector).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("timeline-batch-inspector")).toBeVisible({ timeout: 20_000 });

    const b2Status = page.getByTestId(`timeline-batch-status-${B2_ID}`);
    if (await b2Status.isVisible().catch(() => false)) {
      b2StatusText = ((await b2Status.textContent()) || "").trim();
    }
    await expect(inspector).toContainText(/Status:\s*CandidateReady/i);
    await expect(inspector).not.toContainText(/Status:\s*Approved\b/i);
    b2Approved = /Status:\s*Approved\b/i.test((await inspector.innerText()) || "");
    console.log(`[ORDER2] b2Status=${b2StatusText || "(none)"} b2Approved=${b2Approved}`);

    const approveBtn = page.getByTestId("timeline-batch-approve");
    const approveCount = await approveBtn.count();
    console.log(`[ORDER2] approveCount=${approveCount} (must not click)`);

    const continuity = page.getByTestId("timeline-batch-continuity-status");
    const failed = page.getByTestId("timeline-batch-continuity-failed");
    await expect
      .poll(async () => (await continuity.isVisible().catch(() => false)) || (await failed.isVisible().catch(() => false)), {
        timeout: 20_000,
      })
      .toBeTruthy();
    inspectorDetails = (await continuity.isVisible().catch(() => false))
      ? ((await continuity.innerText()) || "").trim()
      : ((await failed.innerText()) || "").trim();
    const stale = page.getByTestId("timeline-batch-stale");
    staleDetails = (await stale.isVisible().catch(() => false)) ? ((await stale.innerText()) || "").trim() : "";
    staleShowing = Boolean(staleDetails);
    console.log(`[ORDER2] inspectorDetails=${inspectorDetails}`);
    console.log(`[ORDER2] staleDetails=${staleDetails || "(none)"}`);
    console.log(`[ORDER2] bridge=${B2_BRIDGE_ID}`);

    const b2Cand = page.getByTestId(`timeline-take-${B2_CAND_ID}`);
    await expect(b2Cand, `B2 candidate ${B2_CAND_ID} visible`).toBeVisible({ timeout: 20_000 });
    b2CandText = ((await b2Cand.innerText()) || "").trim();
    await expect(b2Cand).not.toHaveClass(/active/);
    await expect(b2Cand).not.toContainText(/\(active\)/i);
    console.log(`[ORDER2] b2CandText=${b2CandText}`);
    screenshots.push(await shot(page, "03-b2-candidate-inspector.png"));

    const masterBefore = await getMaster(page);
    const b1Before = findBatch(masterBefore, B1_ID);
    const b2Before = findBatch(masterBefore, B2_ID);
    expect(b1Before, "B1 present in master").toBeTruthy();
    expect(b2Before, "B2 present in master").toBeTruthy();
    expect(b1Before?.activeTakeId, "B1 approved take").toBe(B1_APPROVED_TAKE_ID);
    expect(b2Before?.status, "B2 CandidateReady").toBe("CandidateReady");
    const b2CandBefore = (b2Before?.candidateVersions || []).find((cand) => cand.id === B2_CAND_ID);
    expect(b2CandBefore, "B2 candidate in master").toBeTruthy();
    expect(b2CandBefore?.approved, "B2 candidate not approved").toBeFalsy();
    const jobsBefore = jobIds(masterBefore);
    console.log(
      `[ORDER2] jobsBefore=${jobsBefore.length} b1Take=${b1Before?.activeTakeId} b2Status=${b2Before?.status} stale=${b2Before?.downstreamStale} incoming=${b2Before?.incomingBridgeId}`,
    );

    if (staleShowing) {
      await revealKeepExisting(page);
      const keepBtn = page.getByTestId("timeline-keep-existing-downstream");
      if (await keepBtn.isVisible().catch(() => false)) {
        await keepBtn.click({ force: true });
        keepExistingClicked = true;
        await expect(keepBtn).toHaveCount(0, { timeout: 30_000 });
      } else {
        expect(keepBtn, "stale showing so Keep existing must be clickable").toBeVisible();
      }

      await expect
        .poll(
          async () => {
            const payload = await getMaster(page);
            const batch = findBatch(payload, B2_ID);
            return batch?.downstreamStale === true;
          },
          { timeout: 30_000 },
        )
        .toBeFalsy();
    } else {
      keepExistingSkipped = true;
      console.log("[ORDER2] Keep existing skipped (stale not showing)");
    }

    const masterAfter = await getMaster(page);
    const b2After = findBatch(masterAfter, B2_ID);
    expect(b2After, "B2 present in master after Keep existing decision").toBeTruthy();
    staleCleared = b2After?.downstreamStale !== true;
    const jobsAfter = jobIds(masterAfter);
    generateCountDelta = jobsAfter.length - jobsBefore.length;
    const b2CandAfter = (b2After?.candidateVersions || []).find((cand) => cand.id === B2_CAND_ID);
    console.log(
      `[ORDER2] keepExistingClicked=${keepExistingClicked} keepExistingSkipped=${keepExistingSkipped} staleCleared=${staleCleared} jobsAfter=${jobsAfter.length} delta=${generateCountDelta} generatePosts=${generatePosts.length} approvePosts=${approvePosts.length}`,
    );
    if (keepExistingClicked) {
      expect(staleCleared, "downstreamStale false after Keep existing").toBeTruthy();
    }
    expect(b2After?.status, "B2 still CandidateReady").toBe("CandidateReady");
    expect(b2CandAfter?.approved, "B2 candidate still not approved").toBeFalsy();
    expect(generateCountDelta, "no new generate jobs").toBe(0);
    expect(jobsAfter, "generation job ids unchanged").toEqual(jobsBefore);
    expect(generatePosts, `no generate POSTs: ${generatePosts.join(",")}`).toEqual([]);
    expect(approvePosts, `no approve POSTs: ${approvePosts.join(",")}`).toEqual([]);

    await closeLeftDrawer(page).catch(() => undefined);
    await b2.click({ force: true });
    await expect(page.getByTestId("timeline-batch-inspector")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId(`timeline-take-${B2_CAND_ID}`)).toBeVisible();
    await expect(page.getByTestId(`timeline-take-${B2_CAND_ID}`)).not.toHaveClass(/active/);
    screenshots.push(await shot(page, "04-keep-existing-decision.png"));

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("continuity-badge")).toHaveCount(0);
    await expect(page.getByText(/Schnick/i).first()).toBeVisible({ timeout: 60_000 });

    const b1Reload = page.getByTestId(`timeline-batch-${B1_ID}`);
    await expect(b1Reload).toBeVisible({ timeout: 30_000 });
    await b1Reload.click({ force: true });
    await expect(page.getByTestId(`timeline-take-${B1_APPROVED_CAND_ID}`)).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId(`timeline-take-${B1_APPROVED_CAND_ID}`)).toHaveClass(/active/);
    await expect(page.getByTestId(`timeline-take-${B1_APPROVED_CAND_ID}`)).toContainText(/\(active\)/i);

    const b2Reload = page.getByTestId(`timeline-batch-${B2_ID}`);
    await expect(b2Reload).toBeVisible({ timeout: 30_000 });
    await b2Reload.click({ force: true });
    await expect(page.getByTestId("timeline-batch-inspector")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("timeline-inspector")).toContainText(/Status:\s*CandidateReady/i);
    await expect(page.getByTestId(`timeline-take-${B2_CAND_ID}`)).toBeVisible();
    await expect(page.getByTestId(`timeline-take-${B2_CAND_ID}`)).not.toHaveClass(/active/);

    const masterReload = await getMaster(page);
    const b1ReloadMaster = findBatch(masterReload, B1_ID);
    const b2ReloadMaster = findBatch(masterReload, B2_ID);
    const b2CandReload = (b2ReloadMaster?.candidateVersions || []).find((cand) => cand.id === B2_CAND_ID);
    reloadPersist =
      b1ReloadMaster?.activeTakeId === B1_APPROVED_TAKE_ID &&
      b2ReloadMaster?.status === "CandidateReady" &&
      b2CandReload?.approved !== true;
    expect(reloadPersist, "reload persist B1 approved + B2 candidate").toBeTruthy();
    screenshots.push(await shot(page, "05-reload-persist.png"));

    const promptAfter = page.locator('[data-testid^="track-clip-prompt-"]').first();
    if (await promptAfter.isVisible().catch(() => false)) {
      await promptAfter.click({ force: true });
    }
    const tempAfter = page
      .getByTestId("timeline-temperature-control")
      .or(page.getByTestId("timeline-temperature-unavailable"))
      .or(page.getByTestId("timeline-temperature-tooltip"));
    await expect(tempAfter.first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("continuity-badge")).toHaveCount(0);

    b2Approved = /Status:\s*Approved\b/i.test((await page.getByTestId("timeline-inspector").innerText()) || "");
    expect(b2Approved, "B2 approved false").toBeFalsy();

    const report = {
      pw: "PASS",
      spec: "tests/e2e/timeline/timeline-continuity-bridge-live.spec.ts",
      chipLabel,
      chipHeight,
      inspectorDetails,
      staleDetails,
      staleShowing,
      b1StatusText,
      b2StatusText,
      b2Approved,
      b2CandText,
      keepExistingClicked,
      keepExistingSkipped,
      keepExisting: keepExistingClicked ? "clicked" : "skipped",
      staleCleared,
      generateCountDelta,
      generatePosts,
      approvePosts,
      reloadPersist,
      INDEX_HASH: indexHash,
      screenshots,
      phase1,
      temperature: phase1.temperature,
    };
    await mkdir(STILLS_DIR, { recursive: true });
    await writeFile(path.join(STILLS_DIR, "order2-report.json"), `${JSON.stringify(report, null, 2)}\n`, "utf8");
    console.log(`[ORDER2] b2Approved=${b2Approved}`);
    console.log(`[ORDER2] keepExisting=${keepExistingClicked ? "clicked" : "skipped"}`);
    console.log(`[ORDER2] reloadPersist=${reloadPersist}`);
    console.log(`[ORDER2] INDEX_HASH=${indexHash}`);
    console.log(`[ORDER2] screenshots=${screenshots.join(",")}`);
  });
});
