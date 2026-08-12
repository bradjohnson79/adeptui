import { expect, test } from "@playwright/test";

/**
 * Dual HunyuanVideo Model Library — SA library surface + API contracts.
 * Does not force multi-GB downloads in CI; proves independent endpoints and LTX default.
 */

test.describe("M42 Dual Hunyuan Video Library", () => {
  test("library matrix keeps LTX default and lists both Hunyuan + WAN + MiniMax", async ({ request }) => {
    const res = await request.get("/api/video-runtime/hunyuan/library");
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.mock).toBe(false);
    expect(body.defaultProviderId).toBe("ltx-local");
    const ids = (body.providers || []).map((p: { providerId: string }) => p.providerId);
    expect(ids).toContain("ltx-local");
    expect(ids).toContain("hunyuan-video-1.5-local");
    expect(ids).toContain("hunyuan-video-13b-local");
    expect(ids).toContain("wan-local");
    expect(ids).toContain("minimax-h3");
    const minimax = (body.providers || []).find((p: { providerId: string }) => p.providerId === "minimax-h3");
    expect(minimax.status).toMatch(/Coming Soon/i);
  });

  test("engines list includes hunyuan15 and hunyuan13b without removing wan/ltx", async ({ request }) => {
    const res = await request.get("/api/engines");
    expect(res.ok()).toBeTruthy();
    const engines = await res.json();
    const ids = engines.map((e: { id: string }) => e.id);
    expect(ids).toContain("ltx");
    expect(ids).toContain("wan");
    expect(ids).toContain("hunyuan15");
    expect(ids).toContain("hunyuan13b");
  });

  test("install endpoints are independent (preflight per provider)", async ({ request }) => {
    for (const id of ["hunyuan-video-1.5-local", "hunyuan-video-13b-local"]) {
      const pre = await request.get(`/api/video-runtime/hunyuan/providers/${id}/preflight`);
      expect(pre.ok()).toBeTruthy();
      const body = await pre.json();
      expect(body.providerId).toBe(id);
      expect(body.recommendedProfile).toBeTruthy();
      expect(body).toHaveProperty("compatible");
    }
  });

  test("Setup Video Model Library UI shows dual Hunyuan controls", async ({ page }) => {
    const projectsRes = await page.request.get("/api/projects");
    if (!projectsRes.ok()) {
      test.skip(true, "API projects unavailable");
      return;
    }
    const projects = (await projectsRes.json()) as Array<{ id?: string }>;
    const project = projects.find((p) => p?.id);
    if (!project?.id) {
      test.skip(true, "No project");
      return;
    }
    await page.goto(`/project/${project.id}?workspace=setup`);
    await expect(page.getByTestId("video-model-library")).toBeVisible({ timeout: 20000 });
    await expect(page.getByTestId("video-model-hunyuan-video-1.5-local")).toBeVisible();
    await expect(page.getByTestId("video-model-hunyuan-video-13b-local")).toBeVisible();
    await expect(page.getByTestId("video-model-ltx-local")).toBeVisible();
    await expect(page.getByTestId("video-model-wan-local")).toBeVisible();
    await expect(page.getByTestId("video-model-install-hunyuan-video-1.5-local")).toBeVisible();
    await expect(page.getByTestId("video-model-install-hunyuan-video-13b-local")).toBeVisible();
  });

  test("Setup Hunyuan action buttons call APIs (Install/Verify/Repair/Benchmark/Remove)", async ({ page }) => {
    const projectsRes = await page.request.get("/api/projects");
    if (!projectsRes.ok()) {
      test.skip(true, "API projects unavailable");
      return;
    }
    const projects = (await projectsRes.json()) as Array<{ id?: string }>;
    const project = projects.find((p) => p?.id);
    if (!project?.id) {
      test.skip(true, "No project");
      return;
    }

    const providerId = "hunyuan-video-1.5-local";
    const calls: string[] = [];

    await page.route(`**/api/video-runtime/hunyuan/providers/${providerId}/**`, async (route) => {
      const req = route.request();
      const url = req.url();
      const method = req.method();
      if (method === "POST" && url.endsWith("/install")) {
        calls.push("install");
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            ok: true,
            message: "Install queued — track progress in Source Manager Active Downloads.",
            operationId: "dl_test_playwright",
            providerId,
          }),
        });
        return;
      }
      if (method === "POST" && url.endsWith("/repair")) {
        calls.push("repair");
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ ok: true, message: "Repair finished." }),
        });
        return;
      }
      if (method === "POST" && url.endsWith("/benchmark")) {
        calls.push("benchmark");
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ ok: true }),
        });
        return;
      }
      if (method === "POST" && url.endsWith("/remove")) {
        calls.push("remove");
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ ok: true, message: "Removed." }),
        });
        return;
      }
      if (method === "GET" && url.endsWith("/health")) {
        calls.push("health");
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            ok: false,
            verify: { message: "Missing or incomplete: weights" },
          }),
        });
        return;
      }
      if (method === "GET" && url.endsWith("/benchmark")) {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: false }) });
        return;
      }
      await route.continue();
    });

    await page.goto(`/project/${project.id}?workspace=setup`);
    await expect(page.getByTestId("video-model-library")).toBeVisible({ timeout: 20000 });

    await page.getByTestId(`video-model-install-${providerId}`).click();
    await expect(page.getByTestId("video-model-library-message")).toContainText(/Install queued|already/i, {
      timeout: 10000,
    });

    await page.getByTestId(`video-model-verify-${providerId}`).click();
    await expect(page.getByTestId("video-model-library-message")).toBeVisible();

    await page.getByTestId(`video-model-repair-${providerId}`).click();
    await expect(page.getByTestId("video-model-library-message")).toContainText(/Repair|queue|Install|Missing|healthy|failed/i);

    await page.getByTestId(`video-model-benchmark-${providerId}`).click();
    await expect(page.getByTestId("video-model-library-message")).toContainText(/Benchmark/i);

    await page.getByTestId(`video-model-remove-${providerId}`).click();
    await expect(page.getByTestId("video-model-library-message")).toContainText(/Removed|Remove/i);

    expect(calls).toEqual(expect.arrayContaining(["install", "health", "repair", "benchmark", "remove"]));
  });

  test("library status is honest when not installed (not silently Ready)", async ({ request }) => {
    const res = await request.get("/api/video-runtime/hunyuan/library");
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    for (const id of ["hunyuan-video-1.5-local", "hunyuan-video-13b-local"]) {
      const row = (body.providers || []).find((p: { providerId: string }) => p.providerId === id);
      expect(row).toBeTruthy();
      // Must not claim Installed/Ready without weights
      if (!row.installed) {
        expect(String(row.status)).not.toMatch(/^Installed/i);
        expect(row.executable).toBeFalsy();
      }
    }
  });
});
