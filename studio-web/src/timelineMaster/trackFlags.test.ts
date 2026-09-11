import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { effectiveTrackFlags, toggleTrackFlag } from "./trackFlags";

describe("trackFlags", () => {
  it("toggles hide/lock/mute and keeps solo exclusive on audio-like tracks", () => {
    let flags = toggleTrackFlag({}, "visual", "eye");
    expect(flags.visual.hidden).toBe(true);
    flags = toggleTrackFlag(flags, "audio", "solo");
    flags = toggleTrackFlag(flags, "sfx", "solo");
    expect(flags.audio.solo).toBe(false);
    expect(flags.sfx.solo).toBe(true);
    expect(effectiveTrackFlags(flags, "audio").muted).toBe(true);
    expect(effectiveTrackFlags(flags, "sfx").muted).toBeUndefined();
  });

  it("TimelineTrackLabel wires control buttons, not decorative spans", () => {
    const src = readFileSync(
      join(__dirname, "../components/timeline-master/TimelineTrackLabel.tsx"),
      "utf8",
    );
    expect(src).toContain("onControlToggle");
    expect(src).toContain("track-control-");
    expect(src).not.toMatch(/<span key=\{control\} className="timeline-v2__track-label-icon" aria-hidden>/);
  });

  it("Timeline Inspector uses Temperature and does not show Weight", () => {
    const src = readFileSync(
      join(__dirname, "../components/timeline-master/TimelineInspector.tsx"),
      "utf8",
    );
    expect(src).toContain("TemperatureControl");
    expect(src).not.toMatch(/<span>\s*Weight\s*<\/span>/);
  });

  it("Timeline Library empty copy tells the creator to open the project Library picker", () => {
    const src = readFileSync(join(__dirname, "../components/AssetTray.tsx"), "utf8");
    expect(src).toContain("timeline-library-empty");
    expect(src).toContain("libraryChooseFiles");
    expect(src).not.toContain("No assets yet");
  });

  it("Timeline Library rows expose an X remove control wired to onRemoveFromLibrary", () => {
    const tray = readFileSync(join(__dirname, "../components/AssetTray.tsx"), "utf8");
    expect(tray).toContain("onRemoveFromLibrary");
    expect(tray).toContain("asset-remove-library-");
    expect(tray).toContain("asset-item__action--remove");
    const shell = readFileSync(
      join(__dirname, "../components/timeline-master/TimelineEditorShell.tsx"),
      "utf8",
    );
    expect(shell).toContain("handleRemoveFromLibrary");
    expect(shell).toContain("onRemoveFromLibrary={handleRemoveFromLibrary}");
    expect(shell).toContain("library_asset_ids");
  });

  it("Timeline Library modal can add media into the project Library", () => {
    const src = readFileSync(
      join(__dirname, "../components/timeline-master/AddFromProjectLibraryModal.tsx"),
      "utf8",
    );
    expect(src).toContain('data-testid="timeline-library-add-media"');
    expect(src).toContain("api.uploadAsset");
    expect(src).toContain("inferLibraryUploadKind");
  });

  it("Timeline Library modal has a top Add button sharing the footer commit", () => {
    const src = readFileSync(
      join(__dirname, "../components/timeline-master/AddFromProjectLibraryModal.tsx"),
      "utf8",
    );
    // Same-render sibling of the footer Add: same commit(), same disabled
    // predicate — zero new state, double execution impossible (commit closes).
    expect(src).toContain('data-testid="timeline-add-from-project-library-add-top"');
    expect(src).toContain('data-testid="timeline-add-from-project-library-add"');
    const addButtons = src.match(/onClick=\{commit\}/g) || [];
    expect(addButtons.length).toBe(2);
    const disabledGuards = src.match(/disabled=\{selected\.size === 0\}/g) || [];
    expect(disabledGuards.length).toBe(2);
  });

  it("TimelineEditorShell remounts the canonical Video Generator dock and Library picker", () => {
    const src = readFileSync(
      join(__dirname, "../components/timeline-master/TimelineEditorShell.tsx"),
      "utf8",
    );
    expect(src).toContain("VideoGeneratorDock");
    expect(src).toContain("AddFromProjectLibraryModal");
    expect(src).toContain("onAssetsChanged");
    expect(src).toContain("timeline-tab-gpu");
    expect(src).toContain("runGenerateScene");
    expect(src).toContain("timeline-v2__dock--scenes");
    expect(src.indexOf("VideoGeneratorDock")).toBeLessThan(src.indexOf("timeline-v2__dock--scenes"));
  });

  it("DirectorTracks board width is pixelsPerSecond times duration", () => {
    const src = readFileSync(join(__dirname, "../components/DirectorTracks.tsx"), "utf8");
    expect(src).toContain("pixelsPerSecond(zoom) * boardDuration");
    expect(src).not.toContain("Math.max(480, pixelsPerSecond");
    expect(src).toContain("--timeline-lane-width");
  });

  it("TrackClipInteractive attaches magnet listeners on pointerdown", () => {
    const src = readFileSync(
      join(__dirname, "../components/timeline-master/TrackClipInteractive.tsx"),
      "utf8",
    );
    expect(src).toContain("magneticSnapMovingEdge");
    expect(src).toContain("dragRef");
    expect(src).toContain('window.addEventListener("pointermove"');
    expect(src).not.toContain("Math.round(t / 0.25)");
  });

  it("scene generator persist uses the canonical PUT master client", () => {
    const apiSrc = readFileSync(join(__dirname, "../api.ts"), "utf8");
    const applySrc = readFileSync(join(__dirname, "./applySceneGenerator.ts"), "utf8");
    expect(apiSrc).toContain("directorTimelinePutMaster:");
    expect(applySrc).toContain("api.directorTimelinePutMaster");
    expect(applySrc).toContain("sceneGeneratorId: args.generatorId");
    expect(applySrc).toContain("turboLora: nextTurboLoraState");
    expect(applySrc).toContain("applyTimelineTurboLora");
  });

  it("toolbar zoom hotkeys use the timelineZoom authority", () => {
    const src = readFileSync(
      join(__dirname, "../components/timeline-master/TimelineToolbar.tsx"),
      "utf8",
    );
    expect(src).toContain("stepTimelineZoom(zoom, 1)");
    expect(src).toContain("stepTimelineZoom(zoom, -1)");
    expect(src).not.toContain("Math.min(3, +(zoom + 0.25)");
    expect(src).toContain("timelineActionError");
  });
});
