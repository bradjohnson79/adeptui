import path from "node:path";
import { expect, test, type APIRequestContext, type ConsoleMessage, type Page, type Request } from "@playwright/test";
import { API, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";

const OUT = path.join("artifacts", "magi-operational-integrity");

const TINY_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64",
);

type Seed = { projectId: string; assetId: string; sceneId: string; clipId: string };

async function seedProject(request: APIRequestContext, name: string): Promise<Seed> {
  const project = await createTempProject(request, name);
  const upload = await request.post(`${API}/api/projects/${project.id}/assets`, {
    multipart: {
      file: { name: "shot.png", mimeType: "image/png", buffer: TINY_PNG },
      tag: "shot",
      kind: "image",
    },
  });
  expect(upload.ok()).toBeTruthy();
  const asset = (await upload.json()) as { id: string };
  const projectBody = await (await request.get(`${API}/api/projects/${project.id}`)).json();
  const sceneId = projectBody.scenes[0].id;
  expect(sceneId).toBeTruthy();
  return { projectId: project.id, assetId: asset.id, sceneId, clipId: `clip_cert_${Date.now()}` };
}

function sequenceBody(projectId: string, assetId: string, clipId: string) {
  return {
    id: `seq_cert_${projectId}`,
    projectId,
    frameRate: 24,
    durationFrames: 24 * 60,
    playheadFrame: 0,
    tracks: [
      { id: "trk_v1", kind: "video", label: "V1", order: 0 },
      { id: "trk_a1", kind: "audio", label: "A1", order: 1 },
      { id: "trk_t1", kind: "text", label: "T1", order: 2 },
    ],
    clips: [
      {
        id: clipId,
        trackId: "trk_v1",
        assetId,
        name: "Cert shot",
        startFrame: 0,
        durationFrames: 120,
        inPoint: 0,
        outPoint: 120,
      },
    ],
    markers: [],
    snapEnabled: true,
    revision: 1,
    updatedAt: new Date().toISOString(),
    recipeId: null,
  };
}

async function seedSequence(request: APIRequestContext, seed: Seed, expectedRevision = 1) {
  const res = await request.put(`${API}/api/magi/projects/${seed.projectId}/sequence`, {
    data: { sequence: sequenceBody(seed.projectId, seed.assetId, seed.clipId) },
  });
  expect(res.ok(), `seed sequence ${res.status()} ${await res.text()}`).toBeTruthy();
  const body = (await res.json()) as { sequence: { revision: number } };
  expect(body.sequence.revision).toBe(expectedRevision);
  return body.sequence;
}

async function openMagi(page: Page, projectId: string) {
  await page.goto(`/project/${projectId}?workspace=magi`);
  await expect(page.getByTestId("magi-editor")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("magi-sequence-timeline")).toBeVisible();
}

function statusMessages(page: Page) {
  return page.locator('.magi-msg[role="status"]');
}

