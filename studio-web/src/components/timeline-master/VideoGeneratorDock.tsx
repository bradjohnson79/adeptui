import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../api";
import type { Scene } from "../../types";
import type { SceneTimelineMaster } from "../../timelineMaster/contracts";
import { resolveGeneratorOption } from "../../timelineMaster/draftCapabilities";
import {
  clipsOverflowGeneratorMax,
  creatorGeneratorLine,
  generatorMaxDurationSec,
  timelineBoardDurationSec,
  trimClipsToDuration,
} from "../../timelineMaster/generatorDuration";
import { useTimelineVideoGenerators } from "../../timelineMaster/useTimelineVideoGenerators";
import { PanelHeading } from "../HelpTip";
import type { DirectorTimeline } from "../DirectorTracks";

function collectTimedClips(timeline: DirectorTimeline | null): Array<{ start: number; length: number }> {
  if (!timeline) return [];
  return [
    ...(timeline.image_clips || []),
    ...(timeline.video_clips || []),
    ...(timeline.prompt_segments || []),
    ...(timeline.camera_clips || []),
    ...(timeline.audio_clips || []),
    ...(timeline.sfx_clips || []),
    ...(timeline.lipsync?.tracks || []).flatMap((track) => track.clips || []),
  ];
}

function sceneWouldOverflow(
  timeline: DirectorTimeline | null,
  master: SceneTimelineMaster | null,
  scene: Scene,
  maxSec: number | null,
): boolean {
  if (maxSec == null) return false;
  const clips = collectTimedClips(timeline);
  if (clipsOverflowGeneratorMax(clips, maxSec) && (master?.batchBlocks.length || 1) <= 1) return true;
  if (clips.some((clip) => clip.length > maxSec + 1e-6)) return true;
  if ((master?.batchBlocks || []).some((batch) => (batch.duration.plannedDuration || 0) > maxSec + 1e-6)) return true;
  if ((timeline?.duration_sec || scene.duration_sec || 0) > maxSec + 1e-6 && (master?.batchBlocks.length || 1) <= 1) {
    return true;
  }
  return false;
}

