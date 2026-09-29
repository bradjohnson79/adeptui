import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { TIMELINE_BATCHES_CREATOR_UI } from "./timelineBatchesCreatorUi";

describe("Owner CLEAR — Timeline Batches creator UI off", () => {
  const root = join(__dirname, "..");
  const flagSrc = readFileSync(join(__dirname, "./timelineBatchesCreatorUi.ts"), "utf8");
  const directorTracks = readFileSync(join(root, "components/DirectorTracks.tsx"), "utf8");
  const toolbar = readFileSync(join(root, "components/timeline-master/TimelineToolbar.tsx"), "utf8");
  const timeline = readFileSync(join(root, "components/Timeline.tsx"), "utf8");

  it("keeps TIMELINE_BATCHES_CREATOR_UI false (Owner CLEAR — do not re-enable without Brad)", () => {
    expect(TIMELINE_BATCHES_CREATOR_UI).toBe(false);
    expect(flagSrc).toContain("Owner CLEAR only");
    expect(flagSrc).toContain("do not re-enable without Brad");
    expect(flagSrc).toContain("Owner UI authority");
    expect(flagSrc).toContain("do not re-enable Timeline Batches without Brad CLEAR");
    expect(flagSrc).not.toMatch(/export const TIMELINE_BATCHES_CREATOR_UI = true/);
  });

  it("does not mount BATCHES track / batch lane while flag is false", () => {
    expect(TIMELINE_BATCHES_CREATOR_UI).toBe(false);
    expect(directorTracks).not.toContain('data-testid="timeline-batch-lane"');
    expect(directorTracks).not.toContain('label="BATCHES"');
    expect(directorTracks).not.toContain("timeline-v2__track-row--batch");
    expect(directorTracks).not.toContain('actionLabel="+ Batch"');
  });

  it("does not expose Batch +/- toolbar while flag is false", () => {
    expect(TIMELINE_BATCHES_CREATOR_UI).toBe(false);
    expect(toolbar).not.toContain('testId="timeline-toolbar-batch"');
    expect(toolbar).not.toContain('label="Batch"');
    expect(toolbar).toContain("TIMELINE_BATCHES_CREATOR_UI");
  });

  it("gates N-batches scene labeling behind Owner flag", () => {
    expect(TIMELINE_BATCHES_CREATOR_UI).toBe(false);
    expect(timeline).toContain("sceneListStatusText");
    expect(timeline).toContain("if (!TIMELINE_BATCHES_CREATOR_UI) return status");
    expect(timeline).toContain("TIMELINE_BATCHES_CREATOR_UI");
  });
});
