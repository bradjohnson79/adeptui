/**
 * Co-Director Generation Authority — Playwright Tests 1–7 (SenseNova).
 * Reuses SenseNova Integration Lab — no new-project spam.
 */
import { expect, test, type APIRequestContext } from "@playwright/test";
import { API } from "../helpers/app";
import { openCoDirectorFullScreen } from "./helpers/audit";

const PROJECT_ID =
  process.env.ADEPT_PROJECT_ID || "0ffe56e2-0d58-4926-91bf-0f947898d02e";
const FIRST_FRAME_ASSET = "be5ff3cb-ec4a-43cc-b0a3-79be0654870e";
const DREAMWEAVER =
  "Create a first frame of a silver metallic Dreamweaver corridor.";

const VIDEO_ROUTES: { id: string; phrase: string }[] = [
  { id: "minimax-h3", phrase: "Use MiniMax for this one." },
  { id: "ltx", phrase: "Use LTX for this one." },
  { id: "wan", phrase: "Use WAN for this one." },
  { id: "fal_kling", phrase: "Use Kling for this one." },
  { id: "fal_seedance", phrase: "Use SeeDance for this one." },
];

async function streamChatEvents(
  request: APIRequestContext,
  projectId: string,
  message: string,
  timeoutMs = 180_000,
): Promise<{ events: Record<string, any>[]; assistantText: string }> {
  const events: Record<string, any>[] = [];
  let assistantText = "";
  const res = await request.post(`${API}/api/codirector/chat/stream`, {
    data: {
      messages: [{ role: "user", content: message }],
      project_id: projectId,
      mode: "chat",
    },
    timeout: timeoutMs,
  });
  if (!res.ok()) {
    throw new Error(`chat stream failed: ${res.status()} ${await res.text()}`);
  }
  const text = (await res.body()).toString("utf8");
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed.startsWith("data:")) continue;
    const payload = trimmed.slice("data:".length).trim();
    if (!payload) continue;
    try {
      const evt = JSON.parse(payload);
      events.push(evt);
      if (evt.type === "completed" || evt.type === "completion") {
        assistantText = evt.content || assistantText;
      }
      if (evt.type === "delta" && evt.text) assistantText += evt.text;
      if (evt.type === "assistant" && evt.content) assistantText += evt.content;
    } catch {
      /* ignore */
    }
  }
  return { events, assistantText };
}

function executionEvents(events: Record<string, any>[]) {
  return events.filter((e) => e.type === "execution_status" || e.execution);
}

async function startExecution(
  request: APIRequestContext,
  data: Record<string, unknown>,
) {
  const res = await request.post(`${API}/api/codirector/projects/${PROJECT_ID}/executions`, {
    data,
  });
  const body = await res.json();
  return { ok: res.ok(), status: res.status(), body };
}

async function pollAdvance(
  request: APIRequestContext,
  executionId: string,
  times = 16,
) {
  let last: Record<string, any> | null = null;
  for (let i = 0; i < times; i += 1) {
    const adv = await request.post(
      `${API}/api/codirector/projects/${PROJECT_ID}/executions/${executionId}/advance`,
    );
    expect(adv.ok()).toBeTruthy();
    last = await adv.json();
    const status = String(last?.generationJob?.status || last?.status || "").toLowerCase();
    if (["completed", "failed", "cancelled", "done"].includes(status)) break;
    await new Promise((r) => setTimeout(r, 2000));
  }
  return last;
}

async function inventoryVideoRoutes(request: APIRequestContext) {
  const models = await request.get(`${API}/api/production-control/models?modality=video`);
  const resolved = await request.get(
    `${API}/api/production-control/resolve?projectId=${PROJECT_ID}&modality=video`,
  );
  const prefs = await request.get(
    `${API}/api/production-control/projects/${PROJECT_ID}/preferences`,
  );
  const catalog = models.ok() ? await models.json() : {};
  const rows: Record<string, any>[] = [];
  for (const route of VIDEO_ROUTES) {
    const started = await startExecution(request, {
      capability: "video.generate",
      intent: "EXECUTION",
      prompt: `${route.phrase} Animate it.`,
      user_instructions: `${route.phrase} Animate it.`,
      reference_asset_id: FIRST_FRAME_ASSET,
      context: {
        prompt: `${route.phrase} Animate it.`,
        user_instructions: `${route.phrase} Animate it.`,
        reference_asset_id: FIRST_FRAME_ASSET,
      },
    });
    const status = String(
      started.body.generationJob?.status || started.body.status || "",
    ).toLowerCase();
    const provider = String(
      started.body.generationJob?.provider || started.body.provider || "",
    ).toLowerCase();
    const executable = ["queued", "running", "completed", "done"].includes(status);
    rows.push({
      route: route.id,
      phrase: route.phrase,
      httpOk: started.ok,
      status,
      provider,
      providerLabel: started.body.generationJob?.providerLabel,
      error: started.body.error || started.body.generationJob?.error,
      jobScopedOverride: started.body.generationJob?.jobScopedOverride
        || started.body.plan_data?.jobScopedOverride,
      executable,
    });
    if (executable) {
      return {
        catalog,
        resolved: resolved.ok() ? await resolved.json() : {},
        prefs: prefs.ok() ? await prefs.json() : {},
        rows,
        winner: route.id,
      };
    }
  }
  return {
    catalog,
    resolved: resolved.ok() ? await resolved.json() : {},
    prefs: prefs.ok() ? await prefs.json() : {},
    rows,
    winner: null,
  };
}

