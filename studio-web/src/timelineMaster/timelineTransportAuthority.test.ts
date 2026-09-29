import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

describe("Timeline transport clock authority", () => {
  it("drives the existing playheadSec clock and does not invent a second timebase", () => {
    const shell = readFileSync(join(__dirname, "../components/timeline-master/TimelineEditorShell.tsx"), "utf8");
    const clock = readFileSync(join(__dirname, "./useTimelineClock.ts"), "utf8");
    const preview = readFileSync(join(__dirname, "../components/LivePreviewMonitor.tsx"), "utf8");
    const toolbar = readFileSync(join(__dirname, "../components/timeline-master/TimelineToolbar.tsx"), "utf8");

    expect(shell).toContain("useTimelineClock({ playheadSec, setPlayheadSec, sceneEndSec })");
    expect(shell).toContain("externalPlayhead={playheadSec}");
    expect(shell).toContain("timelinePlaying={playing}");
    expect(shell).not.toContain("transportPlayhead2");
    expect(shell).not.toContain("previewPlaybackState");

    expect(clock).toContain("Drives the existing playheadSec clock");
    expect(clock).not.toContain("transportPlayhead2");
    expect(clock).not.toContain("previewPlaybackState");

    expect(preview).toContain("if (timelinePlaying) return");
    expect(preview).toContain("void v.play()");
    expect(preview).not.toContain("if (!v.paused) v.pause()");
    expect(preview).toContain("live-preview-scene-clock");
    expect(preview).toContain("same <video> element across batch src changes");
    expect(preview).toContain("onCanPlay");
    expect(preview).toContain("onLoadedData");
    expect(preview).not.toContain("transportPlayhead2");
    expect(preview).not.toContain("previewPlaybackState");

    expect(toolbar).toContain("timeline-transport-scene-start");
    expect(toolbar).toContain("timeline-transport-in");
    expect(toolbar).toContain("timeline-transport-play");
    expect(toolbar).toContain("timeline-transport-out");
    expect(toolbar).toContain("timeline-transport-scene-end");
    expect(toolbar).toContain("onTogglePlay");
    expect(toolbar).toContain("onGoToSceneStart");
    expect(toolbar).toContain("onGoToSceneEnd");
    expect(toolbar).not.toMatch(/data-testid="timeline-transport-pause"/);
  });

  it("consumes one canonical transport bounds helper rather than five independent clocks", () => {
    const shell = readFileSync(join(__dirname, "../components/timeline-master/TimelineEditorShell.tsx"), "utf8");
    const transport = readFileSync(join(__dirname, "./timelineTransport.ts"), "utf8");
    const duration = readFileSync(join(__dirname, "./generatorDuration.ts"), "utf8");

    expect(shell).toContain("resolveTimelineTransportBounds");
    expect(shell).toContain("seek(resolveTransport().sceneStart)");
    expect(shell).toContain("seek(resolveTransport().activeBatchStart)");
    expect(shell).toContain("seek(resolveTransport().activeBatchEnd)");
    expect(shell).toContain("seek(resolveTransport().sceneEnd)");
    expect(shell).toContain("timelineBoardDurationSec(liveMaster, liveDirector, selected)");
    expect(shell).toContain("useLayoutEffect");
    expect(shell).not.toContain("generatorMaxDurationSec(");
    expect(transport).toContain("never generator.maxDuration");
    expect(transport).toContain("timelineBoardDurationSec");
    expect(duration).toContain("One board clock: Scene duration authority");

    const tracks = readFileSync(join(__dirname, "../components/DirectorTracks.tsx"), "utf8");
    expect(tracks).toContain("if (externalPlayhead == null)");
    expect(tracks).toContain("overlayLiveTimeline(incoming, sceneChanged ? null : prev)");
  });
});
