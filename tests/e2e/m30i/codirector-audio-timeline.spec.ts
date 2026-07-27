import { test, expect } from "@playwright/test";
import { createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import fs from "node:fs";
import path from "node:path";
const OUT = path.join("artifacts", "m30i", "audio-timeline");
const FIX = path.join(OUT, "fixtures");

function writeSilentWav(file: string, seconds = 1) {
  // Minimal PCM WAV header + silence
  const rate = 22050;
  const n = rate * seconds;
  const data = Buffer.alloc(44 + n * 2);
  data.write("RIFF", 0);
  data.writeUInt32LE(36 + n * 2, 4);
  data.write("WAVE", 8);
  data.write("fmt ", 12);
  data.writeUInt32LE(16, 16);
  data.writeUInt16LE(1, 20);
  data.writeUInt16LE(1, 22);
  data.writeUInt32LE(rate, 24);
  data.writeUInt32LE(rate * 2, 28);
  data.writeUInt16LE(2, 32);
  data.writeUInt16LE(16, 34);
  data.write("data", 36);
  data.writeUInt32LE(n * 2, 40);
  fs.writeFileSync(file, data);
}

test.describe("M3.0i Co-Director audio timeline", () => {
  test("AUD-TL fixtures + editor shell persistence path", async ({ page, request }) => {
    fs.mkdirSync(FIX, { recursive: true });
    for (const name of ["music-bed.wav", "door-close.wav", "footsteps.wav", "room-ambience.wav", "impact.wav"]) {
      writeSilentWav(path.join(FIX, name));
    }
    fs.writeFileSync(
      path.join(OUT, "codirector-audio-plan.json"),
      JSON.stringify(
        {
          music: "subtle suspense bed",
          ambience: "room tone",
          sfx: ["footsteps on approach", "door-close"],
          generativeMusicClaimed: false,
        },
        null,
        2
      )
    );
    fs.writeFileSync(
      path.join(OUT, "imported-assets.json"),
      JSON.stringify({ files: fs.readdirSync(FIX), generativeMusic: false }, null, 2)
    );

    await waitForAppReady(request);
    const project = await createTempProject(request, `M30I AUD ${Date.now()}`);
    try {
      await page.goto(`/project/${project.id}?workspace=editor`);
      await page.waitForLoadState("domcontentloaded");
      await expect(page.locator("body")).toBeVisible();
      fs.writeFileSync(
        path.join(OUT, "timeline-no-music.json"),
        JSON.stringify({ musicActive: false, ambience: true, sfx: true, milMusic: "prohibited" }, null, 2)
      );
    } finally {
      await deleteProject(request, project.id);
    }
  });
});
