import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

describe("Preview fullscreen transport ownership", () => {
  const transport = readFileSync(join(__dirname, "./PreviewFullscreenTransport.tsx"), "utf8");
  const preview = readFileSync(join(__dirname, "../LivePreviewMonitor.tsx"), "utf8");

  it("resolves videoRef.current inside click/keyboard handlers (no render-time capture)", () => {
    expect(transport).toContain("function readVideo");
    expect(transport).toContain("return videoRef.current");
    expect(transport).toMatch(/const handleForward5[\s\S]*readVideo\(videoRef\)/);
    expect(transport).toMatch(/const handleRewind5[\s\S]*readVideo\(videoRef\)/);
    expect(transport).toMatch(/const handleJumpToStart[\s\S]*readVideo\(videoRef\)/);
    expect(transport).toMatch(/const handleJumpToEnd[\s\S]*readVideo\(videoRef\)/);
    expect(transport).toMatch(/const handlePlayPause[\s\S]*readVideo\(videoRef\)/);
    expect(transport).not.toMatch(
      /if \(!isFullscreen\) return null;[\s\S]*const v = videoRef\.current;[\s\S]*const handleJumpToStart/,
    );
  });

  it("LivePreviewMonitor suppresses timeline clock while preview fullscreen owns video", () => {
    expect(preview).toContain("previewFsOwnsRef");
    expect(preview).toContain("if (previewFsOwnsRef.current) return");
    expect(preview).toContain("previewFsOwnsRef.current = previewFullscreen.isFullscreen");
    expect(preview).toContain("onSeekLocalTime");
  });

  it("does not render Prompt lower-third on Preview Monitor", () => {
    expect(preview).not.toContain('data-testid="timeline-prompt-lower-third"');
    expect(preview).not.toMatch(/className="[^"]*timeline-prompt-lower-third/);
  });
});
