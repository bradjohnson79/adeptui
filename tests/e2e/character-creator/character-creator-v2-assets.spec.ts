import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { TINY_PNG } from "../codirector/helpers/audit";
import { assertNotOwnerWriteTarget, studioApiBase } from "../setup/ownerProjectGuard";

const CERT_PROJECT_ID = "2bc632b8-b329-4d3b-bc40-b68dc41b6bb1";

function certProjectId(): string {
  return process.env.ADEPT_CERT_PROJECT_ID || process.env.ADEPT_PROJECT_ID || CERT_PROJECT_ID;
}

async function ensureMiraVale(request: APIRequestContext): Promise<{ projectId: string; characterId: string }> {
  const api = studioApiBase();
  const projectId = certProjectId();
  assertNotOwnerWriteTarget(projectId);
  const listed = await request.get(`${api}/api/projects/${projectId}/characters`);
  expect(listed.ok(), await listed.text()).toBeTruthy();
  const body = (await listed.json()) as { items?: { id: string; name: string }[] };
  const found = (body.items || []).find((row) => row.name === "Mira Vale");
  if (found) {
    assertNotOwnerWriteTarget(projectId, found.id);
    return { projectId, characterId: found.id };
  }
  const created = await request.post(`${api}/api/projects/${projectId}/characters`, {
    data: {
      name: "Mira Vale",
      description: "Certification character for Character Creator V2. Not Schnick or Korri.",
      gender_presentation: "woman",
      visual_style: "cinematic",
    },
  });
  expect(created.ok(), await created.text()).toBeTruthy();
  const row = (await created.json()) as { id?: string };
  const characterId = String(row.id || "");
  assertNotOwnerWriteTarget(projectId, characterId);
  return { projectId, characterId };
}

async function ensureReference(
  request: APIRequestContext,
  projectId: string,
  characterId: string,
): Promise<string> {
  const api = studioApiBase();
  const state = await request.get(`${api}/api/projects/${projectId}/characters/${characterId}/cc-v2`);
  const body = (await state.json()) as { hasReference?: boolean; referenceAssetId?: string };
  if (body.referenceAssetId) return String(body.referenceAssetId);
  const uploaded = await request.post(`${api}/api/projects/${projectId}/assets`, {
    multipart: {
      file: { name: "mira-ref.png", mimeType: "image/png", buffer: TINY_PNG },
      tag: "character_reference",
      kind: "image",
    },
  });
  expect(uploaded.ok(), await uploaded.text()).toBeTruthy();
  const asset = (await uploaded.json()) as { id?: string };
  const assetId = String(asset.id || "");
  const attached = await request.post(`${api}/api/projects/${projectId}/characters/${characterId}/references`, {
    data: { asset_id: assetId, reference_role: "reference_image", source_type: "upload" },
  });
  expect(attached.ok(), await attached.text()).toBeTruthy();
  return assetId;
}

async function assertImageLoads(page: Page, testId: string, assetUrl: string) {
  const img = page.getByTestId(testId);
  await expect(img).toBeVisible({ timeout: 20_000 });
  const dims = await img.evaluate((el) => {
    const node = el as HTMLImageElement;
    return { w: node.naturalWidth, h: node.naturalHeight, src: node.currentSrc || node.src };
  });
  expect(dims.w, `broken image ${testId}`).toBeGreaterThan(0);
  expect(dims.h, `broken image ${testId}`).toBeGreaterThan(0);
  expect(dims.src).toContain("/api/assets/");
  expect(dims.src).not.toContain("/api/projects/");
  const media = await page.request.get(assetUrl.startsWith("http") ? assetUrl : new URL(assetUrl, page.url()).toString());
  expect(media.status(), await media.text()).toBe(200);
  const type = media.headers()["content-type"] || "";
  expect(type.startsWith("image/")).toBeTruthy();
  expect((await media.body()).byteLength).toBeGreaterThan(0);
}

