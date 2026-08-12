import { chromium } from "@playwright/test";

const baseUrl = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:8760";

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
await page.getByTestId("create-project-open").waitFor({ state: "visible", timeout: 30_000 });
await page.evaluate(async () => {
  localStorage.clear();
  sessionStorage.clear();
  if (indexedDB.databases) {
    const dbs = await indexedDB.databases();
    await Promise.all(
      dbs
        .map((db) => db?.name)
        .filter(Boolean)
        .map((name) => new Promise((resolve) => {
          const req = indexedDB.deleteDatabase(name);
          req.onsuccess = () => resolve(true);
          req.onerror = () => resolve(false);
          req.onblocked = () => resolve(false);
        })),
    );
  }
});
await page.reload({ waitUntil: "domcontentloaded" });
await page.getByTestId("create-project-open").waitFor({ state: "visible", timeout: 30_000 });

const createOpen = page.getByTestId("create-project-open");
await createOpen.click();
await page.getByTestId("create-project-modal").waitFor({ state: "visible" });
await page.getByTestId("create-project-submit").click();
await page.getByTestId("create-project-modal").waitFor({ state: "hidden" });
const activeCard = page.locator("[data-testid^='project-card-'][data-active-project='true']").first();
await activeCard.waitFor({ state: "visible", timeout: 30_000 });
const testId = await activeCard.getAttribute("data-testid");
const projectId = testId?.replace(/^project-card-/, "") || "";

console.log(JSON.stringify({ ok: true, url: page.url(), projectId }, null, 2));
await browser.close();
