/**
 * Adept UI LoRA Support — video runtime-load certification (live).
 * LTX 2.3 batch render through the W46 Timeline adapter with a registered
 * LTX LoRA; verifies the Comfy graph carries LoraLoaderModelOnly with the
 * registered file and that the render succeeds with lora provenance.
 */
import { expect, test, type APIRequestContext } from "@playwright/test";
import { deleteProject } from "../helpers/app";
import { API, createProjectResilient, waitForApi, waitForComfy } from "./loraHelpers";

const TINY_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC",
  "base64",
);

async function pollJob(request: APIRequestContext, jobId: string, timeoutMs = 720000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const res = await request.get(`${API}/api/jobs/${jobId}`);
    expect(res.ok()).toBeTruthy();
    const job = (await res.json()) as { status: string; message?: string; comfy_prompt_id?: string; params_json?: string };
    if (job.status === "done") return job;
    if (job.status === "failed") throw new Error(`video job failed: ${job.message}`);
    await new Promise((resolve) => setTimeout(resolve, 6000));
  }
  throw new Error("video job timeout");
}

async function comfyHistory(request: APIRequestContext, promptId: string) {
  const res = await request.get(`http://127.0.0.1:8188/history/${promptId}`);
  expect(res.ok()).toBeTruthy();
  const data = (await res.json()) as Record<string, any>;
  const entry = data[promptId];
  const raw = entry?.prompt;
  const graph = Array.isArray(raw) ? raw[2] : raw;
  return { prompt: graph || {}, outputs: entry?.outputs || {} };
}

test.describe("LoRA video runtime certification (live)", () => {
  let projectId = "";
  let ltxLoraId = "";
  let sceneId = "";
  let batchId = "";

  test.beforeAll(async ({ request }) => {
    await waitForApi(request);
    await waitForComfy(request);
    projectId = await createProjectResilient(request, "LoRA Video Cert");
    const list = (await (await request.get(`${API}/api/loras`)).json()) as { loras: any[] };
    const ltx = list.loras.find((l) => l.model_family === "ltx" && l.enabled);
    expect(ltx, "an enabled LTX LoRA must be registered").toBeTruthy();
    ltxLoraId = ltx.id;
    // Upload a start frame for the LTX I2V render.
    const up = await request.post(`${API}/api/projects/${projectId}/assets`, {
      multipart: {
        file: { name: "start.png", mimeType: "image/png", buffer: TINY_PNG },
        tag: "start_frame",
        kind: "image",
      },
    });
    expect(up.ok(), `upload failed: ${await up.text()}`).toBeTruthy();
    const asset = (await up.json()) as { id: string };
    const scene = await request.post(`${API}/api/projects/${projectId}/scenes`, {
      data: { name: "LTX LoRA Cert", prompt: "slow push-in on a harbor at dusk", engine: "ltx", duration_sec: 2 },
    });
    expect(scene.ok(), `scene create failed: ${await scene.text()}`).toBeTruthy();
    sceneId = ((await scene.json()) as any).id;
    const patch = await request.patch(`${API}/api/projects/${projectId}/scenes/${sceneId}`, {
      data: { start_asset_id: asset.id },
    });
    expect(patch.ok(), `scene patch failed: ${await patch.text()}`).toBeTruthy();
    // Materialize the W46 Timeline master (migration creates the batch).
    const master = await request.get(
      `${API}/api/director-timeline/projects/${projectId}/scenes/${sceneId}/master`
    );
    expect(master.ok(), `master failed: ${await master.text()}`).toBeTruthy();
    const masterJson = (await master.json()) as { master: { batchBlocks: Array<{ id: string }> } };
    expect(masterJson.master.batchBlocks.length).toBeGreaterThan(0);
    batchId = masterJson.master.batchBlocks[0].id;
    // Pin the LTX generator + attach the LoRA to the batch (the drawer writes
    // the same payload through directorTimelinePatchBatch).
    const bp = await request.patch(
      `${API}/api/director-timeline/projects/${projectId}/scenes/${sceneId}/batches/${batchId}`,
      { data: { generatorId: "ltx-local", lora: { loraId: ltxLoraId, name: "LTX Motion", strength: 0.6 } } },
    );
    expect(bp.ok(), `batch patch failed: ${await bp.text()}`).toBeTruthy();
  });

  test.afterAll(async ({ request }) => {
    if (projectId) await deleteProject(request, projectId).catch(() => undefined);
  });

  test("LTX batch render with LoRA loads the registered LoRA in the Comfy graph and records provenance", async ({ request }) => {
    const gen = await request.post(
      `${API}/api/director-timeline/projects/${projectId}/scenes/${sceneId}/batches/${batchId}/generate`,
      { data: { draftMode: false }, timeout: 60000 },
    );
    expect(gen.ok(), `batch generate failed: ${await gen.text()}`).toBeTruthy();
    const queued = (await gen.json()) as { queueJobId?: string; internalJobId?: string; status?: string };
    const jobId = queued.queueJobId || queued.internalJobId;
    expect(jobId, "batch generate must return a queue job id").toBeTruthy();
    const job = await pollJob(request, jobId);
    const params = JSON.parse(job.params_json || "{}");
    expect(params.lora_provenance?.loraId).toBe(ltxLoraId);
    expect(params.lora_provenance?.strength).toBe(0.6);
    const history = await comfyHistory(request, job.comfy_prompt_id || "");
    const nodes = Object.values(history.prompt) as Array<{ class_type?: string; inputs?: any }>;
    const loraNode = nodes.find((n) => (n.class_type || "").includes("LoraLoaderModelOnly"));
    expect(loraNode, "LTX graph must include LoraLoaderModelOnly").toBeTruthy();
    expect(loraNode.inputs.strength_model).toBe(0.6);
    expect(typeof loraNode.inputs.lora_name).toBe("string");
    expect(loraNode.inputs.lora_name.length).toBeGreaterThan(0);
    // Video actually produced.
    expect(Object.keys(history.outputs || {}).length).toBeGreaterThan(0);
  });
});