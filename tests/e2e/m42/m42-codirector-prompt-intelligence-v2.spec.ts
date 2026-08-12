import { expect, test } from "@playwright/test";

test.describe("Co-Director Prompt Intelligence V2", () => {
  test.beforeAll(async ({ request }) => {
    let lastStatus = 0;
    for (let i = 0; i < 90; i++) {
      try {
        const suites = await request.get("/api/codirector/prompt-intelligence/v2/suites");
        lastStatus = suites.status();
        if (suites.ok()) return;
      } catch {
        /* API still booting */
      }
      await new Promise((r) => setTimeout(r, 500));
    }
    throw new Error(`Prompt Intelligence V2 API not ready (last status ${lastStatus})`);
  });

  test("suites, dry-run, recommend-not-auto, insufficient promote refusal", async ({ request }) => {
    const suites = await request.get("/api/codirector/prompt-intelligence/v2/suites");
    expect(suites.ok()).toBeTruthy();
    const suiteBody = await suites.json();
    expect((suiteBody.suites || []).length).toBeGreaterThanOrEqual(4);

    const plan = await request.post("/api/codirector/prompt-intelligence/v2/plan", {
      data: { suiteId: "image-core", providerId: "comfyui", samplesPerStrategy: 1 },
    });
    expect(plan.ok()).toBeTruthy();
    const planBody = await plan.json();
    expect(planBody.plan.estimatedJobs).toBeGreaterThan(0);

    const run = await request.post("/api/codirector/prompt-intelligence/v2/runs", {
      data: {
        suiteId: "image-core",
        providerId: "comfyui",
        samplesPerStrategy: 1,
        dryRun: true,
      },
    });
    expect(run.ok()).toBeTruthy();
    const runBody = await run.json();
    const suiteRunId = runBody.suiteRun.suiteRunId as string;
    expect(suiteRunId).toBeTruthy();

    let statusBody: Record<string, unknown> = {};
    for (let i = 0; i < 60; i++) {
      const st = await request.get(
        `/api/codirector/prompt-intelligence/v2/runs?suiteRunId=${encodeURIComponent(suiteRunId)}`,
      );
      statusBody = await st.json();
      const suiteRun = statusBody.suiteRun as { status?: string };
      if (suiteRun?.status === "completed" || suiteRun?.status === "failed") break;
      await new Promise((r) => setTimeout(r, 250));
    }
    expect((statusBody.suiteRun as { status?: string }).status).toBe("completed");

    const recommend = await request.post("/api/codirector/prompt-intelligence/v2/recommend", {
      data: {
        domain: "image",
        category: "portrait",
        providerId: "comfyui",
        strategyMode: "recommend",
      },
    });
    expect(recommend.ok()).toBeTruthy();
    const rec = await recommend.json();
    expect(rec.strategyRecommendation.appliedAutomatically).toBeFalsy();

    const auto = await request.post("/api/codirector/prompt-intelligence/v2/recommend", {
      data: {
        domain: "image",
        category: "portrait",
        providerId: "comfyui",
        strategyMode: "automatic_certified",
      },
    });
    const autoBody = await auto.json();
    // Without certified evidence, must not auto-apply
    expect(autoBody.strategyRecommendation.appliedAutomatically).toBeFalsy();

    const evaluate = await request.post("/api/codirector/prompt-intelligence/v2/evaluate", {
      data: {
        providerId: "comfyui",
        domain: "image",
        category: "portrait",
        suiteRunId,
      },
    });
    expect(evaluate.ok()).toBeTruthy();
    const ev = await evaluate.json();
    expect(ev.evidence.status).toBe("insufficient_evidence");

    const promote = await request.post("/api/codirector/prompt-intelligence/v2/promote", {
      data: {
        providerId: "comfyui",
        domain: "image",
        category: "portrait",
        strategy: "bilingual-balanced",
        force: false,
      },
    });
    expect(promote.ok()).toBeFalsy();
    const promoteBody = await promote.json();
    const code = promoteBody.detail?.code || promoteBody.error?.code;
    expect(code).toBe("INSUFFICIENT_EVIDENCE");
  });

  test("blind review path + promote/rollback with force + enhance V2 axes", async ({ request }) => {
    // Seed certified path via force after evaluate
    const promoteForce = await request.post("/api/codirector/prompt-intelligence/v2/promote", {
      data: {
        providerId: "ltx-local",
        domain: "video",
        category: "camera_movement",
        strategy: "refined-english",
        force: true,
      },
    });
    // May succeed even without runs when force=true
    if (promoteForce.ok()) {
      const body = await promoteForce.json();
      expect(body.ok).toBeTruthy();
      const rollback = await request.post("/api/codirector/prompt-intelligence/v2/rollback", {
        data: {
          providerId: "ltx-local",
          domain: "video",
          category: "camera_movement",
        },
      });
      expect(rollback.ok()).toBeTruthy();
    }

    const enhance = await request.post("/api/codirector/prompt-intelligence/enhance", {
      data: {
        creatorPrompt: "Wide shot of a mountain cliff path, slow push-in",
        domain: "video",
        providerId: "ltx-local",
        strategyMode: "recommend",
      },
    });
    expect(enhance.ok()).toBeTruthy();
    const e = await enhance.json();
    expect(e.strategyRecommendation).toBeTruthy();
    expect(e.analyzerV2).toBeTruthy();
    expect(e.analyzerV2.promptQuality).toBeGreaterThan(0);
    expect(e.analyzerV2.providerCompatibility).toBeGreaterThan(0);
    expect(e.record.creatorPrompt).toContain("mountain");

    // Blind reviews list (strategyMap hidden when not submitted)
    const reviews = await request.get("/api/codirector/prompt-intelligence/v2/reviews");
    expect(reviews.ok()).toBeTruthy();
    const rb = await reviews.json();
    for (const r of rb.reviews || []) {
      if (!r.submitted) {
        expect(Object.keys(r.strategyMap || {}).length).toBe(0);
      }
    }
  });

  test("Setup dashboard mounts Prompt Intelligence V2 panel", async ({ page, request }) => {
    const projectsRes = await request.get("/api/projects");
    expect(projectsRes.ok()).toBeTruthy();
    let projects = (await projectsRes.json()) as Array<{ id?: string; archived?: number }>;
    let project = (projects || []).find((p) => p?.id && !p.archived) || (projects || [])[0];
    if (!project?.id) {
      const created = await request.post("/api/projects", {
        data: { name: "PI V2 E2E Project", description: "Prompt Intelligence V2 dashboard smoke" },
      });
      expect(created.ok()).toBeTruthy();
      project = await created.json();
    }
    await page.goto(`/project/${project!.id}?workspace=setup`);
    const dash = page.getByTestId("prompt-intelligence-benchmark-dashboard");
    await expect(dash).toBeVisible({ timeout: 30000 });
    await expect(page.getByTestId("pi-bench-start")).toBeVisible();
  });
});
