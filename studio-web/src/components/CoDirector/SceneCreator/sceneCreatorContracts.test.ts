import { describe, expect, it } from "vitest";
import { candidateProgress, DEFAULT_CINEMATIC } from "./types";
import type { SceneShotCandidate } from "./types";
import { PRODUCTION_MENU_CATALOG } from "../../../core/productionMenu";
import { resolveWorkspace } from "../../../core/workspaces";

function cand(partial: Partial<SceneShotCandidate>): SceneShotCandidate {
  return {
    id: "c1",
    shot_id: "s1",
    index: 0,
    job_id: "j1",
    status: "queued",
    source: "local",
    family: "zimage",
    model: "zimage",
    provenance_label: "LOCAL — Z-Image Turbo",
    take_label: "Take A",
    ...partial,
  };
}

describe("Scene Creator contracts", () => {
    it("treats four candidates as one shot progress, not four shots", () => {
    const candidates = [0, 1, 2, 3].map((index) =>
      cand({ id: `c${index}`, index, status: index < 2 ? "complete" : "generating" }),
    );
    const progress = candidateProgress(candidates);
    expect(progress.total).toBe(4);
    expect(progress.done).toBe(2);
    expect(progress.percent).toBe(50);
  });

  it("reports honest progress for a single production candidate", () => {
    const progress = candidateProgress([cand({ status: "complete", asset_id: "a1" })]);
    expect(progress.total).toBe(1);
    expect(progress.done).toBe(1);
    expect(progress.percent).toBe(100);
  });

  it("keeps cinematic HOW defaults off the Spatial Map WHERE fields", () => {
    expect(DEFAULT_CINEMATIC).toEqual({
      shot_size: "medium_wide",
      motion: "static",
      framing: "two_shot",
    });
  });

  it("puts Scene Creator in Production and hides Continuity and Scene Master Sheet", () => {
    const pre = PRODUCTION_MENU_CATALOG.find((c) => c.id === "pre-production");
    const ids = (pre?.entries || []).map((e) => e.id);
    expect(ids).toContain("scenecreator");
    expect(ids).not.toContain("continuity");
    expect(ids).not.toContain("mastersheet");
    expect(pre?.entries.find((e) => e.id === "scenecreator")?.label).toBe("Scene Creator");
  });

  it("routes legacy Scene Master Sheet links to Scene Creator", () => {
    expect(resolveWorkspace("mastersheet")).toBe("scenecreator");
    expect(resolveWorkspace("scene-creator")).toBe("scenecreator");
  });

  it("puts Re-Take on Express, not only Standard", async () => {
    const src = await import("node:fs").then((fs) =>
      fs.readFileSync(new URL("./SceneCreatorCore.tsx", import.meta.url), "utf8"),
    );
    const express = src.slice(src.indexOf("function ExpressLayout"), src.indexOf("function StandardLayout"));
    expect(express).toContain("RetakeBlock");
    expect(express).toContain("{sc.approved ? <RetakeBlock");
    expect(express).toContain("CinematographerPanel");
    expect(src).toContain("Final Quality Render");
    expect(src).not.toContain("function CameraBlock");
  });

  it("wires placed project props onto the shot as toggle chips", async () => {
    const src = await import("node:fs").then((fs) =>
      fs.readFileSync(new URL("./SceneCreatorCore.tsx", import.meta.url), "utf8"),
    );
    expect(src).toContain("sc.toggleProp");
    expect(src).toContain("scene-creator-prop-chip");
    const hook = await import("node:fs").then((fs) =>
      fs.readFileSync(new URL("./useSceneCreator.ts", import.meta.url), "utf8"),
    );
    expect(hook).toContain("prop_id");
    expect(hook).toContain("toggleProp");
  });
});
