import { useEffect, useRef } from "react";
import { api } from "../../api";
import type { TimelineBoardView } from "../DirectorTracks";
import type { SceneTimelineMaster } from "../../timelineMaster/contracts";
import { collectTimelineAudioAtTime } from "./collectTimelineAudioAtTime";

const DRIFT_SEC = 0.12;

export function useTimelineAudioPlayback(args: {
  projectId: string;
  playing: boolean;
  playheadSec: number;
  timeline: TimelineBoardView | null;
  master: SceneTimelineMaster | null;
}) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const elementsRef = useRef<Map<string, HTMLAudioElement>>(new Map());

  useEffect(() => {
    const host = hostRef.current;
    const elements = elementsRef.current;
    if (!host) return;

    const layers = args.playing
      ? collectTimelineAudioAtTime(args.timeline, args.master, args.playheadSec)
      : [];
    const wanted = new Set(layers.map((layer) => layer.clipId));

    for (const [clipId, el] of elements) {
      if (wanted.has(clipId)) continue;
      el.pause();
    }

    for (const layer of layers) {
      let el = elements.get(layer.clipId);
      if (!el) {
        el = new Audio();
        el.preload = "auto";
        el.setAttribute("data-testid", `timeline-audio-layer-${layer.kind}`);
        el.setAttribute("data-clip-id", layer.clipId);
        el.setAttribute("data-label", layer.label);
        el.setAttribute("data-kind", layer.kind);
        host.appendChild(el);
        elements.set(layer.clipId, el);
      }
      const src = api.assetUrl(layer.assetId, null, args.projectId);
      if (src && el.getAttribute("data-src") !== src) {
        el.src = src;
        el.setAttribute("data-src", src);
      }
      el.volume = layer.volume;
      if (Number.isFinite(el.duration) && Math.abs(el.currentTime - layer.localTime) > DRIFT_SEC) {
        try {
          el.currentTime = layer.localTime;
        } catch {
          /* seek before metadata is ready */
        }
      }
      if (el.paused) {
        void el.play().catch(() => undefined);
      }
    }

    if (!args.playing) {
      for (const el of elements.values()) el.pause();
    }
  }, [args.master, args.playheadSec, args.playing, args.projectId, args.timeline]);

  useEffect(() => {
    const elements = elementsRef.current;
    return () => {
      for (const el of elements.values()) {
        el.pause();
        el.removeAttribute("src");
        el.remove();
      }
      elements.clear();
    };
  }, []);

  return { audioHostRef: hostRef };
}
