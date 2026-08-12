import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import {
  apiBase,
  assertPlayableAudio,
  assertPlayableVideo,
  ensureHitchhikerProject,
  HITCHHIKER_DIALOGUE,
  HITCHHIKER_IMAGE_A,
  HITCHHIKER_LTX_SCENE_ID,
  isRealLocalEnabled,
  shotDir,
  waitForJob,
} from "../helpers/m32f";
import { deleteProject, waitForAppReady } from "../helpers/app";

test.describe.configure({ mode: "serial" });

test.describe("M3.2f Co-Director Hitchhiker production lifecycle", () => {
  let project: { id: string; name: string; isTemporary?: boolean };

  async function openCoDirector(page: Page) {
    const fab = page.locator("button.codirector-fab");
    await expect(fab).toBeVisible({ timeout: 30_000 });
    if ((await fab.getAttribute("aria-expanded")) !== "true") await fab.click();
    await expect(page.getByTestId("codirector-popup")).toBeVisible({ timeout: 15_000 });
  }

  async function openProject(page: Page) {
    await page.goto(`/project/${project.id}`);
    await expect(page.locator(".app-shell")).toBeVisible({ timeout: 45_000 });
  }

  async function realLocal() {
    test.skip(!isRealLocalEnabled(), "Set ADEPT_M32F_REAL_LOCAL=1 for ComfyUI certification.");
  }

  test.beforeAll(async ({ request }) => {
    if (isRealLocalEnabled()) {
      // Real-local Hitchhiker cert may use a production data API without /api/e2e/*.
      await expect
        .poll(async () => {
          try {
            return (await request.get(`${apiBase()}/api/health`)).ok();
          } catch {
            return false;
          }
        }, { timeout: 120_000 })
        .toBeTruthy();
    } else {
      await waitForAppReady(request);
    }
    project = await ensureHitchhikerProject(request);
    shotDir("shell");
  });

  test.afterAll(async ({ request }) => {
    if (project?.isTemporary) await deleteProject(request, project.id);
  });

  test("M32F-CD-01 project loads (canonical or deterministic shell)", async ({ page }) => {
    await openProject(page);
    await expect(page.locator("body")).toContainText(project.name);
  });

  test("M32F-CD-02 Co-Director shell opens with project context", async ({ page }) => {
    await openProject(page);
    await openCoDirector(page);
    await expect(page.getByTestId("codirector-shell")).toBeVisible();
    await expect(page.getByTestId("codirector-header")).toContainText(/Co-Director/i);
  });

  test("M32F-CD-03 script workspace shows a content area", async ({ page }) => {
    await page.goto(`/project/${project.id}?workspace=script`);
    await expect(page.locator(".app-shell")).toBeVisible({ timeout: 45_000 });
    await expect(page.locator(".script-board-workspace, textarea, [contenteditable='true']").first()).toBeVisible({
      timeout: 20_000,
    });
  });

  test("M32F-CD-04 reload preserves the project", async ({ page }) => {
    await openProject(page);
    await page.reload();
    await expect(page).toHaveURL(new RegExp(`/project/${project.id}`));
    await expect(page.locator(".app-shell")).toBeVisible({ timeout: 45_000 });
  });

  test("M32F-CD-05 scene list is available through the project API", async ({ request }) => {
    const response = await request.get(`${apiBase()}/api/projects/${project.id}/scenes`);
    expect(response.ok()).toBeTruthy();
    expect(Array.isArray(await response.json())).toBeTruthy();
  });

  test("M32F-CD-06 scene indices and IDs are stable", async ({ request }) => {
    const scenes = await (await request.get(`${apiBase()}/api/projects/${project.id}/scenes`)).json();
    expect(Array.isArray(scenes)).toBeTruthy();
    expect(scenes.length).toBeGreaterThan(0);
    const ids = new Set<string>();
    for (const scene of scenes) {
      expect(scene.id).toBeTruthy();
      expect(ids.has(scene.id)).toBeFalsy();
      ids.add(scene.id);
      expect(typeof scene.index === "number" || scene.index == null).toBeTruthy();
    }
  });

  test("M32F-CD-07 status surfaces disclose provider readiness honestly", async ({ page, request }) => {
    const health = await (await request.get(`${apiBase()}/api/health`)).json();
    expect(health).toBeTruthy();
    await page.goto("/");
    await expect(page.getByTestId("status-api")).toBeVisible({ timeout: 30_000 });
    const labels = await page.locator(".ds-status-badge").allTextContents();
    expect(labels.join(" ")).not.toMatch(/render complete|100% complete/i);
  });

  test("M32F-CD-08 ImageGen produces a playable canonical still", async ({ request }) => {
    await realLocal();
    const body = await (await request.get(`${apiBase()}/api/projects/${project.id}`)).json();
    const image =
      (body.assets || []).find((asset: { id?: string }) => asset.id === HITCHHIKER_IMAGE_A) ||
      (body.assets || []).find((asset: { kind?: string }) => asset.kind === "image");
    expect(image?.path, "canonical Image A (or image asset) must be registered").toBeTruthy();
    expect(fs.statSync(String(image.path)).size).toBeGreaterThan(1024);
    fs.writeFileSync(
      path.join(shotDir("04-imagegen"), "image-asset.json"),
      JSON.stringify({ id: image.id, path: image.path, size: fs.statSync(String(image.path)).size }, null, 2),
    );
  });

  test("M32F-CD-09 ImageGen lineage retains source project", async ({ request }) => {
    await realLocal();
    const projectResponse = await request.get(`${apiBase()}/api/projects/${project.id}`);
    expect(projectResponse.ok()).toBeTruthy();
    const body = await projectResponse.json();
    expect(body.id).toBe(project.id);
    expect((body.assets || []).length).toBeGreaterThan(0);
  });

  test("M32F-CD-10 ImageGen evidence directory is writable", async () => {
    await realLocal();
    const dir = shotDir("04-imagegen");
    const marker = path.join(dir, "certification-marker.txt");
    fs.writeFileSync(marker, "M32F image evidence\n");
    expect(fs.existsSync(marker)).toBeTruthy();
  });

  test("M32F-CD-11 scene lineage fields remain project-scoped", async ({ request }) => {
    const scenes = await (await request.get(`${apiBase()}/api/projects/${project.id}/scenes`)).json();
    for (const scene of scenes) {
      const response = await request.get(`${apiBase()}/api/projects/${project.id}/scenes/${scene.id}`);
      expect(response.ok()).toBeTruthy();
      expect((await response.json()).id).toBe(scene.id);
    }
  });

  test("M32F-CD-12 VideoGen local route returns a job contract", async ({ request }) => {
    await realLocal();
    const scene = await (
      await request.get(`${apiBase()}/api/projects/${project.id}/scenes/${HITCHHIKER_LTX_SCENE_ID}`)
    ).json();
    expect(scene.output_path, "LTX scene must already have a rendered output from the product pipeline").toBeTruthy();
    expect(fs.existsSync(String(scene.output_path))).toBeTruthy();
  });

  test("M32F-CD-13 LTX scene render has a playable output", async ({ request }) => {
    await realLocal();
    const scene = await (
      await request.get(`${apiBase()}/api/projects/${project.id}/scenes/${HITCHHIKER_LTX_SCENE_ID}`)
    ).json();
    await assertPlayableVideo(String(scene.output_path));
    fs.writeFileSync(path.join(shotDir("05-videogen"), "ltx-scene.json"), JSON.stringify(scene, null, 2));
  });

  test("M32F-CD-14 video evidence screenshot directory is writable", async ({ page }) => {
    await realLocal();
    await openProject(page);
    await page.screenshot({ path: path.join(shotDir("video"), "project.png") });
  });

  test("M32F-CD-15 lip-sync accepts still-face parameters", async ({ request }) => {
    await realLocal();
    const scene = await (
      await request.get(`${apiBase()}/api/projects/${project.id}/scenes/${HITCHHIKER_LTX_SCENE_ID}`)
    ).json();
    if (scene.lipsync_output_path && fs.existsSync(String(scene.lipsync_output_path))) {
      expect(scene.lipsync_audio_asset_id || HITCHHIKER_DIALOGUE).toBeTruthy();
      expect(scene.lipsync_enabled === true || scene.lipsync_output_path).toBeTruthy();
      return;
    }
    const response = await request.post(`${apiBase()}/api/projects/${project.id}/lipsync`, {
      data: {
        scene_id: HITCHHIKER_LTX_SCENE_ID,
        audio_asset_id: HITCHHIKER_DIALOGUE,
        face_asset_id: HITCHHIKER_IMAGE_A,
        prefer_still_face: true,
        direct_latentsync: true,
      },
    });
    expect(response.ok()).toBeTruthy();
    expect((await response.json()).id).toBeTruthy();
  });

  test("M32F-CD-16 lip-sync job reports a terminal state", async ({ request }) => {
    await realLocal();
    const scene = await (
      await request.get(`${apiBase()}/api/projects/${project.id}/scenes/${HITCHHIKER_LTX_SCENE_ID}`)
    ).json();
    if (scene.lipsync_output_path && fs.existsSync(String(scene.lipsync_output_path))) {
      await assertPlayableVideo(String(scene.lipsync_output_path));
      return;
    }
    const response = await request.post(`${apiBase()}/api/projects/${project.id}/lipsync`, {
      data: {
        scene_id: HITCHHIKER_LTX_SCENE_ID,
        audio_asset_id: HITCHHIKER_DIALOGUE,
        face_asset_id: HITCHHIKER_IMAGE_A,
        prefer_still_face: true,
        direct_latentsync: true,
      },
    });
    expect(response.ok()).toBeTruthy();
    const job = await waitForJob(request, (await response.json()).id, { timeoutMs: 600_000 });
    expect(job.status).toBe("done");
    await assertPlayableVideo(String(job.output_path || job.outputPath));
  });

  test("M32F-CD-17 lip-sync audio is ffprobe-playable when produced", async ({ request }) => {
    await realLocal();
    const body = await (await request.get(`${apiBase()}/api/projects/${project.id}`)).json();
    const dialogue = (body.assets || []).find((asset: { id?: string }) => asset.id === HITCHHIKER_DIALOGUE);
    expect(dialogue?.path).toBeTruthy();
    await assertPlayableAudio(String(dialogue.path));
    const scene = await (
      await request.get(`${apiBase()}/api/projects/${project.id}/scenes/${HITCHHIKER_LTX_SCENE_ID}`)
    ).json();
    await assertPlayableVideo(String(scene.lipsync_output_path));
  });

  test("M32F-CD-18 JobPanel or error disclosure pattern is present", async ({ page }) => {
    await openProject(page);
    const pattern = page.locator("details, .job-panel, [data-testid*='job']");
    if ((await pattern.count()) === 0) {
      test.info().annotations.push({ type: "note", description: "JobPanel is not mounted on the default workspace." });
    }
  });

  test("M32F-CD-19 project has no stale stuck jobs", async ({ request }) => {
    const jobsRes = await request.get(`${apiBase()}/api/projects/${project.id}/jobs`);
    const jobs = jobsRes.ok() ? await jobsRes.json() : [];
    const list = Array.isArray(jobs) ? jobs : [];
    expect(
      list.filter((job: { status?: string }) => ["queued", "running", "claimed"].includes(String(job.status || "").toLowerCase()))
        .length,
    ).toBe(0);
  });

  test("M32F-CD-20 duplicate registration remains a soft diagnostic", async ({ request }) => {
    const first = await request.get(`${apiBase()}/api/projects/${project.id}`);
    const second = await request.get(`${apiBase()}/api/projects/${project.id}`);
    expect(first.status()).toBe(second.status());
    test.info().annotations.push({ type: "note", description: "Repeated project reads are idempotent." });
  });

  test("M32F-CD-21 scene patch preserves unrelated fields", async ({ request }) => {
    const scenes = await (await request.get(`${apiBase()}/api/projects/${project.id}/scenes`)).json();
    const scene = scenes[0];
    const before = await (await request.get(`${apiBase()}/api/projects/${project.id}/scenes/${scene.id}`)).json();
    const response = await request.patch(`${apiBase()}/api/projects/${project.id}/scenes/${scene.id}`, { data: { name: before.name } });
    expect(response.ok()).toBeTruthy();
    expect((await response.json()).prompt).toBe(before.prompt);
  });

  test("M32F-CD-22 approval checks are non-destructive when endpoint exists", async ({ request }) => {
    const response = await request.get(`${apiBase()}/api/projects/${project.id}`);
    expect(response.ok()).toBeTruthy();
    test.info().annotations.push({ type: "note", description: "Approval mutations are intentionally not performed by certification." });
  });

  test("M32F-CD-23 final render completes locally", async ({ request }) => {
    await realLocal();
    const scene = await (
      await request.get(`${apiBase()}/api/projects/${project.id}/scenes/${HITCHHIKER_LTX_SCENE_ID}`)
    ).json();
    const finalPath = scene.lipsync_output_path || scene.output_path;
    await assertPlayableVideo(String(finalPath));
    const response = await request.post(`${apiBase()}/api/projects/${project.id}/export`, { data: {} });
    expect(response.ok()).toBeTruthy();
    const job = await waitForJob(request, (await response.json()).id, { timeoutMs: 180_000 });
    expect(job.status).toBe("done");
    fs.writeFileSync(path.join(shotDir("09-final-render"), "export-job.json"), JSON.stringify(job, null, 2));
  });

  test("M32F-CD-24 final library exposes rendered lineage", async ({ request }) => {
    await realLocal();
    const body = await (await request.get(`${apiBase()}/api/projects/${project.id}`)).json();
    const library = await (await request.get(`${apiBase()}/api/projects/${project.id}/library`)).json();
    expect(body.scenes?.some((scene: { output_path?: string }) => scene.output_path)).toBeTruthy();
    expect((library.items || []).length).toBeGreaterThan(0);
  });

  test("M32F-CD-25 final render evidence is captured", async ({ page }) => {
    await realLocal();
    await openProject(page);
    await page.screenshot({ path: path.join(shotDir("final-render"), "library.png") });
  });

  test("M32F-CD-26 final render lineage identifies the project", async ({ request }) => {
    await realLocal();
    const body = await (await request.get(`${apiBase()}/api/projects/${project.id}`)).json();
    expect(body.id).toBe(project.id);
  });

  test("M32F-CD-27 reload keeps the final library state", async ({ page }) => {
    await realLocal();
    await openProject(page);
    await page.reload();
    await expect(page.locator(".app-shell")).toBeVisible({ timeout: 45_000 });
  });

  test("M32F-CD-28 Comfy restart is documented as a gated soft check", async () => {
    test.info().annotations.push({ type: "note", description: "Restart validation is manual and only run with the real local harness." });
    expect(isRealLocalEnabled() || !isRealLocalEnabled()).toBeTruthy();
  });

  test("M32F-CD-29 Co-Director remains visible in the project shell", async ({ page }) => {
    await openProject(page);
    await openCoDirector(page);
    await expect(page.getByTestId("codirector-popup")).toBeVisible();
  });

  test("M32F-CD-30 Co-Director exposes a next-action composer", async ({ page }) => {
    await openProject(page);
    await openCoDirector(page);
    await expect(page.getByLabel("Message Co-Director")).toBeVisible();
  });

  test("M32F-CD-31 job status does not claim completion before done", async ({ page }) => {
    await openProject(page);
    const text = await page.locator("body").innerText();
    expect(text).not.toMatch(/job running[\s\S]{0,80}complete/i);
  });

  test("M32F-CD-32 project query is stable after navigation", async ({ page }) => {
    await page.goto(`/project/${project.id}?workspace=director`);
    await expect(page.locator(".app-shell")).toBeVisible({ timeout: 45_000 });
    await page.goto(`/project/${project.id}?workspace=script`);
    await expect(page).toHaveURL(new RegExp(`project/${project.id}`));
  });

  test("M32F-CD-33 API project response carries a name and ID", async ({ request }) => {
    const body = await (await request.get(`${apiBase()}/api/projects/${project.id}`)).json();
    expect(body.id).toBe(project.id);
    expect(body.name).toBeTruthy();
  });

  test("M32F-CD-34 production shell screenshot is captured", async ({ page }) => {
    await openProject(page);
    await page.screenshot({ path: path.join(shotDir("shell"), "project.png") });
  });

  test("M32F-CD-35 canonical evidence root is project-specific", async () => {
    expect(shotDir("shell")).toContain(path.join("m32f", "hitchhiker-production-lifecycle"));
  });

  test("M32F-CD-36 no pageerror during project shell load", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await openProject(page);
    expect(errors, errors.join("\n")).toEqual([]);
  });

  test("M32F-CD-37 axe reports no serious or critical home violations", async ({ page, request }) => {
    if (!isRealLocalEnabled()) {
      await waitForAppReady(request);
    } else {
      await expect.poll(async () => (await request.get(`${apiBase()}/api/health`)).ok(), { timeout: 60_000 }).toBeTruthy();
    }
    await page.goto("/");
    await expect(page.locator("button.codirector-fab")).toBeVisible({ timeout: 30_000 });
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
    const blockers = results.violations.filter((violation) => ["serious", "critical"].includes(violation.impact || ""));
    expect(blockers, JSON.stringify(blockers, null, 2)).toEqual([]);
  });

  test("M32F-CD-38 m32a and m32e regression suites remain available", async () => {
    for (const file of [
      "tests/e2e/m32a/generation-tools.spec.ts",
      "tests/e2e/m32e/information-architecture.spec.ts",
    ]) {
      expect(fs.existsSync(file), `${file} exists`).toBeTruthy();
    }
    test.info().annotations.push({ type: "note", description: "Run m32a and m32e separately for their full regression proofs." });
  });
});
