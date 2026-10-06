import { useEffect, useMemo, useRef } from "react";
import { api } from "../../api";
import { clipSourceFrame, clipUnderPlayhead } from "../../magiSequence/engine";
import type { MagiSequenceDocument } from "../../magiSequence/types";
import { recordMediaTimeWrite, shouldWriteMediaTime } from "./magiPlaybackClock";

function trackKind(sequence: MagiSequenceDocument, trackId: string): string {
  return sequence.tracks.find((track) => track.id === trackId)?.kind || "";
}

/** Matches MAGI final-render stem gains so music stays under dialogue. */
export function previewStemVolume(kind: string, masterVolume: number): number {
  const gain = kind === "music" ? 0.28 : kind === "sfx" ? 0.35 : 1;
  return Math.max(0, Math.min(1, masterVolume * gain));
}

export function audioLaneOwnsPlayback(sequence: MagiSequenceDocument | null, playheadFrame: number): boolean {
  if (!sequence) return false;
  return Boolean(clipUnderPlayhead(sequence, playheadFrame, "audio"));
}

export function MagiPreviewMixer({
  sequence,
  playing,
  muted,
  volume,
  seekGeneration = 0,
}: {
  sequence: MagiSequenceDocument | null;
  playing: boolean;
  muted: boolean;
  volume: number;
  seekGeneration?: number;
}) {
  const nodes = useMemo(() => {
    if (!sequence) return [];
    return sequence.clips.filter((clip) => {
      const kind = trackKind(sequence, clip.trackId);
      return kind === "audio" || kind === "music" || kind === "sfx";
    });
  }, [sequence]);

  const refs = useRef<Record<string, HTMLAudioElement | null>>({});
  const lastAppliedSeekRef = useRef(0);

  useEffect(() => {
    if (!sequence) return;
    const frame = sequence.playheadFrame;
    const mixKinds = new Set(["audio", "music", "sfx"]);
    const anySolo = sequence.tracks.some((track) => track.solo && mixKinds.has(track.kind));
    const force = seekGeneration > 0 && seekGeneration !== lastAppliedSeekRef.current;
    if (force) lastAppliedSeekRef.current = seekGeneration;
    for (const clip of nodes) {
      const el = refs.current[clip.id];
      if (!el) continue;
      const track = sequence.tracks.find((item) => item.id === clip.trackId);
      const sourceFrame = clipSourceFrame(clip, frame);
      const soloMuted = anySolo && !track?.solo;
      const active = sourceFrame != null && !track?.muted && !soloMuted;
      if (sourceFrame != null) {
        const seconds = sourceFrame / Math.max(1, sequence.frameRate);
        if (
          shouldWriteMediaTime({
            playing,
            mediaTime: el.currentTime,
            targetTime: seconds,
            force,
          })
        ) {
          el.currentTime = seconds;
          recordMediaTimeWrite(playing && !force ? "drift" : "seek");
        }
      }
      el.muted = muted || Boolean(track?.muted) || soloMuted || !active;
      el.volume = previewStemVolume(track?.kind || "", volume);
      if (playing && active && !muted) {
        void el.play().catch(() => undefined);
      } else {
        el.pause();
      }
    }
  }, [muted, nodes, playing, seekGeneration, sequence, volume]);

  if (!sequence) return null;
  return (
    <div hidden data-testid="magi-preview-mixer" aria-hidden="true">
      {nodes.map((clip) => (
        <audio
          key={clip.id}
          ref={(node) => {
            refs.current[clip.id] = node;
          }}
          src={api.assetUrl(clip.assetId)}
          preload="auto"
        />
      ))}
    </div>
  );
}
