import { test, expect, type APIRequestContext } from "@playwright/test";
import { API, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";

/**
 * M3.0 Completion Phase 1 (blocker B4): imported audio must reach the Director timeline.
 *
 * Runs against the live stack the browser uses, through the same HTTP surface the UI calls,
 * so a pass means the deployed API — not just the service class — writes `director_json`.
 * A fixture-generated cue names no file and must stay off the timeline.
 */

/** Real RIFF/WAVE bytes; the API refuses anything that is not a genuine WAV. */
function makeWavBase64(seconds = 1.0, rate = 48000): string {
  const frames = Math.floor(rate * seconds);
  const dataBytes = frames * 2;
  const buf = Buffer.alloc(44 + dataBytes);
  buf.write("RIFF", 0, "ascii");
  buf.writeUInt32LE(36 + dataBytes, 4);
  buf.write("WAVE", 8, "ascii");
  buf.write("fmt ", 12, "ascii");
  buf.writeUInt32LE(16, 16); // PCM chunk size
  buf.writeUInt16LE(1, 20); // PCM
  buf.writeUInt16LE(1, 22); // mono
  buf.writeUInt32LE(rate, 24);
  buf.writeUInt32LE(rate * 2, 28); // byte rate
  buf.writeUInt16LE(2, 32); // block align
  buf.writeUInt16LE(16, 34); // bits per sample
  buf.write("data", 36, "ascii");
  buf.writeUInt32LE(dataBytes, 40);
  for (let i = 0; i < frames; i += 1) {
    buf.writeInt16LE(Math.round(6000 * Math.sin((2 * Math.PI * 440 * i) / rate)), 44 + i * 2);
  }
  return buf.toString("base64");
}

async function operatorFlags(request: APIRequestContext) {
  const res = await request.get(`${API}/api/health`);
  expect(res.ok()).toBeTruthy();
  return (await res.json()).operator as Record<string, boolean>;
}

async function createScene(request: APIRequestContext, projectId: string) {
  const res = await request.post(`${API}/api/projects/${projectId}/scenes`, {
    data: { name: "B4 Sound Scene", prompt: "Empty studio at dawn", duration_sec: 6 },
  });
  expect(res.ok()).toBeTruthy();
  return res.json() as Promise<{ id: string }>;
}

async function getDirector(request: APIRequestContext, projectId: string, sceneId: string) {
  const res = await request.get(`${API}/api/projects/${projectId}/scenes/${sceneId}/director`);
  expect(res.ok()).toBeTruthy();
  return res.json() as Promise<{
    audio_clips: Array<{ asset_id: string; start: number; length: number; volume: number }>;
    sfx_clips: Array<{ asset_id: string; start: number; length: number; volume: number }>;
  }>;
}

test.describe("@critical m30-completion audio to Director timeline (B4)", () => {
  test.beforeEach(async ({ request }) => {
    await waitForAppReady(request);
    const flags = await operatorFlags(request);
    test.skip(
      !flags.audioProductionEnabled || !flags.directorTimelineEnabled,
      "STUDIO_FEATURE_AUDIO_PRODUCTION_V1 / _DIRECTOR_TIMELINE_V1 off in this environment",
    );
  });

  test("imported WAV becomes an sfx clip in director_json", async ({ request }) => {
    const project = await createTempProject(request, `B4 Audio ${Date.now()}`);
    try {
      const scene = await createScene(request, project.id);
      const before = await getDirector(request, project.id, scene.id);
      expect(before.sfx_clips).toHaveLength(0);

      const res = await request.post(`${API}/api/codirector/m29/audio/import`, {
        data: {
          projectId: project.id,
          contentBase64: makeWavBase64(1.25),
          filename: "door-slam.wav",
          kind: "sfx",
          sceneId: scene.id,
          startSec: 2,
        },
      });
      expect(res.ok()).toBeTruthy();
      const imported = await res.json();
      expect(imported.imported).toBe(true);
      expect(imported.fixture).toBe(false);
      expect(imported.timelinePlaced).toBe(true);
      expect(imported.sha256).toMatch(/^[0-9a-f]{64}$/);

      const after = await getDirector(request, project.id, scene.id);
      expect(after.sfx_clips).toHaveLength(1);
      expect(after.sfx_clips[0].asset_id).toBe(imported.assetId);
      expect(after.sfx_clips[0].start).toBeCloseTo(2, 3);
      expect(after.sfx_clips[0].length).toBeCloseTo(1.25, 2);

      // The asset is downloadable, so the clip points at bytes that really exist.
      const file = await request.get(`${API}/api/assets/${imported.assetId}/file`);
      expect(file.ok()).toBeTruthy();
      expect((await file.body()).byteLength).toBeGreaterThan(1000);
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("promote moves an unplaced cue onto the timeline and gain revision updates it", async ({
    request,
  }) => {
    const project = await createTempProject(request, `B4 Promote ${Date.now()}`);
    try {
      const scene = await createScene(request, project.id);

      const imported = await (
        await request.post(`${API}/api/codirector/m29/audio/import`, {
          data: {
            projectId: project.id,
            contentBase64: makeWavBase64(0.75),
            kind: "music",
            filename: "bed.wav",
          },
        })
      ).json();
      expect(imported.timelinePlaced).toBe(false);
      expect((await getDirector(request, project.id, scene.id)).audio_clips).toHaveLength(0);

      const promoted = await request.post(
        `${API}/api/codirector/m29/audio/cues/${imported.cueId}/promote`,
        { data: { projectId: project.id, sceneId: scene.id, volume: 0.8 } },
      );
      expect(promoted.ok()).toBeTruthy();
      expect((await promoted.json()).timelinePlaced).toBe(true);

      let director = await getDirector(request, project.id, scene.id);
      expect(director.audio_clips).toHaveLength(1);
      expect(director.audio_clips[0].volume).toBeCloseTo(0.8, 3);

      const gain = await request.post(
        `${API}/api/codirector/m29/audio/cues/${imported.cueId}/gain`,
        { data: { projectId: project.id, volume: 0.3 } },
      );
      expect(gain.ok()).toBeTruthy();

      director = await getDirector(request, project.id, scene.id);
      expect(director.audio_clips).toHaveLength(1);
      expect(director.audio_clips[0].volume).toBeCloseTo(0.3, 3);
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("a fixture-generated cue is never placed on the timeline", async ({ request }) => {
    const project = await createTempProject(request, `B4 Fixture ${Date.now()}`);
    try {
      const scene = await createScene(request, project.id);
      const res = await request.post(`${API}/api/codirector/m29/audio/generate`, {
        data: {
          projectId: project.id,
          kind: "sfx",
          prompt: "door slam",
          sceneId: scene.id,
        },
      });
      expect(res.ok()).toBeTruthy();
      const generated = await res.json();
      expect(generated.timelinePlaced ?? false).toBe(false);

      const director = await getDirector(request, project.id, scene.id);
      expect(director.sfx_clips).toHaveLength(0);

      if (generated.cueId) {
        const promote = await request.post(
          `${API}/api/codirector/m29/audio/cues/${generated.cueId}/promote`,
          { data: { projectId: project.id, sceneId: scene.id } },
        );
        expect(promote.status()).toBe(409);
      }
    } finally {
      await deleteProject(request, project.id);
    }
  });
});