test.describe("MAGI Operational Integrity (real backend)", () => {
  test("OP-01 workspace surface: banner, docks, accordions, render queue, fullscreen distinction", async ({
    page,
    request,
  }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `MAGI Cert Layout ${Date.now()}`);
    const consoleErrors: string[] = [];
    const requestFailures: string[] = [];
    const onConsole = (msg: ConsoleMessage) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    };
    const onReqFail = (req: Request) => {
      const failure = req.failure();
      if (!failure) return;
      // Superseded fetches abort by design: React StrictMode double-mounts the
      // project editor, and the second refresh() aborts the first's in-flight
      // GET via AbortController (ROUTING CONTRACT in ProjectEditor). The app
      // treats that abort as a graceful supersede, not a genuine failure.
      if (failure.errorText === "net::ERR_ABORTED") return;
      requestFailures.push(`${req.url()} :: ${failure.errorText || "failed"}`);
    };
    page.on("console", onConsole);
    page.on("requestfailed", onReqFail);
    try {
      await openMagi(page, project.id);

      // Banner copy renders without being clipped into a one-line scroll.
      await expect(page.getByTestId("magi-strip")).toBeVisible();
      await expect(page.getByTestId("magi-strip-copy")).toContainText(/MAGI Editor/);

      // Fullscreen: workspace-level control is distinct from the viewer focus toggle.
      const workspaceFs = page.getByTestId("workspace-fullscreen-toggle-magi");
      const viewerFs = page.getByTestId("timeline-viewer-fullscreen");
      await expect(workspaceFs).toBeVisible();
      await expect(viewerFs).toBeVisible();
      await expect(workspaceFs).toHaveAttribute("aria-label", /Full screen/i);
      await expect(viewerFs).toHaveAttribute("aria-label", /Viewer to focus mode/i);

      // Dock toggles and reset workspace.
      const leftDock = page.getByTestId("magi-toggle-left-dock");
      const rightDock = page.getByTestId("magi-toggle-right-dock");
      const reset = page.getByTestId("magi-reset-workspace");
      await expect(leftDock).toBeVisible();
      await expect(rightDock).toBeVisible();
      await expect(reset).toBeVisible();
      await leftDock.click();
      await expect(leftDock).toHaveText(/Show bins/);
      await leftDock.click();
      await expect(leftDock).toHaveText(/Hide bins/);
      await rightDock.click();
      await expect(rightDock).toHaveText(/Show inspector/);
      await rightDock.click();
      await reset.click();
      await expect(page.getByTestId("magi-editor")).toBeVisible();

      // Inspector accordions: high-frequency edits one click away; Clip Properties
      // and Export present; legacy Metadata accordion is gone.
      for (const id of ["transform", "color", "clipProperties", "export"]) {
        await expect(page.locator(`.magi-acc[data-accordion-id="${id}"]`)).toBeVisible();
      }
      await expect(page.locator('.magi-acc[data-accordion-id="metadata"]')).toHaveCount(0);

      // Export accordion opens and hosts a real Send to Timeline button.
      await page.locator("#magi-acc-btn-export").click();
      await expect(page.getByTestId("magi-inspector-export")).toBeVisible();

      // Render queue is collapsible and collapsed by default.
      const queue = page.getByTestId("magi-render-queue");
      await expect(queue.locator(".magi-queue__toggle")).toHaveAttribute("aria-expanded", "false");
      await queue.locator(".magi-queue__toggle").click();
      await expect(queue.locator(".magi-queue__toggle")).toHaveAttribute("aria-expanded", "true");

      await page.screenshot({ path: path.join(OUT, "op-01-workspace.png"), fullPage: true });
    } finally {
      page.off("console", onConsole);
      page.off("requestfailed", onReqFail);
      await deleteProject(request, project.id);
    }
    expect(consoleErrors, consoleErrors.join("\n")).toEqual([]);
    expect(requestFailures, requestFailures.join("\n")).toEqual([]);
  });

  test("OP-02 Clip Properties shows real clip data loaded from the server", async ({ page, request }) => {
    await waitForAppReady(request);
    const seed = await seedProject(request, `MAGI Cert Props ${Date.now()}`);
    try {
      await seedSequence(request, seed);
      await openMagi(page, seed.projectId);

      const clip = page.getByTestId(`magi-clip-${seed.clipId}`);
      await expect(clip).toBeVisible();
      await clip.click();

      await page.locator("#magi-acc-btn-clipProperties").click();
      const panel = page.locator("#magi-acc-panel-clipProperties");
      await expect(panel).toBeVisible();
      await expect(panel.locator('input[readonly]')).toHaveValue("Cert shot");
      await expect(panel).toContainText("Start:");
      await expect(panel).toContainText("Duration:");
    } finally {
      await deleteProject(request, seed.projectId);
    }
  });

  test("OP-03 real save round-trip: an edit autosaves and bumps server revision", async ({ page, request }) => {
    await waitForAppReady(request);
    const seed = await seedProject(request, `MAGI Cert Save ${Date.now()}`);
    try {
      await seedSequence(request, seed, 1);
      await openMagi(page, seed.projectId);
      await expect(page.getByTestId(`magi-clip-${seed.clipId}`)).toBeVisible();

      await page.getByRole("button", { name: "Add marker" }).click();

      await expect
        .poll(async () => {
          const res = await request.get(`${API}/api/magi/projects/${seed.projectId}/sequence`);
          if (!res.ok()) return false;
          const body = (await res.json()) as {
            sequence: { revision: number; markers: Array<{ label: string }> };
          };
          return (
            body.sequence.revision >= 2 &&
            body.sequence.markers.some((m) => m.label === "Beat")
          );
        }, { timeout: 30_000 })
        .toBe(true);
    } finally {
      await deleteProject(request, seed.projectId);
    }
  });

  test("OP-04 export to Timeline places clips on the W46 batch and records the ledger", async ({
    page,
    request,
  }) => {
    await waitForAppReady(request);
    const seed = await seedProject(request, `MAGI Cert Export ${Date.now()}`);
    try {
      await seedSequence(request, seed);
      await openMagi(page, seed.projectId);

      await page.locator("#magi-acc-btn-export").click();
      await expect(page.getByTestId("magi-inspector-export")).toBeVisible();
      await page.getByTestId("magi-inspector-export").click();

      await expect(
        statusMessages(page).filter({ hasText: /Exported 1 clip/ }),
      ).toHaveCount(1, { timeout: 30_000 });

      const master = await request.get(
        `${API}/api/director-timeline/projects/${seed.projectId}/scenes/${seed.sceneId}/master`,
      );
      expect(master.ok()).toBeTruthy();
      const masterBody = (await master.json()) as {
        master: {
          batchBlocks: Array<{
            id: string;
            visualClips: Array<{ legacyClipId?: string }>;
            audioClips: Array<{ legacyClipId?: string }>;
            sfxClips: Array<{ legacyClipId?: string }>;
          }>;
        };
      };
      const blocks = masterBody.master.batchBlocks;
      const placed = blocks.some((block) =>
        [...block.visualClips, ...block.audioClips, ...block.sfxClips].some(
          (clip) => clip.legacyClipId === seed.clipId,
        ),
      );
      expect(placed).toBeTruthy();

      const seq = await (await request.get(`${API}/api/magi/projects/${seed.projectId}/sequence`)).json();
      const ledger = (seq.sequence?.exportLedger || {}) as Record<string, { clips?: Array<{ clipId?: string }> }>;
      const entries = Object.values(ledger);
      expect(entries.some((entry) => (entry.clips || []).some((c) => c.clipId === seed.clipId))).toBeTruthy();
    } finally {
      await deleteProject(request, seed.projectId);
    }
  });

  test("OP-05 error taxonomy: structured envelopes, never raw traces", async ({ page, request }) => {
    await waitForAppReady(request);
    const seed = await seedProject(request, `MAGI Cert Errors ${Date.now()}`);
    try {
      // Revision conflict (genuine trigger).
      await seedSequence(request, seed, 1);
      const second = await request.put(`${API}/api/magi/projects/${seed.projectId}/sequence`, {
        data: { sequence: sequenceBody(seed.projectId, seed.assetId, seed.clipId), expectedRevision: 1 },
      });
      expect(second.ok()).toBeTruthy();
      const stale = await request.put(`${API}/api/magi/projects/${seed.projectId}/sequence`, {
        data: { sequence: sequenceBody(seed.projectId, seed.assetId, seed.clipId), expectedRevision: 1 },
      });
      expect(stale.status()).toBe(409);
      const staleBody = (await stale.json()) as { detail: { error: { code: string; message: string } } };
      expect(staleBody.detail.error.code).toBe("REVISION_CONFLICT");
      expect(staleBody.detail.error.message).toContain("changed on the server");

      // Unknown clipId on export → genuine CLIP_NOT_FOUND.
      const bogus = await request.post(
        `${API}/api/magi/projects/${seed.projectId}/scenes/${seed.sceneId}/timeline/export`,
        { data: { clips: [{ clipId: "clip_does_not_exist", assetId: seed.assetId }] } },
      );
      expect(bogus.status()).toBe(404);
      const bogusBody = (await bogus.json()) as { detail: { error: { code: string; message: string } } };
      expect(bogusBody.detail.error.code).toBe("CLIP_NOT_FOUND");
      expect(bogusBody.detail.error.message).toContain("clip_does_not_exist");

      // Frontend renders the creator-facing taxonomy message when an autosave is refused.
      await openMagi(page, seed.projectId);
      await page.route(`**/api/magi/projects/${seed.projectId}/sequence`, async (route) => {
        if (route.request().method() === "PUT") {
          await route.fulfill({
            status: 409,
            json: {
              detail: {
                error: {
                  code: "REVISION_CONFLICT",
                  message: "The MAGI sequence changed on the server since it was loaded.",
                  fields: { currentRevision: 3, expectedRevision: 1 },
                },
              },
            },
          });
          return;
        }
        await route.continue();
      });
      const clip = page.getByTestId(`magi-clip-${seed.clipId}`);
      await expect(clip).toBeVisible();
      await clip.click();
      await page.getByRole("button", { name: "Add marker" }).click();
      await expect(
        statusMessages(page).filter({ hasText: /changed on the server/ }),
      ).toHaveCount(1, { timeout: 20_000 });
      await expect(statusMessages(page)).not.toContainText(/at /);
    } finally {
      await deleteProject(request, seed.projectId);
    }
  });
});
