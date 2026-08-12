import { expect, test, type Page } from "@playwright/test";

async function openTimeline(page: Page): Promise<string | null> {
  const projectsRes = await page.request.get("/api/projects");
  if (!projectsRes.ok()) return null;
  const projects = (await projectsRes.json()) as Array<{ id?: string; archived?: number }>;
  const project = (projects || []).find((p) => p?.id && !p.archived) || (projects || [])[0];
  if (!project?.id) return null;
  await page.goto(`/project/${project.id}?workspace=timeline`);
  const shell = page.getByTestId("timeline-editor-shell");
  if (!(await shell.isVisible().catch(() => false))) {
    const timelineNav = page.getByRole("button", { name: /^Timeline$/i }).first();
    if ((await timelineNav.count()) > 0) await timelineNav.click();
  }
  await expect(shell).toBeVisible({ timeout: 20000 });
  return project.id;
}

test.describe("Co-Director Prompt Intelligence", () => {
  test("API enhance + analyze expose four layers and scores", async ({ request }) => {
    const enhance = await request.post("/api/codirector/prompt-intelligence/enhance", {
      data: {
        creatorPrompt: "Korri stands on a cliff at sunset, wide shot, soft light",
        domain: "video",
        engineId: "hunyuan15",
        modulesEnabled: {
          productionRefinement: true,
          cinematicRefinement: true,
          motionRefinement: true,
          audioRefinement: false,
          characterContinuity: true,
          providerOptimization: true,
          languageModules: ["en", "zh"],
        },
        languageBalance: "balanced",
        characterNames: ["Korri"],
      },
    });
    expect(enhance.ok()).toBeTruthy();
    const body = await enhance.json();
    expect(body.record.creatorPrompt).toContain("Korri");
    expect(body.record.refinedEnglishPrompt).toBeTruthy();
    expect(body.record.chineseEnhancement || body.record.languageEnhancements?.zh).toBeTruthy();
    expect(body.record.finalProviderPrompt).toBeTruthy();
    expect(body.record.creatorPrompt).toBe("Korri stands on a cliff at sunset, wide shot, soft light");

    const analyze = await request.post("/api/codirector/prompt-intelligence/analyze", {
      data: {
        creatorPrompt: "wide shot of a hero walking through rain, cinematic lighting",
        domain: "video",
        engineId: "wan",
      },
    });
    expect(analyze.ok()).toBeTruthy();
    const a = await analyze.json();
    expect(a.qualityReport.overall).toBeGreaterThan(40);
  });

  test("Timeline Prompt Intelligence preview, apply, override, persist", async ({ page }) => {
    const projectId = await openTimeline(page);
    if (!projectId) {
      test.skip(true, "No project/Timeline available");
      return;
    }

    const panel = page.getByTestId("prompt-intelligence-panel").first();
    await expect(panel).toBeVisible({ timeout: 20000 });
    const toggle = page.getByTestId("prompt-intelligence-toggle").first();
    if (!(await page.getByTestId("prompt-intelligence-chinese").first().isVisible().catch(() => false))) {
      await toggle.click();
    }

    const original = await page.getByTestId("timeline-scene-prompt").inputValue();
    const seed = original?.trim()
      ? original
      : "Korri stands on a cliff at sunset, wide shot, soft cinematic light";
    if (!original?.trim()) {
      await page.getByTestId("timeline-scene-prompt").fill(seed);
    }

    await page.getByTestId("prompt-intelligence-chinese").first().check();
    await page.getByTestId("prompt-intelligence-balance-balanced").first().click();
    await page.getByTestId("prompt-intelligence-preview").first().click();

    await expect(page.getByTestId("prompt-intelligence-preview-sections").first()).toBeVisible({ timeout: 20000 });
    await expect(page.getByTestId("prompt-intelligence-original").first()).toHaveValue(seed);
    await expect(page.getByTestId("prompt-intelligence-refined").first()).not.toHaveValue("");
    await expect(page.getByTestId("prompt-intelligence-final").first()).not.toHaveValue("");
    await expect(page.getByTestId("prompt-intelligence-scores").first()).toBeVisible();

    const finalBefore = await page.getByTestId("prompt-intelligence-final").first().inputValue();
    await page.getByTestId("prompt-intelligence-final").first().fill(`${finalBefore}\nMANUAL_OVERRIDE_MARK`);
    await expect(page.getByTestId("prompt-intelligence-override-banner").first()).toBeVisible();

    await page.getByTestId("prompt-intelligence-preview").first().click();
    await expect(page.getByTestId("prompt-intelligence-final").first()).toHaveValue(/MANUAL_OVERRIDE_MARK/);

    await page.getByTestId("prompt-intelligence-reset").first().click();
    await expect(page.getByTestId("prompt-intelligence-final").first()).not.toHaveValue(/MANUAL_OVERRIDE_MARK/, {
      timeout: 20000,
    });

    const applied = await page.getByTestId("prompt-intelligence-final").first().inputValue();
    await page.getByTestId("prompt-intelligence-apply").first().click();
    await expect
      .poll(async () => page.getByTestId("timeline-scene-prompt").inputValue())
      .toContain(applied.slice(0, 40));

    await page.reload();
    await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 20000 });
    await expect(page.getByTestId("timeline-scene-prompt")).toHaveValue(new RegExp(applied.slice(0, 24).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  });

  test("profiles endpoint lists language modules and providers", async ({ request }) => {
    const res = await request.get("/api/codirector/prompt-intelligence/profiles?engineId=hunyuan15&domain=video");
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.resolved.profileId).toBe("hunyuan-video-1.5");
    expect(body.languageModules.some((m: { languageId: string }) => m.languageId === "ja")).toBeTruthy();
    expect(Array.isArray(body.profiles)).toBeTruthy();
    expect(body.profiles.length).toBeGreaterThan(3);
  });
});
