import { chromium } from "playwright";

const TARGET = "https://adeptui.vercel.app";

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  const page = await context.newPage();

  const consoleErrors = [];
  const requestFailures = [];
  const corsErrors = [];

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      const text = msg.text();
      consoleErrors.push(text);
      if (text.includes("CORS") || text.includes("Access-Control")) corsErrors.push(text);
    }
  });
  page.on("pageerror", (err) => consoleErrors.push(`pageerror: ${err.message}`));
  page.on("requestfailed", (req) => {
    const url = req.url();
    if (url.includes("/api/")) requestFailures.push(`${url}: ${req.failure()?.errorText}`);
  });

  console.log("Opening", TARGET);
  await page.goto(TARGET, { waitUntil: "networkidle", timeout: 30000 });

  // Wait for projects to load
  await page.waitForTimeout(5000);

  // Check for "No Projects Yet" text
  const bodyText = await page.textContent("body").catch(() => "");
  const hasNoProjects = bodyText?.includes("No Projects Yet") ?? false;
  console.log("Has 'No Projects Yet':", hasNoProjects);

  // Count project cards/items in the library
  const projectCards = await page.locator("[data-testid*='project'], .project-card, .project-library-grid > *").count().catch(() => 0);
  console.log("Project cards found:", projectCards);

  // Check for project names in the DOM
  const knownProjects = ["Timeline Refs E2E", "Wiki Authority Cert", "Schnick Coffee", "probe", "Diag Scripted", "DebugProj"];
  const foundProjects = [];
  for (const name of knownProjects) {
    if (bodyText?.includes(name)) {
      foundProjects.push(name);
    }
  }
  console.log("Known projects found in DOM:", foundProjects.length, foundProjects);

  // Try to click on the first project
  if (!hasNoProjects && foundProjects.length > 0) {
    console.log("\nAttempting to open first project...");
    try {
      // Look for clickable project elements
      const firstProject = page.locator(`text=${foundProjects[0]}`).first();
      if (await firstProject.count() > 0) {
        await firstProject.click({ timeout: 5000 });
        await page.waitForTimeout(3000);
        const afterClickText = await page.textContent("body").catch(() => "");
        const stillOnProject = afterClickText?.includes(foundProjects[0]) ?? false;
        console.log("Project opened, name visible:", stillOnProject);
        
        // Go back to Home
        await page.goto(TARGET, { waitUntil: "networkidle", timeout: 30000 });
        await page.waitForTimeout(3000);
        const afterReturnText = await page.textContent("body").catch(() => "");
        const projectsAfterReturn = afterReturnText?.includes(foundProjects[0]) ?? false;
        console.log("Project still in library after return:", projectsAfterReturn);
      }
    } catch (e) {
      console.log("Project open attempt:", e.message);
    }
  }

  // Reload test
  console.log("\nReloading page...");
  await page.reload({ waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(3000);
  const afterReloadText = await page.textContent("body").catch(() => "");
  const projectsAfterReload = afterReloadText?.includes("No Projects Yet") === false;
  console.log("Projects persist after reload:", projectsAfterReload);

  // 2-minute stability check
  console.log("\n2-minute stability soak...");
  let apiCount = 0;
  page.on("request", (req) => { if (req.url().includes("/api/")) apiCount++; });
  await page.waitForTimeout(120000);
  console.log("API requests in 2 min:", apiCount);

  // Final summary
  console.log("\n=== PROJECT LIBRARY VERIFICATION COMPLETE ===");
  console.log("Console errors:", consoleErrors.length);
  console.log("CORS errors:", corsErrors.length);
  console.log("Request failures:", requestFailures.length);
  if (consoleErrors.length > 0) console.log("First 5 errors:", consoleErrors.slice(0, 5));
  if (requestFailures.length > 0) console.log("First 5 failures:", requestFailures.slice(0, 5));

  const result = {
    hasNoProjects,
    projectCards,
    foundProjects,
    projectsAfterReload,
    consoleErrors: consoleErrors.length,
    corsErrors: corsErrors.length,
    requestFailures: requestFailures.length,
    apiCountIn2Min: apiCount,
  };
  console.log("\nRESULT_JSON:", JSON.stringify(result));

  await page.close();
  await browser.close();
})();