test.describe("Character Creator V2 assets + generator + progress", () => {
  test("FRONT_READY image uses the canonical media route and renders", async ({ page, request }) => {
    test.setTimeout(120_000);
    const { projectId, characterId } = await ensureMiraVale(request);
    const api = studioApiBase();
    const stateRes = await request.get(`${api}/api/projects/${projectId}/characters/${characterId}/cc-v2`);
    expect(stateRes.ok(), await stateRes.text()).toBeTruthy();
    const state = (await stateRes.json()) as {
      phase?: string;
      views?: { front?: { assetUrl?: string; status?: string }; back?: { assetUrl?: string } };
    };
    await page.goto(`/project/${projectId}?workspace=characters&characterId=${characterId}`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page.getByTestId("cc-v2-studio")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("cc-v2-generator-select")).toBeVisible();
    const frontUrl = state.views?.front?.assetUrl || "";
    if (state.phase === "FRONT_READY" || frontUrl) {
      expect(frontUrl).toMatch(/^\/api\/assets\/[^/]+\/file$/);
      await assertImageLoads(page, "cc-v2-img-front", frontUrl);
    }
    await expect(page.getByTestId("cc-v2-generate-back")).toHaveCount(0);
    await expect(page.getByTestId("cc-v2-generate-multiview")).toBeVisible();
  });

  test("generator inventory is truthful and generate posts the selected id", async ({ page, request }) => {
    test.setTimeout(90_000);
    const { projectId, characterId } = await ensureMiraVale(request);
    const api = studioApiBase();
    const invRes = await request.get(`${api}/api/projects/${projectId}/characters/${characterId}/cc-v2/generators`);
    expect(invRes.ok(), await invRes.text()).toBeTruthy();
    const inv = (await invRes.json()) as {
      auto?: { id?: string };
      generators?: { id: string; origin: string; operations?: { back?: { available?: boolean } } }[];
    };
    expect(inv.auto?.id).toBe("auto");
    const ids = (inv.generators || []).map((row) => row.id);
    expect(ids.length).toBeGreaterThan(0);
    const qwen = (inv.generators || []).find((row) => row.id === "qwen2512") as
      | { operations?: { front?: { workflowKey?: string }; back?: { workflowKey?: string; available?: boolean } } }
      | undefined;
    if (qwen?.operations?.front?.workflowKey) {
      expect(qwen.operations.front.workflowKey).toBe("qwen2512.ref");
      expect(qwen.operations.front.workflowKey).not.toContain("txt2img");
    }
    if (qwen?.operations?.back?.available) {
      expect(qwen.operations.back.workflowKey).toBe("qwen2512.ref");
    }

    await ensureReference(request, projectId, characterId);
    await page.goto(`/project/${projectId}?workspace=characters&characterId=${characterId}`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page.getByTestId("cc-v2-studio")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("character-auto-prompt")).toBeVisible();
    const select = page.getByTestId("cc-v2-generator-select");
    await expect(select).toBeVisible();
    const flux = (inv.generators || []).find((row) => row.id === "flux");
    if (flux) {
      await select.selectOption("flux");
    }
    let postedBody: { generatorId?: string } | null = null;
    await page.route("**/views/front/generate", async (route) => {
      postedBody = route.request().postDataJSON() as { generatorId?: string };
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ phase: "DRAFT", selectedGenerator: flux ? "flux" : "auto" }),
      });
    });
    await page.getByTestId("cc-v2-generate-front").click();
    await expect.poll(() => postedBody !== null).toBeTruthy();
    if (flux) expect(postedBody?.generatorId).toBe("flux");
  });

  test("live Generate Front reaches FRONT_READY with a visible image", async ({ page, request }) => {
    test.setTimeout(600_000);
    const { projectId, characterId } = await ensureMiraVale(request);
    const api = studioApiBase();
    await ensureReference(request, projectId, characterId);
    const comfy = await request.get(`${api}/api/comfy/health`);
    if (!comfy.ok()) {
      test.skip(true, "Comfy is not reachable");
    }
    await page.goto(`/project/${projectId}?workspace=characters&characterId=${characterId}`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page.getByTestId("cc-v2-studio")).toBeVisible({ timeout: 20_000 });
    const invRes = await request.get(`${api}/api/projects/${projectId}/characters/${characterId}/cc-v2/generators`);
    const inv = (await invRes.json()) as {
      generators?: { id: string; operations?: { front?: { available?: boolean } } }[];
    };
    const qwenReady = (inv.generators || []).some((row) => row.id === "qwen2512" && row.operations?.front?.available);
    if (qwenReady) {
      await page.getByTestId("cc-v2-generator-select").selectOption("qwen2512");
    }
    const before = await request.get(`${api}/api/projects/${projectId}/characters/${characterId}/cc-v2`);
    const beforeBody = (await before.json()) as {
      phase?: string;
      hasReference?: boolean;
      views?: { front?: { assetUrl?: string; status?: string; provenance?: { workflow_key?: string } } };
    };
    expect(beforeBody.hasReference).toBeTruthy();
    const existingKey = String(beforeBody.views?.front?.provenance?.workflow_key || "");
    const needsI2i = !existingKey || existingKey.includes("txt2img");
    if (!beforeBody.views?.front?.assetUrl || needsI2i) {
      const generate = page.waitForResponse(
        (res) => res.url().includes("/views/front/generate") && res.request().method() === "POST",
        { timeout: 30_000 },
      );
      await page.getByTestId("cc-v2-generate-front").click();
      const genRes = await generate;
      expect(genRes.ok(), await genRes.text()).toBeTruthy();
    }
    await expect
      .poll(
        async () => {
          const res = await request.get(`${api}/api/projects/${projectId}/characters/${characterId}/cc-v2`);
          const body = (await res.json()) as {
            phase?: string;
            views?: { front?: { assetUrl?: string; status?: string; progress?: { percent?: number; stage?: string } } };
          };
          const url = body.views?.front?.assetUrl || "";
          const status = String(body.views?.front?.status || "");
          const ready = Boolean(url) && ["ready", "approved"].includes(status);
          return {
            ready,
            url,
            percent: body.views?.front?.progress?.percent,
            stage: body.views?.front?.progress?.stage,
          };
        },
        { timeout: 480_000 },
      )
      .toMatchObject({ ready: true });
    const ready = await request.get(`${api}/api/projects/${projectId}/characters/${characterId}/cc-v2`);
    const readyBody = (await ready.json()) as {
      views?: {
        front?: {
          assetUrl?: string;
          progress?: { percent?: number };
          provenance?: { workflow_key?: string; source_reference_asset_id?: string };
        };
      };
    };
    const frontUrl = readyBody.views?.front?.assetUrl || "";
    expect(frontUrl).toMatch(/^\/api\/assets\/[^/]+\/file$/);
    expect(readyBody.views?.front?.progress?.percent).toBe(100);
    const workflowKey = String(readyBody.views?.front?.provenance?.workflow_key || "");
    expect(workflowKey).not.toContain("txt2img");
    if (qwenReady) expect(workflowKey).toBe("qwen2512.ref");
    expect(readyBody.views?.front?.provenance?.source_reference_asset_id || "").toBeTruthy();
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("cc-v2-studio")).toBeVisible({ timeout: 20_000 });
    await assertImageLoads(page, "cc-v2-img-front", frontUrl);
  });

  test("progress and provenance survive reload from backend truth", async ({ page, request }) => {
    test.setTimeout(90_000);
    const { projectId, characterId } = await ensureMiraVale(request);
    const api = studioApiBase();
    const first = await request.get(`${api}/api/projects/${projectId}/characters/${characterId}/cc-v2`);
    expect(first.ok(), await first.text()).toBeTruthy();
    const body = (await first.json()) as {
      phase?: string;
      views?: { front?: { assetUrl?: string; progress?: { percent?: number; stage?: string }; provenance?: { label?: string } } };
    };
    const percent = body.views?.front?.progress?.percent;
    const stage = body.views?.front?.progress?.stage;
    if (percent != null) {
      expect(percent).toBeGreaterThanOrEqual(0);
      expect(percent).toBeLessThanOrEqual(100);
    }
    if (body.phase === "FRONT_READY") {
      expect(percent).toBe(100);
      expect(stage).toBe("ready");
      expect(body.views?.front?.provenance?.label || "").toMatch(/Local|API/);
    }
    if (percent === 100) {
      expect(body.views?.front?.assetUrl || "").toMatch(/^\/api\/assets\/[^/]+\/file$/);
    }
    await page.goto(`/project/${projectId}?workspace=characters&characterId=${characterId}`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page.getByTestId("cc-v2-studio")).toBeVisible({ timeout: 20_000 });
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("cc-v2-studio")).toBeVisible({ timeout: 20_000 });
    const second = await request.get(`${api}/api/projects/${projectId}/characters/${characterId}/cc-v2`);
    const again = (await second.json()) as {
      phase?: string;
      views?: { front?: { progress?: { percent?: number; stage?: string } } };
    };
    expect(again.phase).toBe(body.phase);
    expect(again.views?.front?.progress?.percent).toBe(percent);
    if (body.phase === "FRONT_READY") {
      await expect(page.getByTestId("cc-v2-progress-front")).toContainText("100%");
      await expect(page.getByTestId("cc-v2-progress-front")).toContainText("Front Ready");
    }
  });

  test("Auto-Prompt describes the reference and does not write the Front lock", async ({ page, request }) => {
    test.setTimeout(180_000);
    const { projectId, characterId } = await ensureMiraVale(request);
    const api = studioApiBase();
    await ensureReference(request, projectId, characterId);
    const before = await request.get(`${api}/api/projects/${projectId}/characters/${characterId}/cc-v2`);
    const beforeBody = (await before.json()) as { hasReference?: boolean; visualLock?: { status?: string } };
    expect(beforeBody.hasReference).toBeTruthy();
    const lockBefore = String(beforeBody.visualLock?.status || "none");

    await page.goto(`/project/${projectId}?workspace=characters&characterId=${characterId}`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page.getByTestId("cc-v2-studio")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("character-auto-prompt")).toBeVisible();
    const first = page.waitForResponse(
      (res) => res.url().includes("/cc-v2/auto-prompt") && res.request().method() === "POST",
      { timeout: 120_000 },
    );
    await page.getByTestId("character-auto-prompt").click();
    const firstRes = await first;
    if (firstRes.status() === 409) {
      await expect(page.getByTestId("character-auto-prompt-confirm")).toBeVisible();
      const replaceRes = page.waitForResponse(
        (res) => res.url().includes("/cc-v2/auto-prompt") && res.request().method() === "POST",
        { timeout: 120_000 },
      );
      await page.getByTestId("character-auto-prompt-replace").click();
      const res = await replaceRes;
      expect(res.ok(), await res.text()).toBeTruthy();
    } else {
      expect(firstRes.ok(), await firstRes.text()).toBeTruthy();
    }
    const after = await request.get(`${api}/api/projects/${projectId}/characters/${characterId}`);
    expect(after.ok(), await after.text()).toBeTruthy();
    const profile = (await after.json()) as { description?: string };
    expect(String(profile.description || "").trim().length).toBeGreaterThan(8);
    const state = await request.get(`${api}/api/projects/${projectId}/characters/${characterId}/cc-v2`);
    const stateBody = (await state.json()) as { visualLock?: { status?: string } };
    expect(String(stateBody.visualLock?.status || "none")).toBe(lockBefore);
  });

  test("V3 retires generator-invented Back after the visual lock", async ({ page, request }) => {
    test.setTimeout(120_000);
    const { projectId, characterId } = await ensureMiraVale(request);
    const api = studioApiBase();
    const frontState = await request.get(`${api}/api/projects/${projectId}/characters/${characterId}/cc-v2`);
    const frontBody = (await frontState.json()) as {
      views?: {
        front?: {
          assetId?: string;
          assetUrl?: string;
          status?: string;
          approved?: boolean;
          provenance?: { workflow_key?: string; source_reference_asset_id?: string };
        };
      };
      visualLock?: { status?: string };
    };
    const frontUrl = frontBody.views?.front?.assetUrl || "";
    const frontKey = String(frontBody.views?.front?.provenance?.workflow_key || "");
    if (!frontUrl || frontKey.includes("txt2img")) {
      test.skip(true, "Front I2I is not ready yet");
    }
    await page.goto(`/project/${projectId}?workspace=characters&characterId=${characterId}`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page.getByTestId("cc-v2-studio")).toBeVisible({ timeout: 20_000 });
    if (String(frontBody.visualLock?.status || "") !== "ok") {
      const approve = page.waitForResponse(
        (res) => res.url().includes("/views/front/approve") && res.request().method() === "POST",
        { timeout: 120_000 },
      );
      await page.getByTestId("cc-v2-approve-front").click();
      const approveRes = await approve;
      expect(approveRes.ok(), await approveRes.text()).toBeTruthy();
    }
    await expect
      .poll(
        async () => {
          const res = await request.get(`${api}/api/projects/${projectId}/characters/${characterId}/cc-v2`);
          const body = (await res.json()) as { visualLock?: { status?: string; error?: string } };
          return { status: body.visualLock?.status, error: body.visualLock?.error };
        },
        { timeout: 120_000 },
      )
      .toMatchObject({ status: "ok" });
    await expect(page.getByTestId("cc-v2-tag")).toContainText("@Mira Vale");
    await expect(page.getByTestId("cc-v2-generate-back")).toHaveCount(0);
    await expect(page.getByTestId("cc-v2-generate-multiview")).toBeVisible();
    const backRes = await request.post(
      `${api}/api/projects/${projectId}/characters/${characterId}/views/back/generate`,
      { data: {} },
    );
    expect(backRes.status()).toBe(409);
    const backJson = (await backRes.json()) as { detail?: { code?: string }; code?: string };
    expect(backJson.detail?.code || backJson.code).toBe("BACK_RETIRED");
    const mvRes = await request.post(
      `${api}/api/projects/${projectId}/characters/${characterId}/multiview/generate`,
      { data: {} },
    );
    expect(mvRes.status()).toBe(409);
    const mvJson = (await mvRes.json()) as { detail?: { code?: string }; code?: string };
    expect(mvJson.detail?.code || mvJson.code).toBe("WONDER3D_LICENSE_BLOCKED");
  });
});
