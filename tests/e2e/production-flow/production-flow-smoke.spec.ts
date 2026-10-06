/**
 * Live Adept UI production flow.
 * Image Generator → Storyboard → Timeline H3 Base Optimized → Publish → MAGI 2K.
 * This spec does not change production source.
 */
import { expect, test, type Page, type Request, type Response } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { legalCanvasSize } from "../../../studio-web/src/video/legalCanvas";

test.use({ trace: "on", video: "on" });

const PROMPTS = [
  "A cinematic misty mountain valley at sunrise, wide establishing shot",
  "A futuristic glass observatory overlooking a calm ocean, cinematic daylight",
  "A peaceful forest clearing with soft golden light, cinematic wide shot",
];
const TIMELINE_PROMPT =
  "A slow cinematic camera move through a peaceful natural environment, maintaining stable composition and realistic depth throughout the shot.";

type Step = { step: string; status: "PASS" | "FAIL" | "BLOCKED"; detail: string };
type NetRow = { method: string; path: string; status: number; owner: string; jobId: string };

test("production flow through the live Adept UI", async ({ page }, testInfo) => {
  test.setTimeout(100 * 60 * 1000);
  const stamp = new Date();
  const token = `20261005_${String(stamp.getHours()).padStart(2, "0")}${String(stamp.getMinutes()).padStart(2, "0")}${String(stamp.getSeconds()).padStart(2, "0")}`;
  let projectName = `PRODUCTION_FLOW_SMOKE_${token}`;
  const evidenceDir = path.join("artifacts", "production-flow-smoke", token);
  fs.mkdirSync(evidenceDir, { recursive: true });

  const steps: Step[] = [];
  const network: NetRow[] = [];
  const consoleErrors: string[] = [];
  const failedRequests: string[] = [];
  let projectId = "";
  let projectUrl = "";
  let halted = "";
  const imageAssets: string[] = [];
  const imageJobs: string[] = [];
  let imageModel = "";
  let storyboardId = "";
  let sceneId = "";
  let renderJobId = "";
  let publishedAssetId = "";
  let magiJobId = "";
  let magiOutputId = "";
  let finishingStatus = "";
  let legalDims = { width: 0, height: 0 };
  let referenceAssetId = "";

  page.on("console", (msg) => {
    if (msg.type() !== "error") return;
    const text = msg.text();
    const where = msg.location()?.url || "";
    if (/chrome-extension|moz-extension|fonts\.gstatic|x-adept-deny-owner-writes/i.test(`${text} ${where}`)) return;
    consoleErrors.push(`${text.slice(0, 240)} @ ${where}`.slice(0, 400));
  });
  page.on("pageerror", (err) => consoleErrors.push(String(err?.message || err).slice(0, 400)));
  page.on("response", (response) => {
    noteResponse(response, network, failedRequests);
    if (response.url().includes("/api/magi/projects/") && response.url().includes("/jobs/")) {
      void response.json().then((body) => {
        if (body?.status) finishingStatus = String(body.status);
        const output = body?.output_asset_id || body?.outputAssetId;
        if (output) magiOutputId = String(output);
      }).catch(() => undefined);
    }
  });
  page.on("request", (request) => noteRequest(request, network));
  page.on("requestfailed", (request) => {
    const url = request.url();
    if (/chrome-extension|moz-extension|fonts\.gstatic|favicon|\.map(\?|$)/i.test(url)) return;
    const reason = request.failure()?.errorText || "failed";
    if (reason === "net::ERR_ABORTED") return;
    failedRequests.push(`${reason} ${url.slice(0, 220)}`);
  });

  async function shot(name: string) {
    await page.screenshot({ path: path.join(evidenceDir, `${name}.png`), fullPage: true }).catch(() => undefined);
  }

  async function record(step: string, fn: () => Promise<string>, shotName?: string) {
    if (halted) {
      steps.push({ step, status: "BLOCKED", detail: halted });
      return;
    }
    try {
      const detail = await fn();
      steps.push({ step, status: "PASS", detail });
      if (shotName) await shot(shotName);
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      steps.push({ step, status: "FAIL", detail: detail.slice(0, 900) });
      halted = `${step}: ${detail.slice(0, 240)}`;
      await page.screenshot({
        path: path.join(evidenceDir, `FAIL_${step}_${token}.png`),
        fullPage: true,
      }).catch(() => undefined);
    }
  }

  const resumeProjectId = process.env.ADEPT_FLOW_PROJECT_ID || "";
  if (resumeProjectId && process.env.ADEPT_FLOW_PROJECT_NAME) {
    projectName = process.env.ADEPT_FLOW_PROJECT_NAME;
  }

  try {
    if (resumeProjectId) {
      await record("project", async () => {
        projectId = resumeProjectId;
        await page.goto(`/project/${projectId}`);
        await page.waitForURL(new RegExp(`/project/${projectId}`), { timeout: 30_000 });
        projectUrl = page.url();
        return `resumed ${projectName} ${projectId} ${projectUrl}`;
      });
      await record("image_generator_load", async () => {
        await page.goto(`/project/${projectId}?workspace=imagegen`);
        await expect(page.getByTestId("cis-prompt")).toBeVisible({ timeout: 30_000 });
        const local = page.getByTestId("cis-hosted-local");
        if (await local.isVisible().catch(() => false)) await local.check().catch(() => local.click());
        await expect(page.getByTestId("cis-using-model")).not.toContainText("No model selected", { timeout: 90_000 });
        imageModel = (await page.getByTestId("cis-using-model").innerText()).trim();
        await shot("01_image_generator_ready");
        return `${imageModel}; three images already in this project's Library`;
      });
    }

    if (!resumeProjectId) {
    await record("project", async () => {
      await page.goto("/");
      await expect(page.getByTestId("generation-studio-home")).toBeVisible({ timeout: 30_000 });
      await page.getByTestId("create-project-open").click();
      await page.locator("#np-name").fill(projectName);
      await page.getByTestId("create-project-submit").click();
      await expect(page.getByTestId("create-project-modal")).toBeHidden({ timeout: 30_000 });
      await expect(page.getByTestId("codirector-project-context")).toContainText(projectName, { timeout: 20_000 });
      await page.getByRole("button", { name: `Open ${projectName}` }).click();
      await page.waitForURL(/\/project\/[^/?#]+/, { timeout: 30_000 });
      projectId = decodeURIComponent(page.url().split("/project/")[1]?.split(/[?#]/)[0] || "");
      expect(projectId).toMatch(/[0-9a-f-]{8,}/i);
      projectUrl = page.url();
      return `${projectName} ${projectId} ${projectUrl}`;
    });

    await record("image_generator_load", async () => {
      await page.goto(`/project/${projectId}?workspace=imagegen`);
      await expect(page.getByTestId("cis-prompt")).toBeVisible({ timeout: 30_000 });
      const local = page.getByTestId("cis-hosted-local");
      if (await local.isVisible().catch(() => false)) await local.check().catch(() => local.click());
      imageModel = (await page.getByTestId("cis-using-model").innerText()).trim();
      await shot("01_image_generator_ready");
      return imageModel;
    });

    for (let index = 0; index < PROMPTS.length; index += 1) {
      const n = index + 1;
      await record(`image_${n}`, async () => {
        const before = await page.locator(".cis-result-card img").count();
        await page.getByTestId("cis-prompt").fill(PROMPTS[index]);
        await expect(page.getByTestId("cis-using-model")).not.toContainText("No model selected", { timeout: 90_000 });
        const blocked = page.getByText("No ready image provider for this mode");
        if (await blocked.isVisible().catch(() => false)) {
          throw new Error("No ready image provider for this mode. Check Production Dock.");
        }
        const responsePromise = page.waitForResponse(
          (response) => response.request().method() === "POST" && response.url().includes("/api/image-product/projects/") && response.url().includes("/generate"),
          { timeout: 180_000 },
        ).catch((error: unknown) => error);
        const blockedPromise = blocked.waitFor({ state: "visible", timeout: 180_000 }).then(
          () => "blocked" as const,
          () => null,
        );
        await page.getByTestId("cis-generate").click();
        const outcome = await Promise.race([
          responsePromise.then((value) => ({ kind: "response" as const, value })),
          blockedPromise.then((value) => ({ kind: "banner" as const, value })),
        ]);
        if (outcome.kind === "banner" && outcome.value === "blocked") {
          throw new Error("No ready image provider for this mode. Check Production Dock.");
        }
        const settled = outcome.kind === "response" ? outcome.value : await responsePromise;
        if (settled instanceof Error) throw settled;
        const response = settled;
        const body = await response.json().catch(() => ({}));
        if (response.status() >= 400) throw new Error(`Image generate HTTP ${response.status()} ${JSON.stringify(body).slice(0, 300)}`);
        const jobId = String(body.jobId || body.jobs?.[0]?.jobId || body.jobs?.[0]?.id || "");
        if (jobId) imageJobs.push(jobId);
        imageModel = (await page.getByTestId("cis-using-model").innerText()).trim();
        let src = "";
        await expect.poll(async () => {
          const images = page.locator(".cis-result-card img");
          const count = await images.count();
          if (count <= before) {
            const pending = await page.locator(".cis-result-card").first().innerText().catch(() => "");
            if (/fail|error|refused/i.test(pending)) return `FAIL ${pending}`;
            return "";
          }
          for (let card = 0; card < count; card += 1) {
            const candidate = (await images.nth(card).getAttribute("src")) || "";
            const id = decodeURIComponent(candidate.match(/assets\/([^/?]+)/)?.[1] || "");
            if (id && !imageAssets.includes(id)) {
              src = candidate;
              return src;
            }
          }
          return "";
        }, { timeout: 12 * 60 * 1000, intervals: [2000, 5000] }).toMatch(/assets\//);
        const assetId = String(src).match(/assets\/([^/?]+)/)?.[1] || "";
        if (!assetId) throw new Error(`Image ${n} rendered without an asset id. src=${src}`);
        imageAssets.push(decodeURIComponent(assetId));
        await shot(`0${n + 1}_image_${n}_created`);
        return `job ${jobId || "unknown"} asset ${imageAssets[index]} model ${imageModel}`;
      });
    }
    }

    await record("storyboard", async () => {
      const docResponsePromise = page.waitForResponse(
        (response) => response.url().includes("/api/storyboard-studio/projects/") && response.ok(),
        { timeout: 20_000 },
      );
      const libraryPromise = page.waitForResponse(
        (response) => response.request().method() === "GET" && /\/api\/projects\/.+\/library/.test(new URL(response.url()).pathname) && response.ok(),
        { timeout: 20_000 },
      ).catch(() => null);
      await page.goto(`/project/${projectId}?workspace=storyboard`);
      await expect(page.getByTestId("storyboard-studio")).toBeVisible({ timeout: 30_000 });
      const docResponse = await docResponsePromise.catch(() => null);
      if (docResponse) {
        const payload = await docResponse.json().catch(() => ({}));
        storyboardId = String(payload.id || payload.document?.id || payload.documentId || "");
      }
      await page.getByTestId("sb-aspect-16-9").click();
      await expect(page.getByTestId("sb-grid")).toHaveAttribute("data-aspect", "16:9", { timeout: 15_000 });
      await shot("05_storyboard_16x9");
      const pane = page.getByTestId("sb-library-pane");
      if (!(await pane.isVisible().catch(() => false))) {
        await page.getByTestId("sb-library-toggle").click();
      }
      await expect(pane).toBeVisible();
      if (!imageAssets.length) {
        const cards = pane.locator("[data-testid^='sb-library-asset-']");
        await expect(cards).toHaveCount(3, { timeout: 20_000 });
        const libraryResponse = await libraryPromise;
        const payload = libraryResponse ? await libraryResponse.json().catch(() => ({})) : {};
        const items = Array.isArray(payload.items) ? payload.items as Array<{ id?: string; kind?: string; created_at?: string }> : [];
        const ordered = items
          .filter((item) => item.kind === "image" && item.id)
          .sort((a, b) => String(a.created_at || "").localeCompare(String(b.created_at || "")));
        if (ordered.length < 3) {
          const domIds: string[] = [];
          for (let index = 0; index < 3; index += 1) {
            domIds.push((await cards.nth(index).getAttribute("data-testid") || "").replace("sb-library-asset-", ""));
          }
          imageAssets.push(...domIds.reverse());
        } else {
          imageAssets.push(...ordered.slice(0, 3).map((item) => String(item.id)));
        }
        steps.push(
          { step: "image_1", status: "PASS", detail: `already generated asset ${imageAssets[0]}` },
          { step: "image_2", status: "PASS", detail: `already generated asset ${imageAssets[1]}` },
          { step: "image_3", status: "PASS", detail: `already generated asset ${imageAssets[2]}` },
        );
      }
      let placed = imageAssets.length === 3;
      for (let index = 0; placed && index < 3; index += 1) {
        const src = (await page.getByTestId(`sb-slot-${index}`).locator("img").getAttribute("src").catch(() => "")) || "";
        if (!src.includes(imageAssets[index])) placed = false;
      }
      if (!placed) {
        for (const assetId of imageAssets) {
          const card = page.getByTestId(`sb-library-asset-${assetId}`);
          await expect(card).toBeVisible({ timeout: 20_000 });
          const filled = await page.locator("[data-testid^='sb-slot-'] img").count();
          await card.click();
          await expect(page.locator("[data-testid^='sb-slot-'] img")).toHaveCount(filled + 1, { timeout: 20_000 });
        }
      }
      for (let index = 0; index < 3; index += 1) {
        const slot = page.getByTestId(`sb-slot-${index}`);
        await expect(slot.locator("img")).toHaveAttribute("src", new RegExp(imageAssets[index]), { timeout: 15_000 });
      }
      await shot("06_storyboard_3_images");
      return storyboardId || "document id not in the first storyboard response";
    });

    await record("storyboard_persistence", async () => {
      await page.reload();
      await expect(page.getByTestId("storyboard-studio")).toBeVisible({ timeout: 30_000 });
      await expect(page.getByTestId("sb-grid")).toHaveAttribute("data-aspect", "16:9");
      for (let index = 0; index < 3; index += 1) {
        await expect(page.getByTestId(`sb-slot-${index}`).locator("img")).toHaveAttribute("src", new RegExp(imageAssets[index]));
      }
      await shot("07_storyboard_after_reload");
      return "16:9 and three frames remained";
    });

    async function showPromptWorkspace() {
      const promptTab = page.getByTestId("film-timeline-workspace-prompt");
      if (await promptTab.count()) await promptTab.click();
      await expect(page.getByTestId("film-timeline-prompt")).toBeVisible({ timeout: 20_000 });
    }

    await record("timeline", async () => {
      await page.goto(`/project/${projectId}?workspace=timeline`);
      await expect(page.getByTestId("film-timeline")).toBeVisible({ timeout: 30_000 });
      await showPromptWorkspace();
      const scene = page.getByTestId("film-timeline-scene");
      if ((await scene.locator("option").count()) === 0) {
        await page.getByTestId("film-timeline-new-scene").click();
        await expect(scene.locator("option").first()).toBeAttached({ timeout: 20_000 });
      }
      sceneId = await scene.inputValue();
      await page.getByTestId("film-timeline-prompt").fill(TIMELINE_PROMPT);
      const model = page.getByTestId("film-timeline-model");
      const option = model.locator("option", { hasText: "MiniMax H3 Base Optimized" });
      await expect(option).toHaveCount(1, { timeout: 20_000 });
      const generatorId = await option.getAttribute("value");
      if (generatorId !== "minimax-h3-base-optimized") throw new Error(`Generator option value is ${generatorId}`);
      await model.selectOption(generatorId);
      await expect(model).toHaveValue("minimax-h3-base-optimized");
      const duration = page.getByTestId("film-timeline-duration");
      const fifteen = duration.locator("option[value='15']");
      if ((await fifteen.count()) !== 1) throw new Error("15 seconds is not a legal duration option");
      await duration.selectOption("15");
      const mp = page.getByTestId("film-timeline-megapixels-select");
      await expect(mp).toBeEnabled({ timeout: 15_000 });
      const mpOption = mp.locator("option", { hasText: /^1\.0 MP/ });
      await expect(mpOption).toHaveCount(1);
      await mp.selectOption(await mpOption.getAttribute("value") || "");
      const legal = legalCanvasSize("minimax-h3", "1.0 MP", "16:9");
      legalDims = { width: legal.width, height: legal.height };
      await expect(mpOption).toContainText(`${legal.width}×${legal.height}`);
      return `scene ${sceneId} 15s ${legal.width}x${legal.height}`;
    }, "09_timeline_h3_base_optimized_15s_1mp");

    await record("environment_reference", async () => {
      await showPromptWorkspace();
      const existing = page.locator(".film-reference-chip.is-environment");
      if ((await existing.count()) === 3) {
        const ids: string[] = [];
        for (let index = 0; index < 3; index += 1) {
          ids.push((await existing.nth(index).getAttribute("data-asset-id")) || "");
          await expect(existing.nth(index)).toHaveAttribute("data-source", /^storyboard:/);
        }
        if (ids.join(",") !== imageAssets.join(",")) {
          throw new Error(`Attached frames ${ids.join(",")} are not the storyboard order`);
        }
        referenceAssetId = ids.join(",");
        await shot("08_timeline_reference_attached");
        await page.reload();
        await expect(page.getByTestId("film-timeline")).toBeVisible({ timeout: 30_000 });
        await showPromptWorkspace();
        const persisted = page.locator(".film-reference-chip.is-environment");
        await expect(persisted).toHaveCount(3, { timeout: 20_000 });
        for (let index = 0; index < 3; index += 1) {
          await expect(persisted.nth(index)).toHaveAttribute("data-asset-id", imageAssets[index]);
        }
        await shot("08b_timeline_reference_persisted");
        return `storyboard already attached ${ids.join(",")}`;
      }
      await page.getByTestId("film-timeline-references").click();
      const modal = page.getByTestId("film-reference-modal");
      await expect(modal).toBeVisible();
      await modal.getByRole("button", { name: "Environment", exact: true }).click();
      await expect(modal.getByText("Loading…")).toHaveCount(0, { timeout: 20_000 });
      const choice = modal.locator("[data-testid^='film-reference-choice-storyboard-']");
      await expect(choice).toHaveCount(1, { timeout: 20_000 });
      const frames = (await choice.getAttribute("data-frames")) || "";
      if (frames !== imageAssets.join(",")) {
        throw new Error(`Storyboard frames ${frames} are not ${imageAssets.join(",")}`);
      }
      const choiceId = (await choice.getAttribute("data-testid")) || "";
      if (storyboardId && !choiceId.endsWith(storyboardId)) {
        throw new Error(`Storyboard choice ${choiceId} is not document ${storyboardId}`);
      }
      await choice.click();
      const savedIds: string[] = [];
      const saved = new Promise<void>((resolve, reject) => {
        const timer = setTimeout(() => reject(new Error(`Storyboard save stopped at ${savedIds.length} frames`)), 25_000);
        const onResponse = async (response: Response) => {
          if (response.request().method() !== "POST") return;
          if (!/\/references$/.test(new URL(response.url()).pathname)) return;
          if (response.status() >= 400) {
            clearTimeout(timer);
            page.off("response", onResponse);
            reject(new Error(`Reference save HTTP ${response.status()}`));
            return;
          }
          const body = response.request().postDataJSON() as { assetId?: string; source?: string; type?: string };
          if (body.type !== "environment" || !String(body.source || "").startsWith("storyboard:")) {
            clearTimeout(timer);
            page.off("response", onResponse);
            reject(new Error(`Reference save was not a storyboard environment frame: ${JSON.stringify(body)}`));
            return;
          }
          savedIds.push(String(body.assetId || ""));
          if (savedIds.length === 3) {
            clearTimeout(timer);
            page.off("response", onResponse);
            resolve();
          }
        };
        page.on("response", onResponse);
      });
      await page.getByTestId("film-reference-save").click();
      await saved;
      if (savedIds.join(",") !== imageAssets.join(",")) {
        throw new Error(`Saved frame order ${savedIds.join(",")} is not ${imageAssets.join(",")}`);
      }
      referenceAssetId = savedIds.join(",");
      await expect(modal).toBeHidden({ timeout: 20_000 });
      const chips = page.locator(".film-reference-chip.is-environment");
      await expect(chips).toHaveCount(3);
      for (let index = 0; index < 3; index += 1) {
        await expect(chips.nth(index)).toHaveAttribute("data-asset-id", imageAssets[index]);
        await expect(chips.nth(index)).toHaveAttribute("data-source", new RegExp("^storyboard:"));
      }
      await shot("08_timeline_reference_attached");
      await page.reload();
      await expect(page.getByTestId("film-timeline")).toBeVisible({ timeout: 30_000 });
      await showPromptWorkspace();
      const persisted = page.locator(".film-reference-chip.is-environment");
      await expect(persisted).toHaveCount(3, { timeout: 20_000 });
      for (let index = 0; index < 3; index += 1) {
        await expect(persisted.nth(index)).toHaveAttribute("data-asset-id", imageAssets[index]);
      }
      await shot("08b_timeline_reference_persisted");
      return `storyboard ${storyboardId || choiceId} frames ${savedIds.join(",")}`;
    });

    await record("timeline_render", async () => {
      await showPromptWorkspace();
      const promptBox = page.getByTestId("film-timeline-prompt");
      if ((await promptBox.inputValue()) !== TIMELINE_PROMPT) await promptBox.fill(TIMELINE_PROMPT);
      await expect(promptBox).toHaveValue(TIMELINE_PROMPT);
      const model = page.getByTestId("film-timeline-model");
      if ((await model.inputValue()) !== "minimax-h3-base-optimized") {
        await model.selectOption("minimax-h3-base-optimized");
      }
      await expect(model).toHaveValue("minimax-h3-base-optimized");
      const durationSelect = page.getByTestId("film-timeline-duration");
      if ((await durationSelect.inputValue()) !== "15") await durationSelect.selectOption("15");
      await expect(durationSelect).toHaveValue("15");
      const mp = page.getByTestId("film-timeline-megapixels-select");
      await expect(mp).toBeEnabled({ timeout: 15_000 });
      const mpText = await mp.locator("option:checked").innerText();
      if (!mpText.includes("1.0 MP") || !mpText.includes("1376×768")) {
        const mpOption = mp.locator("option", { hasText: /^1\.0 MP/ });
        await mp.selectOption((await mpOption.getAttribute("value")) || "");
      }
      await expect(mp.locator("option:checked")).toContainText("1376×768");
      const chips = page.locator(".film-reference-chip.is-environment");
      await expect(chips).toHaveCount(3);
      const filmResponse = await page.request.get(`/api/film-timeline/projects/${projectId}/scenes/${sceneId}`);
      const filmJson = await filmResponse.json() as { film?: { shots?: Array<{ segments?: Array<Record<string, unknown>> }> }; shots?: Array<{ segments?: Array<Record<string, unknown>> }> };
      const filmShots = filmJson.film?.shots || filmJson.shots || [];
      const live = (filmShots[0]?.segments || []).find((segment) => {
        const status = String(segment.status || "");
        return ["queued", "generating", "processing", "downloading", "completed"].includes(status)
          && segment.generatorId === "minimax-h3-base-optimized";
      });
      if (live) {
        const meta = (live.generationMetadata || {}) as { plannedReferenceAssetIds?: string[]; jobId?: string; legalCanvas?: { width?: number; height?: number; megapixels?: number } };
        if (Number(live.durationSec) !== 15) throw new Error(`Existing render duration ${live.durationSec}`);
        if (Number(meta.legalCanvas?.width) !== 1376 || Number(meta.legalCanvas?.height) !== 768) {
          throw new Error(`Existing legal canvas ${JSON.stringify(meta.legalCanvas)}`);
        }
        const planned = meta.plannedReferenceAssetIds || [];
        if (planned.slice(0, 3).join(",") !== imageAssets.join(",")) {
          throw new Error(`Existing job planned ${planned.join(",")} is not the storyboard`);
        }
        renderJobId = String(meta.jobId || "");
      } else {
        let generatePosts = 0;
        const countGenerate = (request: Request) => {
          if (request.method() === "POST" && /\/generate$/.test(new URL(request.url()).pathname)) generatePosts += 1;
        };
        page.on("request", countGenerate);
        const responsePromise = page.waitForResponse(
          (response) => response.request().method() === "POST" && /\/api\/film-timeline\/projects\/.+\/generate$/.test(new URL(response.url()).pathname),
          { timeout: 60_000 },
        );
        await page.getByTestId("film-timeline-generate").click();
        const response = await responsePromise;
        const payload = response.request().postDataJSON() as Record<string, unknown>;
        if (payload.timedPrompt !== TIMELINE_PROMPT) throw new Error(`timedPrompt ${payload.timedPrompt}`);
        if (payload.generatorId !== "minimax-h3-base-optimized") throw new Error(`generatorId ${payload.generatorId}`);
        if (Number(payload.durationSec) !== 15) throw new Error(`durationSec ${payload.durationSec}`);
        const h3 = (payload.providerOptions as { h3Resolution?: { megapixels?: number; width?: number; height?: number } } | undefined)?.h3Resolution;
        if (!h3 || Number(h3.megapixels) !== 1) throw new Error(`h3Resolution ${JSON.stringify(h3)}`);
        const body = await response.json().catch(() => ({})) as {
          ok?: boolean;
          jobId?: string;
          message?: string;
          segment?: { generationMetadata?: { plannedReferenceAssetIds?: string[]; legalCanvas?: { width?: number; height?: number } } };
          shot?: { state?: { references?: Array<{ assetId?: string; type?: string; source?: string }> } };
        };
        if (response.status() >= 400 || body.ok === false) throw new Error(`Generate HTTP ${response.status()} ${body.message || ""}`);
        const legal = body.segment?.generationMetadata?.legalCanvas;
        if (!legal || Number(legal.width) !== 1376 || Number(legal.height) !== 768) {
          throw new Error(`Legal canvas ${JSON.stringify(legal)}`);
        }
        renderJobId = String(body.jobId || "");
        const planned = body.segment?.generationMetadata?.plannedReferenceAssetIds || [];
        if (planned.slice(0, 3).join(",") !== imageAssets.join(",")) {
          throw new Error(`Job ${renderJobId} planned references ${planned.join(",")} did not start with the storyboard frames`);
        }
        const attached = (body.shot?.state?.references || []).filter((ref) => ref.type === "environment" && String(ref.source || "").startsWith("storyboard:"));
        if (attached.map((ref) => ref.assetId).join(",") !== imageAssets.join(",")) {
          throw new Error(`Generate response dropped the storyboard environment references`);
        }
        if (generatePosts !== 1) throw new Error(`Duplicate generation count ${generatePosts}`);
      }
      const video = page.locator("[data-testid='film-timeline-monitor'] video");
      await expect.poll(async () => {
        const error = await page.getByTestId("film-timeline-error").innerText().catch(() => "");
        if (/fail|refused|unavailable/i.test(error)) return `FAIL ${error}`;
        if ((await video.count()) === 0) return "";
        return (await video.first().getAttribute("src")) || "";
      }, { timeout: 45 * 60 * 1000, intervals: [3000, 8000] }).not.toMatch(/^$|^FAIL/);
      const media = await video.first().evaluate((node) => {
        const el = node as HTMLVideoElement;
        const read = () => ({ duration: el.duration, width: el.videoWidth, height: el.videoHeight });
        if (Number.isFinite(el.duration) && el.duration > 0 && el.videoWidth > 0) return Promise.resolve(read());
        return new Promise<{ duration: number; width: number; height: number }>((resolve, reject) => {
          const timer = window.setTimeout(() => reject(new Error("Video metadata did not load")), 20_000);
          el.addEventListener("loadedmetadata", () => {
            window.clearTimeout(timer);
            resolve(read());
          }, { once: true });
          el.load();
        });
      });
      if (!Number.isFinite(media.duration) || media.duration < 12 || media.duration > 18) {
        throw new Error(`Playable duration ${media.duration} is not about 15 seconds`);
      }
      if (media.width !== 1376 || media.height !== 768) {
        throw new Error(`Output is ${media.width}x${media.height}, not 1376x768`);
      }
      await shot("10_timeline_render_complete");
      return `duration ${media.duration} ${media.width}x${media.height} job ${renderJobId || "see network"}`;
    });

    await record("publish", async () => {
      const filmResponse = await page.request.get(`/api/film-timeline/projects/${projectId}/scenes/${sceneId}`);
      const filmJson = await filmResponse.json() as { publishedAssetId?: string; film?: { publishedAssetId?: string } };
      const already = String(filmJson.film?.publishedAssetId || filmJson.publishedAssetId || "");
      if (already) {
        publishedAssetId = already;
        return `already published ${already}`;
      }
      const bar = page.getByTestId("live-preview-publish-bar");
      if ((await bar.getAttribute("data-collapsed")) === "true") {
        await bar.getByRole("button").first().click();
      }
      const publish = page.getByTestId("live-preview-publish");
      await expect(publish).toBeVisible({ timeout: 15_000 });
      if (await publish.isDisabled()) {
        throw new Error("Publish is disabled. A single rendered shot does not become a ready stitch, so the published master cannot be created from this control.");
      }
      const responsePromise = page.waitForResponse(
        (response) => response.request().method() === "POST" && response.url().includes("/api/film-timeline/") && response.url().includes("/publish"),
        { timeout: 60_000 },
      );
      await publish.click();
      const response = await responsePromise;
      const body = await response.json().catch(() => ({}));
      if (response.status() >= 400 || body.ok === false) throw new Error(`Publish HTTP ${response.status()} ${JSON.stringify(body).slice(0, 300)}`);
      publishedAssetId = String(body.assetId || body.publishedAssetId || body.film?.publishedAssetId || "");
      await shot("11_video_published");
      return publishedAssetId || "published";
    });

    await record("send_to_magi", async () => {
      if (publishedAssetId) {
        await page.goto(`/project/${projectId}?workspace=magi&sceneId=${sceneId}`);
        await expect(page.getByTestId("magi-viewer")).toBeVisible({ timeout: 30_000 });
        const video = page.locator("[data-testid='magi-viewer'] video");
        await expect(video.first()).toBeVisible({ timeout: 20_000 });
        await shot("12_sent_to_magi");
        return page.url();
      }
      await page.getByTestId("film-timeline-send-magi").click();
      const note = page.getByTestId("film-timeline-magi-note");
      if (await note.isVisible().catch(() => false)) {
        throw new Error(await note.innerText());
      }
      await page.waitForURL(/workspace=magi/, { timeout: 20_000 });
      await expect(page.getByTestId("magi-viewer")).toBeVisible({ timeout: 30_000 });
      const video = page.locator("[data-testid='magi-viewer'] video");
      await expect(video.first()).toBeVisible({ timeout: 20_000 });
      await shot("12_sent_to_magi");
      return page.url();
    });

    await record("magi_2k", async () => {
      const library = await page.request.get(`/api/projects/${projectId}/library?scope=project&limit=50`);
      const libraryJson = await library.json() as { items?: Array<{ id?: string; filename?: string; kind?: string }> };
      const finished = (libraryJson.items || []).find((item) => item.kind === "video" && String(item.filename || "").startsWith("upscale_"));
      if (finished?.id) {
        magiOutputId = finished.id;
        await expect(page.getByTestId("magi-viewer").locator("video").first()).toBeVisible({ timeout: 20_000 });
        return `2K output ${finished.id} already in the project Library`;
      }
      await page.locator("#magi-acc-btn-upscale").click();
      const target = page.getByTestId("magi-upscale-target");
      await expect(target).toBeVisible();
      await target.selectOption("2K");
      await expect(page.getByTestId("magi-upscale-resolved")).toContainText(/\d+\s*×\s*\d+/);
      await shot("13_magi_2k_selected");
      const responsePromise = page.waitForResponse(
        (response) => response.request().method() === "POST" && response.url().includes("/api/magi/projects/") && response.url().includes("/upscale/apply"),
        { timeout: 30_000 },
      );
      await page.getByTestId("magi-upscale-apply").click();
      const response = await responsePromise;
      const body = await response.json().catch(() => ({}));
      if (response.status() >= 400) throw new Error(`MAGI upscale HTTP ${response.status()} ${JSON.stringify(body).slice(0, 300)}`);
      magiJobId = String(body.job_id || body.jobId || body.id || "");
      await page.locator("#magi-acc-btn-export").click();
      const deadline = Date.now() + 30 * 60 * 1000;
      while (Date.now() < deadline) {
        const status = finishingStatus.toLowerCase();
        if (/fail|cancel|timed_out/.test(status)) throw new Error(`MAGI job ${status}`);
        if (/done|complete/.test(status)) break;
        await page.waitForTimeout(3000);
      }
      if (!/done|complete/.test(finishingStatus.toLowerCase())) {
        throw new Error(`MAGI job did not finish (${finishingStatus || "no status"})`);
      }
      await shot("14_magi_2k_complete");
      return magiJobId || "upscale finished";
    });

    await record("persistence", async () => {
      await page.reload();
      await page.goto(`/project/${projectId}?workspace=storyboard`);
      await expect(page.getByTestId("storyboard-studio")).toBeVisible({ timeout: 30_000 });
      await expect(page.getByTestId("sb-grid")).toHaveAttribute("data-aspect", "16:9");
      for (let index = 0; index < 3; index += 1) {
        await expect(page.getByTestId(`sb-slot-${index}`).locator("img")).toHaveAttribute("src", new RegExp(imageAssets[index]), { timeout: 20_000 });
      }
      const library = await page.request.get(`/api/projects/${projectId}/library?scope=project&ids=${imageAssets.join(",")}&limit=10`);
      const libraryJson = await library.json() as { items?: Array<{ id?: string }> };
      const found = new Set((libraryJson.items || []).map((item) => String(item.id || "")));
      for (const assetId of imageAssets) {
        if (!found.has(assetId)) throw new Error(`Library no longer contains image ${assetId}`);
      }
      await page.goto(`/project/${projectId}?workspace=timeline`);
      await expect(page.getByTestId("film-timeline")).toBeVisible({ timeout: 30_000 });
      await showPromptWorkspace();
      const chips = page.locator(".film-reference-chip.is-environment");
      await expect(chips).toHaveCount(3, { timeout: 20_000 });
      await expect(page.getByTestId("film-timeline-monitor").locator("video")).toBeVisible({ timeout: 30_000 });
      await page.goto(`/project/${projectId}?workspace=magi`);
      await expect(page.getByTestId("magi-viewer").locator("video").first()).toBeVisible({ timeout: 30_000 });
      await shot("15_final_after_reload");
      return "images, storyboard frames, environment reference, timeline video, publish, and MAGI remained";
    });
  } finally {
    const summary = {
      projectName,
      projectId,
      projectUrl,
      imageModel,
      prompts: PROMPTS,
      imageJobs,
      imageAssets,
      storyboardId,
      sceneId,
      timelinePrompt: TIMELINE_PROMPT,
      legalDims,
      renderJobId,
      publishedAssetId,
      magiJobId,
      magiOutputId,
      steps,
      network: network.filter((row) => row.path.startsWith("/api/")).slice(0, 200),
      consoleErrors: consoleErrors.slice(0, 40),
      failedRequests: failedRequests.slice(0, 40),
    };
    fs.writeFileSync(path.join(evidenceDir, "summary.json"), JSON.stringify(summary, null, 2));
    await testInfo.attach("production-flow-summary", {
      body: JSON.stringify(summary, null, 2),
      contentType: "application/json",
    });
  }

  const failed = steps.filter((step) => step.status !== "PASS");
  expect(failed, JSON.stringify(failed, null, 2)).toEqual([]);
});

function ownerFor(url: string): string {
  if (url.includes("/image-product/") || url.includes("/image-studio/")) return "image-generator";
  if (url.includes("/storyboard-studio/")) return "storyboard";
  if (url.includes("/film-timeline/")) return "timeline";
  if (url.includes("/magi/")) return "magi";
  return "product";
}

function noteResponse(response: Response, network: NetRow[], failed: string[]) {
  const url = response.url();
  if (!/127\.0\.0\.1:(5173|8758)/.test(url)) return;
  const status = response.status();
  const pathName = new URL(url).pathname;
  if (!pathName.startsWith("/api/")) return;
  const interesting = /image-product|image-studio|storyboard-studio|film-timeline|\/api\/magi\//.test(pathName);
  if (status >= 400 && /\/api\//.test(url) && !/favicon|\.map(\?|$)/.test(url)) {
    if (!/\/bible$/.test(url)) failed.push(`${status} ${url.slice(0, 220)}`);
  }
  if (!interesting) return;
  const existing = network.find((row) => row.method === response.request().method() && row.path === pathName && row.status === 0);
  if (existing) existing.status = status;
  else network.push({ method: response.request().method(), path: pathName, status, owner: ownerFor(url), jobId: "" });
}

function noteRequest(request: Request, network: NetRow[]) {
  const url = request.url();
  const pathName = new URL(url).pathname;
  if (!pathName.startsWith("/api/")) return;
  if (!/image-product|storyboard-studio|film-timeline|\/api\/magi\//.test(pathName)) return;
  if (!["POST", "PUT", "PATCH"].includes(request.method())) return;
  let jobId = "";
  try {
    const body = request.postDataJSON() as Record<string, unknown> | null;
    jobId = String(body?.jobId || body?.job_id || "");
  } catch {
    jobId = "";
  }
  network.push({ method: request.method(), path: new URL(url).pathname, status: 0, owner: ownerFor(url), jobId });
}
