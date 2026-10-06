/**
 * Production Assurance ↔ Capability Registry truth.
 * Reuses the named Korri project. Does not create a disposable project.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { API } from "../helpers/app";

const KORRI_PROJECT_ID = process.env.ADEPT_PROJECT_ID || "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
const VIDEO_INTEL = "codirector.video_intelligence.ready";

async function waitForApi(page: Page) {
  await expect
    .poll(async () => {
      try {
        const response = await page.request.get(`${API}/api/healthz`);
        return response.ok();
      } catch {
        return false;
      }
    }, { timeout: 60_000 })
    .toBeTruthy();
}

async function freshCapabilities(request: APIRequestContext, projectId: string) {
  const res = await request.get(`${API}/api/capabilities`, {
    params: { projectId, refresh: "true" },
    timeout: 120_000,
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  return res.json();
}

async function openStatusPanel(page: Page, projectId: string) {
  await page.goto(`/co-director?projectId=${projectId}`);
  await expect(page.getByTestId("codirector-status-chip")).toBeVisible({ timeout: 20_000 });
  await page.getByTestId("codirector-status-chip").click();
  await expect(page.getByTestId("codirector-status-panel")).toBeVisible({ timeout: 15_000 });
}

async function askKnowledge(request: APIRequestContext, projectId: string, message: string) {
  const res = await request.post(`${API}/api/codirector/chat/stream`, {
    data: {
      messages: [{ role: "user", content: message }],
      project_id: projectId,
      workspace: "timeline",
      mode: "chat",
    },
    timeout: 60_000,
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  const text = (await res.body()).toString("utf8");
  let assistant = "";
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed.startsWith("data:")) continue;
    const payload = trimmed.slice("data:".length).trim();
    if (!payload) continue;
    try {
      const evt = JSON.parse(payload) as { type?: string; content?: string; text?: string };
      if ((evt.type === "assistant" || evt.type === "completed" || evt.type === "completion") && evt.content) {
        assistant = String(evt.content);
      }
      if (evt.type === "delta" && evt.text) assistant += String(evt.text);
    } catch {
      /* keep-alives */
    }
  }
  return assistant.trim();
}

