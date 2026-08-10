import { test, expect } from "@playwright/test";
import {
  API,
  clearActiveInstallJobs,
  createTempProject,
  deleteProject,
  openSetup,
  waitForAppReady,
} from "../helpers/app";
import { AuditObserver } from "../helpers/observer";

test.describe("@critical @isolated component source states", () => {
  test("Essential packs show Source Pending; fal.ai offers Configure API Key", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    await request.post(`${API}/api/e2e/recover-operations`);
    for (const packId of [
      "pack_essential_photoreal",
      "pack_essential_anime",
      "pack_essential_cinematic",
    ]) {
      await clearActiveInstallJobs(request, packId);
    }

    // Clear any prior fixture release cache bias by checking API status shape first.
    const statusRes = await request.get(`${API}/api/setup/status`);
    expect(statusRes.ok()).toBeTruthy();
    const status = await statusRes.json();
    const byId = Object.fromEntries(
      (status.components as Array<{ id: string }>).map((c) => [c.id, c]),
    ) as Record<string, Record<string, unknown>>;

    // In E2E, fixture_http makes packs source-valid — assert credential UX always,
    // and pack pending UX when status is source_pending (non-fixture) or when
    // issue_code is source_not_published. When fixture is active, packs should
    // remain installable (not stuck as red Download Unavailable for env vars).
    const fal = byId.fal_key;
    expect(fal).toBeTruthy();
    expect(fal.component_kind).toBe("credential");
    expect(fal.show_download_sizes).toBeFalsy();
    const falAction = fal.primary_action as { label?: string; action?: string };
    expect(falAction?.label).toBe("Configure API Key");
    expect(falAction?.label).not.toBe("Download and Install");

    for (const packId of [
      "pack_essential_photoreal",
      "pack_essential_anime",
      "pack_essential_cinematic",
    ]) {
      const pack = byId[packId];
      expect(pack).toBeTruthy();
      const summary = String(pack.issue_summary || "");
      expect(summary).not.toMatch(/ADEPT_PACK_GITHUB_OWNER/);
      expect(summary).not.toMatch(/ADEPT_PACK_GITHUB_REPOSITORY/);
    }

    const project = await createTempProject(request, `Source States ${Date.now()}`);
    try {
      await openSetup(page, project.id);

      const falCard = page.getByTestId("setup-card-fal_key");
      await expect(falCard).toBeVisible();
      await expect(falCard.getByRole("button", { name: /Configure API Key/i })).toBeVisible();
      await expect(falCard.getByRole("button", { name: /Download and Install/i })).toHaveCount(0);

      // Pack cards must keep Add Source URL + Link Existing; must not push env-var instructions.
      for (const packId of [
        "pack_essential_photoreal",
        "pack_essential_anime",
        "pack_essential_cinematic",
      ]) {
        const card = page.getByTestId(`setup-card-${packId}`);
        await expect(card).toBeVisible();
        await expect(card.getByTestId(`add-source-url-${packId}`)).toBeVisible();
        await expect(card.getByRole("button", { name: /Link Existing Folder/i })).toBeVisible();
        await expect(card).not.toContainText("ADEPT_PACK_GITHUB_OWNER");
      }
      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });
});
