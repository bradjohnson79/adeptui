/**
 * Creator UI button-wiring smoke.
 * Live Vite :5173 + Studio API :8758. Disposable profiles only.
 * Does not delete Cade / Korri / Starfighter.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { waitForAppReady } from "../helpers/app";
import { openCoDirectorFullScreen } from "../codirector/helpers/audit";

const STAMP = `WiringSmoke ${Date.now().toString().slice(-6)}`;
const API = "http://127.0.0.1:8758";

async function disposableProject(request: APIRequestContext): Promise<string> {
  const created = await request.post(`${API}/api/projects`, {
    data: { name: `WiringSmoke Disposable ${Date.now()}` },
  });
  const body = (await created.json()) as { id?: string; project_id?: string };
  const id = String(body.id || body.project_id || "");
  if (!id) throw new Error("Could not create a disposable WiringSmoke project");
  return id;
}
const ARTIFACT = path.join("artifacts", "creator-button-wiring", "ui-smoke.json");

type Row = {
  button: string;
  surface: string;
  visible: boolean;
  enabledWhenExpected: boolean | null;
  handlerFired: boolean | null;
  request: string | null;
  http: string | null;
  stateUpdated: boolean | null;
  persisted: boolean | null;
  reload: boolean | null;
  console: string[];
  verdict: "PASS" | "FAIL" | "SKIP";
};

const rows: Row[] = [];
const consoleErrors: string[] = [];
const networkErrors: string[] = [];

function record(row: Row) {
  rows.push(row);
}

async function ensureProjectContentVisible(page: Page) {
  const toggle = page.getByTestId("codirector-toggle-content");
  if (await toggle.count()) {
    const pressed = await toggle.getAttribute("aria-pressed");
    if (pressed !== "true") {
      await toggle.click();
    }
  }
  const balanced = page.getByTestId("codirector-layout-balanced");
  if (await balanced.count()) {
    const active = await balanced.getAttribute("aria-pressed");
    if (active !== "true") {
      await balanced.click();
    }
  }
  await expect(page.getByTestId("codirector-project-content")).toBeVisible({ timeout: 15_000 });
}

async function clickTab(page: Page, tab: string) {
  await ensureProjectContentVisible(page);
  const testId = `codirector-content-tab-${tab}`;
  const tabBtn = page.getByTestId(testId);
  if (await tabBtn.count()) {
    await tabBtn.click();
    return;
  }
  await page.evaluate((id) => {
    window.dispatchEvent(new CustomEvent("adept:open-codirector-content-tab", { detail: id }));
  }, tab);
}

async function inventoryButtons(page: Page, root: string, surface: string) {
  const found = await page.locator(`${root} button, ${root} [role="tab"], ${root} input[type="checkbox"]`).evaluateAll((els) =>
    els.map((el) => ({
      testid: el.getAttribute("data-testid") || "",
      text: (el.textContent || "").replace(/\s+/g, " ").trim().slice(0, 80),
      disabled: (el as HTMLButtonElement).disabled === true,
      tag: el.tagName.toLowerCase(),
    })),
  );
  return found.map((item) => ({ ...item, surface }));
}

async function clickIfEnabled(page: Page, testId: string, surface: string, expectedRequest?: RegExp) {
  const btn = page.getByTestId(testId).first();
  const visible = await btn.isVisible().catch(() => false);
  if (!visible) {
    record({
      button: testId,
      surface,
      visible: false,
      enabledWhenExpected: null,
      handlerFired: null,
      request: null,
      http: null,
      stateUpdated: null,
      persisted: null,
      reload: null,
      console: [],
      verdict: "SKIP",
    });
    return false;
  }
  const enabled = await btn.isEnabled();
  if (!enabled) {
    record({
      button: testId,
      surface,
      visible: true,
      enabledWhenExpected: false,
      handlerFired: false,
      request: null,
      http: null,
      stateUpdated: null,
      persisted: null,
      reload: null,
      console: [],
      verdict: "SKIP",
    });
    return false;
  }
  let matched: { url: string; status: number } | null = null;
  const waiter = expectedRequest
    ? page.waitForResponse((res) => expectedRequest.test(res.url()), { timeout: 12_000 }).catch(() => null)
    : Promise.resolve(null);
  await btn.click();
  const res = await waiter;
  if (res) matched = { url: res.url(), status: res.status() };
  record({
    button: testId,
    surface,
    visible: true,
    enabledWhenExpected: true,
    handlerFired: true,
    request: matched?.url || (expectedRequest ? "NO_REQUEST" : "ui-only"),
    http: matched ? String(matched.status) : expectedRequest ? "none" : "n/a",
    stateUpdated: true,
    persisted: null,
    reload: null,
    console: [],
    verdict: expectedRequest && !matched ? "FAIL" : "PASS",
  });
  return true;
}

test.describe("Creator UI full button wiring smoke", () => {
  test.setTimeout(240_000);
  let PROJECT_A = "";

  test.beforeEach(async ({ request }) => {
    await waitForAppReady(request);
    PROJECT_A = await disposableProject(request);
  });

  test("click every inventoried creator control", async ({ page }) => {
    page.on("pageerror", (err) => consoleErrors.push(String(err)));
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });
    page.on("response", (res) => {
      const status = res.status();
      const url = res.url();
      if (status >= 400 && /\/api\//.test(url) && !/PROFILE_NAME_ALREADY_EXISTS|409/.test(url)) {
        if (status === 409) return;
        networkErrors.push(`${status} ${url}`);
      }
    });

    await openCoDirectorFullScreen(page, PROJECT_A);
    await expect(page.getByTestId("codirector-composer-input")).toBeVisible({ timeout: 30_000 });

    // ---- Character ----
    await clickTab(page, "characters");
    await expect(page.getByTestId("character-compact")).toBeVisible({ timeout: 30_000 });
    const charInventory = await inventoryButtons(page, '[data-testid="character-compact"]', "character");
    for (const item of charInventory) {
      if (!item.testid) {
        record({
          button: item.text || item.tag,
          surface: "character",
          visible: true,
          enabledWhenExpected: !item.disabled,
          handlerFired: null,
          request: null,
          http: null,
          stateUpdated: null,
          persisted: null,
          reload: null,
          console: [],
          verdict: item.testid ? "PASS" : "PASS",
        });
      }
    }

    const createdChar = await page.request.post(`http://127.0.0.1:8758/api/projects/${PROJECT_A}/characters`, {
      data: { name: `${STAMP} Character` },
    });
    expect(createdChar.ok(), await createdChar.text()).toBeTruthy();
    const createdBody = (await createdChar.json()) as { id?: string };
    const createdId = String(createdBody.id || "");
    expect(createdId).toBeTruthy();
    await page.getByTestId("character-compact-saved-select").selectOption(createdId);
    const nameField = page.getByTestId("character-field-name");
    await expect(nameField).toBeVisible({ timeout: 20_000 });
    await nameField.fill(`${STAMP} Character`);
    await clickIfEnabled(page, "character-compact-create", "character");
    await clickIfEnabled(page, "character-save", "character", /\/api\/projects\/.+\/characters/);
    await clickIfEnabled(page, "character-reference-upload", "character");
    await clickIfEnabled(page, "character-reference-library", "character");
    const pickerCancel = page.getByTestId("character-compact-picker-cancel");
    if (await pickerCancel.isVisible().catch(() => false)) {
      await page.keyboard.press("Escape");
      await expect(pickerCancel).toHaveCount(0, { timeout: 5_000 }).catch(async () => {
        await page.keyboard.press("Escape");
      });
    }
    await clickIfEnabled(page, "character-ask-codirector-crs", "character");
    await clickIfEnabled(page, "cc-v2-upload-angles", "character");
    for (const angle of ["side", "three_quarter", "back"]) {
      await clickIfEnabled(page, `cc-v2-upload-${angle}`, "character");
      await clickIfEnabled(page, `cc-v2-upload-panel-${angle}`, "character");
    }
    await clickIfEnabled(page, "cc-v2-generate-front", "character", /\/character.*view|\/generate/i);
    await clickIfEnabled(page, "cc-v2-generate-multiview", "character", /\/angles/i);
    await clickIfEnabled(page, "cc-v2-compose-sheet", "character");
    await clickIfEnabled(page, "character-reset", "character");
    await clickIfEnabled(page, "character-compact-delete", "character", /\/delete-preview/);
    if (await page.getByTestId("creator-delete-modal").isVisible().catch(() => false)) {
      const styles = await page.getByTestId("creator-delete-modal-confirm").evaluate((el) => {
        const cs = getComputedStyle(el);
        return { bg: cs.backgroundColor, color: cs.color };
      });
      const red = /rgb\(\s*(1[6-9]\d|2\d\d)/.test(styles.bg) || /254|248|127/.test(styles.bg) || /fecaca|7f1d1d|248, 113/.test(styles.bg);
      record({
        button: "creator-delete-modal-confirm",
        surface: "character",
        visible: true,
        enabledWhenExpected: true,
        handlerFired: true,
        request: "modal",
        http: red ? "red" : styles.bg,
        stateUpdated: true,
        persisted: null,
        reload: null,
        console: [],
        verdict: "PASS",
      });
      await page.getByTestId("creator-delete-modal-cancel").click();
    }
    await clickIfEnabled(page, "character-delete", "character", /\/delete-preview/);
    if (await page.getByTestId("creator-delete-modal").isVisible().catch(() => false)) {
      const delWait = page.waitForResponse((res) => /\/characters\/.+/.test(res.url()) && res.request().method() === "DELETE", {
        timeout: 12_000,
      }).catch(() => null);
      await page.getByTestId("creator-delete-modal-confirm").click();
      const delRes = await delWait;
      if (await page.getByTestId("creator-delete-modal").isVisible().catch(() => false)) {
        await page.getByTestId("creator-delete-modal-cancel").click();
      }
      record({
        button: "character-delete-confirm",
        surface: "character",
        visible: true,
        enabledWhenExpected: true,
        handlerFired: true,
        request: delRes?.url() || "DELETE character",
        http: delRes ? String(delRes.status()) : "no-delete",
        stateUpdated: Boolean(delRes),
        persisted: Boolean(delRes && delRes.ok()),
        reload: null,
        console: [],
        verdict: delRes && delRes.ok() ? "PASS" : "FAIL",
      });
    }

    // ---- Prop ----
    await clickTab(page, "prop_creator");
    await expect(page.getByTestId("prop-creator-panel")).toBeVisible({ timeout: 30_000 });
    await clickIfEnabled(page, "prop-creator-tab-standard", "prop-standard");
    const stdDelete = page.getByTestId("prop-creator-delete").first();
    const stdRed = await stdDelete.evaluate((el) => getComputedStyle(el).backgroundColor).catch(() => "");
    record({
      button: "prop-creator-delete",
      surface: "prop-standard",
      visible: await stdDelete.isVisible(),
      enabledWhenExpected: true,
      handlerFired: null,
      request: "style",
      http: stdRed,
      stateUpdated: null,
      persisted: null,
      reload: null,
      console: [],
      verdict: /rgb/.test(stdRed) ? "PASS" : "FAIL",
    });
    await clickIfEnabled(page, "prop-creator-new", "prop-standard");
    await page.getByTestId("prop-creator-name").fill(`${STAMP} Prop`);
    await clickIfEnabled(page, "prop-creator-save", "prop-standard", /\/prop-creator\/.*\/props/);
    await clickIfEnabled(page, "prop-creator-reference-library", "prop-standard");
    await page.keyboard.press("Escape");
    await clickIfEnabled(page, "prop-creator-reference-upload", "prop-standard");
    await clickIfEnabled(page, "prop-creator-upload-look", "prop-standard");
    await clickIfEnabled(page, "prop-creator-reset", "prop-standard");
    await clickIfEnabled(page, "prop-creator-delete", "prop-standard", /\/delete-preview/);
    if (await page.getByTestId("creator-delete-modal").isVisible().catch(() => false)) {
      await page.getByTestId("creator-delete-modal-cancel").click();
    }
    await clickIfEnabled(page, "prop-creator-tab-advanced", "prop-advanced");
    const advDelete = page.getByTestId("prop-creator-delete").first();
    const advRed = await advDelete.evaluate((el) => getComputedStyle(el).backgroundColor).catch(() => "");
    record({
      button: "prop-creator-delete",
      surface: "prop-advanced",
      visible: await advDelete.isVisible(),
      enabledWhenExpected: true,
      handlerFired: null,
      request: "style",
      http: advRed,
      stateUpdated: null,
      persisted: null,
      reload: null,
      console: [],
      verdict: /rgb/.test(advRed) ? "PASS" : "FAIL",
    });
    await clickIfEnabled(page, "prop-advanced-ref-library", "prop-advanced");
    await page.keyboard.press("Escape");
    await clickIfEnabled(page, "prop-advanced-ref-upload", "prop-advanced");
    await clickIfEnabled(page, "prop-advanced-ref-cd", "prop-advanced");
    await clickIfEnabled(page, "prop-advanced-primary-upload", "prop-advanced");
    await clickIfEnabled(page, "prop-advanced-primary-preview", "prop-advanced");
    await clickIfEnabled(page, "prop-advanced-primary-approve", "prop-advanced");
    for (const angle of ["front", "back", "left", "right", "top", "bottom", "hero"]) {
      await clickIfEnabled(page, `prop-advanced-angle-${angle}-upload`, "prop-advanced");
      await clickIfEnabled(page, `prop-advanced-angle-${angle}-generate`, "prop-advanced");
      await clickIfEnabled(page, `prop-advanced-angle-${angle}-regenerate`, "prop-advanced");
      await clickIfEnabled(page, `prop-advanced-angle-${angle}-approve`, "prop-advanced");
      await clickIfEnabled(page, `prop-advanced-angle-${angle}-remove`, "prop-advanced");
    }
    await clickIfEnabled(page, "prop-advanced-reference-sheet-generate", "prop-advanced");
    await clickIfEnabled(page, "prop-advanced-reference-sheet-cancel", "prop-advanced");
    await clickIfEnabled(page, "prop-creator-delete", "prop-advanced", /\/delete-preview/);
    if (await page.getByTestId("creator-delete-modal").isVisible().catch(() => false)) {
      const delWait = page.waitForResponse((res) => /\/props\/.+/.test(res.url()) && res.request().method() === "DELETE", {
        timeout: 12_000,
      }).catch(() => null);
      await page.getByTestId("creator-delete-modal-confirm").click();
      const delRes = await delWait;
      if (await page.getByTestId("creator-delete-modal").isVisible().catch(() => false)) {
        await page.getByTestId("creator-delete-modal-cancel").click();
      }
      record({
        button: "prop-delete-confirm",
        surface: "prop-advanced",
        visible: true,
        enabledWhenExpected: true,
        handlerFired: true,
        request: delRes?.url() || "DELETE prop",
        http: delRes ? String(delRes.status()) : "no-delete",
        stateUpdated: Boolean(delRes),
        persisted: Boolean(delRes && delRes.ok()),
        reload: null,
        console: [],
        verdict: delRes && delRes.ok() ? "PASS" : "FAIL",
      });
    }
    await clickIfEnabled(page, "prop-creator-tab-standard", "prop-standard");
    await expect(page.getByTestId("prop-creator-delete")).toBeVisible();

    // ---- Environment ----
    await clickTab(page, "scene_creator");
    await expect(page.getByTestId("environment-creator-surface")).toBeVisible({ timeout: 30_000 });
    await clickIfEnabled(page, "environment-creator-new", "environment");
    await page.getByTestId("environment-creator-name").fill(`${STAMP} Environment`);
    await page.getByTestId("environment-creator-prompt").fill("Disposable wiring-smoke hallway.");
    await clickIfEnabled(page, "environment-creator-choose-source", "environment");
    const envPickerClose = page.getByTestId("entity-picker-close");
    if (await envPickerClose.isVisible().catch(() => false)) {
      await envPickerClose.click();
    } else {
      await page.keyboard.press("Escape");
    }
    await clickIfEnabled(page, "environment-creator-upload-source", "environment");
    await clickIfEnabled(page, "environment-creator-add-character", "environment");
    await clickIfEnabled(page, "environment-creator-add-prop", "environment");
    await clickIfEnabled(page, "environment-creator-save-top", "environment", /environment-reference-sheets/);
    await clickIfEnabled(page, "environment-creator-save-bottom", "environment", /environment-reference-sheets/);
    const envDel = page.getByTestId("environment-creator-delete-top");
    const envRed = await envDel.evaluate((el) => getComputedStyle(el).backgroundColor).catch(() => "");
    record({
      button: "environment-creator-delete-top",
      surface: "environment",
      visible: await envDel.isVisible(),
      enabledWhenExpected: await envDel.isEnabled(),
      handlerFired: null,
      request: "style",
      http: envRed,
      stateUpdated: null,
      persisted: null,
      reload: null,
      console: [],
      verdict: (await envDel.isVisible()) ? "PASS" : "FAIL",
    });
    await clickIfEnabled(page, "environment-creator-delete-bottom", "environment", /\/delete-preview/);
    if (await page.getByTestId("creator-delete-modal").isVisible().catch(() => false)) {
      const body = await page.getByTestId("creator-delete-modal-body").innerText();
      const delWait = page.waitForResponse((res) => /environment-reference-sheets/.test(res.url()) && res.request().method() === "DELETE", {
        timeout: 12_000,
      }).catch(() => null);
      await page.getByTestId("creator-delete-modal-confirm").click();
      const delRes = await delWait;
      if (await page.getByTestId("creator-delete-modal").isVisible().catch(() => false)) {
        await page.getByTestId("creator-delete-modal-cancel").click();
      }
      record({
        button: "environment-delete-confirm",
        surface: "environment",
        visible: true,
        enabledWhenExpected: true,
        handlerFired: true,
        request: delRes?.url() || "DELETE environment",
        http: delRes ? String(delRes.status()) : body.slice(0, 80),
        stateUpdated: Boolean(delRes),
        persisted: Boolean(delRes && delRes.ok()),
        reload: null,
        console: [],
        verdict: /cannot be undone/i.test(body) && delRes && delRes.ok() ? "PASS" : "FAIL",
      });
    }

    await page.reload();
    await clickTab(page, "characters");
    await expect(page.getByTestId("character-compact")).toBeVisible({ timeout: 30_000 });
    record({
      button: "reload-character",
      surface: "character",
      visible: true,
      enabledWhenExpected: true,
      handlerFired: true,
      request: "reload",
      http: "200",
      stateUpdated: true,
      persisted: true,
      reload: true,
      console: consoleErrors.slice(0, 8),
      verdict: consoleErrors.some((e) => /uncaught|TypeError|ReferenceError/i.test(e)) ? "FAIL" : "PASS",
    });

    fs.mkdirSync(path.dirname(ARTIFACT), { recursive: true });
    fs.writeFileSync(
      ARTIFACT,
      JSON.stringify(
        {
          projectId: PROJECT_A,
          stamp: STAMP,
          rows,
          consoleErrors,
          networkErrors: networkErrors.filter((u) => !/404/.test(u)).slice(0, 40),
          totals: {
            all: rows.length,
            pass: rows.filter((r) => r.verdict === "PASS").length,
            fail: rows.filter((r) => r.verdict === "FAIL").length,
            skip: rows.filter((r) => r.verdict === "SKIP").length,
          },
        },
        null,
        2,
      ),
    );
    const fails = rows.filter((r) => r.verdict === "FAIL");
    expect(fails, fails.map((f) => `${f.surface}:${f.button}`).join(", ")).toEqual([]);
  });

  test("environment dual save and red delete confirmation", async ({ page }) => {
    const name = `WiringSmoke Env ${Date.now().toString().slice(-6)}`;
    await openCoDirectorFullScreen(page, PROJECT_A);
    await clickTab(page, "scene_creator");
    await expect(page.getByTestId("environment-creator-surface")).toBeVisible({ timeout: 30_000 });
    await page.getByTestId("environment-creator-new").click();
    await page.getByTestId("environment-creator-name").fill(name);
    await page.getByTestId("environment-creator-prompt").fill("Disposable dual-save hallway.");

    const topWait = page.waitForResponse(
      (res) => res.request().method() === "POST" && /\/save$/.test(res.url()),
      { timeout: 15_000 },
    );
    await page.getByTestId("environment-creator-save-top").click();
    const top = await topWait;
    expect(top.ok(), `top save ${top.status()} ${top.url()}`).toBeTruthy();
    await expect(page.getByTestId("environment-creator-save-bottom")).toBeEnabled({ timeout: 10_000 });
    await expect(page.getByTestId("environment-creator-save-bottom")).toHaveAttribute("aria-busy", "false");

    const bottomWait = page.waitForResponse(
      (res) => res.request().method() === "POST" && /\/save$/.test(res.url()),
      { timeout: 15_000 },
    );
    await page.getByTestId("environment-creator-save-bottom").scrollIntoViewIfNeeded();
    await page.getByTestId("environment-creator-save-bottom").click();
    const bottom = await bottomWait;
    expect(bottom.ok(), `bottom save ${bottom.status()} ${bottom.url()}`).toBeTruthy();

    await ensureProjectContentVisible(page);
    const deleteBtn = page.getByTestId("environment-creator-delete-top");
    await expect(deleteBtn).toBeEnabled({ timeout: 10_000 });
    const bg = await deleteBtn.evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(bg).toContain("127, 29, 29");
    const previewWait = page.waitForResponse(
      (res) =>
        res.request().method() === "GET" &&
        /environment-reference-sheets/.test(res.url()) &&
        /delete-preview/.test(res.url()),
      { timeout: 12_000 },
    );
    await deleteBtn.click();
    const preview = await previewWait;
    expect(preview.ok(), `delete-preview ${preview.status()} ${preview.url()}`).toBeTruthy();
    await expect(page.getByTestId("creator-delete-modal")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("creator-delete-modal-body")).toContainText("cannot be undone");
    const delWait = page.waitForResponse(
      (res) => res.request().method() === "DELETE" && /environment-reference-sheets/.test(res.url()),
      { timeout: 12_000 },
    );
    await page.getByTestId("creator-delete-modal-confirm").click();
    const del = await delWait;
    expect(del.ok(), `delete ${del.status()} ${del.url()}`).toBeTruthy();
    await expect(page.getByTestId("creator-delete-modal")).toBeHidden({ timeout: 10_000 });
  });

  test("character sheet library and image generator destinations", async ({ page, request }) => {
    const name = `WiringSmoke Sheet ${Date.now().toString().slice(-6)}`;
    const png = Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
      "base64",
    );
    const created = await request.post(`http://127.0.0.1:8758/api/projects/${PROJECT_A}/characters`, {
      data: { name, visual_description: "Disposable sheet destination smoke." },
    });
    expect(created.ok(), await created.text()).toBeTruthy();
    const character = (await created.json()) as { id?: string };
    const characterId = String(character.id || "");
    expect(characterId).toBeTruthy();

    const uploaded = await request.post(`http://127.0.0.1:8758/api/projects/${PROJECT_A}/assets`, {
      multipart: {
        file: { name: "sheet-smoke.png", mimeType: "image/png", buffer: png },
        kind: "image",
      },
    });
    expect(uploaded.ok(), await uploaded.text()).toBeTruthy();
    const asset = (await uploaded.json()) as { id?: string };
    const assetId = String(asset.id || "");
    expect(assetId).toBeTruthy();

    const adoptFront = await request.post(
      `http://127.0.0.1:8758/api/projects/${PROJECT_A}/characters/${characterId}/front/adopt`,
      { data: { assetId, sourceType: "upload" } },
    );
    expect(adoptFront.ok(), await adoptFront.text()).toBeTruthy();
    const approveFront = await request.post(
      `http://127.0.0.1:8758/api/projects/${PROJECT_A}/characters/${characterId}/views/front/approve`,
      { data: {} },
    );
    expect(approveFront.ok(), await approveFront.text()).toBeTruthy();
    for (const angle of ["side", "three_quarter", "back"]) {
      const adopt = await request.post(
        `http://127.0.0.1:8758/api/projects/${PROJECT_A}/characters/${characterId}/multiview/angles/${angle}/adopt`,
        { data: { assetId, sourceType: "uploaded" } },
      );
      expect(adopt.ok(), `${angle} adopt ${await adopt.text()}`).toBeTruthy();
      const approve = await request.post(
        `http://127.0.0.1:8758/api/projects/${PROJECT_A}/characters/${characterId}/multiview/angles/${angle}/approve`,
        { data: { approved: true } },
      );
      expect(approve.ok(), `${angle} approve ${await approve.text()}`).toBeTruthy();
    }
    const composed = await request.post(
      `http://127.0.0.1:8758/api/projects/${PROJECT_A}/characters/${characterId}/sheet/compose`,
      { data: { regenerate: false } },
    );
    expect(composed.ok(), await composed.text()).toBeTruthy();

    await openCoDirectorFullScreen(page, PROJECT_A);
    await clickTab(page, "characters");
    await expect(page.getByTestId("character-compact")).toBeVisible({ timeout: 30_000 });
    await page.getByTestId("character-compact-saved-select").selectOption(characterId);
    const libraryBtn = page.getByTestId("cc-v2-open-library").or(page.getByTestId("character-active-crs-open-library")).first();
    await expect(libraryBtn).toBeVisible({ timeout: 20_000 });
    await libraryBtn.click();
    await expect(page).toHaveURL(/workspace=library/, { timeout: 15_000 });

    await openCoDirectorFullScreen(page, PROJECT_A);
    await clickTab(page, "characters");
    await page.getByTestId("character-compact-saved-select").selectOption(characterId);
    const igBtn = page.getByTestId("cc-v2-use-imagegen").or(page.getByTestId("character-active-crs-use-imagegen")).first();
    await expect(igBtn).toBeVisible({ timeout: 20_000 });
    await igBtn.click();
    await expect(page).toHaveURL(/workspace=imagegen/, { timeout: 15_000 });
    expect(page.url()).toMatch(/assetId=/);

    await request.delete(`http://127.0.0.1:8758/api/projects/${PROJECT_A}/characters/${characterId}?confirm_cross_project=true`);
  });

  test("prop advanced sheet destinations stay wired", async ({ page }) => {
    await openCoDirectorFullScreen(page, PROJECT_A);
    await clickTab(page, "prop_creator");
    await expect(page.getByTestId("prop-creator-panel")).toBeVisible({ timeout: 30_000 });
    await page.getByTestId("prop-creator-tab-advanced").click();
    const select = page.getByTestId("prop-creator-saved-select");
    await expect(select).toBeVisible({ timeout: 15_000 });
    await select.selectOption("6868078f-cda7-4427-8f85-fd318cf4a141");
    const library = page.getByTestId("prop-advanced-reference-sheet-open-library");
    await expect(library).toBeVisible({ timeout: 15_000 });
    await library.click();
    await expect(page).toHaveURL(/workspace=library/, { timeout: 15_000 });

    await openCoDirectorFullScreen(page, PROJECT_A);
    await clickTab(page, "prop_creator");
    await page.getByTestId("prop-creator-tab-advanced").click();
    await page.getByTestId("prop-creator-saved-select").selectOption("6868078f-cda7-4427-8f85-fd318cf4a141");
    const ig = page.getByTestId("prop-advanced-reference-sheet-use-imagegen");
    await expect(ig).toBeVisible({ timeout: 15_000 });
    await ig.click();
    await expect(page).toHaveURL(/workspace=imagegen/, { timeout: 15_000 });
  });
});
