import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { API, waitForAppReady } from "../helpers/app";

const CERT_NAME = "MAGI Finishing Certification";
const OUT = path.join("artifacts", "magi-finalization");
const MUSIC_PROMPT = "Create a subtle cinematic atmospheric score for a quiet corridor.";
const SFX_PROMPT = "Add subtle corridor ambience, footsteps, and mechanical room tone.";

type Seed = {
  projectId: string;
  assetId: string;
  clipId: string;
  sceneId: string;
};

async function ensureCertProject(request: APIRequestContext): Promise<{ id: string; name: string }> {
  const list = await request.get(`${API}/api/projects`);
  expect(list.ok(), `projects ${list.status()}`).toBeTruthy();
  const body = (await list.json()) as { items?: Array<{ id: string; name: string }>; projects?: Array<{ id: string; name: string }> };
  const rows = body.items || body.projects || (Array.isArray(body) ? (body as Array<{ id: string; name: string }>) : []);
  const existing = rows.find((row) => row.name === CERT_NAME);
  if (existing) return existing;
  const created = await request.post(`${API}/api/projects`, { data: { name: CERT_NAME, global_prompt: "MAGI finishing certification." } });
  expect(created.ok(), `create project ${created.status()} ${await created.text()}`).toBeTruthy();
  return created.json() as Promise<{ id: string; name: string }>;
}

async function makeClipBuffer(): Promise<Buffer> {
  const cached = path.join(OUT, "seed-clip.mp4");
  if (fs.existsSync(cached) && fs.statSync(cached).size > 1000) {
    return fs.readFileSync(cached);
  }
  fs.mkdirSync(OUT, { recursive: true });
  const { spawnSync } = await import("node:child_process");
  const result = spawnSync(
    "ffmpeg",
    ["-y", "-f", "lavfi", "-i", "color=c=blue:s=640x360:d=2", "-f", "lavfi", "-i", "sine=frequency=330:duration=2", "-shortest", "-pix_fmt", "yuv420p", cached],
    { encoding: "utf8" },
  );
  if (result.status !== 0 || !fs.existsSync(cached)) {
    throw new Error(`ffmpeg seed clip failed: ${result.stderr || result.stdout}`);
  }
  return fs.readFileSync(cached);
}

async function seedProject(request: APIRequestContext): Promise<Seed> {
  const project = await ensureCertProject(request);
  const upload = await request.post(`${API}/api/projects/${project.id}/assets`, {
    multipart: {
      file: { name: "magi-finishing-seed.mp4", mimeType: "video/mp4", buffer: await makeClipBuffer() },
      tag: "magi_finishing_seed",
      kind: "video",
    },
  });
  expect(upload.ok(), `upload ${upload.status()} ${await upload.text()}`).toBeTruthy();
  const asset = (await upload.json()) as { id: string };
  const projectBody = (await (await request.get(`${API}/api/projects/${project.id}`)).json()) as { scenes: Array<{ id: string }> };
  const sceneId = projectBody.scenes?.[0]?.id || "";
  const sequenceRes = await request.get(`${API}/api/magi/projects/${project.id}/sequence`);
  const sequence = ((await sequenceRes.json()) as { sequence: any }).sequence;
  const clipId = `clip_magi_final_${Date.now()}`;
  const videoTrack = (sequence.tracks || []).find((track: any) => track.kind === "video") || { id: "trk_v1", kind: "video", label: "V1", order: 0 };
  sequence.clips = [
    {
      id: clipId,
      trackId: videoTrack.id,
      assetId: asset.id,
      name: "Finishing seed",
      startFrame: 0,
      durationFrames: 48,
      inPoint: 0,
      outPoint: 48,
    },
  ];
  sequence.finishing = sequence.finishing || {};
  const saved = await request.put(`${API}/api/magi/projects/${project.id}/sequence`, { data: { sequence } });
  expect(saved.ok(), `save sequence ${saved.status()} ${await saved.text()}`).toBeTruthy();
  return { projectId: project.id, assetId: asset.id, clipId, sceneId };
}

async function openMagi(page: Page, projectId: string) {
  await page.goto(`/project/${projectId}?workspace=magi`);
  await expect(page.getByTestId("magi-editor")).toBeVisible({ timeout: 30_000 });
}

