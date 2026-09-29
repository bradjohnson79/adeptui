/**
 * Timeline video Re-Take: Preview Monitor launcher + range + mask + prompt.
 * Reuses Korri Anadriya Walk. Never POST /api/projects.
 * Does not activate a new Walk take.
 */
import { expect, test, type Page } from "@playwright/test";

const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
const DIALOGUE_ID = "ae8e5699-a5d8-4b9b-ad8e-0003d81d3639";
const WALK_ID = "b5282a4c-07eb-40db-9d5b-1512eac74dca";

async function waitForTimeline(page: Page) {
  await expect(page.getByTestId("timeline-transport-play")).toBeVisible({ timeout: 60_000 });
}

const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const BATCH_ID = "bb_a062bbb7b274";
const TAKE_A = "cand_ceccb85364ec";
const RETAKE_PROMPT =
  "Make the corridor lighting slightly darker and more cinematic while preserving Korri and Anadriya.";

async function dialogueMaster(request: { get: (url: string) => Promise<{ json: () => Promise<any> }> }) {
  const res = await request.get(`${API}/api/director-timeline/projects/${PROJECT_ID}/scenes/${DIALOGUE_ID}/master`);
  return res.json();
}

function dialogueBatch(master: any) {
  const body = master.master || master;
  const batches = body.batchBlocks || [];
  return batches.find((b: any) => b.id === BATCH_ID) || batches[0];
}

