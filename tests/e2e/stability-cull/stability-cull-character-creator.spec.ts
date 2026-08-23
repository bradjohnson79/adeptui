/**
 * Stability Cull Batch 3 — Character Creator / Director / diagnostics on the
 * named cert project. Never writes Schnick or Korri.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";
import {
  assertNotOwnerWriteTarget,
  CERT_PROJECT_NAME,
  creatorUiBase,
  studioApiBase,
} from "../setup/ownerProjectGuard";

function certProjectId(): string | null {
  const env = process.env.ADEPT_CERT_PROJECT_ID?.trim();
  if (env) return env;
  const file = path.join("data", "runtime", "stability-cert-project.json");
  if (!fs.existsSync(file)) return null;
  try {
    const parsed = JSON.parse(fs.readFileSync(file, "utf8")) as { id?: string };
    return parsed.id || null;
  } catch {
    return null;
  }
}

async function resolveCertProject(request: {
  get: (url: string) => Promise<{ ok: () => boolean; json: () => Promise<unknown> }>;
  post: (url: string, opts: { data: unknown }) => Promise<{ ok: () => boolean; json: () => Promise<unknown> }>;
}): Promise<string> {
  const existing = certProjectId();
  if (existing) {
    assertNotOwnerWriteTarget(existing);
    return existing;
  }
  const api = studioApiBase();
  const listed = await request.get(`${api}/api/projects`);
  expect(listed.ok()).toBeTruthy();
  const body = (await listed.json()) as { projects?: { id: string; name: string }[] } | { id: string; name: string }[];
  const rows = Array.isArray(body) ? body : body.projects || [];
  const found = rows.find((row) => row.name === CERT_PROJECT_NAME);
  if (found?.id) {
    assertNotOwnerWriteTarget(found.id);
    return found.id;
  }
  const created = await request.post(`${api}/api/projects`, { data: { name: CERT_PROJECT_NAME } });
  expect(created.ok()).toBeTruthy();
  const row = (await created.json()) as { id?: string };
  const pid = String(row.id || "");
  assertNotOwnerWriteTarget(pid);
  return pid;
}

test("Character Creator + Director jobs + diagnostics on Adept Stability Cert", async ({
  page,
  request,
}) => {
  test.setTimeout(120_000);
  const ui = creatorUiBase();
  const api = studioApiBase();
  const projectId = await resolveCertProject(request);

  const health = await request.get(`${api}/api/healthz`);
  expect(health.status()).toBe(200);

  const created = await request.post(`${api}/api/projects/${projectId}/characters`, {
    data: {
      name: "Stability Cert Character",
      description: "Named Adept Stability Cert fixture. Not Schnick or Korri.",
    },
  });
  expect(created.ok(), await created.text()).toBeTruthy();
  const row = (await created.json()) as { id?: string; characterId?: string };
  const characterId = String(row.id || row.characterId || "");
  assertNotOwnerWriteTarget(projectId, characterId);

  const jobs = await request.get(`${api}/api/projects/${projectId}/jobs`);
  expect(jobs.ok()).toBeTruthy();

  await page.goto(`${ui}/project/${projectId}?workspace=characters&characterId=${characterId}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("character-core")).toBeVisible({ timeout: 30_000 });
  const generate = page.getByTestId("character-generate");
  await expect(generate).toBeVisible({ timeout: 20_000 });
  if (await generate.isEnabled()) {
    await generate.click();
    await expect(page.getByTestId("character-generate")).toContainText(/Starting|Generating/i, {
      timeout: 15_000,
    });
    const list = (await (await request.get(`${api}/api/projects/${projectId}/jobs`)).json()) as {
      id: string;
      status: string;
    }[];
    for (const job of list || []) {
      if (["queued", "running"].includes(String(job.status || ""))) {
        await request.post(`${api}/api/jobs/${job.id}/cancel`);
      }
    }
  }

  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("character-core")).toBeVisible({ timeout: 30_000 });

  await page.goto(`${ui}/project/${projectId}?workspace=timeline`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.locator("body")).toBeVisible();

  await page.goto(`${ui}/diagnostics`, { waitUntil: "domcontentloaded" });
  await expect(page.locator("body")).not.toContainText("Proxy (8760)");
});
