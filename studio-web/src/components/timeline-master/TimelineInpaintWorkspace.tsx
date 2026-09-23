import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../api";
import type { Scene } from "../../types";
import type { BatchBlock, RepairRange, SceneTimelineMaster } from "../../timelineMaster/contracts";
import { pollJob } from "../../utils/pollJob";
import { useDirectorSelection } from "../DirectorSelectionContext";
import { ImageMaskEditor, type ImageMaskEditorHandle, type MaskTool } from "../imageEdit/ImageMaskEditor";
import { Drawer } from "../ui/Drawer";
import { formatTimelineTime } from "./TimelineSettingsDrawer";

type WorkspaceTarget = {
  batch: BatchBlock;
  repair: RepairRange;
  absoluteStart: number;
  length: number;
  relativeStart: number;
};

function jobAssetId(job: { params_json?: string; history_json?: string } | null): string | null {
  if (!job) return null;
  try {
    const params = JSON.parse(job.params_json || "{}") as Record<string, unknown>;
    if (typeof params.output_asset_id === "string" && params.output_asset_id) return params.output_asset_id;
  } catch {
    /* ignore */
  }
  try {
    const hist = JSON.parse(job.history_json || "{}") as Record<string, unknown>;
    if (typeof hist.assetId === "string" && hist.assetId) return hist.assetId;
  } catch {
    /* ignore */
  }
  return null;
}

function resolveRepairTarget(
  master: SceneTimelineMaster | null,
  selection: { kind: string | null; id?: string },
): WorkspaceTarget | null {
  if (selection.kind !== "repair" || !selection.id || !master) return null;
  let cursor = 0;
  const batches = (master.batchBlocks || []).slice().sort((a, b) => a.order - b.order);
  for (const batch of batches) {
    const length = Math.max(0.1, batch.duration.plannedDuration || 0);
    const repair = (batch.repairRanges || []).find((entry) => entry.id === selection.id);
    if (repair) {
      return {
        batch,
        repair,
        absoluteStart: cursor + repair.start,
        length: repair.length,
        relativeStart: repair.start,
      };
    }
    cursor += length;
  }
  return null;
}

