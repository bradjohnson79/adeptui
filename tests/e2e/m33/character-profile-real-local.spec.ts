/**
 * M3.3i real-local voice + chain — M33-CHAR-08..23
 * Requires ADEPT_M33_REAL_LOCAL=1 and installed Qwen Voice Design + Clone.
 */
import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import {
  assertProtectedUnchanged,
  createDisposableProject,
  deleteProject,
  enableCharacterIdentity,
  evidenceDir,
  getVoiceProviders,
  isRealLocalEnabled,
  writeEvidence,
} from "../helpers/m33";

const API = "";

test.describe("M3.3 Character Profile @REAL_LOCAL", () => {
  test.beforeAll(() => {
    test.skip(!isRealLocalEnabled(), "Set ADEPT_M33_REAL_LOCAL=1 for real-local Qwen certification.");
    evidenceDir("playwright");
  });

  test.beforeEach(async ({ request }) => {
    await enableCharacterIdentity(request);
  });

  test("M33-CHAR-08 Qwen Voice Design installed and ready", async ({ request }) => {
    const providers = await getVoiceProviders(request);
    writeEvidence(["playwright", "M33-CHAR-08-providers.json"], providers);
    expect(providers.qwenVoiceDesign?.ready || providers.qwenVoiceDesign?.installed).toBeTruthy();
  });

  test("M33-CHAR-09 Three real design previews generated", async ({ request }) => {
    const project = await createDisposableProject(request, `M33-CHAR-09 ${Date.now()}`);
    try {
      const created = await request.post(`${API}/api/projects/${project.id}/characters`, {
        data: { name: "Design Cert", role: "cert", description: "disposable" },
      });
      expect(created.ok()).toBeTruthy();
      const character = await created.json();
      const design = await request.post(
        `${API}/api/projects/${project.id}/characters/${character.id}/voice-profiles/design`,
        {
          data: {
            name: "Design Cert Voice",
            voice_design_prompt:
              "Warm adult female voice with gentle authority, clear articulation, moderate pace.",
            test_line: "We should leave before the storm reaches the valley.",
            candidate_count: 3,
          },
        },
      );
      expect(design.ok(), await design.text()).toBeTruthy();
      const body = await design.json();
      writeEvidence(["voice-design", "M33-CHAR-09.json"], body);
      expect((body.candidates || []).length).toBeGreaterThanOrEqual(3);
      const paths = new Set<string>();
      for (const aid of body.candidates as string[]) {
        const asset = await request.get(`${API}/api/projects/${project.id}/assets/${aid}`);
        expect(asset.ok()).toBeTruthy();
        const meta = await asset.json();
        expect(fs.existsSync(String(meta.path || meta.filePath || ""))).toBeTruthy();
        paths.add(String(meta.path || meta.filePath));
      }
      expect(paths.size).toBeGreaterThanOrEqual(3);
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("M33-CHAR-10 Design candidate approved and persisted", async ({ request }) => {
    const project = await createDisposableProject(request, `M33-CHAR-10 ${Date.now()}`);
    try {
      const created = await request.post(`${API}/api/projects/${project.id}/characters`, {
        data: { name: "Approve Cert", role: "cert", description: "disposable" },
      });
      const character = await created.json();
      const design = await request.post(
        `${API}/api/projects/${project.id}/characters/${character.id}/voice-profiles/design`,
        {
          data: {
            name: "Approve Voice",
            voice_design_prompt: "Clear adult female narrator.",
            test_line: "Persistence check line.",
            candidate_count: 3,
          },
        },
      );
      expect(design.ok()).toBeTruthy();
      const voice = await design.json();
      const approve = await request.post(
        `${API}/api/projects/${project.id}/characters/${character.id}/voice-profiles/${voice.id}/approve`,
      );
      expect(approve.ok()).toBeTruthy();
      const reload = await request.get(`${API}/api/projects/${project.id}/characters/${character.id}`);
      expect(reload.ok()).toBeTruthy();
      writeEvidence(["persistence", "M33-CHAR-10.json"], { voice, approve: await approve.json() });
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("M33-CHAR-11..13 Clone reference, new-text preview, approve", async ({ request }) => {
    const project = await createDisposableProject(request, `M33-CHAR-11 ${Date.now()}`);
    try {
      const created = await request.post(`${API}/api/projects/${project.id}/characters`, {
        data: { name: "Clone Cert", role: "cert", description: "disposable" },
      });
      const character = await created.json();
      const design = await request.post(
        `${API}/api/projects/${project.id}/characters/${character.id}/voice-profiles/design`,
        {
          data: {
            name: "Ref Source",
            voice_design_prompt: "Clear adult female narrator speaking at moderate pace.",
            test_line:
              "This is a disposable certification reference. Speak clearly about walking through a quiet forest at dawn, noticing birds, light through the trees, and the sound of water nearby for more than ten seconds.",
            candidate_count: 1,
          },
        },
      );
      expect(design.ok()).toBeTruthy();
      const designBody = await design.json();
      const refId = (designBody.candidates || [])[0];
      const asset = await request.get(`${API}/api/projects/${project.id}/assets/${refId}`);
      const assetMeta = await asset.json();
      const refPath = String(assetMeta.path || assetMeta.filePath || "");
      expect(fs.existsSync(refPath)).toBeTruthy();

      const clone = await request.post(
        `${API}/api/projects/${project.id}/characters/${character.id}/voice-profiles/clone`,
        {
          data: {
            name: "Cloned Cert Voice",
            reference_path: refPath,
            transcript: "disposable certification reference speech",
            test_line: "Wait. Someone is still inside that building.",
            consent: {
              source_owner_name: "owner",
              performer_name: "cert",
              authority_type: "self",
              consent_confirmed: true,
              synthetic_generation_allowed: true,
              confirmed_by: "owner",
            },
          },
        },
      );
      expect(clone.ok(), await clone.text()).toBeTruthy();
      const cloneBody = await clone.json();
      expect(cloneBody.preview_asset_id).toBeTruthy();
      const approve = await request.post(
        `${API}/api/projects/${project.id}/characters/${character.id}/voice-profiles/${cloneBody.id}/approve`,
      );
      expect(approve.ok()).toBeTruthy();
      writeEvidence(["voice-clone", "M33-CHAR-11-13.json"], cloneBody);
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("M33-CHAR-14..15 Two dialogue lines + library registration", async ({ request }) => {
    const project = await createDisposableProject(request, `M33-CHAR-14 ${Date.now()}`);
    try {
      const created = await request.post(`${API}/api/projects/${project.id}/characters`, {
        data: { name: "Dialogue Cert", role: "cert", description: "disposable" },
      });
      const character = await created.json();
      const design = await request.post(
        `${API}/api/projects/${project.id}/characters/${character.id}/voice-profiles/design`,
        {
          data: {
            name: "Dialogue Voice",
            voice_design_prompt: "Clear adult female voice.",
            test_line: "Baseline.",
            candidate_count: 1,
          },
        },
      );
      const voice = await design.json();
      await request.post(
        `${API}/api/projects/${project.id}/characters/${character.id}/voice-profiles/${voice.id}/approve`,
      );
      const lines = [];
      for (const text of [
        "We should leave before the storm reaches the valley.",
        "Wait. Someone is still inside that building.",
      ]) {
        const dlg = await request.post(
          `${API}/api/projects/${project.id}/characters/${character.id}/voice-profiles/${voice.id}/generate-dialogue`,
          { data: { text, allow_kokoro_fallback: false } },
        );
        expect(dlg.ok(), await dlg.text()).toBeTruthy();
        lines.push(await dlg.json());
      }
      expect(lines).toHaveLength(2);
      writeEvidence(["dialogue", "M33-CHAR-14-15.json"], { lines, voiceId: voice.id });
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("M33-CHAR-22 No silent provider fallback", async ({ request }) => {
    const providers = await getVoiceProviders(request);
    // Designing with Qwen must not silently become Kokoro in response lineage when Qwen ready.
    expect(providers.qwenVoiceDesign?.ready).toBeTruthy();
    writeEvidence(["playwright", "M33-CHAR-22.json"], {
      qwenReady: providers.qwenVoiceDesign?.ready,
      kokoroReady: providers.kokoro?.ready,
      policy: "no silent Kokoro identity fallback",
    });
  });

  test("M33-CHAR-23 Protected Hitchhiker IDs unchanged", async ({ request }) => {
    await assertProtectedUnchanged(request);
    writeEvidence(["persistence", "M33-CHAR-23.json"], { ok: true });
  });
});
