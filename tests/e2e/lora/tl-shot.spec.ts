import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { createProjectResilient } from "./loraHelpers";

const WEB = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173";
const OUT = path.resolve("artifacts/lora-cert-screenshots");

test("capture timeline advanced screenshot", async ({ page, request }) => {
  fs.mkdirSync(OUT, { recursive: true });
  const projectId = await createProjectResilient(request, "LoRA TL Shot");
  await request.post(`${WEB.replace("http://127.0.0.1:5173", "http://127.0.0.1:8758")}/api/projects/${projectId}/scenes`, {
    data: { name: "TL Scene", prompt: "test", engine: "ltx", duration_sec: 4 },
  });
  await page.goto(`${WEB}/project/${projectId}?workspace=timeline`, { waitUntil: "domcontentloaded", timeout: 90000 });
  await page.waitForTimeout(10000);
  const advanced = page.getByTestId("timeline-inspector-advanced");
  if (await advanced.count()) {
    await advanced.locator("summary").click({ force: true });
    await page.waitForTimeout(2500);
    await advanced.screenshot({ path: path.join(OUT, "timeline-advanced-lora.png") });
    console.log("TIMELINE SHOT DONE");
  } else {
    console.log("TIMELINE INSPECTOR NOT FOUND");
  }
  await request.delete(`${WEB.replace("http://127.0.0.1:5173", "http://127.0.0.1:8758")}/api/projects/${projectId}`).catch(() => undefined);
});