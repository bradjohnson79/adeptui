/**
 * Revision C live closure — world intelligence advisory + isolation.
 * Certifies 8760 → 8758 only.
 */
import { expect, test } from "@playwright/test";
import { API, BETA_TARGET, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";

test.describe("Revision C World Intelligence 8760→8758", () => {
  test.skip(!BETA_TARGET, "Revision C live closure certifies 8760→8758 only");
  test.skip(!String(API).includes("8758"), `API must be :8758, got ${API}`);

  let projectA = "";
  let projectB = "";

  test.beforeAll(async ({ request }) => {
    await waitForAppReady(request);
    const a = await createTempProject(request, `Rev C World A ${Date.now()}`);
    const b = await createTempProject(request, `Rev C World B ${Date.now()}`);
    projectA = a.id;
    projectB = b.id;
  });

  test.afterAll(async ({ request }) => {
    if (projectA) await deleteProject(request, projectA).catch(() => undefined);
    if (projectB) await deleteProject(request, projectB).catch(() => undefined);
  });

  test("status is advisory-only and never claims JEPA in creator chrome", async ({ request, page }) => {
    const status = await request.get(`${API}/api/codirector/world-intelligence/status`);
    expect(status.ok(), await status.text()).toBeTruthy();
    const body = await status.json();
    expect(body.advisoryOnly).toBeTruthy();
    expect(body).toHaveProperty("installed");
    expect(body).toHaveProperty("available");

    await page.goto(`/project/${projectA}?workspace=scene`, { waitUntil: "domcontentloaded", timeout: 60_000 });
    await expect(page.getByText(/JEPA|V-JEPA|embedding/i)).toHaveCount(0);
  });

  test("policy persists across GET after POST", async ({ request }) => {
    const set = await request.post(`${API}/api/codirector/world-intelligence/policy`, {
      data: { projectId: projectA, enabled: true, policy: "review_on_change" },
    });
    expect(set.ok(), await set.text()).toBeTruthy();
    const get = await request.get(
      `${API}/api/codirector/world-intelligence/policy?projectId=${projectA}`,
    );
    expect(get.ok(), await get.text()).toBeTruthy();
    const policy = await get.json();
    expect(policy.policy).toBe("review_on_change");
    expect(policy.enabled).toBeTruthy();
  });

  test("evaluate rejects a cross-project asset id", async ({ request }) => {
    const res = await request.post(`${API}/api/codirector/world-intelligence/evaluate`, {
      data: {
        projectId: projectA,
        assetId: "not-in-this-project",
        referenceAssetIds: [],
      },
    });
    expect(res.ok(), await res.text()).toBeTruthy();
    const body = await res.json();
    expect(body.packet.availability).toBe("unavailable");
    expect(String(body.packet.reason || "")).toMatch(/not in this project/i);
  });

  test("advisory GET is project-scoped and Scene Creator can mount the note", async ({ request, page }) => {
    const a = await request.get(`${API}/api/codirector/world-intelligence/advisory?projectId=${projectA}`);
    const b = await request.get(`${API}/api/codirector/world-intelligence/advisory?projectId=${projectB}`);
    expect(a.ok(), await a.text()).toBeTruthy();
    expect(b.ok(), await b.text()).toBeTruthy();
    const aBody = await a.json();
    const bBody = await b.json();
    expect(aBody.policy).toBeTruthy();
    expect(bBody.policy).toBeTruthy();
    expect(JSON.stringify(aBody.policy)).not.toBe(JSON.stringify(bBody.policy));

    await page.goto(`/project/${projectA}?workspace=scenecreator`, { waitUntil: "domcontentloaded", timeout: 60_000 });
    await expect(page.locator("body")).toBeVisible();
    await expect(page.getByText(/JEPA/i)).toHaveCount(0);
  });

  test("Schnick Scene Creator shows the persisted world-consistency note", async ({ request, page }) => {
    const schnick = "2347bf46-3762-4763-86c5-4a6032522278";
    const scene = "e4550745-f0ef-44c8-99a5-ef9e20bd47d2";
    const advisory = await request.get(
      `${API}/api/codirector/world-intelligence/advisory?projectId=${schnick}&sceneId=${scene}`,
    );
    expect(advisory.ok(), await advisory.text()).toBeTruthy();
    const body = await advisory.json();
    expect(String(body.advisoryText || "")).toMatch(/world consistency|established world/i);
    expect(String(body.advisoryText || "")).not.toMatch(/JEPA|V-JEPA|embedding|cosine/i);

    await page.goto(`/project/${schnick}?workspace=scenecreator`, { waitUntil: "domcontentloaded", timeout: 60_000 });
    await expect(page.locator("[data-testid=world-consistency-note]")).toBeVisible({ timeout: 45_000 });
    await expect(page.locator("[data-testid=world-consistency-text]")).toContainText(/world consistency|established world/i);
    await expect(page.getByText(/JEPA|V-JEPA|embedding/i)).toHaveCount(0);
  });
});
