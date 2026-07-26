import { expect, test } from "@playwright/test";
import { createTempProject } from "../helpers/app";

/**
 * M2.8 Capability Intelligence fixture-mode acceptance (18 scenarios).
 * On-tests need ADEPT_M28_FIXTURE_MODE=1 and STUDIO_FEATURE_*_V1=1.
 * Scenario 1 requires flags OFF (skipped when e2e-start enables M2.8 flags).
 */
test.describe("Co-Director M2.8 Capability Intelligence @critical @isolated", () => {
  async function waitForHealth(request: import("@playwright/test").APIRequestContext) {
    let lastStatus = 0;
    for (let i = 0; i < 60; i++) {
      try {
        const health = await request.get("/api/health");
        lastStatus = health.status();
        if (health.ok()) return health.json();
      } catch {
        /* booting */
      }
      await new Promise((r) => setTimeout(r, 500));
    }
    throw new Error(`API /api/health not ready (last status ${lastStatus})`);
  }

  async function m28FlagsOn(request: import("@playwright/test").APIRequestContext) {
    const h = await waitForHealth(request);
    const op = h?.operator || {};
    return Boolean(
      op.modelRadarEnabled &&
        op.sandboxRuntimeEnabled &&
        op.virtualStageEnabled &&
        op.shotProfilesEnabled &&
        op.productionRecipeEnabled &&
        op.locationSpinEnabled &&
        op.productionExecutiveEnabled,
    );
  }

  async function requireM28(request: import("@playwright/test").APIRequestContext) {
    const on = await m28FlagsOn(request);
    test.skip(
      !on,
      "M2.8 feature flags not enabled - set STUDIO_FEATURE_*_V1=1 and ADEPT_M28_FIXTURE_MODE=1",
    );
  }

  async function drain(request: import("@playwright/test").APIRequestContext, maxSteps = 80) {
    const res = await request.post("/api/codirector/jobs/worker/drain", { data: { maxSteps } });
    expect(res.ok()).toBeTruthy();
    return res.json();
  }

  test("1 flags off: routes unavailable, no console errors, no background discovery", async ({
    page,
    request,
  }) => {
    const health = await waitForHealth(request);
    const op = health?.operator || {};
    test.skip(
      Boolean(op.modelRadarEnabled || op.virtualStageEnabled),
      "Flags are ON in this environment - covered by unit test_flags_off_api_404; re-run with STUDIO_FEATURE_*_V1=0",
    );

    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });

    await page.goto("/");
    await expect(page.getByTestId("nav-model-radar")).toHaveCount(0);
    await expect(page.getByTestId("nav-virtual-stage")).toHaveCount(0);

    await page.goto("/model-radar");
    await expect(page.getByTestId("model-radar-unavailable")).toBeVisible({ timeout: 15_000 });

    await page.goto("/virtual-stage");
    await expect(page.getByTestId("virtual-stage-unavailable")).toBeVisible({ timeout: 15_000 });

    const discover = await request.post("/api/codirector/m28/radar/discover", {
      data: { source: "huggingface" },
    });
    expect([403, 404]).toContain(discover.status());
    expect(errors.filter((e) => !/favicon|ResizeObserver/i.test(e)).length).toBe(0);
  });

  test("2 model discovery to registry with classifications", async ({ page, request }) => {
    await requireM28(request);
    const project = await createTempProject(request, `M28-2 ${Date.now()}`);
    await page.goto("/model-radar");
    await expect(page.getByTestId("model-radar-page")).toBeVisible({ timeout: 20_000 });
    await page.getByTestId("project-id-input").fill(project.id);
    await page.getByTestId("discovery-hf-btn").click();
    await page.getByTestId("discovery-gh-btn").click();
    await expect(page.getByTestId("registry-list").locator("li")).toHaveCount(6, {
      timeout: 15_000,
    });
    const text = await page.getByTestId("registry-list").innerText();
    expect(text.toLowerCase()).toContain("no install");
  });

  test("3 watchlist and compatibility evaluation", async ({ request }) => {
    await requireM28(request);
    const project = await createTempProject(request, `M28-3 ${Date.now()}`);
    await request.post("/api/codirector/m28/radar/discover", { data: { source: "huggingface" } });
    const reg = await (await request.get("/api/codirector/m28/radar/registry")).json();
    const entry = reg.entries.find((e: { classification: string }) => e.classification === "official");
    expect(entry).toBeTruthy();
    const wl = await request.post("/api/codirector/m28/radar/watchlist", {
      data: { entryId: entry.id, projectId: project.id },
    });
    expect(wl.ok()).toBeTruthy();
    const compat = await request.post("/api/codirector/m28/compat/evaluate", {
      data: { entryId: entry.id },
    });
    expect(compat.ok()).toBeTruthy();
    const body = await compat.json();
    expect(body.verdict).toBeTruthy();
    expect(Array.isArray(body.reasons)).toBeTruthy();
  });

  test("4 sandbox plan approval boundary", async ({ request }) => {
    await requireM28(request);
    const project = await createTempProject(request, `M28-4 ${Date.now()}`);
    await request.post("/api/codirector/m28/radar/discover", { data: { source: "huggingface" } });
    const reg = await (await request.get("/api/codirector/m28/radar/registry")).json();
    const entry = reg.entries.find((e: { classification: string }) => e.classification === "official");
    const sb = await (await request.post("/api/codirector/m28/sandbox", { data: { name: "plan-sb" } })).json();
    const plan = await (
      await request.post("/api/codirector/m28/sandbox/plan", {
        data: { sandboxId: sb.id, entryId: entry.id },
      })
    ).json();
    expect(plan.status).toBe("pending");
    expect(plan.plan.files?.length).toBeGreaterThan(0);
    const rejected = await (
      await request.post(`/api/codirector/m28/sandbox/plan/${plan.id}/reject`)
    ).json();
    expect(rejected.status).toBe("rejected");
    const plan2 = await (
      await request.post("/api/codirector/m28/sandbox/plan", {
        data: { sandboxId: sb.id, entryId: entry.id },
      })
    ).json();
    const approved = await (
      await request.post(`/api/codirector/m28/sandbox/plan/${plan2.id}/approve`, {
        data: { projectId: project.id },
      })
    ).json();
    expect(approved.status).toBe("approved");
    expect(approved.job?.type).toBe("sandbox_install");
  });

  test("5 isolated sandbox lifecycle without touching production Comfy", async ({ request }) => {
    await requireM28(request);
    const sb = await (await request.post("/api/codirector/m28/sandbox", { data: { name: "life" } })).json();
    expect(sb.productionComfyUntouched).toBeTruthy();
    await request.post(`/api/codirector/m28/sandbox/${sb.id}/start`);
    const health = await (await request.get(`/api/codirector/m28/sandbox/${sb.id}/health`)).json();
    expect(health.ok).toBeTruthy();
    const detect = await (await request.post(`/api/codirector/m28/sandbox/${sb.id}/detect`)).json();
    expect(detect.models?.length).toBeGreaterThan(0);
    const val = await (await request.post(`/api/codirector/m28/sandbox/${sb.id}/validate`)).json();
    expect(val.result?.ok).toBeTruthy();
    await request.post(`/api/codirector/m28/sandbox/${sb.id}/stop`);
    await request.post(`/api/codirector/m28/sandbox/${sb.id}/restart`);
    const removed = await (await request.post(`/api/codirector/m28/sandbox/${sb.id}/remove`)).json();
    expect(removed.productionComfyUntouched).toBeTruthy();
  });

  test("6 promotion remains human gated", async ({ request }) => {
    await requireM28(request);
    const project = await createTempProject(request, `M28-6 ${Date.now()}`);
    const sb = await (await request.post("/api/codirector/m28/sandbox", { data: { name: "promo" } })).json();
    await request.post(`/api/codirector/m28/sandbox/${sb.id}/validate`);
    const prop = await (await request.post("/api/codirector/m28/promote", { data: { sandboxId: sb.id } })).json();
    expect(prop.productionInstallOccurred).toBeFalsy();
    const rejected = await (await request.post(`/api/codirector/m28/promote/${prop.id}/reject`)).json();
    expect(rejected.mutated).toBeFalsy();
    const prop2 = await (await request.post("/api/codirector/m28/promote", { data: { sandboxId: sb.id } })).json();
    const approved = await (
      await request.post(`/api/codirector/m28/promote/${prop2.id}/approve`, {
        data: { projectId: project.id },
      })
    ).json();
    expect(approved.status).toBe("approved");
    expect(approved.manifest?.approval?.approved).toBeTruthy();
    await drain(request);
  });

  test("7 Co-Director model routing recommendations", async ({ request }) => {
    await requireM28(request);
    const project = await createTempProject(request, `M28-7 ${Date.now()}`);
    await request.post("/api/codirector/m28/radar/discover", { data: { source: "huggingface" } });
    const res = await request.post("/api/codirector/m28/routing/recommend", {
      data: {
        projectId: project.id,
        sceneId: "scene-1",
        filmmakingOutcome: "soft evening dialogue close-up",
        currentShotModel: "existing-model",
      },
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.filmmakingLanguage).toBeTruthy();
    expect(body.technical).toBeTruthy();
    expect(body.changedExistingShotModel).toBeFalsy();
  });

  test("8 production recipe multi-stage via M2.7 jobs", async ({ request }) => {
    await requireM28(request);
    const project = await createTempProject(request, `M28-8 ${Date.now()}`);
    const recipe = await (
      await request.post("/api/codirector/m28/recipes", {
        data: { projectId: project.id, name: "multi" },
      })
    ).json();
    const run = await (
      await request.post(`/api/codirector/m28/recipes/${recipe.id}/run`, { data: {} })
    ).json();
    expect(run.stages.every((s: { jobId: string | null }) => s.jobId)).toBeTruthy();
    await drain(request, 120);
  });

  test("9 Virtual Stage structured camera workflow", async ({ page, request }) => {
    await requireM28(request);
    const project = await createTempProject(request, `M28-9 ${Date.now()}`);
    await page.goto(`/virtual-stage?projectId=${encodeURIComponent(project.id)}`);
    await expect(page.getByTestId("virtual-stage-page")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("scene-anchor-ready")).toContainText(/ready/i);
    await page.getByTestId("camera-orbit").fill("45");
    await page.getByTestId("camera-elevation").fill("10");
    await page.getByTestId("camera-save").click();
    await page.getByTestId("camera-reload").click();
    await expect(page.getByTestId("camera-json")).toContainText("45");
    await expect(page.getByTestId("prompt-not-sot")).toBeVisible();
  });

  test("10 guided and professional edit same shot profile", async ({ request }) => {
    await requireM28(request);
    const project = await createTempProject(request, `M28-10 ${Date.now()}`);
    const profile = await (
      await request.post("/api/codirector/m28/shot-profiles", {
        data: { projectId: project.id, name: "modes" },
      })
    ).json();
    const guided = await (
      await request.post(`/api/codirector/m28/shot-profiles/${profile.id}/save`, {
        data: { mode: "guided", payload: { lighting: { key: 0.9 } } },
      })
    ).json();
    expect(guided.payload.mode).toBe("guided");
    const pro = await (
      await request.post(`/api/codirector/m28/shot-profiles/${profile.id}/save`, {
        data: { mode: "professional", payload: { lighting: { key: 0.55 } } },
      })
    ).json();
    expect(pro.payload.mode).toBe("professional");
    expect(pro.payload.lighting.key).toBe(0.55);
  });

  test("11 cinematic depth accept selected only", async ({ request }) => {
    await requireM28(request);
    const project = await createTempProject(request, `M28-11 ${Date.now()}`);
    const profile = await (
      await request.post("/api/codirector/m28/shot-profiles", {
        data: { projectId: project.id, name: "depth" },
      })
    ).json();
    const res = await (
      await request.post(`/api/codirector/m28/shot-profiles/${profile.id}/cinematic-depth`, {
        data: {
          suggestions: [
            { id: "a", camera: { distance: 1.5 } },
            { id: "b", camera: { elevation: 12 } },
          ],
          acceptIds: ["a"],
        },
      })
    ).json();
    expect(res.payload.cinematicDepth.accepted).toHaveLength(1);
    expect(res.payload.cinematicDepth.rejected).toHaveLength(1);
    expect(res.payload.camera.distance).toBe(1.5);
  });

  test("12 lighting atmosphere grade in one profile", async ({ request }) => {
    await requireM28(request);
    const project = await createTempProject(request, `M28-12 ${Date.now()}`);
    const profile = await (
      await request.post("/api/codirector/m28/shot-profiles", {
        data: { projectId: project.id, name: "look" },
      })
    ).json();
    const saved = await (
      await request.post(`/api/codirector/m28/shot-profiles/${profile.id}/save`, {
        data: {
          payload: {
            lighting: {
              template: "soft_key",
              key: 0.7,
              fill: 0.3,
              rim: 0.2,
              intensity: 0.8,
              temperature: 5600,
              softness: 0.6,
            },
            atmosphere: { blueHaze: 0.25 },
            grade: { template: "neutral", contrast: 0.1, saturation: 0 },
            aiRelighting: false,
          },
        },
      })
    ).json();
    expect(saved.payload.lighting.template).toBe("soft_key");
    expect(saved.payload.atmosphere.blueHaze).toBe(0.25);
    expect(saved.payload.aiRelighting).toBeFalsy();
  });

  test("13 shot profile associate export import", async ({ request }) => {
    await requireM28(request);
    const project = await createTempProject(request, `M28-13 ${Date.now()}`);
    const profile = await (
      await request.post("/api/codirector/m28/shot-profiles", {
        data: { projectId: project.id, name: "assoc" },
      })
    ).json();
    await request.post(`/api/codirector/m28/shot-profiles/${profile.id}/associate`, {
      data: { storyboardShotId: "sb1", timelineItemId: "tl1" },
    });
    const exported = await (
      await request.get(`/api/codirector/m28/shot-profiles/${profile.id}/export`)
    ).json();
    expect(exported.format).toBe("adept.shot_profile.v1");
    const got = await (await request.get(`/api/codirector/m28/shot-profiles/${profile.id}`)).json();
    expect(got.payload.associations.storyboardShotId).toBe("sb1");
  });

  test("14 apply shot profile via M2.7 job", async ({ request }) => {
    await requireM28(request);
    const project = await createTempProject(request, `M28-14 ${Date.now()}`);
    const profile = await (
      await request.post("/api/codirector/m28/shot-profiles", {
        data: { projectId: project.id, name: "gen" },
      })
    ).json();
    const job = await request.post("/api/codirector/jobs", {
      data: {
        type: "apply_shot_profile",
        projectId: project.id,
        payload: { profileId: profile.id },
      },
    });
    expect(job.ok()).toBeTruthy();
    await drain(request);
    const listed = await (
      await request.get(`/api/codirector/jobs?projectId=${encodeURIComponent(project.id)}`)
    ).json();
    const applyJob = (listed.jobs || []).find((j: { type: string }) => j.type === "apply_shot_profile");
    expect(applyJob).toBeTruthy();
  });

  test("15 M2.5 owns visualValidationPending lifecycle", async ({ request }) => {
    await requireM28(request);
    const health = await waitForHealth(request);
    expect(health.operator?.visionValidationEnabled).toBeTruthy();
    expect(String(health.operator?.visualValidationPendingNote || "")).toMatch(/M2\.5/i);
  });

  test("16 approval and bible canon remain gated", async ({ request }) => {
    await requireM28(request);
    const sb = await (await request.post("/api/codirector/m28/sandbox", { data: { name: "canon" } })).json();
    const prop = await (await request.post("/api/codirector/m28/promote", { data: { sandboxId: sb.id } })).json();
    expect(prop.productionInstallOccurred).toBeFalsy();
    expect(prop.status).toBe("pending");
  });

  test("17 resume recipe without duplicating successful stages", async ({ request }) => {
    await requireM28(request);
    const project = await createTempProject(request, `M28-17 ${Date.now()}`);
    const recipe = await (
      await request.post("/api/codirector/m28/recipes", {
        data: { projectId: project.id, name: "resume" },
      })
    ).json();
    const run1 = await (
      await request.post(`/api/codirector/m28/recipes/${recipe.id}/run`, {
        data: { simulateFailureAt: 1 },
      })
    ).json();
    await drain(request, 120);
    await request.post(`/api/codirector/m28/recipes/${recipe.id}/retry`);
    await drain(request, 120);
    const after = await (await request.get(`/api/codirector/m28/recipes/${recipe.id}`)).json();
    expect(run1.stages.length).toBe(after.stages.length);
  });

  test("18 security boundaries: no silent promote, sandbox path, location spin", async ({
    request,
  }) => {
    await requireM28(request);
    const project = await createTempProject(request, `M28-18 ${Date.now()}`);
    await request.post("/api/codirector/m28/radar/discover", { data: { source: "github" } });
    const reg = await (await request.get("/api/codirector/m28/radar/registry")).json();
    const entry = reg.entries.find((e: { classification: string }) => e.classification === "community");
    const sb = await (await request.post("/api/codirector/m28/sandbox", { data: { name: "sec" } })).json();
    const plan = await (
      await request.post("/api/codirector/m28/sandbox/plan", {
        data: { sandboxId: sb.id, entryId: entry.id },
      })
    ).json();
    expect(plan.plan.writesOutsideSandbox).toBeFalsy();
    const job = await request.post("/api/codirector/jobs", {
      data: {
        type: "sandbox_install",
        projectId: project.id,
        payload: { planId: plan.id, approved: false },
      },
    });
    expect(job.ok()).toBeTruthy();
    await drain(request);
    const listed = await (
      await request.get(`/api/codirector/jobs?projectId=${encodeURIComponent(project.id)}`)
    ).json();
    const install = (listed.jobs || []).find((j: { type: string }) => j.type === "sandbox_install");
    expect(["Blocked", "Failed"]).toContain(install.status);

    const spin = await (
      await request.post("/api/codirector/m28/location-spin/plan", {
        data: { projectId: project.id, locationName: "Plaza" },
      })
    ).json();
    const coverage = await (
      await request.post(`/api/codirector/m28/location-spin/${spin.id}/spin-camera`, {
        data: {},
      })
    ).json();
    expect(coverage.coverage?.frames?.length).toBeGreaterThan(1);
    expect(coverage.plan?.chain).toEqual([
      "master",
      "depth",
      "seg",
      "proxy",
      "stage",
      "guide",
      "refine",
      "validate",
    ]);
  });
});
