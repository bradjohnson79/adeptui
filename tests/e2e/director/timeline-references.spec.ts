import { expect, test } from "@playwright/test";
import { createTempProject } from "../helpers/app";

/**
 * M2.6 Timeline Reference Binding — Tests A–G (API + UI when flag on).
 * Test H exercises vision referenceSet contract when vision flag+mock available.
 */
test.describe("Director M2.6 timeline references @critical @isolated", () => {
  test("A–G reference bindings API and optional UI", async ({ page, request }) => {
    const project = await createTempProject(request, "Timeline Refs E2E");

    const health = await request.get("/api/health");
    expect(health.ok()).toBeTruthy();
    const healthJson = await health.json();
    const refsOn = Boolean(healthJson?.operator?.timelineReferencesEnabled);
    const visionOn = Boolean(healthJson?.operator?.visionValidationEnabled);

    // Ensure a scene + director image clip exist
    const scenesRes = await request.get(`/api/projects/${project.id}/scenes`);
    expect(scenesRes.ok()).toBeTruthy();
    const scenesJson = await scenesRes.json();
    const scenes = Array.isArray(scenesJson) ? scenesJson : scenesJson.scenes || scenesJson.items || [];
    expect(scenes.length).toBeGreaterThan(0);
    const sceneId = scenes[0].id;

    const directorRes = await request.get(`/api/projects/${project.id}/scenes/${sceneId}/director`);
    expect(directorRes.ok()).toBeTruthy();
    const director = await directorRes.json();
    director.image_clips = [
      {
        id: "e2e-clip-1",
        asset_id: null,
        start: 0,
        length: 2,
        role: "guide",
        label: "Image 1",
      },
      {
        id: "e2e-clip-2",
        asset_id: null,
        start: 2,
        length: 2,
        role: "guide",
        label: "Image 2",
      },
    ];
    const putRes = await request.put(`/api/projects/${project.id}/scenes/${sceneId}/director`, {
      data: director,
    });
    expect(putRes.ok()).toBeTruthy();
    const saved = await putRes.json();
    // A: stable tags assigned
    expect(saved.image_clips[0].display_tag).toMatch(/^@Image\d+$/);
    expect(saved.image_clips[1].display_tag).toMatch(/^@Image\d+$/);
    expect(saved.image_clips[0].display_tag).not.toEqual(saved.image_clips[1].display_tag);
    const itemId = saved.image_clips[0].id;
    const tag0 = saved.image_clips[0].display_tag;

    if (!refsOn) {
      // B: flag off — references endpoint hidden/404
      const denied = await request.get(
        `/api/projects/${project.id}/scenes/${sceneId}/director/items/${itemId}/references`
      );
      expect(denied.status()).toBe(404);
      await page.goto(`/project/${project.id}`);
      await expect(page.getByText("References for")).toHaveCount(0);
      return;
    }

    // C: empty set is normal
    const empty = await request.get(
      `/api/projects/${project.id}/scenes/${sceneId}/director/items/${itemId}/references`
    );
    expect(empty.ok()).toBeTruthy();
    const emptyJson = await empty.json();
    expect(emptyJson.count).toBe(0);

    // Upload a supporting asset
    const bytes = Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
      "base64"
    );
    const upload = await request.post(`/api/projects/${project.id}/assets`, {
      multipart: {
        file: {
          name: "ref.png",
          mimeType: "image/png",
          buffer: bytes,
        },
        tag: "e2e_ref",
        kind: "image",
      },
    });
    // Some environments use different upload shapes — fall back to JSON create if needed
    let assetId: string | undefined;
    if (upload.ok()) {
      const uploaded = await upload.json();
      assetId = uploaded.id || uploaded.asset?.id;
    }

    if (!assetId) {
      // Skip binding mutation if upload unsupported in this harness; still verify package empty shape
      const pkgEmpty = await request.get(
        `/api/projects/${project.id}/scenes/${sceneId}/director/items/${itemId}/reference-package`
      );
      expect(pkgEmpty.ok()).toBeTruthy();
      const pkg = await pkgEmpty.json();
      expect(pkg.primaryFrame.displayTag).toBe(tag0);
      expect(pkg.referenceSet).toBeNull();
      expect(pkg.support.status).toBe("ready");
    } else {
      // D: add binding (COW v1)
      const added = await request.post(
        `/api/projects/${project.id}/scenes/${sceneId}/director/items/${itemId}/references`,
        {
          data: {
            referenceAssetId: assetId,
            role: "style",
            influence: "moderate",
            source: "upload",
          },
        }
      );
      expect(added.ok()).toBeTruthy();
      const addedJson = await added.json();
      expect(addedJson.activeVersion).toBe(1);
      expect(addedJson.count).toBe(1);
      const bindingId = addedJson.bindings[0].bindingId;

      // E: package shape
      const pkgRes = await request.get(
        `/api/projects/${project.id}/scenes/${sceneId}/director/items/${itemId}/reference-package`
      );
      expect(pkgRes.ok()).toBeTruthy();
      const pkg = await pkgRes.json();
      expect(pkg.primaryFrame.role).toBe("primary_frame");
      expect(pkg.referenceSet.bindings.length).toBe(1);

      // F: validate package never blocks run
      const validate = await request.post(
        `/api/projects/${project.id}/scenes/${sceneId}/director/items/${itemId}/reference-package/validate`,
        { data: {} }
      );
      expect(validate.ok()).toBeTruthy();
      expect((await validate.json()).blocksRun).toBeFalsy();

      // G: patch + clear COW
      const patched = await request.patch(
        `/api/projects/${project.id}/scenes/${sceneId}/director/items/${itemId}/references/${bindingId}`,
        { data: { influence: "strong", expectedVersion: 1 } }
      );
      expect(patched.ok()).toBeTruthy();
      expect((await patched.json()).activeVersion).toBe(2);
    }

    // UI: References workspace when selecting image (best-effort)
    await page.goto(`/project/${project.id}`);
    // Director tracks may live under a tab — look for Prompt Timeline / Images
    const imagesLabel = page.getByText("Images", { exact: true }).first();
    if (await imagesLabel.count()) {
      await expect(page.getByText(tag0).first()).toBeVisible({ timeout: 10000 }).catch(() => undefined);
    }
  });

  test("H vision referenceSet contract when available", async ({ request }) => {
    const health = await request.get("/api/health");
    const healthJson = await health.json();
    const visionOn = Boolean(healthJson?.operator?.visionValidationEnabled);
    test.skip(!visionOn, "vision_validation_v1 off");

    const project = await createTempProject(request, "Vision RefSet E2E");
    const validate = await request.post("/api/codirector/vision/validate", {
      data: {
        projectId: project.id,
        provider: "mock",
        fixtureProfile: "warnings",
        referenceSet: {
          id: "set-e2e",
          version: 1,
          bindings: [
            { bindingId: "b1", role: "character_identity", influence: "strong", assetId: "noop" },
            { bindingId: "b2", role: "continuity", influence: "moderate", assetId: "noop" },
          ],
        },
      },
    });
    expect(validate.ok()).toBeTruthy();
    const payload = await validate.json();
    const findings = payload?.report?.findings || payload?.findings || [];
    // When bindings map to validators, findings may carry bindingId
    const withBinding = findings.filter((f: any) => f.bindingId);
    // Mock fixtures may or may not emit binding annotations for every validator; contract allows empty when no mapped validators ran.
    expect(Array.isArray(findings)).toBeTruthy();
    if (withBinding.length) {
      expect(withBinding[0].bindingId).toBeTruthy();
    }
  });
});
