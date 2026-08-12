import { expect, test } from "@playwright/test";

/**
 * M42 W45 Audio Studio shell + mixer reachability.
 * Generation durability is covered by API unit tests + primary certification workflows.
 */

test.describe("M42 W45 Audio Studio", () => {
  test("Audio Studio tabs Music / SFX / Ambience / Project Audio", async ({ page }) => {
    const projects = await page.request.get("/api/projects");
    expect(projects.ok()).toBeTruthy();
    const list = await projects.json();
    const project = (Array.isArray(list) ? list : list?.projects || [])[0];
    test.skip(!project?.id, "No project available");

    await page.goto(`/project/${project.id}?workspace=audiostudio`);
    await expect(page.getByTestId("audio-studio-workspace")).toBeVisible({ timeout: 30000 });
    await expect(page.getByTestId("audio-studio-tab-music")).toBeVisible();
    await expect(page.getByTestId("audio-studio-tab-sfx")).toBeVisible();
    await expect(page.getByTestId("audio-studio-tab-ambience")).toBeVisible();
    await expect(page.getByTestId("audio-studio-tab-library")).toBeVisible();

    await page.getByTestId("audio-studio-tab-ambience").click();
    await expect(page.getByText(/Scene beds|Ambience/i).first()).toBeVisible();

    await page.getByTestId("audio-studio-tab-library").click();
    await expect(page.getByText(/Project audio|saved/i).first()).toBeVisible();
  });

  test("W45 gate endpoint is binary and non-mock", async ({ request }) => {
    const res = await request.get("/api/audio-studio/gate/w45");
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.mock).toBe(false);
    expect(typeof body.audioStudioGo).toBe("boolean");
    expect(["GO", "NO-GO"]).toContain(body.verdict);
    expect(body.conditionalGo).toBeUndefined();
    expect(body.flags.providerSwitchNeverSilent).toBe(true);
  });

  test("mix GET/PUT persists gain mute solo", async ({ request }) => {
    const projects = await request.get("/api/projects");
    const list = await projects.json();
    const project = (Array.isArray(list) ? list : list?.projects || [])[0];
    test.skip(!project?.id, "No project available");

    const put = await request.put(`/api/audio-studio/projects/${project.id}/mix`, {
      data: {
        master: { gain: 0.85, peak: -6, lufs_integrated: -18 },
        clip: {
          clip_id: "e2e-mix-clip",
          asset_id: "e2e-asset",
          gain: 0.4,
          pan: -0.1,
          mute: true,
          solo: false,
          fade_in_ms: 50,
          fade_out_ms: 100,
        },
      },
    });
    expect(put.ok()).toBeTruthy();
    const get = await request.get(`/api/audio-studio/projects/${project.id}/mix`);
    expect(get.ok()).toBeTruthy();
    const body = await get.json();
    expect(body.mock).toBe(false);
    expect(body.mix.master.gain).toBe(0.85);
    expect(body.mix.clips["e2e-mix-clip"].mute).toBe(true);
    expect(body.mix.clips["e2e-mix-clip"].gain).toBe(0.4);
  });
});
