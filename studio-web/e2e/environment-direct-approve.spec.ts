import { test, expect, type APIRequestContext } from "@playwright/test";

/**
 * Environment Creator — Path A "Approve as Environment" live E2E (no mocks).
 *
 * Walks the creator journey against the live Beta target (Vite :5173 + Studio
 * API :8758):
 *
 *   Create Environment → add reference from Library → Approve as Environment
 *   → approved item appears in Project Environment Reference Sheets → reload
 *   → remains approved → Co-Director resolution contract fields present
 *   → Timeline binding sees the same environment identity + approved asset.
 *
 * The Co-Director `#Tag` resolver (`reference_resolver._resolve_environment`)
 * reads exactly `list_visible_sheets` + `ers_composite_asset_id`; the service-
 * level resolver and `resolve_binding_id` convergence are covered by
 * studio-api/tests/test_environment_direct_approve.py. Here we assert the same
 * HTTP-visible contract the resolver binds from.
 *
 * The environment name is unique per run and the Global toggle is explicitly
 * unchecked: the surface inherits name/scope from any auto-hydrated Global
 * sheet (pre-existing behavior), and a disposable environment must not leak
 * into other projects.
 */

const API =
  process.env.STUDIO_API_BASE ||
  `http://127.0.0.1:${process.env.STUDIO_API_PORT || "8742"}`;

const ONE_PIXEL_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
  "base64"
);

const ENV_NAME = `E2E Venture Corridor ${Date.now()}`;
const EXPECTED_TAG = ENV_NAME.replace(/[^A-Za-z0-9]/g, "").toLowerCase();

