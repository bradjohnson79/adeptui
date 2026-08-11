import { chromium } from "playwright";

const TARGET = "https://adeptui.vercel.app";
const API_BASE = "https://api-beta.adeptui.org";

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
    if (req.url().includes("/api/")) requestFailures.push(`${req.url()}: ${req.failure()?.errorText}`);
  });

  console.log("=== FOUR PILLARS FOLLOW-UP CERTIFICATION ===\n");
  console.log("Opening", TARGET);
  await page.goto(TARGET, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(3000);

  const bodyText = await page.textContent("body").catch(() => "");
  const hasProjects = !bodyText?.includes("No Projects Yet");
  console.log("Projects visible:", hasProjects);

  // Open Schnick Coffee
  console.log("\n--- OPENING PROJECT ---");
  const schnickLink = page.getByText("Schnick Coffee", { exact: false }).first();
  if (await schnickLink.count() > 0) {
    await schnickLink.click({ timeout: 10000 });
    await page.waitForTimeout(4000);
    console.log("Opened Schnick Coffee project");
  }

  // Open Co-Director in fullscreen
  console.log("\n--- OPENING CO-DIRECTOR ---");
  const coDirectorBtn = page.getByText("Co-Director", { exact: false }).first();
  if (await coDirectorBtn.count() > 0) {
    await coDirectorBtn.click({ timeout: 10000 });
    await page.waitForTimeout(4000);
    console.log("Co-Director opened");
  }

  // Verify fullscreen shell exists
  const fullscreenShell = page.getByTestId("codirector-fullscreen-shell");
  const isFullscreen = await fullscreenShell.count() > 0;
  console.log("Fullscreen shell:", isFullscreen);

  // If not fullscreen, try to switch
  if (!isFullscreen) {
    // Try clicking fullscreen toggle or layout button
    const layoutBtn = page.getByText("Fullscreen", { exact: false }).first();
    if (await layoutBtn.count() > 0) {
      await layoutBtn.click({ timeout: 5000 });
      await page.waitForTimeout(2000);
      console.log("Switched to fullscreen");
    }
  }

  // Wait for content pane
  console.log("\n--- PROJECT BUILDING PANE ---");
  const contentPane = page.getByTestId("codirector-project-content");
  await contentPane.waitFor({ state: "visible", timeout: 15000 }).catch(() => {});
  const paneVisible = await contentPane.isVisible().catch(() => false);
  console.log("Content pane visible:", paneVisible);

  // Check all 7 tabs
  const tabIds = ["wiki", "notes", "story", "scriptwriter", "script", "characters", "library"];
  const tabResults = {};
  for (const tabId of tabIds) {
    const tab = page.getByTestId(`codirector-content-tab-${tabId}`);
    tabResults[tabId] = await tab.count() > 0;
  }
  console.log("All 7 tabs:", tabResults);

  // Click Wiki tab and verify FoundationStatusBar
  console.log("\n--- WIKI + FOUNDATION STATUS ---");
  const wikiTab = page.getByTestId("codirector-content-tab-wiki");
  if (await wikiTab.count() > 0) {
    await wikiTab.click({ timeout: 5000 });
    await page.waitForTimeout(3000);
    
    // Wait for FoundationStatusBar
    const foundationBar = page.getByTestId("codirector-foundation-status");
    await foundationBar.waitFor({ state: "visible", timeout: 10000 }).catch(() => {});
    const foundationVisible = await foundationBar.isVisible().catch(() => false);
    console.log("FoundationStatusBar visible:", foundationVisible);

    if (foundationVisible) {
      // Check pillar buttons
      for (const pillar of ["story", "script", "storyboard", "characters"]) {
        const btn = page.getByTestId(`codirector-foundation-${pillar}`);
        const exists = await btn.count() > 0;
        console.log(`  Pillar ${pillar}:`, exists ? "FOUND" : "NOT FOUND");
      }
    }
  }

  // Click Story tab and verify TipTap editor
  console.log("\n--- STORY TAP EDITOR ---");
  const storyTab = page.getByTestId("codirector-content-tab-story");
  if (await storyTab.count() > 0) {
    await storyTab.click({ timeout: 5000 });
    await page.waitForTimeout(3000);

    const storyEditor = page.getByTestId("story-editor");
    await storyEditor.waitFor({ state: "visible", timeout: 10000 }).catch(() => {});
    const editorVisible = await storyEditor.isVisible().catch(() => false);
    console.log("Story editor visible:", editorVisible);

    if (editorVisible) {
      const titleInput = page.getByTestId("story-title");
      const saveState = page.getByTestId("story-save-state");
      const contentArea = page.getByTestId("story-content");
      console.log("  Title input:", await titleInput.count() > 0);
      console.log("  Save state:", await saveState.count() > 0);
      console.log("  Content area:", await contentArea.count() > 0);

      // Wait for toolbar (TipTap needs to initialize)
      const toolbar = page.getByTestId("story-toolbar");
      await toolbar.waitFor({ state: "visible", timeout: 10000 }).catch(() => {});
      const toolbarVisible = await toolbar.isVisible().catch(() => false);
      console.log("  Toolbar visible:", toolbarVisible);

      if (toolbarVisible) {
        for (const btn of ["bold", "italic", "h1", "h2", "bullet", "numbered", "undo", "redo"]) {
          const button = page.getByTestId(`story-btn-${btn}`);
          const exists = await button.count() > 0;
          console.log(`  Button ${btn}:`, exists ? "FOUND" : "NOT FOUND");
        }
      }

      // Type into the ProseMirror editor
      const proseMirror = page.getByTestId("story-content").locator(".ProseMirror");
      if (await proseMirror.count() > 0) {
        await proseMirror.click({ timeout: 5000 });
        await page.keyboard.type("Test content for persistence verification.", { delay: 50 });
        await page.waitForTimeout(2000); // Wait for autosave
        console.log("  Typed into editor: YES");
        
        // Check save state shows Saved
        const saveText = await saveState.textContent().catch(() => "");
        console.log("  Save state text:", saveText);
      }
    }
  }

  // Verify Script Writer toolbar (navigate to scriptwriter workspace)
  console.log("\n--- SCRIPT WRITER TOOLBAR ---");
  const scriptTab = page.getByTestId("codirector-content-tab-scriptwriter");
  if (await scriptTab.count() > 0) {
    await scriptTab.click({ timeout: 5000 });
    await page.waitForTimeout(4000);

    const toolbar = page.getByTestId("scriptwriter-toolbar");
    await toolbar.waitFor({ state: "visible", timeout: 10000 }).catch(() => {});
    const toolbarVisible = await toolbar.isVisible().catch(() => false);
    console.log("Script Writer toolbar visible:", toolbarVisible);

    if (toolbarVisible) {
      // Verify Storyboard and Timeline buttons are GONE
      const sbButton = toolbar.locator("button:has-text('Storyboard')");
      const tlButton = toolbar.locator("button:has-text('Timeline')");
      const sbCount = await sbButton.count();
      const tlCount = await tlButton.count();
      console.log("  Storyboard button removed:", sbCount === 0 ? "PASS" : "FAIL");
      console.log("  Timeline button removed:", tlCount === 0 ? "PASS" : "FAIL");

      // Verify remaining buttons
      const insertScene = page.getByTestId("scriptwriter-insert-scene");
      const undoBtn = page.getByTestId("scriptwriter-undo");
      const focusBtn = page.getByTestId("scriptwriter-focus");
      const commandBtn = page.getByTestId("scriptwriter-command");
      console.log("  Insert scene:", await insertScene.count() > 0 ? "FOUND" : "NOT FOUND");
      console.log("  Undo:", await undoBtn.count() > 0 ? "FOUND" : "NOT FOUND");
      console.log("  Focus:", await focusBtn.count() > 0 ? "FOUND" : "NOT FOUND");
      console.log("  Command:", await commandBtn.count() > 0 ? "FOUND" : "NOT FOUND");
    }
  }

  // API endpoint verification
  console.log("\n--- API VERIFICATION ---");
  const projectId = "2347bf46-3762-4763-86c5-4a6032522278";

  // Foundation
  try {
    const r = await page.request.get(`${API_BASE}/api/projects/${projectId}/foundation`);
    const f = await r.json();
    console.log("Foundation:", `story=${f.story.status} script=${f.script.status} sb=${f.storyboard.status} chars=${f.characters.status}`);
  } catch (e) { console.log("Foundation API: FAIL", e.message); }

  // Context retriever (foundation)
  try {
    const r = await page.request.get(`${API_BASE}/api/codirector/projects/${projectId}/context?pillars=foundation`);
    const c = await r.json();
    console.log("Context foundation:", c.foundation ? `ready=${c.foundation.ready_for_timeline} missing=${JSON.stringify(c.foundation.missing_pillars)}` : "null");
  } catch (e) { console.log("Context foundation: FAIL", e.message); }

  // Context all pillars
  try {
    const r = await page.request.get(`${API_BASE}/api/codirector/projects/${projectId}/context`);
    const c = await r.json();
    console.log("Context all:", `story=${c.story ? "yes" : "no"} script=${c.script ? "yes" : "no"} sb=${c.storyboard ? "yes" : "no"} chars=${c.characters ? "yes" : "no"}`);
  } catch (e) { console.log("Context all: FAIL", e.message); }

  // Story persistence
  console.log("\n--- STORY PERSISTENCE ---");
  const testContent = `<h2>Follow-up Test</h2><p>Persistence verification at ${Date.now()}.</p>`;
  try {
    const r = await page.request.put(`${API_BASE}/api/projects/${projectId}/story`, {
      data: { content: testContent, title: "Follow-up Test" },
      headers: { "Content-Type": "application/json" },
    });
    const saved = await r.json();
    console.log("Story saved:", `words=${saved.wordCount}`);
  } catch (e) { console.log("Story save: FAIL", e.message); }

  try {
    const r = await page.request.get(`${API_BASE}/api/projects/${projectId}/story`);
    const loaded = await r.json();
    const matches = loaded.content === testContent;
    console.log("Story persistence:", matches ? "PASS" : "FAIL");
  } catch (e) { console.log("Story reload: FAIL", e.message); }

  // Character candidate workflow via API
  console.log("\n--- CHARACTER CANDIDATE WORKFLOW ---");
  
  // List characters
  let characters = [];
  try {
    const r = await page.request.get(`${API_BASE}/api/projects/${projectId}/characters`);
    const data = await r.json();
    characters = data.items || [];
    console.log("Characters:", characters.length);
  } catch (e) { console.log("Characters list: FAIL", e.message); }

  // Find or create a character with sufficient description
  let testChar = characters.find((c) => c.description && c.description.length >= 20);
  if (!testChar && characters.length > 0) {
    // Update first character with description
    testChar = characters[0];
    try {
      const r = await page.request.patch(`${API_BASE}/api/projects/${projectId}/characters/${testChar.id}`, {
        data: { description: "A young elf woman with purple eyes, black twin ponytails, wearing a black apron and black shorts. Energetic and expressive." },
        headers: { "Content-Type": "application/json" },
      });
      console.log("Updated character description:", (await r.json()).name);
    } catch (e) { console.log("Character update: FAIL", e.message); }
  }
  if (!testChar) {
    // Create a new test character
    try {
      const r = await page.request.post(`${API_BASE}/api/projects/${projectId}/characters`, {
        data: {
          name: "Test Hero",
          role: "protagonist",
          description: "A weathered smuggler in a tattered coat, mid-30s, sharp eyes and a cynical smile.",
        },
        headers: { "Content-Type": "application/json" },
      });
      testChar = await r.json();
      console.log("Created test character:", testChar.name, testChar.id);
    } catch (e) { console.log("Character create: FAIL", e.message); }
  } else {
    console.log("Using existing character:", testChar.name, testChar.id);
  }

  // Test missing-description guard with a short description
  if (testChar) {
    console.log("\n--- MISSING-DESCRIPTION GUARD ---");
    // Create a character with short description
    try {
      const r = await page.request.post(`${API_BASE}/api/projects/${projectId}/characters`, {
        data: { name: "Short Desc Char", role: "extra", description: "short" },
        headers: { "Content-Type": "application/json" },
      });
      const shortChar = await r.json();
      
      // Try to propose visual sheet via Co-Director tool
      const propR = await page.request.post(`${API_BASE}/api/codirector/projects/${projectId}/tools/proposals`, {
        data: {
          toolId: "character_creator.propose_visual_sheet",
          arguments: { characterId: shortChar.id, candidates: true },
          createdBy: "live-test",
        },
        headers: { "Content-Type": "application/json" },
      });
      const proposal = await propR.json();
      console.log("Proposal created:", proposal.id ? "YES" : "NO");
      
      if (proposal.id) {
        const apprR = await page.request.post(`${API_BASE}/api/codirector/projects/${projectId}/proposals/${proposal.id}/approve`, {
          data: { decidedBy: "live-test", note: "test" },
          headers: { "Content-Type": "application/json" },
        });
        const receipt = await apprR.json();
        const toolResult = receipt.tool_result || receipt.result;
        console.log("Missing-description guard:", toolResult?.status === "missing_description" ? "PASS" : "FAIL");
        if (toolResult?.message) console.log("  Message:", toolResult.message.substring(0, 100));
      }
    } catch (e) { console.log("Guard test: FAIL", e.message); }
  }

  // Refresh persistence
  console.log("\n--- REFRESH PERSISTENCE ---");
  await page.goto(TARGET, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(3000);
  const afterReload = await page.textContent("body").catch(() => "");
  const projectsAfterReload = !afterReload?.includes("No Projects Yet");
  console.log("Projects after reload:", projectsAfterReload ? "PASS" : "FAIL");

  // 2-minute stability soak
  console.log("\n--- 2-MINUTE STABILITY SOAK ---");
  let apiCount = 0;
  page.on("request", (req) => { if (req.url().includes("/api/")) apiCount++; });
  await page.waitForTimeout(120000);
  console.log("API requests in 2 min:", apiCount);

  // Final summary
  console.log("\n=== CERTIFICATION SUMMARY ===");
  console.log("Console errors:", consoleErrors.length);
  console.log("CORS errors:", corsErrors.length);
  console.log("Request failures:", requestFailures.length);
  if (consoleErrors.length > 0) console.log("First 5 errors:", consoleErrors.slice(0, 5));
  if (requestFailures.length > 0) console.log("Failures:", requestFailures.slice(0, 3));

  const result = {
    projectsVisible: hasProjects,
    projectsAfterReload,
    allTabs: tabResults,
    foundationStatusBar: await page.getByTestId("codirector-foundation-status").count() > 0,
    storyEditor: await page.getByTestId("story-editor").count() > 0,
    storyToolbar: await page.getByTestId("story-toolbar").count() > 0,
    scriptToolbar: await page.getByTestId("scriptwriter-toolbar").count() > 0,
    consoleErrors: consoleErrors.length,
    corsErrors: corsErrors.length,
    requestFailures: requestFailures.length,
    apiCountIn2Min: apiCount,
  };
  console.log("\nRESULT_JSON:", JSON.stringify(result));

  await page.close();
  await browser.close();
})();
