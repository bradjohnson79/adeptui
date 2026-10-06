import { useEffect, useRef, useState } from "react";

type Peaks = { peaks: Float32Array; duration: number };

const peakCache = new Map<string, Peaks>();
const inflight = new Map<string, Promise<Peaks | null>>();

async function loadPeaks(src: string): Promise<Peaks | null> {
  const cached = peakCache.get(src);
  if (cached) return cached;
  let pending = inflight.get(src);
  if (!pending) {
    pending = (async () => {
      try {
        const response = await fetch(src);
        if (!response.ok) return null;
        const raw = await response.arrayBuffer();
        const context = new AudioContext();
        try {
          const audio = await context.decodeAudioData(raw.slice(0));
          const channel = audio.getChannelData(0);
          const buckets = 480;
          const peaks = new Float32Array(buckets);
          const size = Math.max(1, Math.floor(channel.length / buckets));
          for (let index = 0; index < buckets; index += 1) {
            let max = 0;
            const start = index * size;
            const end = Math.min(channel.length, start + size);
            for (let sample = start; sample < end; sample += 4) {
              const value = Math.abs(channel[sample] || 0);
              if (value > max) max = value;
            }
            peaks[index] = max;
          }
          const packed = { peaks, duration: audio.duration };
          peakCache.set(src, packed);
          return packed;
        } finally {
          void context.close();
        }
      } catch {
        return null;
      } finally {
        inflight.delete(src);
      }
    })();
    inflight.set(src, pending);
  }
  return pending;
}

/** Timeline waveform for one audio clip. Peaks are cached per media file. */
export function MagiClipWaveform({
  src,
  inSeconds,
  outSeconds,
}: {
  src: string;
  inSeconds: number;
  outSeconds: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [peaks, setPeaks] = useState<Peaks | null>(() => peakCache.get(src) || null);

  useEffect(() => {
    const cached = peakCache.get(src);
    if (cached) {
      setPeaks(cached);
      return;
    }
    let cancelled = false;
    void loadPeaks(src).then((loaded) => {
      if (!cancelled) setPeaks(loaded);
    });
    return () => {
      cancelled = true;
    };
  }, [src]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !peaks) return;
    const draw = () => {
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      if (width < 2 || height < 2) return;
      const ratio = window.devicePixelRatio || 1;
      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(height * ratio);
      const context = canvas.getContext("2d");
      if (!context) return;
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      context.clearRect(0, 0, width, height);
      const duration = Math.max(0.001, peaks.duration);
      const start = Math.min(duration, Math.max(0, inSeconds));
      const stop = outSeconds > start ? Math.min(duration, outSeconds) : duration;
      const from = Math.floor((start / duration) * peaks.peaks.length);
      const to = Math.max(from + 1, Math.ceil((stop / duration) * peaks.peaks.length));
      const slice = peaks.peaks.subarray(from, to);
      const mid = height / 2;
      context.fillStyle = "rgba(244, 236, 255, 0.92)";
      const bars = Math.max(1, Math.floor(width / 2));
      for (let bar = 0; bar < bars; bar += 1) {
        const sample = slice[Math.min(slice.length - 1, Math.floor((bar / bars) * slice.length))] || 0;
        const barHeight = Math.max(1, sample * (height - 4));
        context.fillRect(bar * 2, mid - barHeight / 2, 1, barHeight);
      }
    };
    draw();
    const observer = new ResizeObserver(draw);
    observer.observe(canvas);
    return () => observer.disconnect();
  }, [inSeconds, outSeconds, peaks]);

  return (
    <canvas
      ref={canvasRef}
      className="magi-clip__wave"
      data-testid="magi-clip-waveform"
      data-ready={peaks ? "true" : "false"}
      aria-hidden="true"
    />
  );
}
