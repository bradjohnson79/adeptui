import fs from "node:fs";
import { test, expect } from "@playwright/test";
import {
  API,
  clearActiveInstallJobs,
  clearComponentLocation,
  createTempProject,
  deleteProject,
  makeTempDir,
  openSetup,
  waitForAppReady,
  writeLinkFixture,
} from "../helpers/app";
import { AuditObserver } from "../helpers/observer";

const PACK = "pack_essential_anime";
const WRONG_PACK = "pack_essential_cinematic";

// A pack card hides its whole action row while an operation is attached to the component, so the
// row disappears for as long as the previous link attempt is still settling server-side. Waiting
// for the button to come back keeps the assertion intact — it must appear — without depending on
// the click's default action timeout being longer than the operation takes to clear.
async function clickLinkExisting(page: import("@playwright/test").Page, packId: string) {
  const button = page
    .getByTestId(`setup-card-${packId}`)
    .getByRole("button", { name: /Link Existing Folder/i });
  await expect(button).toBeVisible({ timeout: 90_000 });
  await button.click();
}

async function startLinkExisting(
  page: import("@playwright/test").Page,
  packId: string,
) {
  const responsePromise = page.waitForResponse(
    (res) =>
      res.url().includes(`/setup/components/${packId}/link-existing`) &&
      res.request().method() === "POST" &&
      res.ok(),
    { timeout: 30_000 },
  );
  await clickLinkExisting(page, packId);
  return (await responsePromise).json() as Promise<{ operation_id: string }>;
}

async function answerCheckpoint(
  request: import("@playwright/test").APIRequestContext,
  operationId: string,
  path: string,
) {
  let checkpointId: string | null = null;
  await expect
    .poll(async () => {
      const status = await request.get(`${API}/api/setup/operations/${operationId}`);
      if (!status.ok()) return null;
      const body = await status.json();
      checkpointId = body.status === "awaiting_checkpoint"
        ? String(body.checkpoint?.checkpoint_id || "")
        : null;
      return checkpointId;
    }, { timeout: 30_000 })
    .toBeTruthy();
  const response = await request.post(`${API}/api/setup/operations/${operationId}/checkpoint`, {
    data: { path, checkpoint_id: checkpointId },
  });
  expect(response.ok()).toBeTruthy();
  return response.json() as Promise<Record<string, unknown>>;
}

async function resetPackState(
  request: import("@playwright/test").APIRequestContext,
  componentId: string,
) {
  await request.post(`${API}/api/e2e/recover-operations`);
  await clearActiveInstallJobs(request, componentId).catch(() => undefined);
  await clearComponentLocation(request, componentId);
  await expect
    .poll(async () => {
      const jobs = await request.get(`${API}/api/setup/install-jobs?componentId=${encodeURIComponent(componentId)}`);
      if (!jobs.ok()) return "jobs-error";
      const jobsBody = await jobs.json() as { jobs?: Array<{ id?: string; active?: boolean }> };
      const status = await request.get(`${API}/api/setup/status`);
      if (!status.ok()) return "status-error";
      const statusBody = await status.json() as { components: Array<{ id: string; status?: string }> };
      const component = statusBody.components.find((item) => item.id === componentId);
      return `${(jobsBody.jobs || []).length}:${component?.status || "missing"}`;
    }, { timeout: 15_000 })
    .toMatch(/^0:(?!ready$).+/);
}

test.describe("@critical @isolated pack link existing", () => {
  test("empty rejected; valid accepted; wrong id rejected", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    await resetPackState(request, PACK);
    await resetPackState(request, WRONG_PACK);
    const project = await createTempProject(request, `Pack Link ${Date.now()}`);
    const empty = makeTempDir("adept-link-empty-");
    const valid = makeTempDir("adept-link-valid-");
    const wrong = makeTempDir("adept-link-wrong-");
    writeLinkFixture(valid, { packId: PACK });
    writeLinkFixture(wrong, { packId: "pack_essential_wrong" });

    try {
      await openSetup(page, project.id);

      const emptyOp = await startLinkExisting(page, PACK);
      await answerCheckpoint(request, emptyOp.operation_id, empty);
      await expect
        .poll(async () => {
          const res = await request.get(`${API}/api/setup/operations/${emptyOp.operation_id}`);
          const body = await res.json();
          return JSON.stringify(body);
        }, { timeout: 30_000 })
        .toMatch(/pack\.json|Empty folders|No pack files|missing/i);

      await resetPackState(request, PACK);
      await openSetup(page, project.id);
      const validOp = await startLinkExisting(page, PACK);
      await answerCheckpoint(request, validOp.operation_id, valid);
      await expect
        .poll(async () => {
          const status = await request.get(`${API}/api/setup/status`);
          const body = await status.json();
          const comp = body.components.find((c: { id: string }) => c.id === PACK);
          return comp?.status;
        }, { timeout: 60_000 })
        .toBe("ready");

      const before = fs.readFileSync(`${wrong}/pack.json`, "utf8");
      await resetPackState(request, WRONG_PACK);
      await openSetup(page, project.id);
      const wrongOp = await startLinkExisting(page, WRONG_PACK);
      await answerCheckpoint(request, wrongOp.operation_id, wrong);
      await expect
        .poll(async () => {
          const res = await request.get(`${API}/api/setup/operations/${wrongOp.operation_id}`);
          const body = await res.json();
          return JSON.stringify(body);
        }, { timeout: 30_000 })
        .toMatch(/pack id|does not match|wrong|mismatch|invalid/i);
      expect(fs.readFileSync(`${wrong}/pack.json`, "utf8")).toBe(before);

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
      for (const dir of [empty, valid, wrong]) {
        try {
          fs.rmSync(dir, { recursive: true, force: true });
        } catch {
          /* ignore */
        }
      }
    }
  });
});
