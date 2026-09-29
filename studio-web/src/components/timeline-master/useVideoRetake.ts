import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../api";
import { pollJob } from "../../utils/pollJob";
import type { BatchTimeWindow } from "../../timelineMaster/batchWindows";
import { batchWindowAtTime } from "../../timelineMaster/batchWindows";
import { findImageFrameReferenceAssetId, type ImageFrameClipLike } from "../../timelineMaster/imageFrameVisual";
import {
  EMPTY_VIDEO_RETAKE,
  boundRetakeToBatch,
  canSubmitVideoRetake,
  closedVideoRetakeSession,
  effectiveRetakePrompt,
  nextRetakeLauncherAction,
  retakeProgressLabel,
  type VideoRetakeSession,
} from "../../timelineMaster/videoRetake";

export function useVideoRetake({
  projectId,
  sceneId,
  playheadSec,
  batchWindows,
  videoClips,
  pausePlayback,
  afterMutation,
}: {
  projectId: string;
  sceneId: string | undefined;
  playheadSec: number;
  batchWindows: BatchTimeWindow[];
  // Current Visual video_clips — used to pass referenceImageAssetId when marks cover imgclip_.
  videoClips?: ImageFrameClipLike[] | null;
  pausePlayback: () => void;
  afterMutation: () => Promise<void>;
}) {
  const [session, setSession] = useState<VideoRetakeSession>(EMPTY_VIDEO_RETAKE);
  const pollStopRef = useRef<(() => void) | null>(null);
  const sessionRef = useRef(session);
  sessionRef.current = session;

  useEffect(() => {
    return () => {
      pollStopRef.current?.();
    };
  }, []);

  useEffect(() => {
    setSession(EMPTY_VIDEO_RETAKE);
    pollStopRef.current?.();
  }, [sceneId]);

  useEffect(() => {
    const current = sessionRef.current;
    if (!current.open) return;
    setSession((prev) => (prev.open ? { ...prev, referenceFrameTime: playheadSec } : prev));
  }, [playheadSec]);

  const open = useCallback(() => {
    pausePlayback();
    pollStopRef.current?.();
    setSession({
      ...EMPTY_VIDEO_RETAKE,
      open: true,
      referenceFrameTime: playheadSec,
      emptyCopy: null,
    });
  }, [pausePlayback, playheadSec]);

  const openWithEmpty = useCallback(
    (emptyCopy: string) => {
      pausePlayback();
      pollStopRef.current?.();
      setSession({
        ...EMPTY_VIDEO_RETAKE,
        open: true,
        referenceFrameTime: playheadSec,
        emptyCopy,
      });
    },
    [pausePlayback, playheadSec],
  );

  const close = useCallback(() => {
    pollStopRef.current?.();
    setSession(closedVideoRetakeSession());
  }, []);

  const toggle = useCallback(() => {
    if (nextRetakeLauncherAction(sessionRef.current.open) === "close") {
      close();
      return;
    }
    open();
  }, [close, open]);

  const patch = useCallback((next: Partial<VideoRetakeSession>) => {
    setSession((prev) => ({ ...prev, ...next }));
  }, []);

  const markIn = useCallback(() => {
    setSession((prev) => ({ ...prev, rangeStart: playheadSec, error: null }));
  }, [playheadSec]);

  const markOut = useCallback(() => {
    setSession((prev) => ({ ...prev, rangeEnd: playheadSec, error: null }));
  }, [playheadSec]);

  /** Toggle No BG — marks+prompt(+No BG) only; no brush/mask paint path. */
  const removeBackground = useCallback(() => {
    if (!sceneId) return;
    pausePlayback();
    setSession((prev) => ({
      ...prev,
      removeBackgroundUsed: !prev.removeBackgroundUsed,
      error: null,
      stage: null,
    }));
  }, [pausePlayback, sceneId]);

  const submit = useCallback(async () => {
    if (!sceneId) return;
    const current = sessionRef.current;
    const gate = canSubmitVideoRetake(current);
    if (!gate.ok) {
      setSession((prev) => ({ ...prev, error: gate.error }));
      return;
    }
    const bounded = boundRetakeToBatch(batchWindows, current.rangeStart, current.rangeEnd);
    if (!bounded.ok) {
      setSession((prev) => ({ ...prev, error: bounded.error }));
      return;
    }
    const batchWin = batchWindowAtTime(batchWindows, current.referenceFrameTime);
    const referenceFrameTime = batchWin
      ? batchWin.start > 0
        ? Math.max(0, current.referenceFrameTime)
        : Math.max(0, current.referenceFrameTime - batchWin.start)
      : current.referenceFrameTime;
    const prompt = effectiveRetakePrompt(current);
    const markIn = bounded.sceneStart;
    const markOut = bounded.sceneEnd;
    const referenceImageAssetId = findImageFrameReferenceAssetId(videoClips, markIn, markOut);
    // Marks + prompt (+ optional No BG) only — never send brush/mask PNG or paint→inpaint.
    // When window is imgclip_ / image_frame, pass that still as I2V referenceImageAssetId.
    const run = async (spendApiCredits: boolean) =>
      api.directorTimelineRetakeRange(projectId, sceneId, bounded.batchId, {
        start: bounded.start,
        length: bounded.length,
        prompt,
        spendApiCredits,
        referenceFrameTime,
        removeBackground: current.removeBackgroundUsed,
        ...(referenceImageAssetId ? { referenceImageAssetId } : {}),
      });

    setSession((prev) => ({
      ...prev,
      busy: true,
      error: null,
      stage: "Preparing Re-Take",
    }));
    try {
      let result = await run(false);
      if (result?.error === "API_CREDIT_CONFIRMATION_REQUIRED") {
        const ok = window.confirm(
          String(result.message || "This Re-Take uses paid credits. Continue?"),
        );
        if (!ok) {
          setSession((prev) => ({ ...prev, busy: false, stage: null }));
          return;
        }
        result = await run(true);
      }
      if (result && result.ok === false) {
        const errCode = String(result.error || "");
        const msg =
          errCode === "IMAGE_FRAME_I2V_UNSUPPORTED"
            ? String(
                result.message ||
                  "This generator cannot use the Visual image frame (needs I2V or R2V). Not a Text-to-Video fallback.",
              )
            : String(result.message || result.error || "Re-Take could not start.");
        setSession((prev) => ({
          ...prev,
          busy: false,
          stage: null,
          error: msg,
          disclosure: typeof result.disclosure === "string" ? result.disclosure : prev.disclosure,
        }));
        return;
      }
      const jobId = typeof result.jobId === "string" ? result.jobId : null;
      if (typeof result.disclosure === "string") {
        setSession((prev) => ({ ...prev, disclosure: result.disclosure as string }));
      }
      if (!jobId) {
        await afterMutation();
        setSession(EMPTY_VIDEO_RETAKE);
        return;
      }
      setSession((prev) => ({ ...prev, jobId, stage: "Generating repair" }));
      pollStopRef.current?.();
      pollStopRef.current = pollJob(jobId, {
        getJob: api.getJob,
        intervalMs: 1500,
        terminalStatuses: ["done", "completed", "failed", "cancelled", "canceled", "timed_out"],
        onUpdate: (job) => {
          setSession((prev) => ({
            ...prev,
            stage: retakeProgressLabel({ jobStatus: job.status, jobStage: job.stage }),
          }));
        },
        onTerminal: (job, status) => {
          void (async () => {
            if (status !== "done" && status !== "completed") {
              setSession((prev) => ({
                ...prev,
                busy: false,
                stage: null,
                error: job.message || "The Re-Take did not finish.",
              }));
              return;
            }
            // Range retake owns apply (replace_visual_range). Do not route brush→keyframe_repair/inpaint.
            setSession((prev) => ({ ...prev, stage: "Saving" }));
            await afterMutation();
            setSession({ ...EMPTY_VIDEO_RETAKE, stage: "Complete" });
            window.setTimeout(() => setSession(EMPTY_VIDEO_RETAKE), 1200);
          })();
        },
      });
    } catch (error) {
      setSession((prev) => ({
        ...prev,
        busy: false,
        stage: null,
        error: error instanceof Error ? error.message : "Re-Take could not start.",
      }));
    }
  }, [afterMutation, batchWindows, projectId, sceneId, videoClips]);

  const highlight =
    session.open && session.rangeStart != null && session.rangeEnd != null
      ? {
          start: Math.min(session.rangeStart, session.rangeEnd),
          length: Math.abs(session.rangeEnd - session.rangeStart),
        }
      : null;

  return {
    session,
    highlight,
    open,
    openWithEmpty,
    close,
    cancel: close,
    toggle,
    markIn,
    markOut,
    setPrompt: (prompt: string) => patch({ prompt }),
    removeBackground,
    submit,
  };
}
