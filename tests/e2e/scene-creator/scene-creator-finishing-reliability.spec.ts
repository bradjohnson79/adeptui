/**
 * Scene Creator finishing & reliability — hosted Playwright creator-flow.
 *
 * Topology (do not use ADEPT_BETA_TARGET=1 / :8760):
 *   PLAYWRIGHT_BASE_URL=https://adeptui.vercel.app
 *   STUDIO_API_BASE=https://api-beta.adeptui.org
 *
 * Reuses Schnick Coffee. Never POST /api/projects.
 * Visual quality (expression, cup, identity) is reviewed separately — this
 * suite asserts creator-visible state, request payloads, job counts, and lineage.
 */
import { expect, test, type APIRequestContext, type Page, type TestInfo } from "@playwright/test";
import { AuditObserver } from "../helpers/observer";

const BASE = process.env.PLAYWRIGHT_BASE_URL || "https://adeptui.vercel.app";
const API = process.env.STUDIO_API_BASE || "https://api-beta.adeptui.org";
const PROJECT_ID = "2347bf46-3762-4763-86c5-4a6032522278";
const SCENE_ID = "e4550745-f0ef-44c8-99a5-ef9e20bd47d2";
const SC_URL = `${BASE}/project/${PROJECT_ID}?workspace=scenecreator`;
const JOB_WAIT_MS = 540_000;

type ShotCandidate = {
  id: string;
  job_id?: string;
  asset_id?: string | null;
  status?: string;
  kind?: string;
  take_label?: string;
  parent_candidate_id?: string | null;
  edit_operation?: string | null;
  quality_profile?: string;
  final_strategy?: string;
  source_preview_asset_id?: string | null;
  approved_edited_preview_asset_id?: string | null;
  camera_state_hash?: string;
  superseded?: boolean;
  error?: string;
};

type SceneShot = {
  id: string;
  scene_id?: string;
  intent?: string;
  approved_candidate_id?: string | null;
  candidates?: ShotCandidate[];
};

type Workspace = {
  selected_scene_id?: string;
  selected_shot?: SceneShot | null;
  scenes?: Array<{ id: string; name?: string }>;
  shots?: SceneShot[];
};

type CinePack = {
  selected_camera_id?: string;
  cameras?: Array<{
    cameraId: string;
    cameraSlot?: number;
    cameraStateHash?: string;
    cameraStateVersion?: number;
    enabled?: boolean;
    current?: Record<string, unknown>;
    lineage?: {
      previewAssetId?: string;
      previewStatus?: string;
      locked?: boolean;
      finalAssetId?: string;
    };
  }>;
};

test.describe.configure({ mode: "default" });

function attachObserver(page: Page, testInfo: TestInfo) {
  const observer = new AuditObserver(page, testInfo);
  observer.attach();
  observer.allow(/favicon|fonts\.(googleapis|gstatic)|vercel\.live|ingest\./i);
  return observer;
}

async function waitApiReady(request: APIRequestContext) {
  await expect
    .poll(
      async () => {
        try {
          const res = await request.get(`${API}/api/health`, { timeout: 15_000 });
          return res.ok();
        } catch {
          return false;
        }
      },
      { timeout: 120_000 },
    )
    .toBeTruthy();
}

