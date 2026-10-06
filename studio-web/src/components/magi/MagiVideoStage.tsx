import { useEffect, useRef } from "react";
import {
  recordMediaTimeWrite,
  shouldWriteMediaTime,
  type MagiClockRole,
} from "./magiPlaybackClock";

/** Playhead-synced MAGI picture stage. Media clock is authority during PLAY. */
export function MagiVideoStage({
  src,
  timeSeconds,
  playing,
  muted = true,
  filter,
  opacity = 1,
  clockRole = "authority",
  seekGeneration = 0,
  onError,
  onReadySize,
  onClock,
  onEnded,
}: {
  src: string;
  timeSeconds: number | null;
  playing: boolean;
  muted?: boolean;
  filter?: string;
  opacity?: number;
  clockRole?: MagiClockRole;
  seekGeneration?: number;
  onError: () => void;
  onReadySize?: (width: number, height: number) => void;
  onClock?: (seconds: number) => void;
  onEnded?: () => void;
}) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const onReadySizeRef = useRef(onReadySize);
  const onClockRef = useRef(onClock);
  const lastAppliedSeekRef = useRef(0);
  onReadySizeRef.current = onReadySize;
  onClockRef.current = onClock;

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    if (timeSeconds == null || !Number.isFinite(timeSeconds)) return;
    const target = Math.max(0, timeSeconds);
    const force = seekGeneration > 0 && seekGeneration !== lastAppliedSeekRef.current;
    if (force) lastAppliedSeekRef.current = seekGeneration;
    if (
      !shouldWriteMediaTime({
        playing,
        mediaTime: video.currentTime,
        targetTime: target,
        force,
      })
    ) {
      return;
    }
    video.currentTime = target;
    recordMediaTimeWrite(playing && !force ? "drift" : "seek");
  }, [timeSeconds, playing, seekGeneration]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    video.muted = muted;
  }, [muted]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    // A gap has no source time. Hold the frame so the file does not keep
    // playing the portion the creator trimmed out.
    const hold = timeSeconds == null || !Number.isFinite(timeSeconds);
    if (playing && !hold) void video.play().catch(() => undefined);
    else video.pause();
  }, [playing, timeSeconds]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !playing || clockRole !== "authority") return;
    let raf = 0;
    const tick = () => {
      if (!video.seeking) onClockRef.current?.(video.currentTime);
      raf = window.requestAnimationFrame(tick);
    };
    raf = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(raf);
  }, [playing, clockRole, src]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    const report = () => {
      if (video.videoWidth > 0 && video.videoHeight > 0) {
        onReadySizeRef.current?.(video.videoWidth, video.videoHeight);
      }
    };
    report();
    video.addEventListener("loadedmetadata", report);
    return () => video.removeEventListener("loadedmetadata", report);
  }, [src]);

  return (
    <video
      ref={videoRef}
      src={src}
      muted={muted}
      playsInline
      loop={false}
      data-testid="magi-video-stage"
      data-clock-role={clockRole}
      data-live-filter={filter || ""}
      style={{ filter: filter || "none", opacity }}
      onError={onError}
      onEnded={onEnded}
      onLoadedMetadata={(event) => {
        const video = event.currentTarget;
        if (video.videoWidth > 0 && video.videoHeight > 0) {
          onReadySize?.(video.videoWidth, video.videoHeight);
        }
      }}
    />
  );
}
