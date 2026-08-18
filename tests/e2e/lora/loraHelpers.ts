import { expect, test, type APIRequestContext } from "@playwright/test";

export const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";

/**
 * Wait until the live Studio API answers /api/health (it can be cycled by
 * the environment watchdog between test runs; certification must not fail
 * on transient restarts).
 */
export async function waitForApi(request: APIRequestContext, timeoutMs = 240000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await request.get(`${API}/api/health`, { timeout: 8000 });
      if (res.ok()) return;
    } catch {
      /* restart in progress */
    }
    await new Promise((resolve) => setTimeout(resolve, 5000));
  }
  throw new Error("Studio API did not become healthy in time");
}

export async function waitForComfy(request: APIRequestContext, timeoutMs = 120000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await request.get("http://127.0.0.1:8188/system_stats", { timeout: 8000 });
      if (res.ok()) return;
    } catch {
      /* comfy restarting */
    }
    await new Promise((resolve) => setTimeout(resolve, 5000));
  }
  throw new Error("ComfyUI did not become healthy in time");
}

/** Create a project with retry (API may be mid-restart). */
export async function createProjectResilient(request: APIRequestContext, name: string) {
  await waitForApi(request);
  let lastError: unknown = null;
  for (let attempt = 0; attempt < 5; attempt += 1) {
    try {
      const res = await request.post(`${API}/api/projects`, {
        data: { name: `${name} ${Date.now()}` },
        timeout: 60000,
      });
      if (res.ok()) {
        const body = (await res.json()) as { id: string };
        expect(body.id).toBeTruthy();
        return body.id;
      }
      lastError = new Error(`create project HTTP ${res.status()}: ${(await res.text()).slice(0, 200)}`);
    } catch (error) {
      lastError = error;
      await new Promise((resolve) => setTimeout(resolve, 8000));
    }
  }
  throw lastError instanceof Error ? lastError : new Error("create project failed");
}