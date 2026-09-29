import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { TIMELINE_LIPSYNC_CREATOR_UI } from "./timelineLipSyncCreatorUi";

describe("Owner CLEAR — Timeline Lip Sync creator UI off", () => {
  const root = join(__dirname, "..");
  const flagSrc = readFileSync(join(__dirname, "./timelineLipSyncCreatorUi.ts"), "utf8");
  const directorTracks = readFileSync(join(root, "components/DirectorTracks.tsx"), "utf8");
  const toolbar = readFileSync(join(root, "components/timeline-master/TimelineToolbar.tsx"), "utf8");
  const shell = readFileSync(join(root, "components/timeline-master/TimelineEditorShell.tsx"), "utf8");
  const inspector = readFileSync(join(root, "components/timeline-master/TimelineInspector.tsx"), "utf8");
  const lipPanel = readFileSync(join(root, "components/LipSyncTracks.tsx"), "utf8");

  it("keeps TIMELINE_LIPSYNC_CREATOR_UI false (Owner CLEAR — do not re-enable without Brad)", () => {
    expect(TIMELINE_LIPSYNC_CREATOR_UI).toBe(false);
    expect(flagSrc).toContain("Owner CLEAR only");
    expect(flagSrc).toContain("Owner UI authority");
    expect(flagSrc).toContain("do not re-enable Timeline Lip Sync without Brad CLEAR");
    expect(flagSrc).not.toMatch(/export const TIMELINE_LIPSYNC_CREATOR_UI = true/);
  });

  it("does not expose Lip Sync +/- toolbar while flag is false", () => {
    expect(TIMELINE_LIPSYNC_CREATOR_UI).toBe(false);
    expect(toolbar).not.toContain('testId="timeline-toolbar-lipsync"');
    expect(toolbar).not.toContain('label="Lip Sync"');
    expect(toolbar).not.toContain("Prepare Lip Sync");
  });

  it("does not mount creator Lip Sync track lane while flag is false", () => {
    expect(TIMELINE_LIPSYNC_CREATOR_UI).toBe(false);
    expect(directorTracks).not.toContain('data-testid="timeline-lipsync-lane"');
    expect(directorTracks).not.toContain('label="LIP SYNC"');
    expect(directorTracks).not.toContain('label="Lip Sync"');
    expect(directorTracks).not.toContain("timeline-v2__track-row--lipsync");
  });

  it("documents Lip Sync track UI removed; no Prepare Lip Sync creator chrome", () => {
    expect(shell).toContain("Lip Sync track UI removed");
    expect(inspector).not.toContain("Prepare Lip Sync");
    expect(lipPanel).not.toContain("Prepare Lip Sync");
    // Performance Retake panel may live in LipSyncTracks.tsx — that is not creator Lip Sync chrome.
    expect(lipPanel).toContain("Performance Retake");
  });
});
