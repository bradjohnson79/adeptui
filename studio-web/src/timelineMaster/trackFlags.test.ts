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
