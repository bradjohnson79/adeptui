import { useEffect, useRef, useState } from "react";
import { DRAFT_SEQUENCE_FPS, draftPlaybackMode } from "./draftFrameSequence";

/**
 * Plays buffered draft still URLs as a looping low-FPS sequence.
 * Single-frame buffers stay as a still (honest — no fake motion).
 */
export function DraftSequencePlayer({
  urls,
  alt,
  fit = "contain",
  fps = DRAFT_SEQUENCE_FPS,
  paused = false,
  testId = "live-preview-draft-sequence",
}: {
  urls: string[];
  alt: string;
  fit?: "contain" | "cover" | "none";
  fps?: number;
  paused?: boolean;
  testId?: string;
}) {
  const mode = draftPlaybackMode(urls.length);
  const [index, setIndex] = useState(0);
  const urlsRef = useRef(urls);
  urlsRef.current = urls;

  useEffect(() => {
    setIndex(0);
  }, [urls[0], urls.length]);

  useEffect(() => {
    if (mode !== "sequence" || paused) return;
    const ms = Math.max(80, Math.round(1000 / Math.max(1, fps)));
    const id = window.setInterval(() => {
      const list = urlsRef.current;
      if (list.length < 2) return;
      setIndex((i) => (i + 1) % list.length);
    }, ms);
    return () => window.clearInterval(id);
  }, [mode, paused, fps, urls.length]);

  if (mode === "empty") return null;

  const src = urls[Math.min(index, urls.length - 1)] || urls[0];
  const objectFit = fit === "cover" ? "cover" : fit === "none" ? "none" : "contain";

  return (
    <img
      key={mode === "still" ? src : "draft-sequence"}
      src={src}
      alt={alt}
      data-testid={testId}
      data-draft-playback={mode}
      data-draft-frame-count={urls.length}
      data-draft-frame-index={mode === "sequence" ? index : 0}
      style={{ objectFit, width: "100%", height: "100%" }}
    />
  );
}
