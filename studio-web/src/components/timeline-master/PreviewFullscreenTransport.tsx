import { useEffect, useState, type RefObject } from "react";
import { TransportBatchEndIcon, TransportBatchStartIcon, TransportForward5Icon, TransportPauseIcon, TransportPlayIcon, TransportRewind5Icon, TransportSceneEndIcon, TransportSceneStartIcon } from "./previewTransportIcons";

/**
 * Fullscreen-only transport bar for the Preview Monitor.
 *
 * Shows ONLY when the Preview Monitor is in browser fullscreen mode.
 * Normal embedded Preview Monitor does NOT show these controls.
 *
 * While fullscreen, this transport OWNS the preview <video> element:
 * Play/Pause/seek must use videoRef.current at click/key time (never a
 * render-time capture). LivePreviewMonitor suppresses applyTimelineVideoClock
 * while isFullscreen so the timeline clock cannot pause/seek-fight us.
 *
 * Layout:
 *   [ VIDEO / IMAGE ]
 *         00:34 / 01:12
 *   |<<  -5s  ▶/⏸  +5s  >>|
 *   Re-Take    Exit Fullscreen
 *
 * Those transport buttons stay in fullscreen even before a clip is rendered.
 * With no video element they move the Timeline playhead.
 */

function formatTime(seconds: number): string {
  const safe = Math.max(0, Number.isFinite(seconds) ? seconds : 0);
  const whole = Math.floor(safe + 1e-6);
  const m = Math.floor(whole / 60);
  const s = whole % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function readVideo(videoRef: RefObject<HTMLVideoElement | null>): HTMLVideoElement | null {
  return videoRef.current;
}

export function PreviewFullscreenTransport({
  videoRef,
  isFullscreen,
  isVideoMedia,
  onExitFullscreen,
  onTogglePlay,
  onSeekLocalTime,
  onRetake,
  retakeActive,
  timelineTimeSec = 0,
  timelineDurationSec = 0,
  timelinePlaying = false,
  sceneTimeSec,
  sceneDurationSec = 0,
  onSceneSeek,
  onBatchStart,
  onBatchEnd,
}: {
  videoRef: RefObject<HTMLVideoElement | null>;
  isFullscreen: boolean;
  isVideoMedia: boolean;
  onExitFullscreen: () => void | Promise<void>;
  onTogglePlay?: () => void;
  /** Notify parent of clip-local seek so playhead can stay aligned on exit. */
  onSeekLocalTime?: (localSec: number) => void;
  onRetake?: () => void;
  retakeActive?: boolean;
  timelineTimeSec?: number;
  timelineDurationSec?: number;
  timelinePlaying?: boolean;
  sceneTimeSec?: number;
  sceneDurationSec?: number;
  onSceneSeek?: (sceneTime: number) => void;
  onBatchStart?: () => void;
  onBatchEnd?: () => void;
}) {
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);

  // Track video time/duration/play state while fullscreen
  useEffect(() => {
    if (!isFullscreen) return;
    const v = readVideo(videoRef);
    if (!v) return;

    const onTime = () => setCurrentTime(v.currentTime);
    const onDur = () => setDuration(v.duration || 0);
    const onPlay = () => setIsPlaying(true);
    const onPause = () => setIsPlaying(false);
    const onEnded = () => setIsPlaying(false);

    setCurrentTime(v.currentTime);
    setDuration(v.duration || 0);
    setIsPlaying(!v.paused && !v.ended);

    v.addEventListener("timeupdate", onTime);
    v.addEventListener("durationchange", onDur);
    v.addEventListener("loadedmetadata", onDur);
    v.addEventListener("play", onPlay);
    v.addEventListener("pause", onPause);
    v.addEventListener("ended", onEnded);
    return () => {
      v.removeEventListener("timeupdate", onTime);
      v.removeEventListener("durationchange", onDur);
      v.removeEventListener("loadedmetadata", onDur);
      v.removeEventListener("play", onPlay);
      v.removeEventListener("pause", onPause);
      v.removeEventListener("ended", onEnded);
    };
  }, [isFullscreen, videoRef]);

  // Keyboard shortcuts while fullscreen — always resolve videoRef.current inside handlers
  useEffect(() => {
    if (!isFullscreen) return;

    const seek = (delta: number) => {
      if (onSceneSeek) {
        const base = sceneTimeSec ?? timelineTimeSec;
        const limit = sceneDurationSec > 0 ? sceneDurationSec : Number.POSITIVE_INFINITY;
        onSceneSeek(Math.max(0, Math.min(limit, base + delta)));
        return;
      }
      const v = readVideo(videoRef);
      const base = v ? v.currentTime : timelineTimeSec;
      const dur =
        (v && Number.isFinite(v.duration) && v.duration > 0 ? v.duration : 0) ||
        duration ||
        timelineDurationSec;
      const next = Math.max(0, Math.min(dur > 0 ? dur : Number.POSITIVE_INFINITY, base + delta));
      if (v) v.currentTime = next;
      setCurrentTime(next);
      onSeekLocalTime?.(next);
    };

    const jumpToStart = () => {
      if (onSceneSeek) {
        onSceneSeek(0);
        return;
      }
      const v = readVideo(videoRef);
      if (v) v.currentTime = 0;
      setCurrentTime(0);
      onSeekLocalTime?.(0);
    };

    const jumpToEnd = () => {
      if (onSceneSeek) {
        onSceneSeek(sceneDurationSec);
        return;
      }
      const v = readVideo(videoRef);
      const dur =
        (v && Number.isFinite(v.duration) && v.duration > 0 ? v.duration : 0) ||
        duration ||
        timelineDurationSec ||
        0;
      const next = Math.max(0, dur - 0.01);
      if (v) v.currentTime = next;
      setCurrentTime(next);
      onSeekLocalTime?.(next);
    };

    const togglePlay = () => {
      if (onSceneSeek) {
        onTogglePlay?.();
        return;
      }
      const v = readVideo(videoRef);
      if (isVideoMedia && v) {
        if (v.paused) {
          void v.play().catch(() => undefined);
        } else {
          v.pause();
        }
        return;
      }
      onTogglePlay?.();
    };

    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) {
        return;
      }

      switch (e.key) {
        case " ":
        case "Spacebar":
          e.preventDefault();
          e.stopPropagation();
          togglePlay();
          break;
        case "ArrowLeft":
          e.preventDefault();
          e.stopPropagation();
          seek(-5);
          break;
        case "ArrowRight":
          e.preventDefault();
          e.stopPropagation();
          seek(5);
          break;
        case "Home":
          e.preventDefault();
          e.stopPropagation();
          jumpToStart();
          break;
        case "End":
          e.preventDefault();
          e.stopPropagation();
          jumpToEnd();
          break;
        case "Escape":
          e.preventDefault();
          e.stopPropagation();
          void onExitFullscreen();
          break;
        default:
          break;
      }
    };

    document.addEventListener("keydown", onKey, true);
    return () => {
      document.removeEventListener("keydown", onKey, true);
    };
  }, [isFullscreen, videoRef, onExitFullscreen, onTogglePlay, onSeekLocalTime, onSceneSeek, duration, timelineTimeSec, timelineDurationSec, sceneTimeSec, sceneDurationSec, isVideoMedia]);

  if (!isFullscreen) return null;

  const shownScene = onSceneSeek != null;
  const handleJumpToStart = () => {
    if (shownScene) {
      onSceneSeek?.(0);
      return;
    }
    const v = readVideo(videoRef);
    if (v) v.currentTime = 0;
    setCurrentTime(0);
    onSeekLocalTime?.(0);
  };
  const handleRewind5 = () => {
    if (shownScene) {
      onSceneSeek?.(Math.max(0, (sceneTimeSec ?? 0) - 5));
      return;
    }
    const v = readVideo(videoRef);
    const base = v ? v.currentTime : timelineTimeSec;
    const next = Math.max(0, base - 5);
    if (v) v.currentTime = next;
    setCurrentTime(next);
    onSeekLocalTime?.(next);
  };
  const handleForward5 = () => {
    if (shownScene) {
      const limit = sceneDurationSec > 0 ? sceneDurationSec : Number.POSITIVE_INFINITY;
      onSceneSeek?.(Math.min(limit, (sceneTimeSec ?? 0) + 5));
      return;
    }
    const v = readVideo(videoRef);
    const base = v ? v.currentTime : timelineTimeSec;
    const dur =
      (v && Number.isFinite(v.duration) && v.duration > 0 ? v.duration : 0) ||
      duration ||
      timelineDurationSec ||
      Number.POSITIVE_INFINITY;
    const next = Math.min(dur, base + 5);
    if (v) v.currentTime = next;
    setCurrentTime(next);
    onSeekLocalTime?.(next);
  };
  const handleJumpToEnd = () => {
    if (shownScene) {
      onSceneSeek?.(sceneDurationSec);
      return;
    }
    const v = readVideo(videoRef);
    const dur =
      (v && Number.isFinite(v.duration) && v.duration > 0 ? v.duration : 0) ||
      duration ||
      timelineDurationSec ||
      0;
    const next = Math.max(0, dur - 0.01);
    if (v) v.currentTime = next;
    setCurrentTime(next);
    onSeekLocalTime?.(next);
  };
  const handlePlayPause = () => {
    if (shownScene) {
      onTogglePlay?.();
      return;
    }
    const v = readVideo(videoRef);
    if (isVideoMedia && v) {
      if (v.paused) {
        void v.play().catch(() => undefined);
      } else {
        v.pause();
      }
      return;
    }
    onTogglePlay?.();
  };

  const live = readVideo(videoRef);
  const playing = shownScene ? timelinePlaying : isVideoMedia && live ? isPlaying : timelinePlaying;
  const shownTime = shownScene ? sceneTimeSec ?? 0 : live ? currentTime : timelineTimeSec;
  const durDisplay = shownScene
    ? sceneDurationSec
    : duration || (live && Number.isFinite(live.duration) ? live.duration : 0) || timelineDurationSec;

  return (
    <div className="preview-fullscreen-transport" data-testid="preview-fullscreen-transport">
      {durDisplay > 0 ? (
        <div className="preview-fullscreen-time" data-testid="preview-fullscreen-time">
          {formatTime(shownTime)} / {formatTime(durDisplay)}
        </div>
      ) : null}

      <div className="preview-fullscreen-controls" role="toolbar" aria-label="Fullscreen Preview Transport">
          <button
            type="button"
            className="preview-transport-btn"
            data-testid="preview-fs-jump-start"
            title="Jump to Beginning"
            aria-label="Jump to Beginning"
            onClick={handleJumpToStart}
          >
            <TransportSceneStartIcon />
          </button>
          {onBatchStart ? (
            <button
              type="button"
              className="preview-transport-btn"
              data-testid="preview-fs-batch-start"
              title="Start of Batch"
              aria-label="Start of Batch"
              onClick={onBatchStart}
            >
              <TransportBatchStartIcon />
            </button>
          ) : null}
          <button
            type="button"
            className="preview-transport-btn"
            data-testid="preview-fs-rewind-5"
            title="Rewind 5 Seconds"
            aria-label="Rewind 5 Seconds"
            onClick={handleRewind5}
          >
            <TransportRewind5Icon />
          </button>
          <button
            type="button"
            className="preview-transport-btn preview-transport-play"
            data-testid="preview-fs-play-pause"
            title={playing ? "Pause" : "Play"}
            aria-label={playing ? "Pause" : "Play"}
            aria-pressed={playing}
            onClick={handlePlayPause}
          >
            {playing ? <TransportPauseIcon /> : <TransportPlayIcon />}
          </button>
          <button
            type="button"
            className="preview-transport-btn"
            data-testid="preview-fs-forward-5"
            title="Forward 5 Seconds"
            aria-label="Forward 5 Seconds"
            onClick={handleForward5}
          >
            <TransportForward5Icon />
          </button>
          {onBatchEnd ? (
            <button
              type="button"
              className="preview-transport-btn"
              data-testid="preview-fs-batch-end"
              title="End of Batch"
              aria-label="End of Batch"
              onClick={onBatchEnd}
            >
              <TransportBatchEndIcon />
            </button>
          ) : null}
          <button
            type="button"
            className="preview-transport-btn"
            data-testid="preview-fs-jump-end"
            title="Jump to End"
            aria-label="Jump to End"
            onClick={handleJumpToEnd}
          >
            <TransportSceneEndIcon />
          </button>
      </div>

      <div className="preview-fullscreen-bottom-row">
        {onRetake ? (
          <button
            type="button"
            className="preview-transport-btn preview-fs-retake"
            data-testid="preview-fs-retake"
            title={retakeActive ? "Close Re-Take" : "Re-Take this shot"}
            aria-label={retakeActive ? "Close Re-Take" : "Re-Take this shot"}
            aria-pressed={retakeActive}
            onClick={onRetake}
          >
            Re-Take
          </button>
        ) : null}
        <button
          type="button"
          className="preview-transport-btn preview-fs-exit"
          data-testid="preview-fs-exit"
          title="Exit Fullscreen"
          aria-label="Exit Fullscreen"
          onClick={() => void onExitFullscreen()}
        >
          Exit Fullscreen
        </button>
      </div>
    </div>
  );
}
