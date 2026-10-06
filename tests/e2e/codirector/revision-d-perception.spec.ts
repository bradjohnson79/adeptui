import fs from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";
import { API, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";

const SUBJECT_PNG = fs.readFileSync(path.join(__dirname, "../fixtures/revision-d-subject.png"));

test.describe("Revision D perception APIs", () => {
  test("capability includes select and removeBackground", async ({ request }) => {
    await waitForAppReady(request);
    const res = await request.get(`${API}/api/perception/capability`);
    expect(res.ok(), await res.text()).toBeTruthy();
    const body = await res.json();
    const cap = body.capability || {};
    expect(cap).toHaveProperty("select");
    expect(cap).toHaveProperty("removeBackground");
    expect(cap).toHaveProperty("track");
    expect(cap.chatRequired).toBeFalsy();
  });

  test("select without a picture is honest", async ({ request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, "Revision D Select Honesty");
    try {
      const res = await request.post(`${API}/api/perception/projects/${project.id}/select`, {
        data: { assetId: "missing-asset", kind: "subject" },
      });
      expect(res.ok(), await res.text()).toBeTruthy();
      const body = await res.json();
      if (body.ok) {
        expect(body.maskAssetId).toBeTruthy();
      } else {
        expect(body.maskAssetId || "").toBe("");
        expect(String(body.message || "").length).toBeGreaterThan(4);
        expect(String(body.message)).not.toMatch(/SAM|JEPA|logits/i);
      }
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("project isolation: selection GET does not leak", async ({ request }) => {
    await waitForAppReady(request);
    const projectA = await createTempProject(request, "Revision D Isolation A");
    const projectB = await createTempProject(request, "Revision D Isolation B");
    try {
      const missingA = await request.get(`${API}/api/perception/projects/${projectA.id}/selections/sel_missing`);
      expect(missingA.status()).toBe(404);
      const missingB = await request.get(`${API}/api/perception/projects/${projectB.id}/selections/sel_missing`);
      expect(missingB.status()).toBe(404);
      const cross = await request.get(`${API}/api/perception/projects/${projectB.id}/tracks/trk_from_a`);
      expect([404, 400]).toContain(cross.status());
    } finally {
      await deleteProject(request, projectA.id);
      await deleteProject(request, projectB.id);
    }
  });

  test("remove background persists or stays honest", async ({ request }) => {
    test.setTimeout(180_000);
    await waitForAppReady(request);
    const capRes = await request.get(`${API}/api/perception/capability`);
    const cap = ((await capRes.json()) as { capability?: { select?: string } }).capability || {};
    const project = await createTempProject(request, "Revision D Rembg Persist");
    try {
      const upload = await request.post(`${API}/api/projects/${project.id}/assets`, {
        multipart: {
          file: { name: "subject.png", mimeType: "image/png", buffer: SUBJECT_PNG },
          tag: "edit_source",
          kind: "image",
        },
      });
      expect(upload.ok(), await upload.text()).toBeTruthy();
      const asset = await upload.json();
      const rembg = await request.post(`${API}/api/perception/projects/${project.id}/remove-background`, {
        data: { assetId: asset.id, saveToLibrary: true, tag: "no-background" },
        timeout: 180_000,
      });
      expect(rembg.ok(), await rembg.text()).toBeTruthy();
      const body = await rembg.json();
      if (cap.select === "available" && body.ok) {
        expect(body.maskAssetId).toBeTruthy();
        expect(body.resultAssetId).toBeTruthy();
        const listed = await request.get(`${API}/api/projects/${project.id}/library`);
        expect(listed.ok()).toBeTruthy();
        const assets = await listed.json();
        const rows = Array.isArray(assets) ? assets : assets.items || assets.assets || [];
        const ids = rows.map((row: { id?: string }) => row.id);
        expect(ids).toContain(body.resultAssetId);
      } else {
        expect(body.ok).toBeFalsy();
        expect(String(body.message || "")).toMatch(/Paint|Essentials Pack|picture/i);
        expect(String(body.message)).not.toMatch(/SAM|JEPA|logits/i);
      }
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("track stays honest and discloses native video inpaint is blocked", async ({ request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, "Revision D Track Honesty");
    try {
      const res = await request.post(`${API}/api/perception/projects/${project.id}/track`, {
        data: { assetId: "missing-video", label: "vehicle" },
      });
      expect(res.ok(), await res.text()).toBeTruthy();
      const body = await res.json();
      if (body.ok) {
        expect(body.nativeVideoInpaint).toBeFalsy();
        expect(String(body.disclosure || body.message || "")).toMatch(/range|retake|unavailable/i);
      } else {
        expect(String(body.message || "")).toMatch(/Paint|Essentials Pack|picture|video|Track/i);
        expect(String(body.message)).not.toMatch(/SAM|JEPA|logits/i);
      }
    } finally {
      await deleteProject(request, project.id);
    }
  });
});
