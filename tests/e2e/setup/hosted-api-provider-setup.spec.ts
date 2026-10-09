/**
 * Scenarios C–D: OpenAI-compatible connect UI + capability honesty; budget preference.
 * Uses a local mock HTTP server — never logs secrets.
 */
import { test, expect } from "@playwright/test";
import * as http from "http";
import {
  createTempProject,
  deleteProject,
  openSetup,
  resetLiveBetaTestSurface,
  waitForAppReady,
} from "../helpers/app";

const API = process.env.STUDIO_API_BASE_URL || "http://127.0.0.1:8758";

function startMockOpenAI(): Promise<{ url: string; close: () => Promise<void> }> {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      if (req.url?.startsWith("/v1/models")) {
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ data: [{ id: "mock-chat-mini" }, { id: "mock-chat-pro" }] }));
        return;
      }
      res.writeHead(404);
      res.end();
    });
    server.listen(0, "127.0.0.1", () => {
      const addr = server.address();
      const port = typeof addr === "object" && addr ? addr.port : 0;
      resolve({
        url: `http://127.0.0.1:${port}`,
        close: () =>
          new Promise((r) => {
            server.close(() => r());
          }),
      });
    });
  });
}

test.beforeEach(async ({ page, request }) => {
  await waitForAppReady(request);
  await resetLiveBetaTestSurface(request, page);
});

async function restoreOwnerPreferences(
  request: import("@playwright/test").APIRequestContext,
  prefsBefore: { preferredProvider?: string; budgetPreference?: string } | null,
) {
  if (!prefsBefore?.preferredProvider) return;
  await request
    .put(`${API}/api/hosted-providers/preferences`, {
      data: {
        preferredProvider: prefsBefore.preferredProvider,
        budgetPreference: prefsBefore.budgetPreference,
      },
      headers: { "X-Adept-Preference-Lease": "restore" },
    })
    .catch(() => undefined);
}

test.describe("@critical hosted api provider setup", () => {
  test("C–D: OpenAI-compatible discover LLM; spending preference persists", async ({
    page,
    request,
  }) => {
    const mock = await startMockOpenAI();
    const project = await createTempProject(request, `Hosted API ${Date.now()}`);
    let endpointId = "";
    let prefsBefore: { preferredProvider?: string; budgetPreference?: string } | null = null;
    try {
      await request
        .post(`${API}/api/hosted-providers/openai-compatible/purge-test-artifacts`)
        .catch(() => undefined);

      const beforePrefs = await request.get(`${API}/api/hosted-providers/preferences`);
      expect(beforePrefs.ok()).toBeTruthy();
      prefsBefore = await beforePrefs.json();

      const connect = await request.post(`${API}/api/hosted-providers/openai-compatible`, {
        data: {
          displayName: "Mock OpenAI Compat",
          baseUrl: mock.url,
          api_key: "test-key-not-a-secret-for-prod",
          disposable: true,
        },
      });
      expect(connect.ok()).toBeTruthy();
      const body = await connect.json();
      expect(body.ok).toBeTruthy();
      expect(body.disposable).toBeTruthy();
      endpointId = String(body.endpoint?.id || "");
      expect(endpointId).not.toBe("");
      expect((body.probe?.models || []).length).toBeGreaterThanOrEqual(1);
      expect(body.probe?.capabilities?.llm).toBeTruthy();
      // Secret must not echo in response
      const raw = JSON.stringify(body);
      expect(raw).not.toContain("test-key-not-a-secret-for-prod");

      const ownerList = await request.get(`${API}/api/hosted-providers/openai-compatible`);
      expect(ownerList.ok()).toBeTruthy();
      const ownerBody = await ownerList.json();
      const ownerRaw = JSON.stringify(ownerBody.endpoints || []);
      expect(ownerRaw).not.toContain("Mock OpenAI Compat");
      expect(ownerRaw).not.toContain(mock.url);

      const scratch = await request.get(
        `${API}/api/hosted-providers/openai-compatible?includeDisposable=true`,
      );
      expect(scratch.ok()).toBeTruthy();
      const scratchBody = await scratch.json();
      expect(JSON.stringify(scratchBody.disposable || [])).toContain("Mock OpenAI Compat");
      expect(JSON.stringify(scratchBody.endpoints || [])).not.toContain("Mock OpenAI Compat");

      const prefs = await request.put(`${API}/api/hosted-providers/preferences`, {
        data: { preferredProvider: "automatic", budgetPreference: "low_cost" },
        headers: { "X-Adept-Preference-Lease": "begin" },
      });
      expect(prefs.ok()).toBeTruthy();
      const prefsBody = await prefs.json();
      expect(prefsBody.budgetPreference).toBe("low_cost");

      const resolve = await request.post(`${API}/api/hosted-providers/resolve`, {
        data: {},
      });
      const resolveBody = await resolve.json();
      expect(resolveBody.budgetPreference).toBe("low_cost");
      expect(resolveBody.silentSwitchForbidden).toBeTruthy();

      await restoreOwnerPreferences(request, prefsBefore);

      await openSetup(page, project.id);
      await expect(page.getByTestId("setup-openai-compatible")).toBeVisible({ timeout: 30_000 });
      await expect(page.getByTestId("openai-compat-endpoint-list")).not.toContainText("Mock OpenAI Compat", {
        timeout: 15_000,
      });
      await expect(page.getByTestId("hosted-budget-preference")).toBeVisible();
    } finally {
      if (endpointId) {
        await request
          .delete(`${API}/api/hosted-providers/openai-compatible/${encodeURIComponent(endpointId)}`)
          .catch(() => undefined);
      }
      await request
        .post(`${API}/api/hosted-providers/openai-compatible/purge-test-artifacts`)
        .catch(() => undefined);
      await restoreOwnerPreferences(request, prefsBefore);
      await deleteProject(request, project.id);
      await mock.close();
    }
  });
});
