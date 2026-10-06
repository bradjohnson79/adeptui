import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

describe("Timeline preview transport placement", () => {
  const shell = readFileSync(join(__dirname, "./FilmTimelineShell.tsx"), "utf8");
  const track = readFileSync(join(__dirname, "./VisualTrack.tsx"), "utf8");
  const fullscreen = readFileSync(join(__dirname, "../timeline-master/PreviewFullscreenTransport.tsx"), "utf8");
  const icons = readFileSync(join(__dirname, "../timeline-master/previewTransportIcons.tsx"), "utf8");

  it("places the five icon controls under preview and leaves the track free of transport", () => {
    expect(shell).toContain('data-testid="film-timeline-transport"');
    expect(shell).toContain('aria-label="Beginning of Scene"');
    expect(shell).toContain('aria-label="Start of Batch"');
    expect(shell).toContain('aria-label="End of Batch"');
    expect(shell).toContain('aria-label="End of Scene"');
    expect(shell).toContain("onSeek={seekScene}");
    expect(shell).toContain("onTogglePlay={togglePlay}");
    expect(track).not.toContain("film-timeline-transport");
    expect(track).toContain('data-testid="film-timeline-add-from-library"');
    expect(track).toContain('data-testid="film-timeline-add-batch"');
    expect(track).toContain('data-testid="film-timeline-add-previous"');
  });

  it("shares the fullscreen play and scene-jump marks", () => {
    for (const name of ["TransportPlayIcon", "TransportPauseIcon", "TransportSceneStartIcon", "TransportSceneEndIcon"]) {
      expect(icons).toContain(`function ${name}`);
      expect(shell).toContain(name);
      expect(fullscreen).toContain(name);
    }
    expect(shell).toContain("TransportBatchStartIcon");
    expect(shell).toContain("TransportBatchEndIcon");
    expect(fullscreen).toContain('title={playing ? "Pause" : "Play"}');
  });

  it("shares the five-second skip icons between preview and full screen", () => {
    for (const name of ["TransportRewind5Icon", "TransportForward5Icon"]) {
      expect(icons).toContain(`function ${name}`);
      expect(shell).toContain(name);
      expect(fullscreen).toContain(name);
    }
    expect(shell).toContain('data-testid="film-timeline-skip-back"');
    expect(shell).toContain('data-testid="film-timeline-skip-forward"');
    expect(fullscreen).not.toContain(">-5s<");
    expect(fullscreen).not.toContain(">+5s<");
  });
});
