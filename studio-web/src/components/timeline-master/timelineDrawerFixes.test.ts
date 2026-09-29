import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("Timeline drawer and preview fixes", () => {
  it("Render Queue has a Clear control", () => {
    const src = readFileSync(new URL("./CompactRenderQueue.tsx", import.meta.url), "utf8");
    expect(src).toContain('data-testid="timeline-render-queue-clear"');
    expect(src).toContain("saveDismissedRenderJobIds");
    expect(src).toContain("useProjectJobs");
    expect(src).not.toMatch(/await api\.listJobs\(projectId\)/);
  });

  it("Preview Monitor dismiss stays above the video action menu and clears a pinned failure", () => {
    const monitor = readFileSync(new URL("../LivePreviewMonitor.tsx", import.meta.url), "utf8");
    const css = readFileSync(new URL("../../styles.css", import.meta.url), "utf8");
    expect(monitor).toContain("dismissedJobIds.has(activeJob.id)");
    expect(css).toContain(".live-preview-overlay.bad");
    expect(css).toMatch(/\.live-preview-overlay\.bad\s*\{[^}]*z-index:\s*6/s);
  });

  it("Preview Monitor has an on-stage close button", () => {
    const src = readFileSync(new URL("../LivePreviewMonitor.tsx", import.meta.url), "utf8");
    expect(src).toContain('data-testid="live-preview-close"');
    expect(src).toContain("onClearLibraryAsset");
    expect(src).toContain('current.includes("from Library")');
  });

  it("workspace layout persist defers parent setState off the render turn", () => {
    const layout = readFileSync(new URL("../../timelineMaster/workspaceLayout.ts", import.meta.url), "utf8");
    expect(layout).toContain("queueMicrotask");
    expect(layout).toContain("TIMELINE_LAYOUT_EVENT");
  });

  it("Preview Monitor publish bar has a Timeline-persisted visibility toggle", () => {
    const src = readFileSync(new URL("../LivePreviewMonitor.tsx", import.meta.url), "utf8");
    const layout = readFileSync(new URL("../../timelineMaster/workspaceLayout.ts", import.meta.url), "utf8");
    expect(src).toContain('data-testid="live-preview-publish-bar-visibility"');
    expect(src).toContain("Hide preview actions");
    expect(src).toContain("Show preview actions");
    expect(src).toContain("saveTimelineWorkspaceLayout({ previewPublishBarVisible: next })");
    expect(layout).toContain("previewPublishBarVisible: true");
    expect(layout).toContain("TIMELINE_WORKSPACE_KEY");
    expect(layout).toContain("MAGI_CENTER_SPLIT_KEY");
    expect(src).toContain("{publishChrome ? (");
    expect(src).not.toContain("publishChrome.showPublish || publishChrome.showUpdatePublished");
    expect(src).toContain('data-testid="live-preview-publish"');
    expect(src).toContain('data-testid="live-preview-update-published"');
    expect(src).toContain('data-testid="live-preview-upscale-magi"');
    expect(src).not.toContain("{publishChrome.showPublish ? (");
    expect(src).not.toContain("{publishChrome.showUpdatePublished ? (");
    expect(src).toContain("disabled={publishBusy || upscaleBusy}");
    expect(src).not.toContain("!publishChrome.showPublish}");
    expect(src).not.toContain("!publishChrome.showUpdatePublished}");
    expect(src).not.toContain("!publishChrome.showUpscaleWithMagi}");
  });

  it("Timed Prompt drag commits through the shared timeline mutate path", () => {
    const tracks = readFileSync(new URL("../DirectorTracks.tsx", import.meta.url), "utf8");
    const clip = readFileSync(new URL("./TrackClipInteractive.tsx", import.meta.url), "utf8");
    expect(tracks).toContain('kind === "prompt"');
    expect(tracks).toContain("persistViaMutate");
    expect(clip).toContain("setPointerCapture");
  });

  it("Preview Cancel clears the standby notice and requests a local job cancel", () => {
    const src = readFileSync(new URL("./TimelineEditorShell.tsx", import.meta.url), "utf8");
    const handler = src.slice(src.indexOf("const handleTimelineCancelRender"), src.indexOf("const runGenerateScene"));
    expect(handler).toContain("setGenerationStandby(false)");
    expect(handler).toContain('action: "cancel_active_local_job"');
    expect(handler.indexOf("setGenerationStandby(false)")).toBeLessThan(handler.indexOf("directorTimelineCancel"));
  });

  it("Generate Scene surfaces timelineActionError", () => {
    const src = readFileSync(new URL("./TimelineEditorShell.tsx", import.meta.url), "utf8");
    expect(src).toContain("timelineActionError");
    expect(src).toContain("runGenerateScene");
    expect(src).toContain('data-testid="timeline-action-notice"');
  });

  it("Review & Extend is wired next to Generate Scene", () => {
    const src = readFileSync(new URL("./TimelineEditorShell.tsx", import.meta.url), "utf8");
    expect(src).toContain('data-testid="timeline-header-review-extend"');
    expect(src).toContain("runReviewExtend");
    expect(src).toContain("directorTimelineExtend");
    expect(src).toContain("reviewExtendBusy");
  });

  it("Inspector shows a creator-facing next-shot status when long-form continuity exists", () => {
    const src = readFileSync(new URL("./TimelineInspector.tsx", import.meta.url), "utf8");
    expect(src).toContain('data-testid="timeline-extend-status"');
    expect(src).toContain("latestExtendSegment");
    expect(src).toContain("longFormContinuity");
    expect(src).toContain("storyState");
  });

  it("Timeline Viewer toolbar does not include Pause Viewer", () => {
    const src = readFileSync(new URL("./TimelineEditorShell.tsx", import.meta.url), "utf8");
    expect(src).not.toContain("timeline-viewer-pause");
    expect(src).not.toContain("pauseViewer");
    expect(src).not.toContain("pauseUpdates");
    expect(src).toContain("timeline-viewer-guides");
  });

  it("Guides render from one master composition rect and stay viewer-only", () => {
    const monitor = readFileSync(new URL("../LivePreviewMonitor.tsx", import.meta.url), "utf8");
    const overlay = readFileSync(new URL("./PreviewGuidesOverlay.tsx", import.meta.url), "utf8");
    const shared = readFileSync(new URL("../shared/AdeptCompositionGuides.tsx", import.meta.url), "utf8");
    const geometry = readFileSync(new URL("../../workspace/compositionGuides.ts", import.meta.url), "utf8");
    const css = readFileSync(new URL("../../styles/shared/adept-composition-guides.css", import.meta.url), "utf8");
    expect(monitor).toContain("PreviewGuidesOverlay");
    expect(monitor).toContain("aspectRatio={scene?.aspect_ratio}");
    expect(monitor).toContain("visible={!hideOverlay}");
    expect(overlay).toContain("AdeptCompositionGuides");
    expect(overlay).toContain('mode="fit"');
    expect(shared).toContain("getCompositionRect");
    expect(shared).toContain('data-testid="adept-composition-guides"');
    expect(geometry).toContain("export function fitAspectRect");
    expect(css).toContain("pointer-events: none");
    expect(css).toContain("overflow: hidden");
  });

  it("MAGI guides use the same shared fill renderer, not a second overlay implementation", () => {
    const magiOverlay = readFileSync(new URL("../magi/overlays/MagiOverlayLayer.tsx", import.meta.url), "utf8");
    const magiFrame = readFileSync(new URL("../magi/MagiPreviewFitFrame.tsx", import.meta.url), "utf8");
    const magiWorkspace = readFileSync(new URL("../magi/MagiEditorWorkspace.tsx", import.meta.url), "utf8");
    const magiSplit = readFileSync(new URL("../magi/MagiSplitView.tsx", import.meta.url), "utf8");
    expect(magiOverlay).not.toContain("AdeptCompositionGuides");
    expect(magiOverlay).not.toContain("magi-safe-guides");
    expect(magiFrame).toContain("AdeptCompositionGuides");
    expect(magiFrame).toContain('mode="fill"');
    expect(magiWorkspace).toContain('data-testid="magi-viewer-guides"');
    expect(magiWorkspace).toContain("guidesVisible={overlays.safeGuides}");
    expect(magiSplit).toContain("guidesVisible={guidesVisible}");
  });

  it("Preview Monitor status heading is take-aware", () => {
    const strip = readFileSync(new URL("./SceneStatusStrip.tsx", import.meta.url), "utf8");
    const shell = readFileSync(new URL("./TimelineEditorShell.tsx", import.meta.url), "utf8");
    expect(strip).toContain('data-testid="timeline-preview-take-status"');
    expect(strip).toContain("previewStatusLabel");
    expect(strip).not.toContain("getTimelineSceneStatus");
    expect(strip).not.toContain("totalScenes");
    expect(shell).toContain("formatPreviewTakeStatusLabel");
    expect(shell).toContain("previewTakeStatusLabel");
  });
});