export function VideoGeneratorDock({
  projectId,
  scene,
  master,
  timeline,
  onRefresh,
  mutateTimeline,
}: {
  projectId: string;
  scene: Scene;
  master: SceneTimelineMaster | null;
  timeline: DirectorTimeline | null;
  onRefresh: () => void | Promise<void>;
  mutateTimeline: (
    mutator: (current: DirectorTimeline) => DirectorTimeline,
    opts?: { refresh?: boolean },
  ) => Promise<void>;
}) {
  const options = useTimelineVideoGenerators();
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const selected = useMemo(
    () =>
      resolveGeneratorOption(
        options,
        master?.sceneGeneratorId,
        master?.batchBlocks[0]?.generatorId,
        scene.engine,
      ),
    [master?.batchBlocks, master?.sceneGeneratorId, options, scene.engine],
  );
  const hydratedRef = useRef(false);

  const applyGenerator = async (generatorId: string, trim: boolean) => {
    const option = resolveGeneratorOption(options, generatorId);
    const maxSec = generatorMaxDurationSec(option);
    setBusy(true);
    try {
      const boardSec = timelineBoardDurationSec(master, timeline, scene);
      const nextDuration = trim && maxSec != null ? Math.min(boardSec || maxSec, maxSec) : boardSec || scene.duration_sec;
      if (trim && maxSec != null) {
        await mutateTimeline(
          (current) => ({
            ...current,
            duration_sec: nextDuration,
            image_clips: trimClipsToDuration(current.image_clips || [], maxSec),
            video_clips: trimClipsToDuration(current.video_clips || [], maxSec),
            prompt_segments: trimClipsToDuration(current.prompt_segments || [], maxSec),
            camera_clips: trimClipsToDuration(current.camera_clips || [], maxSec),
            audio_clips: trimClipsToDuration(current.audio_clips || [], maxSec),
            sfx_clips: trimClipsToDuration(current.sfx_clips || [], maxSec),
          }),
          { refresh: false },
        );
      } else if (Math.abs((timeline?.duration_sec || scene.duration_sec || 0) - nextDuration) > 1e-6) {
        await mutateTimeline(
          (current) => ({ ...current, duration_sec: nextDuration }),
          { refresh: false },
        );
      }
      if (Math.abs((scene.duration_sec || 0) - nextDuration) > 1e-6) {
        await api.updateScene(projectId, scene.id, { duration_sec: nextDuration });
      }
      if (master) {
        await api.directorTimelinePutMaster(projectId, scene.id, {
          ...master,
          sceneGeneratorId: generatorId,
          batchBlocks: master.batchBlocks.map((batch) => ({
            ...batch,
            generatorId,
            duration: {
              ...batch.duration,
              plannedDuration:
                trim && maxSec != null
                  ? Math.min(batch.duration.plannedDuration || maxSec, maxSec)
                  : batch.duration.plannedDuration,
            },
          })),
        });
      } else {
        const first = master?.batchBlocks[0];
        if (first) {
          await api.directorTimelinePatchBatch(projectId, scene.id, first.id, { generatorId });
        }
      }
      await onRefresh();
    } finally {
      setBusy(false);
      setPendingId(null);
    }
  };

  useEffect(() => {
    if (hydratedRef.current || busy || !master || !selected?.id) return;
    const missing =
      !master.sceneGeneratorId ||
      master.batchBlocks.some((batch) => !String(batch.generatorId || "").trim());
    if (!missing) {
      hydratedRef.current = true;
      return;
    }
    hydratedRef.current = true;
    void applyGenerator(selected.id, false);
    // Persist the visible engine onto empty batches — not a silent model swap.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [busy, master, selected?.id]);

  const onSelect = (generatorId: string) => {
    if (!generatorId || generatorId === selected?.id) return;
    const option = resolveGeneratorOption(options, generatorId);
    const maxSec = generatorMaxDurationSec(option);
    if (sceneWouldOverflow(timeline, master, scene, maxSec)) {
      setPendingId(generatorId);
      return;
    }
    void applyGenerator(generatorId, false);
  };

  return (
    <div className="timeline-v2__dock timeline-v2__dock--generator" data-testid="timeline-video-generator">
      <PanelHeading
        title="Video Generator"
        tip="The engine that makes this scene. Duration comes from what that engine can actually run."
      />
      <label className="field">
        <span className="sr-only">Video Generator</span>
        <select
          data-testid="timeline-video-generator-select"
          value={selected?.id || ""}
          disabled={busy}
          onChange={(event) => onSelect(event.target.value)}
        >
          <option value="">{options.length ? "Choose an engine" : "No local engines ready"}</option>
          {options.map((option) => (
            <option key={option.id} value={option.id} title={option.notes} disabled={!option.executable}>
              {creatorGeneratorLine(option)}
              {option.executable ? "" : " — not ready"}
            </option>
          ))}
        </select>
      </label>
      {selected ? (
        <p className="scene-meta" data-testid="timeline-video-generator-summary">
          {creatorGeneratorLine(selected)}
        </p>
      ) : null}
      {pendingId ? (
        <div className="ds-dialog-backdrop" role="presentation" data-testid="timeline-generator-overflow-dialog">
          <div className="ds-dialog" role="dialog" aria-labelledby="timeline-generator-overflow-title">
            <h2 id="timeline-generator-overflow-title" className="ds-dialog__title">
              Trim this scene?
            </h2>
            <p className="ds-dialog__body">
              The new engine cannot keep clips past its longest run. Trim this scene to that length, or cancel and
              keep everything as it is.
            </p>
            <div className="ds-dialog__actions">
              <button type="button" className="ghost" onClick={() => setPendingId(null)}>
                Cancel
              </button>
              <button type="button" className="primary" onClick={() => void applyGenerator(pendingId, true)}>
                Trim to Scene
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