export function TimelineInpaintWorkspace({
  open,
  projectId,
  scene,
  master,
  playheadSec: _playheadSec,
  onClose,
  onRefresh,
}: {
  open: boolean;
  projectId: string;
  scene: Scene;
  master: SceneTimelineMaster | null;
  playheadSec: number;
  onClose: () => void;
  onRefresh: () => Promise<void>;
}) {
  void _playheadSec;
  const { selection } = useDirectorSelection();
  const maskRef = useRef<ImageMaskEditorHandle | null>(null);
  const pollStopRef = useRef<(() => void) | null>(null);
  const [busy, setBusy] = useState(false);
  const [loadingFrame, setLoadingFrame] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [prompt, setPrompt] = useState("");
  const [tool, setTool] = useState<MaskTool>("brush");
  const [brushSize, setBrushSize] = useState(28);
  const [hasMask, setHasMask] = useState(false);
  const [frameAssetId, setFrameAssetId] = useState<string | null>(null);
  const [atSeconds, setAtSeconds] = useState(0);
  const [previewAssetId, setPreviewAssetId] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string | null>(null);

  const target = useMemo(() => resolveRepairTarget(master, selection), [master, selection]);

  useEffect(() => {
    return () => {
      pollStopRef.current?.();
    };
  }, []);

  useEffect(() => {
    if (!open || !target) return;
    let cancelled = false;
    setMessage(null);
    setPreviewAssetId(null);
    setJobId(null);
    setJobStatus(null);
    setHasMask(false);
    setPrompt("");
    maskRef.current?.clear();
    setLoadingFrame(true);
    api
      .directorTimelineExtractRepairFrame(projectId, scene.id, target.batch.id, target.repair.id, {
        atSeconds: target.relativeStart + Math.min(0.15, target.length / 2),
      })
      .then((result) => {
        if (cancelled) return;
        if (result.ok === false) {
          setMessage(String(result.message || result.error || "Could not open this range."));
          setFrameAssetId(null);
          return;
        }
        setFrameAssetId(typeof result.frameAssetId === "string" ? result.frameAssetId : null);
        setAtSeconds(typeof result.atSeconds === "number" ? result.atSeconds : target.relativeStart);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setMessage(error instanceof Error ? error.message : "Could not open this range.");
        setFrameAssetId(null);
      })
      .finally(() => {
        if (!cancelled) setLoadingFrame(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, projectId, scene.id, target?.batch.id, target?.repair.id, target?.relativeStart, target?.length]);

  const rangeLabel = target
    ? `${formatTimelineTime(target.absoluteStart, "timecode")} – ${formatTimelineTime(
        target.absoluteStart + target.length,
        "timecode",
      )}`
    : "No range selected";

  const canPaint = Boolean(target && frameAssetId && !busy);
  const canPreview = Boolean(canPaint && hasMask && prompt.trim());
  const canApply = Boolean(target && (previewAssetId || jobId) && !busy);

  const handlePreview = async () => {
    if (!target) return;
    const maskPngBase64 = (await maskRef.current?.exportPng()) || "";
    if (!maskPngBase64) {
      setMessage("Paint the area that needs repair first.");
      return;
    }
    if (!prompt.trim()) {
      setMessage("Write what should change in the painted area.");
      return;
    }
    setBusy(true);
    setMessage(null);
    setPreviewAssetId(null);
    pollStopRef.current?.();
    try {
      const submitted = await api.directorTimelineSubmitInpaint(projectId, scene.id, target.batch.id, target.repair.id, {
        prompt: prompt.trim(),
        maskPngBase64,
        atSeconds,
        frameAssetId: frameAssetId || undefined,
      });
      if (submitted.ok === false) {
        setMessage(String(submitted.message || submitted.error || "Preview could not start."));
        setBusy(false);
        return;
      }
      const nextJobId = typeof submitted.jobId === "string" ? submitted.jobId : null;
      if (!nextJobId) {
        setMessage("The repair job did not start.");
        setBusy(false);
        return;
      }
      setJobId(nextJobId);
      setJobStatus("queued");
      setMessage("Painting the repair…");
      pollStopRef.current = pollJob(nextJobId, {
        getJob: api.getJob,
        intervalMs: 1500,
        onUpdate: (job) => setJobStatus(job.status),
        onTerminal: (job, status) => {
          if (status === "done" || status === "completed") {
            const assetId = jobAssetId(job);
            setPreviewAssetId(assetId);
            setMessage(assetId ? "Preview ready. Apply to keep it on this range, or Cancel to leave the shot as it is." : "Preview finished, but no picture was saved.");
          } else {
            setMessage(job.message || "The painted repair did not finish.");
          }
          setBusy(false);
        },
      });
      return;
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : "Preview could not start.");
    }
    setBusy(false);
  };

  const handleApply = async () => {
    if (!target) return;
    if (!previewAssetId && !jobId) {
      await handlePreview();
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      const applied = await api.directorTimelineApplyInpaint(projectId, scene.id, target.batch.id, target.repair.id, {
        jobId: jobId || undefined,
        repairedAssetId: previewAssetId || undefined,
      });
      if (applied.ok === false) {
        setMessage(String(applied.message || applied.error || "Could not apply this repair."));
        return;
      }
      await onRefresh();
      setMessage("Repair ready as a new take. The rest of the shot is unchanged.");
      onClose();
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : "Could not apply this repair.");
    } finally {
      setBusy(false);
    }
  };

  const frameUrl = frameAssetId ? api.assetUrl(frameAssetId) : "";
  const previewUrl = previewAssetId ? api.assetUrl(previewAssetId) : "";

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title="Repair this part"
      side="right"
      testId="timeline-inpaint-workspace"
    >
      <div className="timeline-inpaint-workspace">
        <div className="timeline-inpaint-workspace__header">
          <div className="timeline-inspector__eyebrow">Video Finishing</div>
          <strong>{rangeLabel}</strong>
          <p className="scene-meta">
            {target ? `${target.batch.label} · painted repair on this range only` : "Select a Mask/Repair range first."}
          </p>
          <p className="scene-meta" data-testid="timeline-inpaint-native-disclosure">
            Native video inpaint is unavailable. Adept repairs the painted area on this frame and applies that repair only to the selected time range.
          </p>
        </div>

        <div className="timeline-inpaint-workspace__tools" role="toolbar" aria-label="Repair tools">
          {(["brush", "erase"] as const).map((item) => (
            <button
              key={item}
              type="button"
              className={tool === item ? "primary" : "ghost"}
              onClick={() => setTool(item)}
            >
              {item === "brush" ? "Brush" : "Erase"}
            </button>
          ))}
          <label className="scene-meta">
            Size
            <input
              type="range"
              min={8}
              max={72}
              value={brushSize}
              onChange={(e) => setBrushSize(Number(e.target.value))}
            />
          </label>
          <button
            type="button"
            className="ghost"
            onClick={() => {
              maskRef.current?.clear();
              setHasMask(false);
            }}
            disabled={!hasMask}
          >
            Clear
          </button>
        </div>

        <div className="timeline-inpaint-workspace__canvas" data-testid="timeline-inpaint-canvas">
          <div className="timeline-inpaint-workspace__canvas-title">Paint the problem</div>
          {loadingFrame ? <p className="scene-meta">Loading the picture to paint on…</p> : null}
          {frameUrl ? (
            <ImageMaskEditor
              ref={maskRef}
              imageUrl={previewUrl || frameUrl}
              hideChrome
              fill
              tool={tool}
              brushSize={brushSize}
              feather={6}
              interactive={canPaint && !previewAssetId}
              onChange={setHasMask}
            />
          ) : (
            <p className="scene-meta">{message || "Select a Mask/Repair range with an approved take."}</p>
          )}
        </div>

        <label className="field">
          <span>What should change</span>
          <textarea
            value={prompt}
            placeholder="Example: remove the extra hand, keep the corridor wall clean"
            onChange={(e) => setPrompt(e.target.value)}
            data-testid="timeline-inpaint-prompt"
          />
        </label>

        {jobStatus ? <p className="scene-meta">Repair: {jobStatus}</p> : null}
        {message ? <p className="scene-meta" data-testid="timeline-inpaint-message">{message}</p> : null}

        <div className="timeline-inpaint-workspace__actions">
          <button type="button" className="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button type="button" onClick={() => void handlePreview()} disabled={!canPreview}>
            Preview
          </button>
          <button type="button" className="primary" onClick={() => void handleApply()} disabled={!canApply && !canPreview}>
            Apply
          </button>
        </div>
      </div>
    </Drawer>
  );
}
