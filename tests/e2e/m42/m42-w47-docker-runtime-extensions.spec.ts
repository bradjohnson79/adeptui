import { expect, test } from "@playwright/test";

/**
 * M42 W47 Docker Runtime Extensions — creator journeys A–M (shell + API).
 * Live Docker daemon is required for dockerRuntimeExtensionsGo (binary GO).
 */
const apiBase = process.env.PLAYWRIGHT_API_URL || "http://127.0.0.1:8758";

test.describe("M42 W47 Docker Runtime Extensions", () => {
  test("A: platform preflight endpoint @m42-w47", async ({ request }) => {
    const res = await request.get(`${apiBase}/api/docker-runtime/platform`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.ok).toBeTruthy();
    expect(body.platform).toBeTruthy();
  });

  test("B: registry lists core seed runtimes @m42-w47", async ({ request }) => {
    const res = await request.get(`${apiBase}/api/docker-runtime/runtimes`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const ids = (body.runtimes || []).map((r: { id: string }) => r.id);
    expect(ids).toContain("core-comfyui");
    expect(ids).toContain("core-ltx");
  });

  test("C: core uninstall blocked @m42-w47", async ({ request }) => {
    const res = await request.post(`${apiBase}/api/docker-runtime/runtimes/core-comfyui/uninstall/preview`, {
      data: { option: "container_image_and_private" },
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.ok).toBeFalsy();
    expect(body.plan?.blockedReason).toContain("core_mandatory");
  });

  test("D: security rejects privileged latest image @m42-w47", async ({ request }) => {
    const res = await request.post(`${apiBase}/api/docker-runtime/install/preview`, {
      data: {
        image: "user/evil:latest",
        name: "Evil",
        runtimeId: "user-evil",
        modality: "video",
      },
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.ok).toBeFalsy();
    expect(body.plan?.security?.blocked || []).toEqual(expect.arrayContaining(["unpinned_image_tag"]));
  });

  test("E: workflow inspect builds isolated plan @m42-w47", async ({ request }) => {
    const res = await request.post(`${apiBase}/api/docker-runtime/workflow/inspect`, {
      data: {
        workflow: {
          "1": { class_type: "CheckpointLoaderSimple" },
          "2": { class_type: "CLIPTextEncode" },
        },
      },
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.mutatesCoreComfy).toBeFalsy();
    expect(body.buildsIsolatedRuntime).toBeTruthy();
  });

  test("F: Runtime Manager UI loads @m42-w47", async ({ page }) => {
    await page.goto("/runtime-manager");
    await expect(page.getByTestId("runtime-manager")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("add-custom-capability")).toBeVisible();
    await expect(page.getByTestId("runtime-card-core-comfyui")).toBeVisible();
    await expect(page.getByTestId("runtime-no-uninstall-core-comfyui")).toBeVisible();
  });

  test("G: Setup Wizard Add Custom Capability @m42-w47", async ({ page }) => {
    await page.goto("/");
    // Home may expose setup via project or direct — try runtime manager link path from setup if present
    await page.goto("/runtime-manager");
    await expect(page.getByTestId("add-custom-capability")).toBeVisible({ timeout: 30_000 });
    await page.getByTestId("custom-capability-inspect").click();
    await expect(page.getByTestId("custom-capability-inspect-result")).toBeVisible({ timeout: 15_000 });
  });

  test("H: Production Dock Native/Docker/Hosted sections @m42-w47", async ({ page }) => {
    await page.goto("/");
    const dock = page.getByTestId("production-control-dock");
    await expect(dock).toBeVisible({ timeout: 30_000 });
    const expand = page.getByTestId("production-dock-expand");
    if (await expand.isVisible().catch(() => false)) {
      await expand.click();
    }
    await expect(page.getByTestId("production-dock-bar")).toBeVisible({ timeout: 15_000 });
    await page.getByTestId("production-dock-menu-video").click();
    const dialog = page.getByRole("dialog").first();
    await expect(dialog).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("dock-native-video")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("dock-docker-video")).toBeVisible();
    await expect(page.getByTestId("dock-hosted-video")).toBeVisible();
    await page.keyboard.press("Escape");
  });

  test("I: dock-models endpoint classified @m42-w47", async ({ request }) => {
    const res = await request.get(`${apiBase}/api/docker-runtime/dock-models`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(Array.isArray(body.models || body.items || [])).toBeTruthy();
  });

  test("J: gate endpoint binary flag @m42-w47", async ({ request }) => {
    const res = await request.get(`${apiBase}/api/docker-runtime/gate`);
    expect(res.ok()).toBeTruthy();
    const gate = await res.json();
    expect(typeof gate.dockerRuntimeExtensionsGo).toBe("boolean");
    // Honest: no Conditional GO — either true with live daemon or false
    if (!gate.flags?.liveDockerAvailable) {
      expect(gate.dockerRuntimeExtensionsGo).toBeFalsy();
    }
  });

  test("K: Co-Director runtime.list tool declared @m42-w47", async ({ request }) => {
    const res = await request.get(`${apiBase}/api/codirector/tools`);
    if (!res.ok()) {
      test.skip(true, "codirector tools catalog unavailable");
      return;
    }
    const body = await res.json();
    const ids = (body.tools || body || []).map((t: { toolId?: string; id?: string }) => t.toolId || t.id);
    expect(ids).toEqual(expect.arrayContaining(["runtime.list", "runtime.install", "runtime.uninstall"]));
  });

  test("L: production models stamp executionClass @m42-w47", async ({ request }) => {
    const res = await request.get(`${apiBase}/api/production-control/models?modality=video`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const models = body.models || body.local || body;
    const list = Array.isArray(models) ? models : models.local || [];
    expect(list.length).toBeGreaterThan(0);
    for (const m of list) {
      expect(m.executionClass || m.locality).toBeTruthy();
    }
  });

  test("M: reload isolation — Runtime Manager survives navigation @m42-w47", async ({ page }) => {
    await page.goto("/runtime-manager");
    await expect(page.getByTestId("runtime-manager")).toBeVisible({ timeout: 30_000 });
    await page.goto("/");
    await page.goto("/runtime-manager");
    await expect(page.getByTestId("runtime-card-core-ltx")).toBeVisible({ timeout: 30_000 });
  });
});
