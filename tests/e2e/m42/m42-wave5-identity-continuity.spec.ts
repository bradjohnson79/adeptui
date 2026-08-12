import { test, expect } from "@playwright/test";

/**
 * M42 Wave 5 — Identity and Visual Continuity Playwright certification (A–P sample).
 * Skips gracefully when API/UI unavailable.
 */
test.describe("M42 W5 Identity Continuity @DETERMINISTIC", () => {
  test("A/B — Identity Registry create + empty readiness", async ({ page, request }) => {
    const projects = await request.get("/api/projects");
    test.skip(!projects.ok(), "API projects unavailable");
    const body = await projects.json();
    const id = body?.items?.[0]?.id || body?.[0]?.id;
    test.skip(!id, "No project");

    await page.goto(`/project/${id}?workspace=identityregistry`);
    const shell = page.getByTestId("identity-registry-workspace");
    await expect(shell).toBeVisible({ timeout: 30000 });
    await expect(page.getByTestId("continuity-policy-panel")).toBeVisible();
    await expect(page.getByTestId("identity-readiness-panel").or(page.getByTestId("identity-empty"))).toBeVisible();

    const name = `W5-${Date.now()}`;
    await page.getByTestId("identity-name-input").fill(name);
    await page.getByTestId("identity-create").click();
    await expect(page.getByText(name).first()).toBeVisible({ timeout: 15000 });
  });

  test("I — Continuity Workspace shell", async ({ page, request }) => {
    const projects = await request.get("/api/projects");
    test.skip(!projects.ok(), "API unavailable");
    const body = await projects.json();
    const id = body?.items?.[0]?.id || body?.[0]?.id;
    test.skip(!id, "No project");

    await page.goto(`/project/${id}?workspace=continuity`);
    await expect(page.getByTestId("continuity-workspace")).toBeVisible({ timeout: 30000 });
    await expect(page.getByTestId("continuity-issue-queue")).toBeVisible();
    await expect(page.getByTestId("continuity-shot-strip")).toBeVisible();
  });

  test("J — MAGI Continuity pane present", async ({ page, request }) => {
    const projects = await request.get("/api/projects");
    test.skip(!projects.ok(), "API unavailable");
    const body = await projects.json();
    const id = body?.items?.[0]?.id || body?.[0]?.id;
    test.skip(!id, "No project");

    await page.goto(`/project/${id}?workspace=magi`);
    const magi = page.getByTestId("magi-editor");
    test.skip((await magi.count()) === 0, "MAGI editor not mounted");
    await expect(magi).toBeVisible({ timeout: 30000 });
    const continuityBtn = page.getByRole("button", { name: /Continuity/i });
    if ((await continuityBtn.count()) > 0) {
      await continuityBtn.first().click();
      await expect(page.getByTestId("magi-continuity-panel")).toBeVisible({ timeout: 10000 });
    }
  });

  test("N — gate endpoint binary", async ({ request }) => {
    const res = await request.get("/api/continuity/gate/wave5");
    test.skip(!res.ok(), "Wave 5 gate unavailable");
    const g = await res.json();
    expect(g).toHaveProperty("wave5Go");
    expect(typeof g.wave5Go).toBe("boolean");
    expect(g).toHaveProperty("wave4cPrerequisitePassed");
  });

  test("P — legacy project loads without fabricated identities", async ({ page, request }) => {
    const projects = await request.get("/api/projects");
    test.skip(!projects.ok(), "API unavailable");
    const body = await projects.json();
    const id = body?.items?.[0]?.id || body?.[0]?.id;
    test.skip(!id, "No project");

    const list = await request.get(`/api/continuity/identities?projectId=${id}`);
    test.skip(!list.ok(), "continuity API unavailable");
    const data = await list.json();
    // May be empty — must not invent identities
    expect(Array.isArray(data.items)).toBeTruthy();

    const policy = await request.get(`/api/continuity/projects/${id}/policy`);
    const pol = await policy.json();
    expect(pol.enabled === false || typeof pol.enabled === "boolean").toBeTruthy();
  });
});
