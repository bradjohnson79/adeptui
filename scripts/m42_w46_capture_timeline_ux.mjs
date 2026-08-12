import { chromium } from "playwright";
import path from "path";
import fs from "fs";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const art = path.join(__dirname, "..", "artifacts", "m42", "w46", "timeline-ux");
fs.mkdirSync(art, { recursive: true });

const shots = [
  ["beta-1280-night.png", 1280, 720, "aurora-night"],
  ["beta-1920-night.png", 1920, 1080, "aurora-night"],
  ["beta-1280-day.png", 1280, 720, "aurora-day"],
  ["beta-1920-day.png", 1920, 1080, "aurora-day"],
];

const browser = await chromium.launch({ headless: true });
for (const [name, w, h, theme] of shots) {
  const context = await browser.newContext({ viewport: { width: w, height: h } });
  const page = await context.newPage();
  const projectId = process.env.ADEPT_CAPTURE_PROJECT_ID || "e32dae30-a014-4ea4-a2f2-69f4b7809bde";
  await page.goto(`http://127.0.0.1:8760/project/${projectId}?workspace=timeline`, {
    waitUntil: "domcontentloaded",
    timeout: 30000,
  });
  await page.evaluate((t) => {
    document.documentElement.setAttribute("data-theme", t);
    try {
      localStorage.setItem("adept_ui_theme", t);
    } catch {
      /* ignore */
    }
  }, theme);
  try {
    await page.getByTestId("timeline-editor-shell").waitFor({ timeout: 20000 });
    await page.getByTestId("timeline-track-board").waitFor({ timeout: 15000 });
    // Wait until loader clears (tracks rendered or empty instructional lanes)
    await page.waitForFunction(() => {
      const board = document.querySelector('[data-testid="timeline-track-board"]');
      if (!board) return false;
      const text = board.textContent || "";
      return !text.includes("Loading Timeline tracks");
    }, { timeout: 20000 });
  } catch (e) {
    console.log("nav soft fail", name, String(e.message || e));
    try {
      await page.getByRole("button", { name: /unlock|continue|open/i }).first().click({ timeout: 3000 });
      await page.getByTestId("timeline-editor-shell").waitFor({ timeout: 15000 });
    } catch {
      /* ignore */
    }
  }
  const out = path.join(art, name);
  await page.screenshot({ path: out });
  console.log("captured", name, fs.statSync(out).size);
  await context.close();
}
await browser.close();
