import { expect, test } from "@playwright/test";
import { API, waitForAppReady } from "../helpers/app";

/**
 * M3.0 Completion Phase 5 - real local ComfyUI artifact through the Adept ImageGen path.
 *
 * This spec never fixtures. It drives `POST /api/projects/{id}/imagegen`, the same endpoint
 * `studio-web`'s `api.imagegen()` calls, and asserts that a real file lands on disk with a
 * matching Asset row. It therefore needs an actual ComfyUI at 127.0.0.1:8188 with the
 * catalogued Z-Image Turbo stack installed, so it is opt-in via ADEPT_M30A_LOCAL_LIVE=1.
 */

const LIVE = process.env.ADEPT_M30A_LOCAL_LIVE === "1";
const PROMPT =
  "cinematic wide shot of a lone lighthouse on a rocky coast at dusk, storm clouds, volumetric light, film grain, 35mm";

test.describe("M3.0 completion local ComfyUI artifact @critical", () => {
  test.skip(!LIVE, "Set ADEPT_M30A_LOCAL_LIVE=1 with a real local ComfyUI + Z-Image stack to run.");

  test.beforeEach(async ({ request }) => {
    await waitForAppReady(request);
  });

  test("local ImageGen readiness is reported before any submit", async ({ request }) => {
    const health = await request.get(`${API}/api/health`);
    expect(health.ok()).toBeTruthy();
    const healthBody = await health.json();
    expect(healthBody.comfy_reachable).toBe(true);
    expect(healthBody.comfy_status).toBe("ready");

    const caps = await request.get(`${API}/api/capabilities`);
    expect(caps.ok()).toBeTruthy();
    const capabilities = (await caps.json()).capabilities as Record<string, unknown>[];
    const byId = new Map(capabilities.map((c) => [String(c.id), c]));
    // A local proof is only meaningful when the still-image stack really verifies on disk.
    for (const id of ["models.image.ready", "workflows.image.ready", "generation.image.queue"]) {
      expect(byId.get(id), `missing capability ${id}`).toBeTruthy();
      expect(byId.get(id)?.available, `${id} unavailable`).toBe(true);
    }
  });

  test("generates one real artifact with an Asset row and a file on disk", async ({ request }) => {
    test.setTimeout(600_000);

    const created = await request.post(`${API}/api/projects`, {
      data: { name: `M3.0 Local Artifact Proof ${Date.now()}`, width: 1024, height: 1024 },
    });
    expect(created.ok(), await created.text()).toBeTruthy();
    const projectId = (await created.json()).id as string;

    const submitted = await request.post(`${API}/api/projects/${projectId}/imagegen`, {
      data: {
        prompt: PROMPT,
        model: "zimage",
        width: 1024,
        height: 1024,
        seed: 30500,
        tag: "m30-local-proof",
      },
    });
    expect(submitted.ok(), await submitted.text()).toBeTruthy();
    const job = await submitted.json();
    expect(job.kind).toBe("imagegen");
    const jobId = job.id as string;

    let final: Record<string, unknown> = {};
    await expect
      .poll(
        async () => {
          const res = await request.get(`${API}/api/jobs/${jobId}`);
          if (!res.ok()) return "pending";
          final = await res.json();
          return String(final.status);
        },
        { timeout: 540_000, intervals: [2_000] },
      )
      .toMatch(/^(done|error|failed|cancelled|canceled)$/);

    // An honest failure names the gap; it must never be papered over with a fixture.
    expect(final.status, String(final.message ?? "")).toBe("done");
    expect(String(final.comfy_prompt_id ?? "").length).toBeGreaterThan(0);

    const history = JSON.parse(String(final.history_json || "{}"));
    expect(history.checkpoint).toContain("z_image_turbo");

    const library = await request.get(`${API}/api/projects/${projectId}/library?scope=project`);
    expect(library.ok()).toBeTruthy();
    const assets = (await library.json()) as Record<string, unknown>[];
    const asset = assets.find((a) => a.tag === "m30-local-proof");
    expect(asset, "no Asset row for the generated image").toBeTruthy();
    expect(asset?.kind).toBe("image");
    expect(asset?.project_id).toBe(projectId);

    // Byte-level proof: the API serves a real PNG, not a zero-length placeholder.
    const file = await request.get(`${API}/api/assets/${asset?.id}/file`);
    expect(file.ok()).toBeTruthy();
    expect(String(file.headers()["content-type"])).toContain("image/png");
    const bytes = await file.body();
    expect(bytes.byteLength).toBeGreaterThan(10_000);
    expect(bytes.subarray(0, 8).toString("hex")).toBe("89504e470d0a1a0a");

    // Provenance survives as a versioned lineage row, which is what inspect reads back.
    const graph = await request.get(`${API}/api/assets/${asset?.id}/graph`);
    expect(graph.ok()).toBeTruthy();
    const graphBody = await graph.json();
    expect(graphBody.versions.length).toBeGreaterThan(0);
    expect(graphBody.versions[0].model).toContain("z_image_turbo");

    await request.delete(`${API}/api/projects/${projectId}`);
  });
});