test.describe("@critical production assurance truth", () => {
  test.describe.configure({ timeout: 360_000 });

  test("Status Re-check stays aligned with a fresh Capability Registry", async ({ page, request }) => {
    await waitForApi(page);

    const caps = await freshCapabilities(request, KORRI_PROJECT_ID);
    const video = (caps.capabilities || []).find((item: { id: string }) => item.id === VIDEO_INTEL);
    expect(video).toBeTruthy();
    expect(video.readinessClass).toBe("advisory_review_degraded");
    const videoBlocked = String(video.status) === "blocked";

    const seeded = await request.post(`${API}/api/codirector/status/check`, {
      data: { projectId: KORRI_PROJECT_ID, forceRefresh: true },
      timeout: 180_000,
    });
    expect(seeded.ok(), await seeded.text()).toBeTruthy();
    const seededRun = await seeded.json();
    expect(seededRun.forceRefresh).toBeTruthy();
    expect(seededRun.readOnly).toBeTruthy();
    expect(seededRun.mutatesRuntime).toBeFalsy();
    expect(seededRun.installsModels).toBeFalsy();
    expect(seededRun.summary.scoreSemantics).toContain("Production Readiness");

    const checkIds = (seededRun.results || []).map((item: { checkId: string }) => item.checkId);
    expect(checkIds).toEqual(expect.arrayContaining([
      "capabilities.registry",
      "create.path",
      "timeline.generator_truth",
      "timeline.context_binding",
      "posecraft.identity_nav",
      "codirector.grounded_routing",
      "runtime.authority",
    ]));

    const capResult = (seededRun.results || []).find((item: { checkId: string }) => item.checkId === "capabilities.registry");
    expect(capResult).toBeTruthy();
    const registryBlocked = (caps.blockers || []).some((item: { capabilityId: string }) => item.capabilityId === VIDEO_INTEL);
    const videoDegraded = String(video.status) === "degraded";
    if (registryBlocked || videoBlocked || videoDegraded) {
      expect(capResult.status).not.toBe("healthy");
      expect(seededRun.summary.score).toBeLessThan(100);
      expect(capResult.readinessClass).toBe("advisory_review_degraded");
      const productionBlocked = (seededRun.results || []).some((item: { readinessClass?: string; status?: string }) => (
        (item.readinessClass === "platform_critical" || item.readinessClass === "production_critical")
        && item.status === "blocked"
      ));
      if (!productionBlocked) {
        expect(seededRun.summary.statusIndicator).not.toBe("Blocked");
        expect(seededRun.summary.score).toBeGreaterThanOrEqual(85);
        expect(seededRun.summary.score).toBeLessThanOrEqual(94);
        expect(seededRun.summary.band).not.toBe("Excellent");
      }
    }

    const runtime = (seededRun.results || []).find((item: { checkId: string }) => item.checkId === "runtime.authority");
    expect(runtime).toBeTruthy();
    expect(runtime.details.singleAuthority).toContain("Runtime Supervisor");
    expect(runtime.details.legacyAffectsCurrentSession).toBeFalsy();
    expect(runtime.details.liveSessionOwner).toContain("Runtime Supervisor");

    await openStatusPanel(page, KORRI_PROJECT_ID);
    await expect(page.getByTestId("codirector-status-score-semantics")).toContainText("Production Readiness");
    await expect(page.getByTestId("codirector-status-indicator")).toBeVisible();
    await expect(page.getByTestId("codirector-status-recheck")).toBeVisible();

    const indicatorBefore = (await page.getByTestId("codirector-status-indicator").innerText()).trim();
    expect([
      "Operational",
      "Degraded",
      "Blocked",
      "Not Checked",
      "Checking studio readiness…",
    ]).toContain(indicatorBefore);

    await page.getByTestId("codirector-status-recheck").click();
    await expect(page.getByTestId("codirector-status-recheck")).toBeEnabled({ timeout: 180_000 });

    const afterCaps = await request.get(`${API}/api/capabilities`, {
      params: { projectId: KORRI_PROJECT_ID },
      timeout: 30_000,
    });
    expect(afterCaps.ok()).toBeTruthy();
    const afterSnap = await afterCaps.json();
    const afterVideo = (afterSnap.capabilities || []).find((item: { id: string }) => item.id === VIDEO_INTEL);
    const afterBlocked = String(afterVideo?.status) === "blocked" || String(afterVideo?.status) === "degraded";
    const latest = await request.get(`${API}/api/codirector/status/latest`, {
      params: { projectId: KORRI_PROJECT_ID },
    });
    expect(latest.ok()).toBeTruthy();
    const latestRun = (await latest.json()).run;
    expect(latestRun).toBeTruthy();
    const latestCap = (latestRun.results || []).find((item: { checkId: string }) => item.checkId === "capabilities.registry");
    if (afterBlocked) {
      expect(latestCap.status).not.toBe("healthy");
      expect(latestRun.summary.score).toBeLessThan(100);
      const productionBlockedAfter = (latestRun.results || []).some((item: { readinessClass?: string; status?: string }) => (
        (item.readinessClass === "platform_critical" || item.readinessClass === "production_critical")
        && item.status === "blocked"
      ));
      if (!productionBlockedAfter) {
        expect(latestRun.summary.statusIndicator).not.toBe("Blocked");
        expect(latestRun.summary.band).not.toBe("Excellent");
      }
    } else {
      expect(["healthy", "warning"]).toContain(latestCap.status);
    }

    const indicatorAfter = (await page.getByTestId("codirector-status-indicator").innerText()).trim();
    expect(["Operational", "Degraded", "Blocked"]).toContain(indicatorAfter);
    if (afterBlocked) {
      await expect(page.getByTestId("codirector-status-advisories")).toBeVisible();
    }

    const wan = await askKnowledge(request, KORRI_PROJECT_ID, "What is WAN in this Adept project?");
    expect(wan.toLowerCase()).toContain("retired");
    expect(wan.toLowerCase()).not.toContain("wide area network");
    expect(wan.toLowerCase()).not.toMatch(/first and last frame video/);
    const wanNet = await askKnowledge(request, KORRI_PROJECT_ID, "What does WAN mean in computer networking?");
    expect(wanNet.toLowerCase()).toContain("wide area network");
  });
});
