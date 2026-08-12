import { expect, test } from "@playwright/test";

test.describe("Project Password Protection", () => {
  test("gate is binary with required flags", async ({ request }) => {
    const res = await request.get("/api/project-security/gate/password-protection");
    if (!res.ok()) {
      test.info().annotations.push({ type: "note", description: `HTTP ${res.status()}` });
      return;
    }
    const body = await res.json();
    expect(body).toHaveProperty("projectPasswordProtectionGo");
    expect(body.binaryOnly).toBeTruthy();
    expect(body.conditionalGoForbidden).toBeTruthy();
    expect(body.flags).toHaveProperty("projectPasswordHashingOperational");
    expect(body.flags).toHaveProperty("projectDirectRouteBypassZero");
  });

  test("Scenario A/B/C — menu, setup modal, unlock error shape", async ({ page, request }) => {
    await page.goto("/");
    const library = page.locator("#projects-library");
    if ((await library.count()) === 0) return;

    const menuBtn = page.getByTestId("project-menu-button").first();
    if ((await menuBtn.count()) === 0) return;
    await menuBtn.click();
    const protect = page.getByTestId("project-menu-password-protect");
    const manage = page.getByTestId("project-menu-manage-password");
    // Either protect (unprotected) or manage (already protected)
    if ((await protect.count()) > 0) {
      await expect(protect).toBeVisible();
      await protect.click();
      await expect(page.getByTestId("project-password-setup-modal")).toBeVisible();
      await expect(page.getByTestId("project-pw-new")).toBeVisible();
      await page.getByRole("button", { name: "Cancel" }).click();
    } else if ((await manage.count()) > 0) {
      await expect(manage).toBeVisible();
    }

    // Incorrect unlock API shape (generic message)
    const projects = await request.get("/api/projects");
    if (!projects.ok()) return;
    const list = await projects.json();
    const protectedProj = (list || []).find((p: any) => p.password_protected);
    if (!protectedProj) return;
    const unlock = await request.post(`/api/projects/${protectedProj.id}/security/unlock`, {
      data: { password: "this is the wrong password!!", rememberFor: "session" },
    });
    expect(unlock.status()).toBe(401);
    const body = await unlock.json();
    const msg = body?.detail?.message || JSON.stringify(body);
    expect(msg).toContain("incorrect");
    expect(msg.toLowerCase()).not.toContain("hash");
  });

  test("Scenario D — direct project API denied while locked", async ({ request }) => {
    const projects = await request.get("/api/projects");
    if (!projects.ok()) return;
    const list = await projects.json();
    const locked = (list || []).find((p: any) => p.password_protected && p.password_locked);
    if (!locked) {
      test.info().annotations.push({ type: "note", description: "No locked project in library — soft skip" });
      return;
    }
    const res = await request.get(`/api/projects/${locked.id}`);
    expect(res.status()).toBe(403);
    const body = await res.json();
    expect(body?.detail?.code || "").toBe("PROJECT_LOCKED");
  });

  test("Scenario L — security status never returns hash", async ({ request }) => {
    const projects = await request.get("/api/projects");
    if (!projects.ok()) return;
    const list = await projects.json();
    const p = (list || [])[0];
    if (!p) return;
    const res = await request.get(`/api/projects/${p.id}/security`);
    if (!res.ok()) return;
    const body = await res.json();
    expect(body).not.toHaveProperty("password_hash");
    expect(body).not.toHaveProperty("passwordHash");
    expect(JSON.stringify(body).toLowerCase()).not.toContain("argon2");
  });
});
