import { expect, test } from "@playwright/test";
import { createTempProject } from "../helpers/app";

const PNG_1X1 = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64"
);

async function uploadPng(request: any, projectId: string, tag: string) {
  const upload = await request.post(`/api/projects/${projectId}/assets`, {
    multipart: {
      file: { name: `${tag}.png`, mimeType: "image/png", buffer: PNG_1X1 },
      tag,
      kind: "image",
    },
  });
  if (!upload.ok()) return undefined;
  const body = await upload.json();
  return body.id || body.asset?.id;
}

async function ensureTwoClips(request: any, projectId: string) {
  const scenesRes = await request.get(`/api/projects/${projectId}/scenes`);
  expect(scenesRes.ok()).toBeTruthy();
  const scenesJson = await scenesRes.json();
  const scenes = Array.isArray(scenesJson) ? scenesJson : scenesJson.scenes || scenesJson.items || [];
  const sceneId = scenes[0].id;
  const directorRes = await request.get(`/api/projects/${projectId}/scenes/${sceneId}/director`);
  expect(directorRes.ok()).toBeTruthy();
  const director = await directorRes.json();
  const a1 = await uploadPng(request, projectId, "primary1");
  const a2 = await uploadPng(request, projectId, "primary2");
  director.image_clips = [
    { id: "cl-image-1", asset_id: a1 || null, start: 0, length: 3, role: "guide", label: "Image 1" },
    { id: "cl-image-2", asset_id: a2 || null, start: 3, length: 3, role: "guide", label: "Image 2" },
  ];
  const put = await request.put(`/api/projects/${projectId}/scenes/${sceneId}/director`, { data: director });
  expect(put.ok()).toBeTruthy();
  const saved = await put.json();
  return { sceneId, image1: saved.image_clips[0], image2: saved.image_clips[1] };
}

