/**
 * Setup Wizard preservation, Full API FFmpeg behavior, and the real Update Manager.
 * Does not remove saved keys or switch the live installation profile.
 */
import { expect, test } from "@playwright/test";
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const REPO = path.resolve(__dirname, "../../..");
const PYTHONW = path.join(REPO, "studio-api", ".venv", "Scripts", "pythonw.exe");
const DEMO = path.join(REPO, "install", "lifecycle", "demo_update_ui.py");

test.describe.configure({ mode: "serial" });

test("approved setup wizard stays on one page", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/setup");
  const degraded = page.getByRole("button", { name: "Continue in Degraded Mode" });
  if (await degraded.isVisible().catch(() => false)) await degraded.click();
  const wizard = page.getByTestId("setup-wizard-permanent");
  await expect(wizard).toBeVisible({ timeout: 45_000 });
  const radios = wizard.getByRole("radio");
  await expect(radios).toHaveCount(3);
  await expect(wizard.locator(".setup-choice-title")).toHaveText([
    "Full Local Installation",
    "Hybrid Installation — Local + API",
    "Full API Installation",
  ]);
  await expect(wizard.getByText("Full Local Installation", { exact: true })).toBeVisible();
  await expect(wizard.getByText("Hybrid Installation — Local + API", { exact: true })).toBeVisible();
  await expect(wizard.getByText("Full API Installation", { exact: true })).toBeVisible();
  await expect(page.getByTestId("profile-radio-api")).toBeChecked();
  await expect(wizard.getByRole("textbox", { name: "fal.ai API key" })).toBeVisible();
  await expect(wizard.getByRole("textbox", { name: "kie.ai API key" })).toBeVisible();
  await expect(wizard.getByRole("textbox", { name: "Wavespeed.ai API key" })).toBeVisible();
  await expect(wizard.getByRole("textbox", { name: "ElevenLabs API key" })).toBeVisible();
  await expect(wizard.getByRole("button", { name: "Test Connection" }).first()).toBeVisible();
  await expect(wizard.getByRole("button", { name: /Save Key|Update Key/ }).first()).toBeVisible();
  await expect(wizard.getByRole("button", { name: "Manage Keys" })).toHaveCount(0);
  await expect(page.getByText("HostedProvidersSetupPanel")).toHaveCount(0);
  await expect(wizard).toContainText("ComfyUI and local generation models are not required");
  const linkColor = await wizard.locator("a").first().evaluate((element) => getComputedStyle(element).color).catch(() => "");
  expect(linkColor).not.toBe("rgb(0, 0, 238)");
  expect(errors).toEqual([]);
  await page.screenshot({ path: path.join("artifacts", "update-manager-cert", "setup-wizard.png"), fullPage: false });
});

test("full API apply does not enqueue FFmpeg", async ({ request }) => {
  const before = await request.get(`${API}/api/setup/status`);
  expect(before.ok()).toBeTruthy();
  const status = await before.json();
  expect(status.installationProfile).toBe("api");
  const scan = status.firstRunScan || {};
  expect(scan.essentialNeeded || []).not.toEqual(expect.arrayContaining([expect.objectContaining({ id: "ffmpeg" })]));
  expect(scan.baselineIds || []).not.toContain("ffmpeg");
  expect(scan.baselineIds || []).not.toContain("comfyui");
  const applied = await request.post(`${API}/api/setup/installation-profile/apply`, { data: {} });
  expect(applied.ok()).toBeTruthy();
  const body = await applied.json();
  expect(body.profile).toBe("api");
  expect(body.errors || []).toEqual([]);
  expect(body.queued || []).not.toContain("ffmpeg");
  const providers = (status.connectedProviders || []).map((item: { id: string }) => item.id);
  expect(providers).toEqual(expect.arrayContaining(["kie", "elevenlabs"]));
});

