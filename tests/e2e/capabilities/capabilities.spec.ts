import { test, expect } from "@playwright/test";
import { API, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";

const STATUSES = [
  "not_implemented",
  "ui_only",
  "backend_only",
  "partially_wired",
  "mock_verified",
  "locally_verified",
  "production_ready",
  "blocked",
  "degraded",
  "not_configured",
  "unknown",
];

type Capability = {
  id: string;
  status: string;
  subsystem: string;
  displayName: string;
  /** Per-item "safe to call right now"; the snapshot's `callable` list must agree with it. */
  available: boolean;
};

type Snapshot = {
  capabilities: Capability[];
  blockers: { capabilityId: string; status: string; message: string }[];
  callable: string[];
  counts: Record<string, number>;
  generatedAt: string;
  probeWarnings: string[];
};

test.describe("@critical @isolated capabilities", () => {
  test("capability API reports a complete, well-formed snapshot", async ({ request }) => {
    await waitForAppReady(request);

    const res = await request.get(`${API}/api/capabilities`);
    expect(res.ok()).toBeTruthy();
    const snapshot: Snapshot = await res.json();

    expect(snapshot.capabilities.length).toBeGreaterThan(30);
    for (const capability of snapshot.capabilities) {
      expect(STATUSES).toContain(capability.status);
    }

    // `callable` is the list the Co-Director will read; it must agree with the per-item flag.
    const flagged = snapshot.capabilities.filter((c) => c.available).map((c) => c.id).sort();
    expect(snapshot.callable.slice().sort()).toEqual(flagged);

    // Blockers must be a strict subset of the snapshot, never a parallel invention.
    const ids = new Set(snapshot.capabilities.map((c) => c.id));
    for (const blocker of snapshot.blockers) {
      expect(ids.has(blocker.capabilityId)).toBeTruthy();
      expect(blocker.message.length).toBeGreaterThan(0);
    }

    const single = await request.get(`${API}/api/capabilities/project.create`);
    expect(single.ok()).toBeTruthy();
    expect((await single.json()).id).toBe("project.create");

    const missing = await request.get(`${API}/api/capabilities/does.not.exist`);
    expect(missing.status()).toBe(404);
    expect((await missing.json()).detail.code).toBe("CAPABILITY_NOT_FOUND");

    const refreshed = await request.post(`${API}/api/capabilities/refresh`);
    expect(refreshed.ok()).toBeTruthy();
    const after: Snapshot = await refreshed.json();
    expect(new Date(after.generatedAt).getTime()).toBeGreaterThanOrEqual(
      new Date(snapshot.generatedAt).getTime(),
    );
  });

  test("scene CRUD is reported callable and storage-backed capabilities are honest", async ({
    request,
  }) => {
    await waitForAppReady(request);

    const res = await request.get(`${API}/api/capabilities`);
    const snapshot: Snapshot = await res.json();
    const byId = new Map(snapshot.capabilities.map((c) => [c.id, c]));

    // These are the ones this milestone claims are safe to call right now.
    for (const id of [
      "project.create",
      "project.list",
      "project.read",
      "project.update",
      "project.scenes.create",
      "project.scenes.read",
      "project.scenes.update",
      "project.scenes.delete",
    ]) {
      const capability = byId.get(id);
      expect(capability, `${id} missing from registry`).toBeTruthy();
      expect(capability!.available, `${id} is ${capability!.status}`).toBeTruthy();
    }

    // Things with no implementation must say so, not sit at "unknown".
    expect(byId.get("project.scenes.reorder")!.status).toBe("not_implemented");
    expect(byId.get("references.remove")!.status).toBe("not_implemented");
  });

  test("project-scoped capabilities resolve against a real project", async ({ request }) => {
    await waitForAppReady(request);

    const project = await createTempProject(request, `E2E Caps ${Date.now()}`);
    try {
      const res = await request.get(`${API}/api/projects/${project.id}/capabilities`);
      expect(res.ok()).toBeTruthy();
      const snapshot: Snapshot = await res.json();
      expect(snapshot.capabilities.some((c) => c.subsystem === "references")).toBeTruthy();

      const unknownProject = await request.get(`${API}/api/projects/not-a-project/capabilities`);
      expect(unknownProject.status()).toBe(404);
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("Comfy health and workflow readiness never claim more than they can prove", async ({
    request,
  }) => {
    await waitForAppReady(request);

    const health = await request.get(`${API}/api/comfy/health`);
    expect(health.ok()).toBeTruthy();
    const body = await health.json();
    expect(["ready", "degraded", "unreachable"]).toContain(body.status);
    expect(typeof body.reachable).toBe("boolean");
    expect(Array.isArray(body.missingModelComponentIds)).toBeTruthy();
    if (body.status !== "ready") {
      expect(body.reasonCode).toBeTruthy();
      expect(body.recommendedAction).toBeTruthy();
    }
    // The health payload must not leak a filesystem path for a component it could not find.
    expect(JSON.stringify(body)).not.toMatch(/[A-Za-z]:\\\\Users\\\\/);

    const workflows = await request.get(`${API}/api/workflows`);
    expect(workflows.ok()).toBeTruthy();
    const list = (await workflows.json()).workflows as { id: string }[];
    expect(list.length).toBeGreaterThan(0);

    const readiness = await request.get(
      `${API}/api/workflows/${encodeURIComponent(list[0].id)}/readiness`,
    );
    expect(readiness.ok()).toBeTruthy();
    const detail = await readiness.json();
    // "unknown" is a first-class answer: with ComfyUI down we must not guess either way.
    expect(["ready", "blocked", "unknown"]).toContain(detail.status);
    expect(Array.isArray(detail.missingModels)).toBeTruthy();
    expect(Array.isArray(detail.missingExtensions)).toBeTruthy();
    if (detail.status !== "ready") expect(detail.recommendedAction).toBeTruthy();

    const unknown = await request.get(`${API}/api/workflows/no-such-workflow/readiness`);
    expect(unknown.status()).toBe(404);
    expect((await unknown.json()).detail.code).toBe("WORKFLOW_NOT_FOUND");
  });

  test("Home surfaces capability readiness and the chrome badge agrees with the API", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);

    try {
      const snapshot: Snapshot = await (await request.get(`${API}/api/capabilities`)).json();

      await page.goto("/");
      await expect(page.getByTestId("capability-panel")).toBeVisible({ timeout: 45_000 });
      await expect(page.getByTestId("capability-summary")).toBeVisible();
      await expect(page.getByTestId("capability-callable-count")).toHaveText(
        String(snapshot.callable.length),
        { timeout: 30_000 },
      );

      const badge = page.getByTestId("capability-badge").first();
      await expect(badge).toBeVisible();
      await expect(badge).toHaveText(
        snapshot.blockers.length
          ? new RegExp(`${snapshot.blockers.length} Capability Blocker`)
          : /Capabilities Ready/,
      );

      if (snapshot.blockers.length > 0) {
        await expect(page.getByTestId("capability-blockers")).toBeVisible();
      } else {
        await expect(page.getByTestId("capability-no-blockers")).toBeVisible();
      }

      // Refresh re-probes; it must never kick off a download.
      const downloadStarts: string[] = [];
      page.on("request", (req) => {
        if (/\/(download|install|prepare)\b/.test(req.url()) && req.method() === "POST") {
          downloadStarts.push(req.url());
        }
      });
      await page.getByTestId("capability-refresh").first().click();
      await expect(page.getByTestId("capability-summary")).toBeVisible();
      expect(downloadStarts).toEqual([]);

      observer.assertHealthyBrowser();
    } finally {
      observer.flush();
    }
  });

  test("Source Manager lists blocked capabilities without starting downloads", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);

    try {
      await page.goto("/source-manager");
      await expect(page.getByTestId("source-manager-page")).toBeVisible({ timeout: 45_000 });
      await expect(
        page.getByRole("heading", { name: "What is blocked right now" }),
      ).toBeVisible();
      await expect(page.getByTestId("capability-panel")).toBeVisible();
      observer.assertHealthyBrowser();
    } finally {
      observer.flush();
    }
  });

  test("Setup Wizard refuses to claim ready while a required capability is blocked", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);

    const project = await createTempProject(request, `E2E Setup Caps ${Date.now()}`);
    try {
      const snapshot: Snapshot = await (await request.get(`${API}/api/capabilities`)).json();
      const required = new Set([
        "storage.project_data",
        "storage.database",
        "comfyui.health",
        "models.video.ready",
        "workflows.video.ready",
      ]);
      const requiredBlockers = snapshot.blockers.filter((b) => required.has(b.capabilityId));

      await page.goto(`/project/${project.id}?workspace=setup`);
      await expect(page.locator(".setup-wizard-page").first()).toBeVisible({ timeout: 60_000 });

      const overall = page.getByTestId("setup-overall-status");
      await expect(overall).toBeVisible({ timeout: 30_000 });

      if (requiredBlockers.length > 0) {
        await expect(page.getByTestId("setup-capability-blockers")).toBeVisible({
          timeout: 30_000,
        });
        await expect(overall).not.toHaveText(/^Ready$/);
        await expect(page.getByTestId("setup-blockers-open-source-manager")).toBeVisible();
      } else {
        await expect(page.getByTestId("setup-capability-blockers")).toHaveCount(0);
      }

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });
});