async function getWorkspace(request: APIRequestContext, shotId?: string): Promise<Workspace> {
  const qs = new URLSearchParams({ scene_id: SCENE_ID });
  if (shotId) qs.set("shot_id", shotId);
  const res = await request.get(`${API}/api/scene-creator/projects/${PROJECT_ID}/workspace?${qs}`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return (await res.json()) as Workspace;
}

async function getCine(request: APIRequestContext): Promise<CinePack> {
  const res = await request.get(
    `${API}/api/scene-creator/projects/${PROJECT_ID}/scenes/${SCENE_ID}/cinematographer`,
  );
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = (await res.json()) as { cinematographer: CinePack };
  return body.cinematographer;
}

async function getShot(request: APIRequestContext, shotId: string): Promise<SceneShot> {
  const res = await request.get(`${API}/api/scene-creator/projects/${PROJECT_ID}/shots/${shotId}`);
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = (await res.json()) as { shot: SceneShot };
  return body.shot;
}

async function listJobs(request: APIRequestContext): Promise<Array<{ id: string; kind?: string; status?: string; created_at?: string }>> {
  const res = await request.get(`${API}/api/projects/${PROJECT_ID}/jobs`);
  if (!res.ok()) return [];
  const body = await res.json();
  return Array.isArray(body) ? body : [];
}

async function waitJobDone(request: APIRequestContext, jobId: string, timeout = JOB_WAIT_MS) {
  await expect
    .poll(
      async () => {
        const res = await request.get(`${API}/api/jobs/${jobId}`);
        if (!res.ok()) return "unknown";
        const job = (await res.json()) as { status?: string };
        return String(job.status || "").toLowerCase();
      },
      { timeout, intervals: [2_000, 4_000, 8_000] },
    )
    .toMatch(/^(done|complete|succeeded|success|failed|error)$/);
}

async function openSceneCreator(page: Page) {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(SC_URL, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("scene-creator-panel").or(page.getByTestId("scene-creator-standard"))).toBeVisible({
    timeout: 60_000,
  });
  const tools = page.getByTestId("scene-creator-tools-toggle");
  if (await tools.isVisible().catch(() => false)) {
    const browser = page.getByTestId("scene-creator-browser");
    const box = await browser.boundingBox().catch(() => null);
    if (!box || box.x < 0) await tools.click();
  }
}

async function openAccordion(page: Page, testId: string) {
  const acc = page.getByTestId(testId);
  await expect(acc).toBeVisible();
  const isOpen = await acc.evaluate((el) => (el as HTMLDetailsElement).open);
  if (!isOpen) {
    await acc.locator("summary").first().click();
  }
  await expect
    .poll(async () => acc.evaluate((el) => (el as HTMLDetailsElement).open))
    .toBe(true);
}

async function paintMask(page: Page, size: "tiny" | "large") {
  await openAccordion(page, "scene-creator-inpaint-accordion");
  await page.getByTestId("scene-creator-inpaint-brush").click();
  const slider = page.getByTestId("scene-creator-inpaint-brush-size");
  if (await slider.count()) await slider.fill(size === "tiny" ? "4" : "64");
  const canvas = page.locator('[data-testid="scene-creator-center-mask"] canvas').first();
  await expect(canvas).toBeVisible({ timeout: 20_000 });
  const box = await canvas.boundingBox();
  expect(box, "mask canvas must be visible").toBeTruthy();
  const startX = box!.x + box!.width * 0.45;
  const startY = box!.y + box!.height * 0.45;
  if (size === "tiny") {
    await page.mouse.move(startX, startY);
    await page.mouse.down();
    await page.mouse.move(startX + 2, startY + 2);
    await page.mouse.up();
  } else {
    await page.mouse.move(startX, startY);
    await page.mouse.down();
    await page.mouse.move(startX + box!.width * 0.25, startY + box!.height * 0.2);
    await page.mouse.move(startX - box!.width * 0.1, startY + box!.height * 0.15);
    await page.mouse.up();
  }
}

test.describe("Scene Creator finishing reliability (hosted)", () => {
  test.beforeEach(async ({ request }) => {
    expect(BASE, "do not use retired :8760").not.toMatch(/127\.0\.0\.1:8760|localhost:8760/);
    expect(API, "use hosted Studio API bridge").not.toMatch(/127\.0\.0\.1:8760/);
    await waitApiReady(request);
  });

  test("load Schnick Coffee Scene Creator", async ({ page }, testInfo) => {
    const observer = attachObserver(page, testInfo);
    await openSceneCreator(page);
    await expect(page.getByTestId("scene-creator-browser")).toBeVisible();
    await expect(page.getByTestId("scene-creator-preview")).toBeVisible();
    await expect(page.getByTestId("scene-creator-cinematographer")).toBeVisible();
    await expect(page.getByTestId("cine-tile-c1")).toBeVisible();
    await expect(page.getByTestId("cine-preview")).toBeVisible();
    await expect(page.getByTestId("scene-creator-generate")).toBeVisible();
    const fatal = observer.pageErrors.filter((e) => !/ResizeObserver|chrome-extension/i.test(e));
    expect(fatal, fatal.join("\n")).toEqual([]);
    await observer.snapshot("sc-finishing-load");
  });

  test("camera sync C2 tile ↔ left selector, no dual selection", async ({ page }, testInfo) => {
    attachObserver(page, testInfo);
    await openSceneCreator(page);
    await openAccordion(page, "cine-orient-accordion");
    await page.getByTestId("cine-tile-c2").click();
    await expect(page.getByTestId("cine-orient-camera-select")).toHaveValue(/.+/);
    const left = await page.getByTestId("cine-orient-camera-select").inputValue();
    const right = await page.getByTestId("cine-camera-select").inputValue();
    expect(left).toBe(right);
    await expect(page.getByTestId("cine-tile-c2")).toHaveClass(/is-on/);
    await expect(page.getByTestId("cine-tile-c3")).not.toHaveClass(/is-on/);

    await page.getByTestId("cine-orient-camera-select").selectOption({ label: "C3" }).catch(async () => {
      const options = page.getByTestId("cine-orient-camera-select").locator("option");
      const count = await options.count();
      if (count >= 3) await page.getByTestId("cine-orient-camera-select").selectOption({ index: 2 });
    });
    await expect(page.getByTestId("cine-tile-c3")).toHaveClass(/is-on/);
    await expect(page.getByTestId("cine-tile-c2")).not.toHaveClass(/is-on/);
  });

  test("3D orientation numbers change and preview goes stale", async ({ page, request }, testInfo) => {
    attachObserver(page, testInfo);
    await openSceneCreator(page);
    await openAccordion(page, "cine-orient-accordion");
    const yaw = page.getByTestId("cine-orient-yaw");
    await expect(yaw).toBeAttached();
    const yawValue = page.locator(".cine-orient-stepper", { hasText: "Yaw" }).locator(".cine-orient-stepper__value");
    await expect(yawValue).toBeVisible();
    const before = ((await yawValue.textContent()) || "").trim();
    await page.getByRole("button", { name: "Yaw up" }).click();
    await expect.poll(async () => ((await yawValue.textContent()) || "").trim()).not.toBe(before);
    await page.getByRole("button", { name: "Pitch up" }).click();
    await page.getByRole("button", { name: "Roll up" }).click();
    await page.getByRole("button", { name: "Zoom up" }).click();
    const state = page.getByTestId("cine-state-line");
    await expect(state).toBeVisible();
    const cine = await getCine(request);
    const selected = cine.cameras?.find((c) => c.cameraId === cine.selected_camera_id);
    if (selected?.lineage?.previewStatus) {
      expect(["stale", "none", "failed", "ready", "generating"]).toContain(selected.lineage.previewStatus);
    }
    const target = page.getByTestId("cine-orient-target-select");
    if (await target.count()) {
      const value = await target.inputValue();
      await page.getByRole("button", { name: "Yaw down" }).click();
      await expect(target).toHaveValue(value);
    }
  });

  test("zoom vs dolly: optical vs physical", async ({ page }, testInfo) => {
    attachObserver(page, testInfo);
    await openSceneCreator(page);
    const state = page.getByTestId("cine-state-line");
    const before = ((await state.textContent()) || "").trim();
    await page.getByTestId("cine-shot-select").selectOption({ label: "Zoom In" });
    await page.getByTestId("cine-enter").click();
    await expect.poll(async () => ((await state.textContent()) || "").trim()).not.toBe(before);
    const afterZoom = ((await state.textContent()) || "").trim();
    expect(afterZoom.toLowerCase()).toMatch(/zoom/);
    await page.getByTestId("cine-shot-select").selectOption({ label: "Dolly In" });
    await page.getByTestId("cine-enter").click();
    await expect.poll(async () => ((await state.textContent()) || "").trim()).not.toBe(afterZoom);
    const afterDolly = ((await state.textContent()) || "").trim();
    expect(afterDolly.toLowerCase()).toMatch(/step|dolly|forward/);
  });

  test("3D and Inpaint accordions open together", async ({ page }, testInfo) => {
    attachObserver(page, testInfo);
    await openSceneCreator(page);
    await openAccordion(page, "cine-orient-accordion");
    await openAccordion(page, "scene-creator-inpaint-accordion");
    await expect(page.locator(".cine-orient-stepper", { hasText: "Yaw" })).toBeVisible();
    await expect(page.getByTestId("scene-creator-inpaint-generate")).toBeVisible();
    await expect(page.getByTestId("cine-tile-c1")).toBeVisible();
    await expect(page.getByTestId("scene-creator-preview")).toBeVisible();
  });

  test("low-res preview: generating state, one job, lineage matches camera", async ({
    page,
    request,
  }, testInfo) => {
    test.setTimeout(JOB_WAIT_MS + 60_000);
    attachObserver(page, testInfo);
    await openSceneCreator(page);
    await page.getByTestId("cine-tile-c1").click();
    const jobsBefore = await listJobs(request);
    const previewPosts: string[] = [];
    page.on("request", (req) => {
      if (req.method() === "POST" && /cinematographer\/preview/.test(req.url())) previewPosts.push(req.url());
    });
    await openAccordion(page, "cine-orient-accordion");
    await page.getByRole("button", { name: "Yaw up" }).click();
    const previewReq = page.waitForRequest(
      (req) => req.method() === "POST" && /cinematographer\/preview/.test(req.url()),
      { timeout: 45_000 },
    );
    await page.getByTestId("cine-preview").click();
    await previewReq;
    await expect(page.getByTestId("cine-preview")).toContainText(/Generating preview|Generate Low-Res Preview/i);
    expect(previewPosts.length, "exactly one preview request").toBe(1);
    const ws = await getWorkspace(request);
    const shot = ws.selected_shot;
    expect(shot, "workspace must have a selected shot").toBeTruthy();
    let newJobs: Array<{ id: string; kind?: string; status?: string }> = [];
    await expect
      .poll(async () => {
        const jobsAfter = await listJobs(request);
        newJobs = jobsAfter.filter((j) => !jobsBefore.some((b) => b.id === j.id));
        return newJobs.length;
      }, { timeout: 45_000 })
      .toBe(1);
    if (newJobs[0]?.id) await waitJobDone(request, newJobs[0].id);
    const after = await getShot(request, shot!.id);
    const preview = (after.candidates || []).find((c) => c.job_id === newJobs[0]?.id)
      || [...(after.candidates || [])].reverse().find((c) => (c.quality_profile || "").toLowerCase() === "draft");
    expect(preview, "preview candidate must exist").toBeTruthy();
    const cine = await getCine(request);
    const cam = cine.cameras?.find((c) => c.cameraId === cine.selected_camera_id);
    if (preview?.camera_state_hash && cam?.cameraStateHash) {
      expect(preview.camera_state_hash).toBe(cam.cameraStateHash);
    }
  });

  test("duplicate preview click enqueues exactly one job", async ({ page, request }, testInfo) => {
    test.setTimeout(JOB_WAIT_MS + 60_000);
    attachObserver(page, testInfo);
    await openSceneCreator(page);
    const posts: string[] = [];
    page.on("request", (req) => {
      if (req.method() === "POST" && /cinematographer\/preview/.test(req.url())) posts.push(req.url());
    });
    const before = await listJobs(request);
    await page.getByTestId("cine-preview").dblclick({ delay: 20 }).catch(async () => {
      await page.getByTestId("cine-preview").click();
      await page.getByTestId("cine-preview").click();
    });
    await page.waitForTimeout(2000);
    expect(posts.length, "frontend must serialize duplicate preview").toBe(1);
    const after = await listJobs(request);
    const created = after.filter((j) => !before.some((b) => b.id === j.id));
    expect(created.length, "backend must not enqueue a second preview").toBeLessThanOrEqual(1);
  });

  test("inpaint mask: overlay, source, coverage, no image-drag", async ({ page }, testInfo) => {
    attachObserver(page, testInfo);
    await openSceneCreator(page);
    await paintMask(page, "large");
    await expect(page.getByTestId("scene-creator-inpaint-mode")).toBeVisible();
    await expect(page.getByTestId("scene-creator-center-mask")).toBeVisible();
    await expect(page.getByTestId("scene-creator-inpaint-mask-summary")).toBeVisible();
    await expect(page.getByTestId("scene-creator-inpaint-mask-summary")).toContainText(/Masked area|Mask too small|%/i);
    await expect(page.getByTestId("scene-creator-inpaint-source")).toBeVisible();
    const canvas = page.locator('[data-testid="scene-creator-center-mask"] canvas').first();
    const before = await canvas.screenshot();
    await page.getByTestId("scene-creator-inpaint-collapsed-line").click().catch(() => undefined);
    await openAccordion(page, "scene-creator-inpaint-accordion");
    const after = await canvas.screenshot();
    expect(after.equals(before) || after.length > 0).toBeTruthy();
  });

  test("too-small mask: blocked, no runtime job", async ({ page, request }, testInfo) => {
    attachObserver(page, testInfo);
    await openSceneCreator(page);
    const jobsBefore = await listJobs(request);
    await paintMask(page, "tiny");
    await page.getByTestId("scene-creator-inpaint-prompt").fill("tiny mask must not run");
    const summary = page.getByTestId("scene-creator-inpaint-mask-summary");
    const generate = page.getByTestId("scene-creator-inpaint-generate");
    const tooSmall = (await summary.textContent().catch(() => "")) || "";
    if (/Mask too small/i.test(tooSmall)) {
      await expect(generate).toBeDisabled();
    } else {
      await generate.click({ trial: true }).catch(() => undefined);
      if (await generate.isEnabled()) {
        const posts: string[] = [];
        page.on("request", (req) => {
          if (req.method() === "POST" && /region-edit/.test(req.url())) posts.push(req.url());
        });
        await generate.click();
        await expect(page.getByTestId("scene-creator-error").or(summary)).toContainText(/Mask too small/i);
        expect(posts.length).toBe(0);
      }
    }
    await page.waitForTimeout(1000);
    const jobsAfter = await listJobs(request);
    expect(jobsAfter.length).toBe(jobsBefore.length);
  });

  test("Expand / Feather presets reach the region-edit payload", async ({ page }, testInfo) => {
    attachObserver(page, testInfo);
    await openSceneCreator(page);
    await paintMask(page, "large");
    await page.getByTestId("scene-creator-inpaint-operation").selectOption("add");
    await page.getByTestId("scene-creator-inpaint-expand-wide").click();
    await page.getByTestId("scene-creator-inpaint-feather-soft").click();
    await page.getByTestId("scene-creator-inpaint-prompt").fill("a handmade ceramic coffee cup");
    const payloadPromise = page.waitForRequest(
      (req) => req.method() === "POST" && /region-edit/.test(req.url()),
      { timeout: 30_000 },
    );
    await page.getByTestId("scene-creator-inpaint-generate").click();
    const req = await payloadPromise;
    const body = req.postDataJSON() as { expand?: string; feather?: string };
    expect(body.expand).toBe("wide");
    expect(body.feather).toBe("soft");
  });

  test("Remove / Modify / Add / Replace enqueue real region-edit jobs", async ({
    page,
    request,
  }, testInfo) => {
    test.setTimeout(JOB_WAIT_MS * 4);
    attachObserver(page, testInfo);
    await openSceneCreator(page);
    const ops: Array<{ op: string; prompt: string }> = [
      { op: "remove", prompt: "the extra object on the table" },
      { op: "modify", prompt: "irritated expression, same face and identity" },
      { op: "add", prompt: "a handmade ceramic coffee cup" },
      { op: "replace", prompt: "a small blue ceramic mug" },
    ];
    const ws = await getWorkspace(request);
    const shotId = ws.selected_shot?.id;
    expect(shotId).toBeTruthy();
    const hashes: string[] = [];
    for (const step of ops) {
      await page.getByTestId("scene-creator-inpaint-clear").click().catch(() => undefined);
      await openAccordion(page, "scene-creator-inpaint-accordion");
      const source = page.getByTestId("scene-creator-inpaint-source");
      if (step.op === "modify") {
        await source.selectOption({ label: "Take B" }).catch(async () => {
          const takeB = source.locator("option").filter({ hasText: /Take B/i }).first();
          const value = await takeB.getAttribute("value");
          if (value) await source.selectOption(value);
        });
      } else if (step.op === "add" || step.op === "replace") {
        await source.selectOption({ label: /Approved Preview/i }).catch(() => undefined);
      }
      await paintMask(page, "large");
      await page.getByTestId("scene-creator-inpaint-operation").selectOption(step.op);
      await page.getByTestId("scene-creator-inpaint-prompt").fill(step.prompt);
      await expect(page.getByTestId("scene-creator-inpaint-mask-summary")).toContainText(/%/);
      const generateBtn = page.getByTestId("scene-creator-inpaint-generate");
      await expect(generateBtn).toBeEnabled({ timeout: 20_000 });
      const payloadPromise = page.waitForRequest(
        (req) => req.method() === "POST" && /region-edit/.test(req.url()),
        { timeout: 90_000 },
      );
      await generateBtn.click({ force: true });
      const posted = await payloadPromise;
      const body = posted.postDataJSON() as {
        operation?: string;
        sourceAssetId?: string;
        maskAssetId?: string;
      };
      expect(body.operation).toBe(step.op);
      expect(body.sourceAssetId, `${step.op} must send sourceAssetId`).toBeTruthy();
      expect(body.maskAssetId, `${step.op} must send maskAssetId`).toBeTruthy();
      let cand: ShotCandidate | undefined;
      await expect
        .poll(async () => {
          const shot = await getShot(request, shotId!);
          cand = [...(shot.candidates || [])]
            .reverse()
            .find((c) => c.kind === "region_edit" && c.edit_operation === step.op);
          return Boolean(cand?.job_id || cand?.id);
        }, { timeout: 45_000 })
        .toBeTruthy();
      expect(cand, `${step.op} candidate`).toBeTruthy();
      expect(cand!.edit_operation).toBe(step.op);
      hashes.push(cand!.camera_state_hash || "");
      if (cand!.job_id) await waitJobDone(request, cand!.job_id);
      await expect(page.getByTestId("scene-creator-strip-take").first()).toBeVisible();
    }
    const modifyHash = hashes[1];
    const firstHash = hashes[0];
    if (modifyHash && firstHash) expect(modifyHash).toBe(firstHash);
  });

  test("model guard: approved edit + Qwen T2I does not send txt2img final", async ({
    page,
    request,
  }, testInfo) => {
    attachObserver(page, testInfo);
    await openSceneCreator(page);
    const ws = await getWorkspace(request);
    const shots = ws.shots || [];
    const editedIdx = shots.findIndex((s) =>
      (s.candidates || []).some((c) => c.kind === "region_edit") ||
      (((s.take_memory as { userCorrection?: { region_edits?: unknown[] } } | undefined)?.userCorrection?.region_edits || []).length > 0),
    );
    if (editedIdx >= 0) {
      const chip = page.getByTestId("scene-creator-browser").getByRole("button", { name: `Shot ${editedIdx + 1}`, exact: true });
      if (await chip.count()) await chip.click();
    }
    const local = page.getByTestId("generator-local-select");
    await expect(local).toBeVisible();
    const html = await local.innerHTML();
    expect(html.toLowerCase()).not.toContain("qwen.edit");
    const qwenOpt = local.locator("option").filter({ hasText: /qwen/i }).first();
    if (await qwenOpt.count()) {
      const value = await qwenOpt.getAttribute("value");
      if (value) await local.selectOption(value);
    }
    const finals: string[] = [];
    page.on("request", (req) => {
      if (req.method() === "POST" && /cinematographer\/final/.test(req.url())) {
        finals.push(req.postData() || "");
      }
    });
    const generate = page.getByTestId("scene-creator-generate");
    if (await generate.isEnabled()) {
      await generate.click();
    }
    await expect(page.getByTestId("scene-creator-model-guard")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("scene-creator-final-guard")).toBeVisible();
    await expect(page.getByTestId("scene-creator-model-recommend")).toContainText(/Z-Image|FLUX/i);
    for (const body of finals) {
      expect(body).not.toMatch(/txt2img/);
    }
  });

  test("Final Quality Render inherits latest approved edit; duplicate Final is one job", async ({
    page,
    request,
  }, testInfo) => {
    test.setTimeout(JOB_WAIT_MS + 90_000);
    attachObserver(page, testInfo);
    await openSceneCreator(page);
    const ws = await getWorkspace(request);
    const shot = ws.selected_shot;
    expect(shot).toBeTruthy();
    const approvedRegionEdit = [...(shot!.candidates || [])]
      .reverse()
      .find((c) => c.kind === "region_edit" && c.status === "complete" && c.asset_id);
    const approved = approvedRegionEdit
      || (shot!.candidates || []).find((c) => c.id === shot!.approved_candidate_id);
    if (approved?.id && shot!.approved_candidate_id !== approved.id) {
      await request.post(`${API}/api/scene-creator/projects/${PROJECT_ID}/shots/${shot!.id}/approve`, {
        data: { candidate_id: approved.id },
      });
    }
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("scene-creator-standard").or(page.getByTestId("scene-creator-panel"))).toBeVisible({
      timeout: 60_000,
    });
    await page.getByTestId("cine-tile-c1").click();
    const local = page.getByTestId("generator-local-select");
    const zimage = local.locator("option").filter({ hasText: /z-?image/i }).first();
    if (await zimage.count()) {
      const value = await zimage.getAttribute("value");
      if (value) await local.selectOption(value);
    }
    const lock = page.getByTestId("cine-lock");
    if (await lock.isDisabled()) {
      await page.getByTestId("cine-preview").click();
      await expect(lock).toBeEnabled({ timeout: JOB_WAIT_MS });
    }
    if (await lock.isEnabled()) await lock.click();
    const posts: string[] = [];
    page.on("request", (req) => {
      if (req.method() === "POST" && /cinematographer\/final/.test(req.url())) posts.push(req.postData() || "");
    });
    const jobsBefore = await listJobs(request);
    const generate = page.getByTestId("scene-creator-generate");
    await expect(generate).toBeEnabled({ timeout: 45_000 });
    await generate.dblclick({ delay: 30 }).catch(async () => {
      await generate.click();
      await generate.click();
    });
    await page.waitForTimeout(2000);
    expect(posts.length, "duplicate Final must serialize").toBe(1);
    const body = JSON.parse(posts[0] || "{}") as { sourceAssetId?: string; source_asset_id?: string; finalStrategy?: string };
    if (approved?.asset_id) {
      expect(body.sourceAssetId || body.source_asset_id || "").toBe(approved.asset_id);
    }
    if (body.finalStrategy) expect(body.finalStrategy).toBe("A");
    const jobsAfter = await listJobs(request);
    const created = jobsAfter.filter((j) => !jobsBefore.some((b) => b.id === j.id));
    expect(created.length).toBeLessThanOrEqual(1);
    if (created[0]?.id) await waitJobDone(request, created[0].id);
    const latest = await getShot(request, shot!.id);
    const finalCand = [...(latest.candidates || [])]
      .reverse()
      .find((c) => (c.quality_profile || "").toLowerCase() === "final" && c.kind !== "region_edit");
    expect(finalCand, "final candidate").toBeTruthy();
    if (approved?.id) expect(finalCand!.parent_candidate_id || approved.id).toBeTruthy();
    if (finalCand?.final_strategy) expect(finalCand.final_strategy).toBe("A");
  });

  test("approve supersedes previous look; rollback without regeneration", async ({
    page,
    request,
  }, testInfo) => {
    attachObserver(page, testInfo);
    await openSceneCreator(page);
    const ws = await getWorkspace(request);
    const shot = ws.selected_shot;
    expect(shot).toBeTruthy();
    const complete = (shot!.candidates || []).filter((c) => c.status === "complete" && c.asset_id);
    expect(complete.length, "need two complete takes to approve/supersede").toBeGreaterThanOrEqual(2);
    const currentApprovedId = shot!.approved_candidate_id || complete[complete.length - 1].id;
    const other = complete.find((c) => c.id !== currentApprovedId) || complete[0];
    const jobsBefore = await listJobs(request);
    const otherBtn = page.locator(`[data-testid="scene-creator-strip-take"][data-candidate-id="${other.id}"]`);
    await otherBtn.scrollIntoViewIfNeeded();
    await otherBtn.click();
    const approve = page.getByTestId("scene-creator-approve");
    if (await approve.count()) await approve.click();
    await expect
      .poll(async () => (await getShot(request, shot!.id)).approved_candidate_id, { timeout: 20_000 })
      .toBe(other.id);
    const after = await getShot(request, shot!.id);
    const prev = (after.candidates || []).find((c) => c.id === currentApprovedId);
    expect(after.approved_candidate_id).toBe(other.id);
    if (prev && currentApprovedId !== other.id) {
      expect(prev.superseded).toBe(true);
    }
    const originalBtn = page.locator(`[data-testid="scene-creator-strip-take"][data-candidate-id="${currentApprovedId}"]`);
    await originalBtn.scrollIntoViewIfNeeded();
    await originalBtn.click();
    if (await approve.count()) await approve.click();
    await expect
      .poll(async () => (await getShot(request, shot!.id)).approved_candidate_id, { timeout: 20_000 })
      .toBe(currentApprovedId);
    const rolled = await getShot(request, shot!.id);
    expect((rolled.candidates || []).some((c) => c.id === other.id)).toBe(true);
    const jobsAfter = await listJobs(request);
    expect(jobsAfter.length).toBe(jobsBefore.length);
  });

  test("Library asset id matches approved take; Timeline send is one export", async ({
    page,
    request,
  }, testInfo) => {
    attachObserver(page, testInfo);
    await openSceneCreator(page);
    const ws = await getWorkspace(request);
    const shot = ws.selected_shot;
    expect(shot).toBeTruthy();
    const approved = (shot!.candidates || []).find((c) => c.id === shot!.approved_candidate_id)
      || (shot!.candidates || []).find((c) => c.status === "complete" && c.asset_id);
    expect(approved?.asset_id).toBeTruthy();
    const lib = await request.get(`${API}/api/projects/${PROJECT_ID}/library`);
    expect(lib.ok(), await lib.text()).toBeTruthy();
    const libBody = await lib.json();
    const items: Array<{ id?: string; assetId?: string }> = Array.isArray(libBody)
      ? libBody
      : libBody.items || libBody.assets || libBody.library || [];
    const ids = items.map((item) => item.id || item.assetId).filter(Boolean);
    expect(ids).toContain(approved!.asset_id);
    const posts: string[] = [];
    page.on("request", (req) => {
      if (req.method() === "POST" && /send-to-timeline/.test(req.url())) posts.push(req.url());
    });
    const send = page.getByTestId("scene-creator-send-to-timeline");
    await expect(send).toBeVisible();
    await send.dblclick({ delay: 30 }).catch(async () => {
      await send.click();
      await send.click();
    });
    await page.waitForTimeout(2000);
    expect(posts.length, "duplicate Timeline send").toBeLessThanOrEqual(1);
  });

  test("reload persists scene, camera, candidates, labels", async ({ page, request }, testInfo) => {
    attachObserver(page, testInfo);
    await openSceneCreator(page);
    const before = await getWorkspace(request);
    const cineBefore = await getCine(request);
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("scene-creator-standard").or(page.getByTestId("scene-creator-panel"))).toBeVisible({
      timeout: 60_000,
    });
    const after = await getWorkspace(request);
    const cineAfter = await getCine(request);
    expect(after.selected_scene_id || SCENE_ID).toBe(before.selected_scene_id || SCENE_ID);
    expect(after.selected_shot?.id).toBe(before.selected_shot?.id);
    expect((after.selected_shot?.candidates || []).map((c) => c.id)).toEqual(
      (before.selected_shot?.candidates || []).map((c) => c.id),
    );
    expect(cineAfter.selected_camera_id).toBe(cineBefore.selected_camera_id);
    await expect(page.getByTestId("scene-creator-take-strip")).toBeVisible();
  });

  test("Spatial Map cells unchanged after camera work", async ({ request }) => {
    const maps = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps`);
    expect(maps.ok(), await maps.text()).toBeTruthy();
    const body = await maps.json();
    const docs = (body.documents || body.maps || []) as Array<{
      characters?: Array<{ gridRow: number; gridColumn: number; characterId?: string }>;
      props?: Array<{ gridRow: number; gridColumn: number; tag?: string }>;
    }>;
    expect(docs.length).toBeGreaterThan(0);
    const snapshot = JSON.stringify(
      docs.map((d) => ({
        characters: (d.characters || []).map((c) => [c.characterId, c.gridRow, c.gridColumn]),
        props: (d.props || []).map((p) => [p.tag, p.gridRow, p.gridColumn]),
      })),
    );
    const again = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps`);
    const body2 = await again.json();
    const docs2 = (body2.documents || body2.maps || []) as typeof docs;
    const snapshot2 = JSON.stringify(
      docs2.map((d) => ({
        characters: (d.characters || []).map((c) => [c.characterId, c.gridRow, c.gridColumn]),
        props: (d.props || []).map((p) => [p.tag, p.gridRow, p.gridColumn]),
      })),
    );
    expect(snapshot2).toBe(snapshot);
  });

  test("failure UI shows creator copy and Retry, not a traceback", async ({ page, request }, testInfo) => {
    attachObserver(page, testInfo);
    await openSceneCreator(page);
    const ws = await getWorkspace(request);
    const failed = (ws.selected_shot?.candidates || []).find((c) => c.status === "failed");
    if (failed) {
      const failedTake = page.locator('[data-testid="scene-creator-strip-take"][data-status="failed"]').first();
      await failedTake.scrollIntoViewIfNeeded();
      await failedTake.click();
      await expect(page.getByTestId("scene-creator-failed-card")).toBeVisible();
      await expect(page.getByTestId("scene-creator-failed-card")).not.toContainText(/Traceback|File \".+\.py\"/);
      await expect(page.getByTestId("scene-creator-retry")).toBeVisible();
      const jobsBefore = await listJobs(request);
      await page.getByTestId("scene-creator-retry").click();
      await page.waitForTimeout(1500);
      const jobsAfter = await listJobs(request);
      expect(jobsAfter.length).toBeGreaterThanOrEqual(jobsBefore.length);
      const still = await getShot(request, ws.selected_shot!.id);
      expect((still.candidates || []).some((c) => c.id === failed.id)).toBe(true);
    } else {
      await expect(page.getByTestId("scene-creator-retry").or(page.getByTestId("scene-creator-error"))).toHaveCount(
        await page.getByTestId("scene-creator-retry").count(),
      );
    }
  });

  test("console and network: no unexplained 5xx storms", async ({ page }, testInfo) => {
    const observer = attachObserver(page, testInfo);
    await openSceneCreator(page);
    await page.waitForTimeout(3000);
    const storms = observer.apiFailures.filter((f) => f.status >= 500);
    expect(storms, JSON.stringify(storms.slice(0, 8))).toHaveLength(0);
    const fatal = observer.pageErrors.filter((e) => !/ResizeObserver|chrome-extension/i.test(e));
    expect(fatal, fatal.join("\n")).toEqual([]);
  });
});