test("update manager shows measured progress and the completion footer", async ({ page }) => {
  test.skip(!fs.existsSync(PYTHONW), "hidden Python runtime is not available");
  const urlFile = path.join(os.tmpdir(), `adept-updater-url-${Date.now()}.txt`);
  const child = spawn(PYTHONW, [DEMO], {
    windowsHide: true,
    stdio: "ignore",
    env: {
      ...process.env,
      ADEPT_DEMO_ROOT: path.join(os.tmpdir(), `adept-update-demo-${Date.now()}`),
      ADEPT_DEMO_SCENARIO: "update",
      ADEPT_UPDATER_URL_FILE: urlFile,
      ADEPT_CHUNK_PAUSE: "0.12",
      ADEPT_HOLD_SECONDS: "25",
    },
  });
  try {
    await expect.poll(() => (fs.existsSync(urlFile) ? fs.readFileSync(urlFile, "utf8").trim() : ""), { timeout: 30_000 }).toMatch(/^http:\/\/127\.0\.0\.1:\d+\/$/);
    const url = fs.readFileSync(urlFile, "utf8").trim();
    await page.goto(url);
    const downloading = page.getByText("Downloading update");
    if (await downloading.isVisible().catch(() => false)) {
      await page.screenshot({ path: path.join("artifacts", "update-manager-cert", "downloading.png") });
    }
    await expect(page.getByText("Updates complete.")).toBeVisible({ timeout: 40_000 });
    await expect(page.getByText("Adept UI 1.1.3 installed successfully.")).toBeVisible();
    const progress = await page.evaluate(async () => {
      const response = await fetch("/progress", { cache: "no-store" });
      return response.json();
    });
    expect(progress.complete).toBe(true);
    expect(progress.overallPercent).toBe(100);
    expect(progress.footer).toBe("Updates complete.");
    await page.screenshot({ path: path.join("artifacts", "update-manager-cert", "updates-complete.png") });
  } finally {
    child.kill();
  }
});

test("a failed update does not say Updates complete", async ({ page }) => {
  test.skip(!fs.existsSync(PYTHONW), "hidden Python runtime is not available");
  const urlFile = path.join(os.tmpdir(), `adept-updater-fail-${Date.now()}.txt`);
  const child = spawn(PYTHONW, [DEMO], {
    windowsHide: true,
    stdio: "ignore",
    env: {
      ...process.env,
      ADEPT_DEMO_ROOT: path.join(os.tmpdir(), `adept-update-fail-${Date.now()}`),
      ADEPT_DEMO_SCENARIO: "fail",
      ADEPT_UPDATER_URL_FILE: urlFile,
      ADEPT_CHUNK_PAUSE: "0.02",
      ADEPT_HOLD_SECONDS: "8",
    },
  });
  try {
    await expect.poll(() => (fs.existsSync(urlFile) ? fs.readFileSync(urlFile, "utf8").trim() : ""), { timeout: 30_000 }).toMatch(/^http:/);
    await page.goto(fs.readFileSync(urlFile, "utf8").trim());
    await expect(page.locator("#footer")).toHaveText("The downloaded file does not match the approved checksum.", { timeout: 30_000 });
    await expect(page.getByText("Updates complete.")).toHaveCount(0);
    await page.screenshot({ path: path.join("artifacts", "update-manager-cert", "update-failed.png") });
  } finally {
    child.kill();
  }
});

test("no update does not show the completion footer", async ({ page }) => {
  test.skip(!fs.existsSync(PYTHONW), "hidden Python runtime is not available");
  const root = path.join(os.tmpdir(), `adept-noupdate-${Date.now()}`);
  const child = spawn(PYTHONW, [DEMO], {
    windowsHide: true,
    stdio: "ignore",
    env: {
      ...process.env,
      ADEPT_DEMO_ROOT: root,
      ADEPT_DEMO_SCENARIO: "noupdate",
      ADEPT_HOLD_SECONDS: "1",
    },
  });
  try {
    const resultPath = path.join(root, "result.txt");
    await expect.poll(() => (fs.existsSync(resultPath) ? fs.readFileSync(resultPath, "utf8") : ""), { timeout: 30_000 }).toContain("LAUNCHED");
    const progressPath = path.join(root, "install", "update-progress.json");
    if (fs.existsSync(progressPath)) {
      const progress = JSON.parse(fs.readFileSync(progressPath, "utf8"));
      expect(progress.footer).not.toBe("Updates complete.");
    }
    const startup = JSON.parse(fs.readFileSync(path.join(root, "install", "startup-update.json"), "utf8"));
    expect(startup.code).toBe("NO_UPDATE");
    await page.goto("/");
    await expect(page.getByText("Updates complete.")).toHaveCount(0);
  } finally {
    child.kill();
  }
});