async function waitForApi(request: APIRequestContext) {
  const deadline = Date.now() + 60_000;
  let lastError = "never contacted";
  while (Date.now() < deadline) {
    try {
      const res = await request.get(`${API}/api/healthz`);
      if (res.ok()) return;
      lastError = `HTTP ${res.status()}`;
    } catch (error) {
      lastError = String(error);
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`API at ${API} never became ready: ${lastError}`);
}

test.describe("Environment Creator — Approve as Environment (Path A)", () => {
  let projectId = "";
  let assetId = "";
  let sheetId = "";

  test.beforeAll(async ({ request }) => {
    await waitForApi(request);
    const project = await request.post(`${API}/api/projects`, {
      data: { name: `E2E Direct Approve ${Date.now()}` },
    });
    expect(project.ok()).toBeTruthy();
    projectId = (await project.json()).id;

    const upload = await request.post(`${API}/api/projects/${projectId}/assets`, {
      multipart: {
        file: { name: "e2e_direct_approve_ref.png", mimeType: "image/png", buffer: ONE_PIXEL_PNG },
        tag: "e2e_direct_approve_ref",
        kind: "image",
      },
    });
    expect(upload.ok()).toBeTruthy();
    assetId = (await upload.json()).id;
  });

  test.afterAll(async ({ request }) => {
    // Delete the sheet before the project so a (possibly Global) sheet is never
    // orphaned by project deletion.
    if (projectId && sheetId) {
      await request.delete(
        `${API}/api/environment-reference-sheets/projects/${projectId}/${sheetId}`
      );
    }
    if (projectId) await request.delete(`${API}/api/projects/${projectId}`);
  });

  test("library image → approve → lower list → reload → resolver/binding contract", async ({
    page,
    request,
  }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (err) => pageErrors.push(String(err)));
    // Track failed responses with URLs. Allowed noise (pre-existing product
    // behavior, unrelated to this flow):
    //  - GET codirector bible 404: a fresh disposable project has no Story
    //    bible yet; the story-theme inheritance effect probes and handles it.
    //  - PATCH identity 403: GlobalScopeField patches the auto-hydrated foreign
    //    Global sheet when we uncheck Global; the product catches it silently.
    // Everything else on OUR project must stay clean.
    const failedOnOurProject: string[] = [];
    page.on("response", (res) => {
      const url = res.url();
      if (res.status() < 400) return;
      if (!url.includes(projectId)) return;
      if (res.status() === 404 && url.includes("/bible")) return;
      if (res.status() === 403 && url.includes("/identity")) return;
      failedOnOurProject.push(`${res.status()} ${url}`);
    });

    await page.goto(`/project/${projectId}?workspace=environmentcreator`);
    await expect(page.getByTestId("environment-creator-surface")).toBeVisible({ timeout: 30_000 });

    // No image attached yet → Approve disabled.
    const approveBtn = page.getByTestId("environment-creator-approve-source").first();
    await expect(approveBtn).toBeVisible();
    await expect(approveBtn).toBeDisabled();

    // Name the environment identity.
    await page.getByTestId("environment-creator-name").fill(ENV_NAME);

    // Disposable environment stays project-scoped: the surface inherits Global
    // scope from any auto-hydrated Global sheet, so explicitly uncheck it.
    const globalCheckbox = page.getByTestId("environment-creator-global-checkbox");
    if (await globalCheckbox.isChecked()) {
      await globalCheckbox.click();
      await expect(globalCheckbox).not.toBeChecked();
    }

    // Attach the library image.
    await page.getByTestId("environment-creator-choose-source").click();
    await expect(page.getByTestId("environment-picker-grid")).toBeVisible({ timeout: 15_000 });
    await page.getByTestId(`environment-asset-${assetId}`).click();
    await page.getByTestId("environment-picker-confirm").click();

    // Image attached, not approved → Approve enabled.
    await expect(page.getByTestId("environment-creator-source")).toBeVisible({ timeout: 10_000 });
    const approveReady = page.getByTestId("environment-creator-approve-source");
    await expect(approveReady).toBeEnabled();
    await expect(approveReady).toHaveText("Approve as Environment");
    await expect(approveReady).toHaveAttribute("data-approved", "false");

    // Approve — unsaved plan is upserted first, then approved (one committed action).
    await approveReady.click();
    await expect(approveReady).toHaveText("Approved Environment ✓", { timeout: 30_000 });
    await expect(approveReady).toHaveAttribute("data-approved", "true");
    await expect(approveReady).toBeDisabled();

    // Lower panel hydrates immediately — approved item with thumbnail.
    const sheetItem = page
      .getByTestId("environment-creator-sheet-item")
      .filter({ hasText: ENV_NAME });
    await expect(sheetItem).toHaveCount(1, { timeout: 15_000 });
    await expect(sheetItem).toContainText("approved");
    await expect(sheetItem.getByTestId("environment-creator-sheet-thumb")).toBeVisible();

    // Reload → approval persists.
    await page.reload();
    await expect(page.getByTestId("environment-creator-surface")).toBeVisible({ timeout: 30_000 });
    const sheetItemAfter = page
      .getByTestId("environment-creator-sheet-item")
      .filter({ hasText: ENV_NAME });
    await expect(sheetItemAfter).toHaveCount(1, { timeout: 15_000 });
    await expect(sheetItemAfter).toContainText("approved");
    await expect(sheetItemAfter.getByTestId("environment-creator-sheet-thumb")).toBeVisible();

    // Select the sheet → attached reference hydrates as the approved visual.
    await sheetItemAfter.getByTestId("environment-creator-select-sheet").click();
    const approveHydrated = page.getByTestId("environment-creator-approve-source");
    await expect(approveHydrated).toHaveText("Approved Environment ✓", { timeout: 15_000 });
    await expect(approveHydrated).toHaveAttribute("data-approved", "true");

    // ── Co-Director resolution contract (HTTP surface the resolver binds from) ──
    const sheetsRes = await request.get(
      `${API}/api/environment-reference-sheets/projects/${projectId}`
    );
    expect(sheetsRes.ok()).toBeTruthy();
    const sheetsBody = await sheetsRes.json();
    const sheet = (sheetsBody.sheets || []).find(
      (s: { name?: string }) => s.name === ENV_NAME
    );
    expect(sheet, "approved sheet visible in project list").toBeTruthy();
    expect(sheet.status).toBe("approved");
    // Official environment visual IS the attached library image — same identity,
    // no duplicate environment.
    expect(sheet.ers_composite_asset_id).toBe(assetId);
    sheetId = String(sheet.sheetId || "");
    expect(sheetId).toBeTruthy();

    // Canonical #EnvironmentTag unchanged — full sheet record carries it.
    const fullRes = await request.get(
      `${API}/api/environment-reference-sheets/projects/${projectId}/${sheetId}`
    );
    expect(fullRes.ok()).toBeTruthy();
    const full = await fullRes.json();
    expect(String(full.sheet.canonicalTag || "").replace(/^#/, "").toLowerCase()).toBe(
      EXPECTED_TAG
    );
    // Plan keeps the attached reference image as reference_asset_id.
    expect(
      String(full.sheet.provenance?.details?.environmentCreatorPlan?.referenceImageAssetId || "")
    ).toBe(assetId);

    // ── Timeline binding: same environment identity + approved asset ──
    const bindRes = await request.post(`${API}/api/projects/${projectId}/references`, {
      data: {
        asset_id: assetId,
        scope_type: "project",
        scope_id: projectId,
        reference_type: "environment",
        media_kind: "image",
        alias: ENV_NAME,
        usage_modes: ["environment"],
        reference_roles: ["environment"],
        identity_id: sheetId,
      },
    });
    expect(bindRes.ok()).toBeTruthy();
    const binding = await bindRes.json();
    const bindingId = binding.id;
    expect(bindingId).toBeTruthy();

    const bindingRes = await request.get(
      `${API}/api/projects/${projectId}/references/id/${bindingId}`
    );
    expect(bindingRes.ok()).toBeTruthy();
    const resolvedBinding = await bindingRes.json();
    expect(resolvedBinding.identity_id ?? resolvedBinding.identityId).toBe(sheetId);
    expect(resolvedBinding.asset_id ?? resolvedBinding.assetId).toBe(assetId);

    expect(pageErrors, `page errors: ${pageErrors.join(" | ")}`).toEqual([]);
    expect(
      failedOnOurProject,
      `failed requests on our project: ${failedOnOurProject.join(" | ")}`
    ).toEqual([]);
  });
});