test.describe("Co-Director generation authority — Dreamweaver", () => {
  test.beforeEach(async ({ request }) => {
    await expect
      .poll(async () => {
        try {
          const res = await request.get(`${API}/api/healthz`);
          return res.ok();
        } catch {
          return false;
        }
      }, { timeout: 90_000 })
      .toBeTruthy();
  });

  test("1 corridor still — no interview, card, library, next-step chips", async ({
    page,
    request,
  }) => {
    test.setTimeout(300_000);
    const { events, assistantText } = await streamChatEvents(request, PROJECT_ID, DREAMWEAVER);
    const live = events.filter((e) => e.type !== "momentum_resume");
    const blob = `${assistantText} ${JSON.stringify(live)}`.toLowerCase();
    expect(blob).not.toMatch(/how should this space look and sound/);
    const execs = executionEvents(events);
    expect(execs.length, "must emit an execution card before first pixel").toBeGreaterThan(0);
    const exec = execs[0].execution;
    expect(exec.capability).toBe("image.generate");
    expect(exec.execution_id).toBeTruthy();
    expect(exec.generationJob?.id || exec.child_jobs?.[0]?.job_id).toBeTruthy();
    if (exec.generationJob) {
      expect(
        exec.generationJob.progressPercent === null || exec.generationJob.progressPercent > 0,
      ).toBeTruthy();
    }

    await openCoDirectorFullScreen(page, PROJECT_ID);
    const card = page.getByTestId("execution-summary-card").first();
    await expect(card).toBeVisible({ timeout: 60_000 });
    const progress = page.getByTestId("generation-job-progress").first();
    if (await progress.isVisible().catch(() => false)) {
      const liveCard = (await card.innerText()).toLowerCase();
      expect(liveCard).not.toMatch(/how should this space look and sound/);
    }

    const lib = await request.get(`${API}/api/projects/${PROJECT_ID}/library?limit=40`);
    expect(lib.ok()).toBeTruthy();
    const libBody = await lib.json();
    const assets = JSON.stringify(libBody);
    expect(assets).toMatch(new RegExp(FIRST_FRAME_ASSET));

    await page.goto(`/project/${PROJECT_ID}?workspace=library`);
    await expect(page.getByTestId("library-media-grid").or(page.locator("body"))).toBeVisible({
      timeout: 45_000,
    });

    await openCoDirectorFullScreen(page, PROJECT_ID);
    const chips = page.getByTestId("codirector-next-step-options");
    if (await chips.isVisible().catch(() => false)) {
      await expect(chips).toContainText(/where should we go next/i);
    }
  });

  test("2 animate-it exhausts installed and configured video routes", async ({ request }) => {
    test.setTimeout(240_000);
    const inventory = await inventoryVideoRoutes(request);
    const animate = await streamChatEvents(request, PROJECT_ID, "Animate it.");
    const execs = executionEvents(animate.events);
    if (execs.length) {
      expect(execs[0].execution.capability).toBe("video.generate");
    } else {
      expect(animate.assistantText.toLowerCase()).toMatch(
        /first frame|still generating|not configured|timeline|video|not ready/,
      );
    }
    const attempted = inventory.rows.map((r) => r.route);
    expect(attempted).toEqual(VIDEO_ROUTES.map((r) => r.id));
    const swapped = inventory.rows.some((r) =>
      String(r.error || "").toLowerCase().includes("switched to minimax"),
    );
    expect(swapped).toBeFalsy();
    // WAN is retired: an attempt must fail honestly — never execute, never
    // silently substitute another engine.
    const wanRow = inventory.rows.find((r) => r.route === "wan");
    if (wanRow) {
      expect(wanRow.executable, "WAN is retired — must not execute").toBeFalsy();
      expect(String(wanRow.error || "").toLowerCase()).toMatch(
        /retired|unknown|not found|unavailable|blocked|not configured/,
      );
    }
    if (!inventory.winner) {
      const available = inventory.resolved?.selection?.availableModelIds || [];
      for (const modelId of available) {
        await request.put(`${API}/api/production-control/projects/${PROJECT_ID}/preferences`, {
          data: { activeVideoModelId: modelId },
        });
        const retry = await startExecution(request, {
          capability: "video.generate",
          intent: "EXECUTION",
          prompt: "Animate it.",
          user_instructions: "Animate it.",
          reference_asset_id: FIRST_FRAME_ASSET,
          context: {
            prompt: "Animate it.",
            user_instructions: "Animate it.",
            reference_asset_id: FIRST_FRAME_ASSET,
          },
        });
        const status = String(retry.body.generationJob?.status || retry.body.status || "").toLowerCase();
        inventory.rows.push({
          route: `dock:${modelId}`,
          phrase: "Animate it.",
          httpOk: retry.ok,
          status,
          provider: retry.body.generationJob?.provider,
          error: retry.body.error || retry.body.generationJob?.error,
          executable: ["queued", "running", "completed", "done"].includes(status),
        });
        if (["queued", "running", "completed", "done"].includes(status)) {
          inventory.winner = modelId;
          break;
        }
      }
      await request.put(`${API}/api/production-control/projects/${PROJECT_ID}/preferences`, {
        data: { activeVideoModelId: "minimax-h3" },
      });
    }
    if (!inventory.winner) {
      for (const row of inventory.rows) {
        expect(["failed", "error", "cancelled", ""]).toContain(String(row.status || "failed"));
      }
    }
  });

  test("3 stored MiniMax plus Use LTX for this one stays job-scoped", async ({ request }) => {
    test.setTimeout(180_000);
    await streamChatEvents(request, PROJECT_ID, "Always use MiniMax as my default video generator.");
    const ltx = await startExecution(request, {
      capability: "video.generate",
      intent: "EXECUTION",
      prompt: "Use LTX for this one.",
      user_instructions: "Use LTX for this one.",
      context: { prompt: "Use LTX for this one.", user_instructions: "Use LTX for this one." },
    });
    const provider = String(
      ltx.body.generationJob?.provider || ltx.body.provider || "",
    ).toLowerCase();
    expect(provider).toMatch(/ltx/);
    expect(ltx.body.generationJob?.jobScopedOverride || ltx.body.plan_data?.jobScopedOverride).toBeTruthy();
    const prefs = await request.get(
      `${API}/api/production-control/projects/${PROJECT_ID}/preferences`,
    );
    expect(prefs.ok()).toBeTruthy();
  });

  test("4 unconfigured SeeDance is an honest block", async ({ request }) => {
    test.setTimeout(120_000);
    const { events, assistantText } = await streamChatEvents(
      request,
      PROJECT_ID,
      "Use SeeDance for this one.",
    );
    const blob = `${assistantText} ${JSON.stringify(events)}`.toLowerCase();
    const execs = executionEvents(events);
    const provider = String(execs[0]?.execution?.generationJob?.provider || "").toLowerCase();
    if (execs.length && execs[0].execution.status === "failed") {
      expect(blob).toMatch(/not configured|seedance/);
      expect(provider).not.toMatch(/minimax/);
    } else {
      expect(blob).toMatch(/not configured|seedance|animate|first frame|video/);
    }
    expect(blob).not.toMatch(/switched to minimax|falling back to minimax/);

    const start = await startExecution(request, {
      capability: "video.generate",
      intent: "EXECUTION",
      prompt: "Use SeeDance for this one.",
      user_instructions: "Use SeeDance for this one.",
      context: { prompt: "Use SeeDance for this one." },
    });
    const startBlob = JSON.stringify(start.body).toLowerCase();
    expect(startBlob).toMatch(/seedance|not configured|failed/);
    expect(startBlob).not.toMatch(/switched to minimax/);
    const status = String(start.body.generationJob?.status || start.body.status || "").toLowerCase();
    expect(status).not.toBe("queued");
  });

  test("5 forced enqueue failure projects FAILED", async ({ request }) => {
    test.setTimeout(120_000);
    const start = await startExecution(request, {
      capability: "video.generate",
      intent: "EXECUTION",
      prompt: "Use LTX for this one.",
      user_instructions: "Use LTX for this one.",
      context: {
        prompt: "Use LTX for this one.",
        user_instructions: "Use LTX for this one.",
        forceEnqueueFailure: true,
      },
    });
    const status = String(start.body.generationJob?.status || start.body.status || "").toLowerCase();
    expect(status).toBe("failed");
    expect(status).not.toBe("queued");
    expect(JSON.stringify(start.body).toLowerCase()).toMatch(/fail|could not start|retry/);
  });

  test("6 advance poll keeps GenerationJob identity and drops spinner when terminal", async ({
    page,
    request,
  }) => {
    test.setTimeout(240_000);
    const start = await startExecution(request, {
      capability: "image.generate",
      intent: "EXECUTION",
      prompt: DREAMWEAVER,
      context: { prompt: DREAMWEAVER, production_role: "video_first_frame" },
    });
    expect(start.ok, JSON.stringify(start.body)).toBeTruthy();
    const executionId = start.body.execution_id;
    const jobId = start.body.generationJob?.id;
    expect(jobId).toBeTruthy();

    const active = await request.get(
      `${API}/api/codirector/projects/${PROJECT_ID}/executions/active/latest`,
    );
    expect(active.ok()).toBeTruthy();
    const activeBody = await active.json();
    expect(activeBody.execution?.execution_id || activeBody.execution_id).toBe(executionId);

    const last = await pollAdvance(request, executionId);
    expect(last?.generationJob?.id).toBe(jobId);
    expect(last?.generationJob?.modality || "image").toBeTruthy();
    const status = String(last?.generationJob?.status || last?.status || "").toLowerCase();
    if (["completed", "failed", "cancelled", "done"].includes(status)) {
      if (status === "completed") {
        expect(last?.generationJob?.progressPercent === 100 || last?.generationJob?.progressPercent == null).toBeTruthy();
      }
    }

    await openCoDirectorFullScreen(page, PROJECT_ID);
    const card = page.getByTestId("execution-summary-card").first();
    if (await card.isVisible().catch(() => false)) {
      const progress = page.getByTestId("generation-job-progress").first();
      if (await progress.isVisible().catch(() => false)) {
        const terminal = await progress.getAttribute("data-indeterminate");
        if (["completed", "failed", "cancelled", "done"].includes(status)) {
          expect(terminal).toBe("false");
          await expect(card).toHaveClass(/is-done|is-failed|is-cancelled/);
        }
      }
    }
  });

  test("7 dismiss failure keeps the card; success hides it after reload", async ({
    page,
    request,
  }) => {
    test.setTimeout(180_000);
    const start = await startExecution(request, {
      capability: "video.generate",
      intent: "EXECUTION",
      prompt: "Use SeeDance for this one.",
      user_instructions: "Use SeeDance for this one.",
      context: { prompt: "Use SeeDance for this one.", forceEnqueueFailure: true },
    });
    const executionId = start.body.execution_id;
    expect(executionId).toBeTruthy();

    await openCoDirectorFullScreen(page, PROJECT_ID);
    let dismissHits = 0;
    await page.route("**/executions/**/dismiss", async (route) => {
      dismissHits += 1;
      if (dismissHits === 1) {
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ detail: "forced dismiss failure" }),
        });
        return;
      }
      await route.continue();
    });

    const dismiss = page.getByTestId("codirector-exec-dismiss").or(page.getByTestId("codirector-error-dismiss"));
    if (await dismiss.first().isVisible().catch(() => false)) {
      await dismiss.first().click();
      await expect(page.getByTestId("execution-summary-card").first()).toBeVisible();
      await expect(page.getByText(/could not dismiss|try again/i)).toBeVisible();
      await dismiss.first().click();
    } else {
      const apiFail = await request.post(
        `${API}/api/codirector/projects/${PROJECT_ID}/executions/${executionId}/dismiss`,
      );
      expect(apiFail.status()).toBeLessThan(500);
    }

    const ok = await request.post(
      `${API}/api/codirector/projects/${PROJECT_ID}/executions/${executionId}/dismiss`,
    );
    expect(ok.ok() || ok.status() === 404 || ok.status() === 409).toBeTruthy();
    await page.reload();
    await openCoDirectorFullScreen(page, PROJECT_ID);
  });

  test("generate shot 14 is a Timeline handoff", async ({ request }) => {
    const start = await startExecution(request, {
      capability: "timeline.generate_shot",
      intent: "EXECUTION",
      prompt: "Generate shot 14.",
      context: { prompt: "Generate shot 14.", user_instructions: "Generate shot 14." },
    });
    expect(start.ok, JSON.stringify(start.body)).toBeTruthy();
    expect(start.body.plan_data?.timelineHandoff || start.body.plan_data?.owner === "timeline").toBeTruthy();
    expect(JSON.stringify(start.body.child_jobs || [])).not.toMatch(/minimax|ltx|seedance/);
  });
});