test.describe("Timeline video Re-Take", () => {
  test.skip(process.env.ADEPT_ALLOW_KORRI_MUTATION !== "1", "Requires ADEPT_ALLOW_KORRI_MUTATION=1");
  test.setTimeout(2_700_000);

  test("video launcher, range, rembg toggle, cancel, submit, image gate", async ({ page, request }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(String(err)));
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });

    await page.goto(
      `/project/${PROJECT_ID}?workspace=timeline&sceneId=${DIALOGUE_ID}`,
    );
    await waitForTimeline(page);
    const finishing = page.getByTestId("timeline-mode-video-finishing");
    if (await finishing.isVisible()) await finishing.click();
    await expect(page.getByTestId("live-preview-video")).toBeVisible({ timeout: 45_000 });
    await expect(page.getByTestId("preview-video-retake")).toBeVisible();
    await expect(page.getByTestId("timeline-toolbar-inpaint")).toHaveCount(0);
    await expect(page.getByTestId("timeline-mask-repair-lane")).toHaveCount(0);

    const launcher = page.getByTestId("preview-video-retake");
    await launcher.click();
    await expect(page.getByTestId("timeline-retake-overlay")).toBeVisible();
    await expect(page.getByTestId("timeline-retake-prompt")).toBeVisible();
    await expect(page.getByTestId("timeline-retake-close")).toHaveAttribute("aria-label", "Close Re-Take");
    await expect(launcher).toBeVisible();
    await expect(launcher).toHaveAttribute("aria-pressed", "true");

    await launcher.click();
    await expect(page.getByTestId("timeline-retake-overlay")).toHaveCount(0);
    await expect(launcher).toHaveAttribute("aria-pressed", "false");

    await launcher.click();
    await page.getByTestId("timeline-retake-prompt").fill("typed then closed");
    await page.getByTestId("timeline-retake-close").click();
    await expect(page.getByTestId("timeline-retake-overlay")).toHaveCount(0);
    await expect(page.getByTestId("timeline-retake-mark")).toHaveCount(0);

    await launcher.click();
    await page.getByTestId("timeline-retake-prompt").fill("escape should clear this");
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("timeline-retake-overlay")).toHaveCount(0);
    await expect(page.getByTestId("timeline-retake-mark")).toHaveCount(0);

    await launcher.click();
    await expect(page.getByTestId("timeline-retake-prompt")).toHaveValue("");

    await page.getByTestId("timeline-transport-play").evaluate(() => undefined);
    await page.keyboard.press("Home");
    for (let i = 0; i < 10; i += 1) await page.keyboard.press("ArrowRight");
    await page.getByTestId("timeline-retake-mark-in").click();
    for (let i = 0; i < 20; i += 1) await page.keyboard.press("ArrowRight");
    await page.getByTestId("timeline-retake-mark-out").click();
    await expect(page.getByTestId("timeline-retake-range-label")).toContainText("Repair Range");
    await expect(page.getByTestId("timeline-retake-mark")).toBeVisible();

    await expect(page.getByTestId("timeline-retake-brush")).toHaveCount(0);
    await expect(page.getByTestId("timeline-retake-erase")).toHaveCount(0);
    await expect(page.getByTestId("timeline-retake-brush-size")).toHaveCount(0);
    await expect(page.getByTestId("timeline-retake-mask-canvas")).toHaveCount(0);
    await page.getByTestId("timeline-retake-remove-background").click();
    await expect(page.getByTestId("timeline-retake-remove-background")).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("timeline-retake-overlay")).toBeVisible();
    await page.getByTestId("timeline-retake-prompt").fill("Repair the warped wall panel and match the surrounding plating.");
    await page.getByTestId("timeline-retake-close").click();
    await expect(page.getByTestId("timeline-retake-overlay")).toHaveCount(0);
    await expect(page.getByTestId("preview-video-retake")).toBeVisible();
    await expect(page.getByTestId("timeline-retake-mark")).toHaveCount(0);

    const already = dialogueBatch(await dialogueMaster(request));
    let takeB = (already.candidateVersions || []).find((c: any) => c.id !== TAKE_A && c.assetId);
    let batch = already;
    if (!takeB) {
      await page.getByTestId("preview-video-retake").click();
      await page.getByTestId("timeline-retake-mark-in").click();
      for (let i = 0; i < 16; i += 1) await page.keyboard.press("ArrowRight");
      await page.getByTestId("timeline-retake-mark-out").click();
      await page.getByTestId("timeline-retake-prompt").fill(RETAKE_PROMPT);
      const submit = page.waitForResponse(
        (res) => res.url().includes("/retake-range") && res.request().method() === "POST",
        { timeout: 30_000 },
      );
      await page.getByTestId("timeline-retake-submit").click();
      const posted = await submit;
      expect(posted.ok(), `retake-range ${posted.status()}`).toBeTruthy();
      const body = await posted.json().catch(() => ({}));
      expect(body.ok, JSON.stringify(body)).toBeTruthy();
      const jobId = String(body.jobId || body.queueJobId || "");
      expect(jobId, JSON.stringify(body)).toBeTruthy();
      expect(String(body.message || body.error || ""), JSON.stringify(body)).not.toMatch(/LoadAudio|missing uploaded voices/i);
      await expect(page.getByTestId("timeline-retake-progress")).toBeVisible({ timeout: 15_000 });

      let jobStatus = "";
      let jobMessage = "";
      for (let i = 0; i < 240; i += 1) {
        const jobRes = await request.get(`${API}/api/jobs/${jobId}`);
        const job = await jobRes.json().catch(() => ({}));
        jobStatus = String(job.status || "");
        jobMessage = String(job.message || job.error || "");
        expect(jobMessage, jobMessage).not.toMatch(/LoadAudio|missing uploaded voices/i);
        if (["done", "completed", "failed", "cancelled", "canceled", "timed_out"].includes(jobStatus)) {
          break;
        }
        await page.waitForTimeout(5_000);
      }
      expect(jobStatus, jobMessage).toMatch(/^(done|completed)$/);

      for (let i = 0; i < 60; i += 1) {
        const master = await dialogueMaster(request);
        batch = dialogueBatch(master);
        const cands = batch?.candidateVersions || [];
        takeB = cands.find((c: any) => c.id !== TAKE_A && c.assetId);
        if (takeB) break;
        await page.waitForTimeout(2_000);
      }
    }
    expect(takeB, "reviewable Re-Take candidate").toBeTruthy();
    expect(batch.approvedClip.candidateId).toBe(TAKE_A);
    expect(batch.approvedClip.assetId).toBe("5a2e74b3-8834-45b3-ba93-901af9120ef2");
    expect(takeB.approved).not.toBe(true);

    await page.reload();
    await waitForTimeline(page);
    const afterReload = dialogueBatch(await dialogueMaster(request));
    expect(afterReload.approvedClip.candidateId).toBe(TAKE_A);
    expect((afterReload.candidateVersions || []).some((c: any) => c.id === takeB.id)).toBeTruthy();

    const approvedB = await request.post(
      `${API}/api/director-timeline/projects/${PROJECT_ID}/scenes/${DIALOGUE_ID}/batches/${BATCH_ID}/activate-take`,
      { data: { candidateId: takeB.id } },
    );
    expect(approvedB.ok(), `approve Take B ${approvedB.status()}`).toBeTruthy();
    expect(dialogueBatch(await dialogueMaster(request)).approvedClip.candidateId).toBe(takeB.id);
    const rejected = await request.post(
      `${API}/api/director-timeline/projects/${PROJECT_ID}/scenes/${DIALOGUE_ID}/batches/${BATCH_ID}/reject`,
      { data: { candidateId: takeB.id } },
    );
    expect(rejected.ok(), `reject Take B ${rejected.status()}`).toBeTruthy();
    const restore = await request.post(
      `${API}/api/director-timeline/projects/${PROJECT_ID}/scenes/${DIALOGUE_ID}/batches/${BATCH_ID}/activate-take`,
      { data: { candidateId: TAKE_A } },
    );
    expect(restore.ok(), `restore Take A ${restore.status()}`).toBeTruthy();
    expect(dialogueBatch(await dialogueMaster(request)).approvedClip.candidateId).toBe(TAKE_A);

    await page.goto(`/project/${PROJECT_ID}?workspace=timeline&sceneId=${WALK_ID}`);
    await waitForTimeline(page);
    await expect(page.getByTestId("live-preview-image")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("preview-video-retake")).toHaveCount(0);
    await expect(page.getByTestId("timeline-retake-overlay")).toHaveCount(0);

    const leftover = errors.filter(
      (line) =>
        !/favicon|ResizeObserver|fonts\.gstatic|fonts\.googleapis|x-adept-deny-owner-writes|net::ERR|404 \(Not Found\)|500 \(Internal Server Error\)/i.test(
          line,
        ),
    );
    expect(leftover, leftover.join("\n")).toEqual([]);
  });
});