test.describe("M2.6.1 closed-loop integration @critical @isolated", () => {
  test("Scenario 1 - app loads and flag UI honesty", async ({ page, request }) => {
    await expect.poll(async () => (await request.get("/api/health")).ok(), { timeout: 60_000 }).toBeTruthy();
    const health = await request.get("/api/health");
    expect(health.ok()).toBeTruthy();
    const h = await health.json();
    const refsOn = Boolean(h?.operator?.timelineReferencesEnabled);
    const visionOn = Boolean(h?.operator?.visionValidationEnabled);
    const project = await createTempProject(request, "Closed Loop Flags");
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(String(err)));
    await page.goto(`/project/${project.id}`);
    await expect(page.locator("body")).toBeVisible();
    await expect(page.getByText(/Co-Director|Director/i).first()).toBeVisible({ timeout: 15000 });
    if (!refsOn) await expect(page.getByText("References for")).toHaveCount(0);
    if (!visionOn) await expect(page.getByTestId("codirector-validation-workspace")).toHaveCount(0);
    expect(errors, errors.join("\n")).toEqual([]);
  });

  test("Scenarios 2-3,6,9 - package refs COW binding-validate", async ({ request }) => {
    const health = await request.get("/api/health");
    const h = await health.json();
    test.skip(!h?.operator?.timelineReferencesEnabled, "timeline refs flag off");
    const visionOn = Boolean(h?.operator?.visionValidationEnabled);
    const project = await createTempProject(request, "Closed Loop Package");
    const { sceneId, image1, image2 } = await ensureTwoClips(request, project.id);
    expect(image1.display_tag).toMatch(/^@Image\d+$/);
    expect(image2.display_tag).toMatch(/^@Image\d+$/);

    const emptyPkg = await request.get(
      `/api/projects/${project.id}/scenes/${sceneId}/director/items/${image1.id}/reference-package`
    );
    expect(emptyPkg.ok()).toBeTruthy();
    const emptyBody = await emptyPkg.json();
    expect(emptyBody.referenceSet).toBeNull();
    expect(emptyBody.primaryFrame.displayTag).toBe(image1.display_tag);

    const identity = await uploadPng(request, project.id, "identity");
    const wardrobe = await uploadPng(request, project.id, "wardrobe");
    test.skip(!identity || !wardrobe, "asset upload unavailable");

    const add1 = await request.post(
      `/api/projects/${project.id}/scenes/${sceneId}/director/items/${image2.id}/references`,
      { data: { referenceAssetId: identity, role: "character_identity", influence: "strong", source: "upload" } }
    );
    expect(add1.ok()).toBeTruthy();
    expect((await add1.json()).activeVersion).toBe(1);
    const add2 = await request.post(
      `/api/projects/${project.id}/scenes/${sceneId}/director/items/${image2.id}/references`,
      { data: { referenceAssetId: wardrobe, role: "costume", influence: "moderate", source: "upload" } }
    );
    expect(add2.ok()).toBeTruthy();
    const refs = await add2.json();
    expect(refs.activeVersion).toBe(2);
    expect(refs.count).toBe(2);

    const pkg = await (
      await request.get(
        `/api/projects/${project.id}/scenes/${sceneId}/director/items/${image2.id}/reference-package`
      )
    ).json();
    expect(pkg.primaryFrame.role).toBe("primary_frame");
    expect(pkg.referenceSet.version).toBe(2);

    const bindingId = refs.bindings[0].bindingId;
    const patched = await request.patch(
      `/api/projects/${project.id}/scenes/${sceneId}/director/items/${image2.id}/references/${bindingId}`,
      { data: { influence: "loose", expectedVersion: 2 } }
    );
    expect(patched.ok()).toBeTruthy();
    expect((await patched.json()).activeVersion).toBe(3);

    if (visionOn) {
      const validate = await request.post("/api/codirector/vision/validate", {
        data: {
          projectId: project.id,
          sceneId,
          provider: "mock",
          fixtureProfile: "warnings",
          referenceSet: {
            id: pkg.referenceSet.id,
            version: pkg.referenceSet.version,
            bindings: pkg.referenceSet.bindings.map((b: any) => ({
              bindingId: b.bindingId,
              role: b.role,
              influence: b.influence,
              assetId: b.referenceAssetId,
            })),
          },
        },
      });
      expect(validate.ok()).toBeTruthy();
      const findings = (await validate.json())?.report?.findings || [];
      expect(Array.isArray(findings)).toBeTruthy();
      expect(findings.filter((f: any) => f.bindingId).length).toBeGreaterThan(0);
    }
  });

  test("Scenarios 4-5 - Co-Director inspect and proposal boundary", async ({ request }) => {
    const health = await request.get("/api/health");
    const h = await health.json();
    test.skip(!h?.operator?.timelineReferencesEnabled, "timeline refs flag off");
    const project = await createTempProject(request, "Closed Loop Tools");
    const { sceneId, image2 } = await ensureTwoClips(request, project.id);
    const env = await uploadPng(request, project.id, "environment");
    test.skip(!env, "asset upload unavailable");

    const listed = await request.post(`/api/codirector/projects/${project.id}/tools/read`, {
      data: { toolId: "list_timeline_images", arguments: { sceneId } },
    });
    expect(listed.ok()).toBeTruthy();

    const resolved = await request.post(`/api/codirector/projects/${project.id}/tools/read`, {
      data: { toolId: "get_timeline_image", arguments: { sceneId, displayTag: image2.display_tag } },
    });
    expect(resolved.ok()).toBeTruthy();

    const unknown = await request.post(`/api/codirector/projects/${project.id}/tools/read`, {
      data: { toolId: "get_timeline_image", arguments: { sceneId, displayTag: "@Image999" } },
    });
    expect(unknown.ok()).toBeFalsy();

    const before = await (
      await request.get(`/api/projects/${project.id}/scenes/${sceneId}/director/items/${image2.id}/references`)
    ).json();
    expect(before.count).toBe(0);

    const propose = await request.post(`/api/codirector/projects/${project.id}/tools/proposals`, {
      data: {
        toolId: "propose_add_reference_binding",
        arguments: {
          sceneId,
          timelineItemId: image2.id,
          referenceAssetId: env,
          role: "environment",
          influence: "moderate",
        },
      },
    });
    expect(propose.ok()).toBeTruthy();
    const proposal = await propose.json();
    expect(proposal.status).toBe("pending");

    const mid = await (
      await request.get(`/api/projects/${project.id}/scenes/${sceneId}/director/items/${image2.id}/references`)
    ).json();
    expect(mid.count).toBe(0);

    const approve = await request.post(
      `/api/codirector/projects/${project.id}/proposals/${proposal.id}/approve`,
      { data: {} }
    );
    expect(approve.ok()).toBeTruthy();
    const after = await (
      await request.get(`/api/projects/${project.id}/scenes/${sceneId}/director/items/${image2.id}/references`)
    ).json();
    expect(after.count).toBe(1);
    expect(after.activeVersion).toBe(1);
  });

  test("Scenarios 7-8 - review approve and optional Bible link", async ({ request }) => {
    const health = await request.get("/api/health");
    const h = await health.json();
    test.skip(!h?.operator?.visionValidationEnabled, "vision flag off");
    const project = await createTempProject(request, "Closed Loop Review");
    const draft = await uploadPng(request, project.id, "draft");
    test.skip(!draft, "asset upload unavailable");

    const validate = await request.post("/api/codirector/vision/validate", {
      data: { projectId: project.id, assetId: draft, provider: "mock", fixtureProfile: "pass" },
    });
    expect(validate.ok()).toBeTruthy();
    const sessionId = (await validate.json()).session.sessionId;

    const approve = await request.post("/api/codirector/vision/approve", {
      data: { projectId: project.id, sessionId, linkToBible: true, notes: "e2e approve" },
    });
    expect(approve.ok()).toBeTruthy();
    const body = await approve.json();
    const bibleProp = body.bibleLinkProposal || body.bible_link_proposal;
    if (bibleProp) expect(bibleProp.proposalId || bibleProp.id).toBeTruthy();
  });

  test("Scenario 10 - capability limitation honesty", async ({ request }) => {
    const health = await request.get("/api/health");
    expect(health.ok()).toBeTruthy();
    const h = await health.json();
    test.skip(!h?.operator?.timelineReferencesEnabled, "timeline refs flag off");
    const project = await createTempProject(request, "Closed Loop Caps");
    const { sceneId, image2 } = await ensureTwoClips(request, project.id);
    const style = await uploadPng(request, project.id, "style");
    test.skip(!style, "asset upload unavailable");
    await request.post(
      `/api/projects/${project.id}/scenes/${sceneId}/director/items/${image2.id}/references`,
      { data: { referenceAssetId: style, role: "style", influence: "moderate", source: "upload" } }
    );
    const pkg = await (
      await request.get(
        `/api/projects/${project.id}/scenes/${sceneId}/director/items/${image2.id}/reference-package`
      )
    ).json();
    expect(["ready", "degraded"]).toContain(pkg.support.status);
    if (pkg.support.status === "degraded") {
      expect((pkg.support.unsupportedBindings || []).length).toBeGreaterThan(0);
      expect(pkg.support.icLoraReady).toBeFalsy();
    }
    const check = await request.post(
      `/api/projects/${project.id}/scenes/${sceneId}/director/items/${image2.id}/reference-package/validate`,
      { data: {} }
    );
    expect(check.ok()).toBeTruthy();
    expect((await check.json()).blocksRun).toBeFalsy();
  });
});