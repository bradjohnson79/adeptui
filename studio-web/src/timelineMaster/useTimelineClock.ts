/** Drives the existing playheadSec clock. Not a second Timeline timebase. */

import { useCallback, useEffect, useRef, useState } from "react";

const SCENE_END_EPS = 1e-3;

export function useTimelineClock(args: {
  playheadSec: number;
  setPlayheadSec: (time: number | ((current: number) => number)) => void;
  sceneEndSec: number;
}) {
  const [playing, setPlaying] = useState(false);
  const playingRef = useRef(false);
  const playheadRef = useRef(args.playheadSec);
  const sceneEndRef = useRef(args.sceneEndSec);
  const setPlayheadSec = args.setPlayheadSec;
  playheadRef.current = args.playheadSec;
  sceneEndRef.current = Math.max(0, args.sceneEndSec);
  playingRef.current = playing;

  const seek = useCallback(
    (time: number | ((current: number) => number)) => {
      const resolved = typeof time === "function" ? time(playheadRef.current) : time;
      // Premiere-style counter: scrub is not capped at the scene/sequence end.
      // Playback still stops at sceneEndSec below.
      const next = Math.max(0, Number.isFinite(resolved) ? resolved : 0);
      playheadRef.current = next;
      setPlayheadSec(next);
    },
    [setPlayheadSec],
  );

  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const dt = Math.min(0.1, Math.max(0, (now - last) / 1000));
      last = now;
      const end = sceneEndRef.current;
      const next = playheadRef.current + dt;
      if (next >= end - 1e-9) {
        playheadRef.current = end;
        setPlayheadSec(end);
        playingRef.current = false;
        setPlaying(false);
        return;
      }
      playheadRef.current = next;
      setPlayheadSec(next);
      raf = window.requestAnimationFrame(tick);
    };
    raf = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(raf);
  }, [playing, setPlayheadSec]);

  const pause = useCallback(() => {
    playingRef.current = false;
    setPlaying(false);
  }, []);

  const play = useCallback(() => {
    const end = sceneEndRef.current;
    if (playheadRef.current >= end - SCENE_END_EPS) {
      playheadRef.current = 0;
      setPlayheadSec(0);
    }
    playingRef.current = true;
    setPlaying(true);
  }, [setPlayheadSec]);

  const toggle = useCallback(() => {
    if (playingRef.current) pause();
    else play();
  }, [pause, play]);

  return { playing, play, pause, toggle, seek };
}