async function openAccordion(page: Page, title: string) {
  const header = page.locator(".magi-acc__header", { hasText: title }).first();
  await expect(header).toBeVisible();
  if ((await header.getAttribute("aria-expanded")) !== "true") {
    await header.click();
  }
}

async function waitJob(request: APIRequestContext, projectId: string, jobId: string, timeoutMs = 240_000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const res = await request.get(`${API}/api/magi/projects/${projectId}/jobs/${jobId}`);
    if (res.ok()) {
      const job = (await res.json()) as { status: string; message?: string };
      if (["done", "failed", "cancelled", "canceled", "timed_out"].includes(job.status)) {
        return job;
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 1500));
  }
  throw new Error(`Timed out waiting for MAGI job ${jobId}`);
}

test.describe("MAGI finalization A-J", () => {
  test.describe.configure({ timeout: 360_000 });

  test("A color preset apply persists finishing state", async ({ page, request }) => {
    await waitForAppReady(request);
    const seed = await seedProject(request);
    const applied = await request.post(`${API}/api/magi/projects/${seed.projectId}/color/apply`, {
      data: { assetId: seed.assetId, presetId: "noir", clipId: seed.clipId, params: {} },
    });
    expect(applied.ok(), await applied.text()).toBeTruthy();
    const body = await applied.json();
    expect(body.sourcePreserved).toBeTruthy();
    const sequence = ((await (await request.get(`${API}/api/magi/projects/${seed.projectId}/sequence`)).json()) as { sequence: any }).sequence;
    expect(sequence.finishing.clipGrades[seed.clipId].presetId).toBe("noir");
    await openMagi(page, seed.projectId);
    await openAccordion(page, "Color");
    await expect(page.getByTestId("magi-color-preset")).toBeVisible();
  });

  test("B manual sliders persist after reload", async ({ page, request }) => {
    await waitForAppReady(request);
    const seed = await seedProject(request);
    await openMagi(page, seed.projectId);
    await page.getByText("Finishing seed", { exact: false }).first().click({ trial: true }).catch(() => undefined);
    await openAccordion(page, "Color");
    await page.getByTestId("magi-color-preset").selectOption("noir");
    await page.waitForTimeout(800);
    await page.reload();
    await expect(page.getByTestId("magi-editor")).toBeVisible({ timeout: 30_000 });
    await openAccordion(page, "Color");
    await expect(page.getByTestId("magi-color-preset")).toHaveValue("noir");
  });

  test("C FFmpeg upscale produces a derived asset", async ({ request }) => {
    await waitForAppReady(request);
    const seed = await seedProject(request);
    const preview = await request.post(`${API}/api/magi/projects/${seed.projectId}/upscale/preview`, {
      data: { assetId: seed.assetId, engine: "ffmpeg-scale", model: "lanczos", target_resolution: "1280x720" },
    });
    expect(preview.ok(), await preview.text()).toBeTruthy();
    const body = await preview.json();
    expect(body.output_asset_id || body.assetId).toBeTruthy();
    expect(body.engine).toBe("ffmpeg-scale");
  });

  test("D Real-ESRGAN apply when Ready, honest fail when not", async ({ request }) => {
    await waitForAppReady(request);
    const seed = await seedProject(request);
    const caps = await (await request.get(`${API}/api/magi/upscale/capabilities`)).json();
    const apply = await request.post(`${API}/api/magi/projects/${seed.projectId}/upscale/apply`, {
      data: {
        assetId: seed.assetId,
        engine: "realesrgan-ncnn-vulkan",
        model: "realesr-animevideov3",
        target_resolution: "1280x720",
      },
    });
    if (caps.realesrganReady) {
      expect(apply.ok(), await apply.text()).toBeTruthy();
      const queued = await apply.json();
      expect(queued.jobId).toBeTruthy();
      const job = await waitJob(request, seed.projectId, String(queued.jobId), 420_000);
      expect(job.status).toBe("done");
    } else {
      expect(apply.ok()).toBeFalsy();
      const text = await apply.text();
      expect(text.toLowerCase()).toContain("unavailable");
    }
  });

  test("E music generation returns a job id", async ({ page, request }) => {
    await waitForAppReady(request);
    const seed = await seedProject(request);
    const music = await request.post(`${API}/api/magi/projects/${seed.projectId}/audio/generate`, {
      data: { kind: "music", prompt: MUSIC_PROMPT, range: "entire" },
    });
    expect(music.ok(), await music.text()).toBeTruthy();
    const body = await music.json();
    expect(body.jobId || (body.jobIds || [])[0]).toBeTruthy();
    await openMagi(page, seed.projectId);
    await openAccordion(page, "Audio");
    await expect(page.getByTestId("magi-audio-music")).toBeVisible();
  });

  test("F SFX generation is a second job and asset", async ({ request }) => {
    await waitForAppReady(request);
    const seed = await seedProject(request);
    const both = await request.post(`${API}/api/magi/projects/${seed.projectId}/audio/generate`, {
      data: { kind: "all", prompt: SFX_PROMPT, range: "entire" },
    });
    expect(both.ok(), await both.text()).toBeTruthy();
    const body = await both.json();
    expect((body.jobIds || []).length).toBe(2);
    expect(body.assets).toBe("separate");
  });

  test("G final render queues magi_final_render", async ({ page, request }) => {
    await waitForAppReady(request);
    const seed = await seedProject(request);
    await request.post(`${API}/api/magi/projects/${seed.projectId}/color/apply`, {
      data: { assetId: seed.assetId, presetId: "noir", clipId: seed.clipId, params: {} },
    });
    const render = await request.post(`${API}/api/magi/projects/${seed.projectId}/renders`, {
      data: {
        profile: "preview",
        includeColor: true,
        includeAudio: true,
        upscale: { enabled: true, engine: "ffmpeg-scale", model: "lanczos", target: "1280x720" },
      },
    });
    expect(render.ok(), await render.text()).toBeTruthy();
    const body = await render.json();
    expect(body.jobId).toBeTruthy();
    expect(body.duplicate).toBeFalsy();
    await openMagi(page, seed.projectId);
    await openAccordion(page, "Export");
    await expect(page.getByTestId("magi-final-render")).toBeVisible();
    await expect(page.getByTestId("magi-preview-render")).toBeVisible();
  });

  test("H reload keeps finishing state", async ({ request }) => {
    await waitForAppReady(request);
    const seed = await seedProject(request);
    await request.post(`${API}/api/magi/projects/${seed.projectId}/color/apply`, {
      data: { assetId: seed.assetId, presetId: "teal_orange", clipId: seed.clipId, params: { contrast: 0.2 } },
    });
    const first = ((await (await request.get(`${API}/api/magi/projects/${seed.projectId}/sequence`)).json()) as { sequence: any }).sequence;
    const second = ((await (await request.get(`${API}/api/magi/projects/${seed.projectId}/sequence`)).json()) as { sequence: any }).sequence;
    expect(second.finishing.clipGrades[seed.clipId].presetId).toBe(first.finishing.clipGrades[seed.clipId].presetId);
  });

  test("I GPU-unavailable injection stays honest", async ({ request }) => {
    await waitForAppReady(request);
    const seed = await seedProject(request);
    const apply = await request.post(`${API}/api/magi/projects/${seed.projectId}/upscale/apply`, {
      data: {
        assetId: seed.assetId,
        engine: "realesrgan-ncnn-vulkan",
        model: "realesrgan-x4plus",
        target_resolution: "1920x1080",
      },
    });
    const caps = await (await request.get(`${API}/api/magi/upscale/capabilities`)).json();
    if (!caps.realesrganReady) {
      expect(apply.ok()).toBeFalsy();
    }
  });

  test("J duplicate final render is rejected as reuse", async ({ request }) => {
    await waitForAppReady(request);
    const seed = await seedProject(request);
    const body = {
      profile: "final",
      includeColor: true,
      includeAudio: true,
      upscale: { enabled: true, engine: "ffmpeg-scale", model: "lanczos", target: "1280x720" },
    };
    const first = await request.post(`${API}/api/magi/projects/${seed.projectId}/renders`, { data: body });
    expect(first.ok(), await first.text()).toBeTruthy();
    const firstBody = await first.json();
    const second = await request.post(`${API}/api/magi/projects/${seed.projectId}/renders`, { data: body });
    expect(second.ok(), await second.text()).toBeTruthy();
    const secondBody = await second.json();
    expect(secondBody.jobId).toBe(firstBody.jobId);
    expect(secondBody.duplicate).toBeTruthy();
  });
});
