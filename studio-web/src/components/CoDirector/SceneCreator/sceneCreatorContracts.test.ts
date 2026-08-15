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
    expect(resolveWorkspace("scene_creator")).toBe("scenecreator");
  });

  it("keeps Express as a launcher into Standard, not a second editor", async () => {
    const src = await import("node:fs").then((fs) =>
      fs.readFileSync(new URL("./SceneCreatorCore.tsx", import.meta.url), "utf8"),
    );
    const panel = await import("node:fs").then((fs) =>
      fs.readFileSync(new URL("./SceneCreatorPanel.tsx", import.meta.url), "utf8"),
    );
    const launcher = await import("node:fs").then((fs) =>
      fs.readFileSync(new URL("./SceneCreatorExpressLauncher.tsx", import.meta.url), "utf8"),
    );
    expect(src).not.toContain("function ExpressLayout");
    expect(src).not.toContain("function ExpressMaskStage");
    expect(src).toContain("function StandardLayout");
    expect(src).toContain("Final Quality Render");
    expect(src).not.toContain("function CameraBlock");
    expect(panel).toContain("SceneCreatorExpressLauncher");
    expect(panel).not.toContain('variant="express"');
    expect(launcher).toContain("scene-creator-open-standard");
    expect(launcher).toContain("Open Scene Creator");
    expect(launcher).toContain("onGoTab?.(\"scenecreator\")");
    expect(launcher).not.toContain("CinematographerPanel");
    expect(launcher).not.toContain("scene-creator-generate");
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

  it("keeps the three-zone tool law: left tools, center mask, right camera cards", async () => {
    const src = await import("node:fs").then((fs) =>
      fs.readFileSync(new URL("./SceneCreatorCore.tsx", import.meta.url), "utf8"),
    );
    const standard = src.slice(src.indexOf("function StandardLayout"), src.indexOf("function usePreviewAsset"));
    const browser = standard.slice(standard.indexOf("scene-creator-standard__browser"), standard.indexOf("StandardPreview"));
    const inspector = standard.slice(standard.indexOf("scene-creator-standard__inspector"), standard.indexOf("scene-creator-standard__strip"));
    expect(browser).toContain("OrientationAccordion");
    expect(browser).toContain("RegionEditBlock");
    expect(inspector).toContain("CinematographerPanel");
    expect(inspector).not.toContain("OrientationAccordion");
    expect(inspector).not.toContain("RegionEditBlock");
    expect(standard).toContain("StandardPreview");
    expect(src).toContain("CenterMaskCanvas");
    const cine = await import("node:fs").then((fs) =>
      fs.readFileSync(new URL("./cinematographer/CinematographerPanel.tsx", import.meta.url), "utf8"),
    );
    expect(cine).toContain("cine-tile-c${slot + 1}");
    expect(cine).not.toContain("<OrientationAccordion");
    expect(cine).not.toContain("function OrientationSection");
    const inpaint = await import("node:fs").then((fs) =>
      fs.readFileSync(new URL("./regionEdit/RegionEditPanel.tsx", import.meta.url), "utf8"),
    );
    expect(inpaint).not.toContain("ImageMaskEditor");
    expect(inpaint).toContain("scene-creator-inpaint-source");
    const css = await import("node:fs").then((fs) =>
      fs.readFileSync(new URL("./sceneCreator.css", import.meta.url), "utf8"),
    );
    expect(css).toContain("grid-template-columns: 220px minmax(0, 1fr) 280px");
    const mask = await import("node:fs").then((fs) =>
      fs.readFileSync(new URL("../../imageEdit/ImageMaskEditor.tsx", import.meta.url), "utf8"),
    );
    expect(mask).toContain("}, [imageUrl]);");
    expect(mask).not.toContain("[imageUrl, onChange, syncDisplay]");
  });
});
