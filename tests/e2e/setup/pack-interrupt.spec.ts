import { test, expect } from "@playwright/test";
import { API, waitForAppReady } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";

test.describe("@critical @isolated pack interrupt recovery", () => {
  test("stale configuring operation becomes interrupted/recoverable", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);

    const seed = await request.post(`${API}/api/e2e/seed-stale-operation`, {
      data: {
        component_id: "pack_essential_photoreal",
        status: "running",
        phase: "configuring",
        stage: "Configuring…",
      },
    });
    expect(seed.ok()).toBeTruthy();
    const op = await seed.json();

    const recovered = await request.post(`${API}/api/e2e/recover-operations`);
    expect(recovered.ok()).toBeTruthy();
    const body = await recovered.json();
    expect(Array.isArray(body.recovered)).toBeTruthy();

    const snap = await request.get(`${API}/api/setup/operations/${op.operation_id}`);
    expect(snap.ok()).toBeTruthy();
    const after = await snap.json();
    expect(["interrupted", "failed", "cancelled"]).toContain(after.status);
    expect(String(after.error || after.stage || "").toLowerCase()).toMatch(
      /interrupt|recover|stale|fail/,
    );

    await page.goto("/");
    expect((await request.get(`${API}/api/health`)).ok()).toBeTruthy();
    observer.assertHealthyBrowser();
    observer.flush();
  });
});
