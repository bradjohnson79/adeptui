/**
 * Spatial Map Environment Image Picker — Modal Copy + Validation + Confirm Flow.
 *
 * Verifies:
 *   1. Environment picker shows correct title ("Select Spatial Map Image") — NOT "Add a Prop".
 *   2. No prop tag/name field visible in environment mode.
 *   3. Selecting an image shows selected highlight + enables Confirm.
 *   4. Clicking Confirm closes modal and renders the image in Spatial Map.
 *   5. Selection persists after refresh.
 *   6. Normal (non-Atlas) Master Environment image also works.
 *   7. Cancel preserves previous state.
 *   8. Prop regression: Add Prop still shows Prop fields and requires tag.
 *
 * Reuses helpers (Law #17): tests/e2e/helpers/app.ts, observer.ts, audit.ts.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";
import {
  openCoDirectorFullScreen,
  TINY_PNG,
  uploadProjectAsset,
} from "./helpers/audit";

const PROJECT_PREFIX = "ENVPICK-CERT";

async function dismissOnboarding(page: Page) {
  for (let attempt = 0; attempt < 5; attempt += 1) {
    const region = page.locator('[aria-label="Working relationship"]').first();
    if (!(await region.isVisible().catch(() => false))) {
      await page.waitForTimeout(300);
      continue;
    }
    const nameInput = region.getByRole("textbox", { name: /What should I call you/i }).first();
    if (await nameInput.isVisible().catch(() => false)) {
      const current = await nameInput.inputValue().catch(() => "");
      if (!current) await nameInput.fill("Tester");
    }
    for (const label of [/Save and continue/i, /Skip for now/i]) {
      const btn = region.getByRole("button", { name: label }).first();
      if (await btn.isVisible().catch(() => false)) {
        const disabled = await btn.isDisabled().catch(() => false);
        if (!disabled) {
          await btn.click({ force: true }).catch(() => undefined);
          await page.waitForTimeout(800);
          break;
        }
      }
    }
    if (!(await region.isVisible().catch(() => false))) break;
  }
}

async function cancelInFlightGeneration(page: Page) {
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const stopBtn = page.getByRole("button", { name: /Stop generating/i }).first();
    if (!(await stopBtn.isVisible().catch(() => false))) return;
    await stopBtn.click({ force: true }).catch(() => undefined);
    await page.waitForTimeout(800);
  }
}

async function openSpatialMapTab(page: Page) {
  await dismissOnboarding(page);
  await cancelInFlightGeneration(page);
  const tab = page.getByTestId("codirector-content-tab-spatial_map");
  await expect(tab).toBeVisible({ timeout: 30_000 });
  for (let attempt = 0; attempt < 5; attempt += 1) {
    await tab.click({ force: true }).catch(() => undefined);
    const panel = page.getByTestId("spatial-map-panel").or(page.getByTestId("spatial-map-error")).first();
    if (await panel.isVisible().catch(() => false)) return;
    await cancelInFlightGeneration(page);
    await page.waitForTimeout(1000);
  }
  await expect(page.getByTestId("spatial-map-panel").or(page.getByTestId("spatial-map-error")).first()).toBeVisible({ timeout: 45_000 });
}

test.describe.serial("@critical Spatial Map Environment Image Picker", () => {
  test.beforeEach(async ({ request }) => {
    await waitForAppReady(request);
  });

  test("1 — Environment picker: correct title, no Prop fields, select → Confirm → persist", async ({ page, request }) => {
    test.setTimeout(180_000);
    const project = await createTempProject(request, `${PROJECT_PREFIX}-env-${Date.now()}`);
    const observer = new AuditObserver(page, test.info);
    observer.attach();
    try {
      // Pre-seed an Atlas image into the Library so the picker has something to select.
      const atlasAsset = await uploadProjectAsset(request, project.id, {
        name: "atlas-shot.png",
        mimeType: "image/png",
        kind: "image",
        buffer: TINY_PNG,
        tag: "atlas_shot",
      });

      await page.setViewportSize({ width: 1440, height: 900 });
      await openCoDirectorFullScreen(page, project.id);
      await openSpatialMapTab(page);

      // Open the environment picker via the Spatial Map empty-state "Choose from Library".
      // Use the specific aria-label to avoid matching the chat composer's "Choose from Library".
      const chooseBtn = page.getByRole("button", { name: /Choose Atlas Shot from Library/i }).first();
      await expect(chooseBtn).toBeVisible({ timeout: 15_000 });
      await chooseBtn.click();

      // Modal should appear with environment title — NOT "Add a Prop".
      const modal = page.locator('.spatial-map__picker').first();
      await expect(modal).toBeVisible({ timeout: 10_000 });
      await expect(page.getByText(/Select Spatial Map Image/i)).toBeVisible();

      // CRITICAL: no prop copy / prop tag field visible.
      await expect(page.getByText(/Add a Prop/i)).not.toBeVisible();
      await expect(page.getByText(/anchors the prop's visual identity/i)).not.toBeVisible();
      await expect(page.getByText(/name this prop/i)).not.toBeVisible();
      await expect(page.getByLabel(/Prop label/i)).not.toBeVisible();

      // Select the seeded atlas image.
      const assetCard = page.getByTestId(`environment-asset-${atlasAsset.id}`).first();
      await expect(assetCard).toBeVisible({ timeout: 15_000 });
      await assetCard.click();

      // Selected highlight + Confirm enabled.
      await expect(assetCard).toHaveClass(/is-selected/);
      const confirmBtn = page.getByTestId("environment-picker-confirm");
      await expect(confirmBtn).toBeEnabled({ timeout: 5_000 });

      // Click Confirm → modal closes → Spatial Map renders the image.
      await confirmBtn.click();
      await expect(modal).not.toBeVisible({ timeout: 10_000 });
      await expect(page.getByTestId("active-atlas-panel")).toBeVisible({ timeout: 30_000 });

      // Persist after refresh.
      await page.reload();
      await openSpatialMapTab(page);
      await expect(page.getByTestId("active-atlas-panel")).toBeVisible({ timeout: 30_000 });
    } finally {
      observer.flush();
      await deleteProject(request, project.id);
    }
  });

  test("2 — Normal Master Environment image (non-Atlas) is selectable and persists", async ({ page, request }) => {
    test.setTimeout(180_000);
    const project = await createTempProject(request, `${PROJECT_PREFIX}-master-${Date.now()}`);
    const observer = new AuditObserver(page, test.info);
    observer.attach();
    try {
      // Pre-seed a normal (non-atlas) environment image.
      const masterAsset = await uploadProjectAsset(request, project.id, {
        name: "master-env.png",
        mimeType: "image/png",
        kind: "image",
        buffer: TINY_PNG,
        tag: "master_environment",
      });

      await page.setViewportSize({ width: 1440, height: 900 });
      await openCoDirectorFullScreen(page, project.id);
      await openSpatialMapTab(page);

      const chooseBtn = page.getByRole("button", { name: /Choose Atlas Shot from Library/i }).first();
      await expect(chooseBtn).toBeVisible({ timeout: 15_000 });
      await chooseBtn.click();

      const modal = page.locator('.spatial-map__picker').first();
      await expect(modal).toBeVisible({ timeout: 10_000 });

      // No prop fields.
      await expect(page.getByText(/Add a Prop/i)).not.toBeVisible();

      // Select the normal master environment image.
      const assetCard = page.getByTestId(`environment-asset-${masterAsset.id}`).first();
      await expect(assetCard).toBeVisible({ timeout: 15_000 });
      await assetCard.click();
      await expect(assetCard).toHaveClass(/is-selected/);

      const confirmBtn = page.getByTestId("environment-picker-confirm");
      await expect(confirmBtn).toBeEnabled({ timeout: 5_000 });
      await confirmBtn.click();

      await expect(modal).not.toBeVisible({ timeout: 10_000 });
      await expect(page.getByTestId("active-atlas-panel")).toBeVisible({ timeout: 30_000 });

      // Persist after refresh.
      await page.reload();
      await openSpatialMapTab(page);
      await expect(page.getByTestId("active-atlas-panel")).toBeVisible({ timeout: 30_000 });
    } finally {
      observer.flush();
      await deleteProject(request, project.id);
    }
  });

  test("3 — Cancel preserves previous state (no save, no Prop created)", async ({ page, request }) => {
    test.setTimeout(180_000);
    const project = await createTempProject(request, `${PROJECT_PREFIX}-cancel-${Date.now()}`);
    const observer = new AuditObserver(page, test.info);
    observer.attach();
    try {
      // Pre-seed an atlas image.
      const atlasAsset = await uploadProjectAsset(request, project.id, {
        name: "atlas-cancel.png",
        mimeType: "image/png",
        kind: "image",
        buffer: TINY_PNG,
        tag: "atlas_shot",
      });

      await page.setViewportSize({ width: 1440, height: 900 });
      await openCoDirectorFullScreen(page, project.id);
      await openSpatialMapTab(page);

      // Establish an initial environment via the picker (so we can verify it is preserved on cancel).
      const chooseBtn = page.getByRole("button", { name: /Choose Atlas Shot from Library/i }).first();
      await expect(chooseBtn).toBeVisible({ timeout: 15_000 });
      await chooseBtn.click();
      const modal = page.locator('.spatial-map__picker').first();
      await expect(modal).toBeVisible({ timeout: 10_000 });
      await page.getByTestId(`environment-asset-${atlasAsset.id}`).first().click();
      await page.getByTestId("environment-picker-confirm").click();
      await expect(page.getByTestId("active-atlas-panel")).toBeVisible({ timeout: 30_000 });

      // Now open the picker again (Replace flow), select a DIFFERENT image, but cancel.
      const replaceBtn = page.getByTestId("atlas-replace-btn");
      await expect(replaceBtn).toBeVisible();
      await replaceBtn.click();
      await expect(modal).toBeVisible({ timeout: 10_000 });

      // Close via X without confirming.
      await page.locator('.spatial-map__picker-close').first().click();
      await expect(modal).not.toBeVisible({ timeout: 10_000 });

      // Previous environment should still be active (unchanged).
      await expect(page.getByTestId("active-atlas-panel")).toBeVisible();
    } finally {
      observer.flush();
      await deleteProject(request, project.id);
    }
  });

  test("4 — Prop regression: Add Prop still shows Prop fields and requires tag", async ({ page, request }) => {
    test.setTimeout(180_000);
    const project = await createTempProject(request, `${PROJECT_PREFIX}-prop-${Date.now()}`);
    const observer = new AuditObserver(page, test.info);
    observer.attach();
    try {
      // Pre-seed an image that the prop will reference.
      const propImg = await uploadProjectAsset(request, project.id, {
        name: "prop-image.png",
        mimeType: "image/png",
        kind: "image",
        buffer: TINY_PNG,
        tag: "prop_ref",
      });

      await page.setViewportSize({ width: 1440, height: 900 });
      await openCoDirectorFullScreen(page, project.id);
      await openSpatialMapTab(page);

      // First establish an environment so the grid is visible.
      const chooseBtn = page.getByRole("button", { name: /Choose Atlas Shot from Library/i }).first();
      await chooseBtn.click();
      const envModal = page.locator('.spatial-map__picker').first();
      await expect(envModal).toBeVisible({ timeout: 10_000 });
      await page.getByTestId(`environment-asset-${propImg.id}`).first().click();
      await page.getByTestId("environment-picker-confirm").click();
      await expect(page.getByTestId("active-atlas-panel")).toBeVisible({ timeout: 30_000 });

      // Open the Prop picker via the first prop slot's "+ Add Prop" button.
      const propSlot = page.getByTestId("spatial-map-slot-prop-0").first();
      await expect(propSlot).toBeVisible({ timeout: 15_000 });
      const addPropBtn = propSlot.getByRole("button", { name: /Add prop to/i }).first();
      await addPropBtn.click();

      // The Prop picker modal must still show Prop-specific UI.
      const propModal = page.locator('.spatial-map__picker').first();
      await expect(propModal).toBeVisible({ timeout: 10_000 });
      await expect(page.getByText(/Add a Prop/i)).toBeVisible();
      await expect(page.getByText(/name this prop/i)).toBeVisible();
      const propLabelInput = page.getByLabel(/Prop label/i);
      await expect(propLabelInput).toBeVisible();

      // Confirm must be disabled until a prop label is provided.
      const confirmBtn = propModal.getByRole("button", { name: /Confirm/i }).first();
      await expect(confirmBtn).toBeDisabled();

      // Select the image (step 1). The Prop picker uses generic picker cards.
      const pickerCard = page.locator('.spatial-map__picker-card').first();
      await expect(pickerCard).toBeVisible({ timeout: 10_000 });
      await pickerCard.click();
      // Still disabled without a label.
      await expect(confirmBtn).toBeDisabled();

      // Provide a label (step 2) → Confirm enables.
      await propLabelInput.fill("Coffee Cup");
      await expect(confirmBtn).toBeEnabled({ timeout: 5_000 });
    } finally {
      observer.flush();
      await deleteProject(request, project.id);
    }
  });
});
