import { useEffect, useMemo, useState } from "react";
import { api } from "../../api";
import type { Scene } from "../../types";
import type {
  BatchBlock,
  InPaintStrategy,
  RepairRange,
  SceneTimelineMaster,
} from "../../timelineMaster/contracts";
import { useDirectorSelection } from "../DirectorSelectionContext";
import type { DirectorTimeline, TimelineClip } from "../DirectorTracks";
import { Drawer } from "../ui/Drawer";
import { formatTimelineTime } from "./TimelineSettingsDrawer";

type GeneratorCapability = {
  id: string;
  label: string;
  executable?: boolean;
  capabilityLabel?: string;
  inPaintStrategies?: string[];
  notes?: string | null;
};

type BatchWindow = {
  batch: BatchBlock;
  start: number;
  length: number;
};

type InpaintDraft = {
  prompt?: string;
  maskType?: string;
  feather?: number;
  generatorId?: string | null;
  requestedStrategy?: InPaintStrategy;
  resolvedStrategy?: InPaintStrategy;
  strategyDisclosure?: {
    strategy: InPaintStrategy;
    requested: InPaintStrategy;
    disclosed: boolean;
    message?: string;
  };
  preservationLocks?: {
    preserveAudio?: boolean;
    preserveMotion?: boolean;
    preserveComposition?: boolean;
  };
  mask?: {
    activeTool?: string;
    revision?: number;
    strokes?: Array<{ id: string; tool: string; at: number; x: number; y: number }>;
  };
};

type WorkspaceTarget = {
  sourceKind: "videoClip" | "repair";
  batch: BatchBlock;
  batchWindow: BatchWindow;
  repair: RepairRange | null;
  clip: TimelineClip | null;
  absoluteStart: number;
  length: number;
  relativeStart: number;
  note: string | null;
};

const MASK_TYPES = [
  { value: "include", label: "Painted fix" },
  { value: "exclude", label: "Protected holdout" },
  { value: "replace", label: "Replace region" },
] as const;

const STRATEGY_OPTIONS: Array<{ value: InPaintStrategy; label: string }> = [
  { value: "native", label: "Native" },
  { value: "range_replacement", label: "Range Replacement" },
  { value: "keyframe_repair", label: "Keyframe Repair" },
  { value: "frame_repair_propagation", label: "Frame Repair Propagation" },
  { value: "complete_batch_retake", label: "Complete Batch Retake" },
];

const TOOL_OPTIONS = ["brush", "erase"] as const;

function generatorFromSceneEngine(engine: Scene["engine"]): string | null {
  if (engine === "ltx") return "ltx-local";
  if (engine === "hunyuan15") return "hunyuan-video-1.5-local";
  if (engine === "hunyuan13b") return "hunyuan-video-13b-local";
  if (engine === "wan") return "wan-local";
  if (engine === "fal_seedance") return "seedance-kie";
  if (engine === "fal_kling") return "kling-fal";
  return null;
}

function buildBatchWindows(master: SceneTimelineMaster | null): BatchWindow[] {
  return (master?.batchBlocks || [])
    .slice()
    .sort((a, b) => a.order - b.order)
    .map((batch, index, items) => {
      const start = items
        .slice(0, index)
        .reduce((sum, item) => sum + Math.max(0.1, item.duration.plannedDuration || 0), 0);
      return {
        batch,
        start,
        length: Math.max(0.1, batch.duration.plannedDuration || 0),
      };
    });
}

function parseDraft(repair: RepairRange | null): InpaintDraft {
  const raw = repair?.metadata;
  if (!raw || typeof raw !== "object") return {};
  const inpaint = (raw as Record<string, unknown>).inpaint;
  if (!inpaint || typeof inpaint !== "object") return {};
  return inpaint as InpaintDraft;
}

function resolveDisclosure(
  generatorId: string | null,
  requested: InPaintStrategy,
  generators: GeneratorCapability[],
): { strategy: InPaintStrategy; requested: InPaintStrategy; disclosed: boolean; message?: string } {
  if (requested === "native") {
    return {
      requested,
      strategy: "range_replacement",
      disclosed: true,
      message: "Native video Inpaint is not certified. This repair will use Range Replacement.",
    };
  }
  const generator = generators.find((item) => item.id === generatorId);
  const supported = Array.isArray(generator?.inPaintStrategies) && generator.inPaintStrategies.length
    ? (generator.inPaintStrategies as InPaintStrategy[])
    : (["complete_batch_retake"] as InPaintStrategy[]);
  if (!supported.includes(requested)) {
    return {
      requested,
      strategy: supported[0],
      disclosed: true,
      message: `${requested.replace(/_/g, " ")} is not supported by this generator. This repair will use ${supported[0].replace(/_/g, " ")}.`,
    };
  }
  return { requested, strategy: requested, disclosed: true };
}

function makeRepairLabel(batch: BatchBlock, start: number, length: number) {
  return `${batch.label} Inpaint ${start.toFixed(1)}-${(start + length).toFixed(1)}s`;
}

function resolveWorkspaceTarget(
  master: SceneTimelineMaster | null,
  timeline: DirectorTimeline | null,
  selection: { kind: string | null; id?: string },
  playheadSec: number,
): WorkspaceTarget | null {
  const batchWindows = buildBatchWindows(master);
  if (selection.kind === "repair" && selection.id) {
    for (const window of batchWindows) {
      const repair = (window.batch.repairRanges || []).find((entry) => entry.id === selection.id);
      if (!repair) continue;
      return {
        sourceKind: "repair",
        batch: window.batch,
        batchWindow: window,
        repair,
        clip: null,
        absoluteStart: window.start + repair.start,
        length: repair.length,
        relativeStart: repair.start,
        note: null,
      };
    }
    return null;
  }
  if (selection.kind !== "videoClip" || !selection.id || !timeline) return null;
  const clip = (timeline.video_clips || []).find((entry) => entry.id === selection.id);
  if (!clip) return null;
  const clipStart = Math.max(0, clip.start || 0);
  const clipEnd = clipStart + Math.max(0.1, clip.length || 0);
  const byPlayhead =
    batchWindows.find((window) => playheadSec >= window.start && playheadSec <= window.start + window.length) ||
    null;
  const overlapping = batchWindows.find((window) => window.start < clipEnd && window.start + window.length > clipStart) || null;
  const fallback = batchWindows.length === 1 ? batchWindows[0] : null;
  const batchWindow = byPlayhead || overlapping || fallback;
  if (!batchWindow) {
    return {
      sourceKind: "videoClip",
      batch: {
        id: "",
        sceneId: "",
        order: 0,
        label: "No batch selected",
        status: "Draft",
        generatorOverride: false,
        duration: { plannedDuration: Math.max(0.1, clip.length || 0) },
        sourceAnchors: [],
        promptSegments: [],
        visualClips: [],
        audioClips: [],
        sfxClips: [],
        cameraInstructions: [],
        generationJobs: [],
        candidateVersions: [],
        repairRanges: [],
        references: [],
        createdAt: "",
        updatedAt: "",
        legacyImageClipIds: [],
      },
      batchWindow: {
        batch: {
          id: "",
          sceneId: "",
          order: 0,
          label: "No batch selected",
          status: "Draft",
          generatorOverride: false,
          duration: { plannedDuration: Math.max(0.1, clip.length || 0) },
          sourceAnchors: [],
          promptSegments: [],
          visualClips: [],
          audioClips: [],
          sfxClips: [],
          cameraInstructions: [],
          generationJobs: [],
          candidateVersions: [],
          repairRanges: [],
          references: [],
          createdAt: "",
          updatedAt: "",
          legacyImageClipIds: [],
        },
        start: clipStart,
        length: Math.max(0.1, clip.length || 0),
      },
      repair: null,
      clip,
      absoluteStart: clipStart,
      length: Math.max(0.1, clip.length || 0),
      relativeStart: 0,
      note: "Add a Batch to the timeline before creating an inpaint repair range.",
    };
  }
  const absoluteStart = Math.max(clipStart, batchWindow.start);
  const absoluteEnd = Math.min(clipEnd, batchWindow.start + batchWindow.length);
  const length = Math.max(0.1, absoluteEnd - absoluteStart);
  return {
    sourceKind: "videoClip",
    batch: batchWindow.batch,
    batchWindow,
    repair: null,
    clip,
    absoluteStart,
    length,
    relativeStart: Math.max(0, absoluteStart - batchWindow.start),
    note:
      batchWindows.length > 1
        ? `Using ${batchWindow.batch.label} at the current playhead for this inpaint range.`
        : null,
  };
}

export function TimelineInpaintWorkspace({
  open,
  projectId,
  scene,
  master,
  playheadSec,
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
  const { selection } = useDirectorSelection();
  const [timeline, setTimeline] = useState<DirectorTimeline | null>(null);
  const [generators, setGenerators] = useState<GeneratorCapability[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [prompt, setPrompt] = useState("");
  const [maskType, setMaskType] = useState<(typeof MASK_TYPES)[number]["value"]>("include");
  const [feather, setFeather] = useState(8);
  const [generatorId, setGeneratorId] = useState<string>("");
  const [requestedStrategy, setRequestedStrategy] = useState<InPaintStrategy>("range_replacement");
  const [preserveAudio, setPreserveAudio] = useState(true);
  const [preserveMotion, setPreserveMotion] = useState(true);
  const [preserveComposition, setPreserveComposition] = useState(true);
  const [activeTool, setActiveTool] = useState<(typeof TOOL_OPTIONS)[number]>("brush");
  const [maskStrokes, setMaskStrokes] = useState<Array<{ id: string; tool: string; at: number; x: number; y: number }>>([]);
  const [maskRevision, setMaskRevision] = useState(0);
  const [savedRepairId, setSavedRepairId] = useState<string | null>(null);
  const [scrubberSec, setScrubberSec] = useState(0);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    setMessage(null);
    Promise.all([
      api.getDirector(projectId, scene.id),
      api.directorTimelineGenerators().catch(() => ({ generators: [] })),
    ])
      .then(([director, generatorPayload]) => {
        if (cancelled) return;
        setTimeline(director as DirectorTimeline);
        const items = Array.isArray((generatorPayload as { generators?: unknown[] }).generators)
          ? ((generatorPayload as { generators?: GeneratorCapability[] }).generators || [])
          : [];
        setGenerators(items);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setMessage(error instanceof Error ? error.message : "Unable to open Inpaint workspace.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, projectId, scene.id]);

  const target = useMemo(
    () => resolveWorkspaceTarget(master, timeline, selection, playheadSec),
    [master, playheadSec, selection, timeline],
  );

  const disclosure = useMemo(
    () => resolveDisclosure(generatorId || null, requestedStrategy, generators),
    [generatorId, generators, requestedStrategy],
  );

  useEffect(() => {
    if (!open || !target) return;
    const draft = parseDraft(target.repair);
    const defaultGenerator =
      draft.generatorId || target.batch.generatorId || master?.sceneGeneratorId || generatorFromSceneEngine(scene.engine) || "";
    const defaultRequested = draft.requestedStrategy || target.repair?.inPaintStrategy || "range_replacement";
    setPrompt(draft.prompt || "");
    setMaskType((draft.maskType as (typeof MASK_TYPES)[number]["value"]) || "include");
    setFeather(typeof draft.feather === "number" ? draft.feather : 8);
    setGeneratorId(defaultGenerator);
    setRequestedStrategy(defaultRequested);
    setPreserveAudio(draft.preservationLocks?.preserveAudio ?? true);
    setPreserveMotion(draft.preservationLocks?.preserveMotion ?? true);
    setPreserveComposition(draft.preservationLocks?.preserveComposition ?? true);
    setActiveTool((draft.mask?.activeTool as (typeof TOOL_OPTIONS)[number]) || "brush");
    setMaskStrokes(draft.mask?.strokes || []);
    setMaskRevision(draft.mask?.revision || 0);
    setSavedRepairId(target.repair?.id || null);
    setScrubberSec(target.absoluteStart);
  }, [master?.sceneGeneratorId, open, scene.engine, target]);

  const rangeLabel = target
    ? `${formatTimelineTime(target.absoluteStart, "timecode")} - ${formatTimelineTime(
        target.absoluteStart + target.length,
        "timecode",
      )}`
    : "No range selected";

  const generatorLabel =
    generators.find((item) => item.id === generatorId)?.label || (generatorId ? generatorId : "Auto");
  const canPersist = Boolean(target && target.batch.id);

  const addStroke = () => {
    if (!target) return;
    const nextRevision = maskRevision + 1;
    setMaskRevision(nextRevision);
    setMaskStrokes((items) => [
      ...items,
      {
        id: `stroke-${Date.now()}-${items.length}`,
        tool: activeTool,
        at: scrubberSec,
        x: Number((((items.length % 5) + 1) / 6).toFixed(3)),
        y: Number((((items.length % 4) + 1) / 5).toFixed(3)),
      },
    ]);
  };

  const clearMask = () => {
    setMaskRevision((value) => value + 1);
    setMaskStrokes([]);
  };

  const persistRepair = async () => {
    if (!target) throw new Error("Select a Video clip or Repair range first.");
    if (!target.batch.id) throw new Error("Add a Batch before creating an Inpaint repair range.");

    const label = target.repair?.label || makeRepairLabel(target.batch, target.absoluteStart, target.length);
    let repairId = savedRepairId || target.repair?.id || null;

    if (!repairId) {
      await api.directorTimelineAddRepair(projectId, scene.id, target.batch.id, {
        start: target.relativeStart,
        length: target.length,
        label,
        inPaintStrategy: requestedStrategy,
      });
    }

    const afterAdd = await api.directorTimelineMaster(projectId, scene.id);
    const nextMaster = afterAdd.master as SceneTimelineMaster;
    const nextBatch = nextMaster.batchBlocks.find((item) => item.id === target.batch.id);
    if (!nextBatch) throw new Error("The target batch disappeared while saving this repair range.");

    if (!repairId) {
      repairId =
        nextBatch.repairRanges.find(
          (entry) =>
            Math.abs(entry.start - target.relativeStart) < 0.001 &&
            Math.abs(entry.length - target.length) < 0.001,
        )?.id ||
        nextBatch.repairRanges[nextBatch.repairRanges.length - 1]?.id ||
        null;
    }
    if (!repairId) throw new Error("Unable to resolve the saved repair range.");

    const metadata = {
      inpaint: {
        prompt: prompt.trim(),
        maskType,
        feather,
        generatorId: generatorId || null,
        requestedStrategy,
        resolvedStrategy: disclosure.strategy,
        strategyDisclosure: disclosure,
        preservationLocks: {
          preserveAudio,
          preserveMotion,
          preserveComposition,
        },
        mask: {
          activeTool,
          revision: maskRevision,
          strokes: maskStrokes,
        },
        selectionSource: target.sourceKind,
        range: {
          start: target.absoluteStart,
          length: target.length,
          relativeStart: target.relativeStart,
        },
        updatedAt: new Date().toISOString(),
      },
    };

    await api.directorTimelinePatchBatch(projectId, scene.id, nextBatch.id, {
      ...(generatorId ? { generatorId } : {}),
      repairRanges: nextBatch.repairRanges.map((entry) =>
        entry.id === repairId
          ? {
              ...entry,
              label,
              inPaintStrategy: requestedStrategy,
              metadata,
            }
          : entry,
      ),
    });

    const finalMaster = await api.directorTimelineMaster(projectId, scene.id);
    const finalBatch = (finalMaster.master as SceneTimelineMaster).batchBlocks.find((item) => item.id === nextBatch.id);
    const finalRepair = finalBatch?.repairRanges.find((entry) => entry.id === repairId) || null;
    setSavedRepairId(finalRepair?.id || repairId);
    await onRefresh();
    return {
      batchId: nextBatch.id,
      batchLabel: nextBatch.label,
      repairId,
      resolvedStrategy: finalRepair?.inPaintStrategy || disclosure.strategy,
    };
  };

  const handlePreview = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const saved = await persistRepair();
      setMessage(
        `Saved inpaint setup on ${saved.batchLabel}. No dedicated timeline preview endpoint is available yet, so Preview persists the repair range and mask state.`,
      );
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : "Preview save failed.");
    } finally {
      setBusy(false);
    }
  };

  const handleGenerate = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const saved = await persistRepair();
      await api.directorTimelineGenerateBatch(projectId, scene.id, saved.batchId);
      await onRefresh();
      setMessage(`Queued candidate generation for ${saved.batchLabel} using ${saved.resolvedStrategy.replace(/_/g, " ")}.`);
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : "Generate Candidates failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title="Video Inpaint"
      side="right"
      testId="timeline-inpaint-workspace"
    >
      <div className="timeline-inpaint-workspace">
        <div className="timeline-inpaint-workspace__header">
          <div>
            <div className="timeline-inspector__eyebrow">Video Finishing</div>
            <strong>{rangeLabel}</strong>
            <p className="scene-meta">
              {target ? `${target.batch.label} · ${generatorLabel}` : "Select a Video clip or Repair range."}
            </p>
          </div>
          {target?.note ? <p className="scene-meta">{target.note}</p> : null}
        </div>

        <div className="timeline-inpaint-workspace__tools" role="toolbar" aria-label="Inpaint tools">
          {TOOL_OPTIONS.map((tool) => (
            <button
              key={tool}
              type="button"
              className={activeTool === tool ? "primary" : "ghost"}
              onClick={() => setActiveTool(tool)}
            >
              {tool === "brush" ? "Brush" : "Erase"}
            </button>
          ))}
          <button type="button" onClick={addStroke} disabled={!canPersist}>
            {activeTool === "brush" ? "Paint Mark" : "Erase Mark"}
          </button>
          <button type="button" className="ghost" onClick={clearMask} disabled={maskStrokes.length === 0}>
            Clear
          </button>
        </div>

        <button
          type="button"
          className="timeline-inpaint-workspace__canvas"
          onClick={addStroke}
          disabled={!canPersist}
          title="Canvas placeholder for mask overlay"
        >
          <div className="timeline-inpaint-workspace__canvas-title">Mask Overlay</div>
          <div className="timeline-inpaint-workspace__canvas-body">
            <div className="timeline-inpaint-workspace__canvas-grid" />
            {maskStrokes.length === 0 ? (
              <span className="scene-meta">Click here or use Paint Mark to add mask strokes.</span>
            ) : (
              maskStrokes.slice(-12).map((stroke) => (
                <span
                  key={stroke.id}
                  className={`timeline-inpaint-workspace__stroke timeline-inpaint-workspace__stroke--${stroke.tool}`}
                  style={{ left: `${stroke.x * 100}%`, top: `${stroke.y * 100}%` }}
                />
              ))
            )}
          </div>
        </button>

        <label className="field">
          <span>Scrubber</span>
          <input
            type="range"
            min={target?.absoluteStart ?? 0}
            max={target ? target.absoluteStart + target.length : 1}
            step={0.01}
            value={scrubberSec}
            disabled={!canPersist}
            onChange={(e) => setScrubberSec(Number(e.target.value))}
          />
          <span className="scene-meta">{formatTimelineTime(scrubberSec, "timecode")}</span>
        </label>

        <div className="timeline-inpaint-workspace__inspector">
          <label className="field">
            <span>Prompt</span>
            <textarea
              value={prompt}
              placeholder="Describe what should be repaired inside the selected range."
              onChange={(e) => setPrompt(e.target.value)}
            />
          </label>

          <label className="field">
            <span>Mask Type</span>
            <select value={maskType} onChange={(e) => setMaskType(e.target.value as (typeof MASK_TYPES)[number]["value"])}>
              {MASK_TYPES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>Feather</span>
            <input
              type="range"
              min={0}
              max={64}
              step={1}
              value={feather}
              onChange={(e) => setFeather(Number(e.target.value))}
            />
            <span className="scene-meta">{feather}px</span>
          </label>

          <div className="timeline-inpaint-workspace__checks">
            <label>
              <input type="checkbox" checked={preserveAudio} onChange={(e) => setPreserveAudio(e.target.checked)} />
              Preserve Audio
            </label>
            <label>
              <input type="checkbox" checked={preserveMotion} onChange={(e) => setPreserveMotion(e.target.checked)} />
              Preserve Motion
            </label>
            <label>
              <input
                type="checkbox"
                checked={preserveComposition}
                onChange={(e) => setPreserveComposition(e.target.checked)}
              />
              Preserve Composition
            </label>
          </div>

          <label className="field">
            <span>Strategy</span>
            <select
              value={requestedStrategy}
              onChange={(e) => setRequestedStrategy(e.target.value as InPaintStrategy)}
            >
              {STRATEGY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <div className="timeline-inpaint-workspace__strategy">
            <strong>Strategy Disclosure</strong>
            <p className="scene-meta">
              Requested: {requestedStrategy.replace(/_/g, " ")}
            </p>
            <p className="scene-meta">
              Executed as: {disclosure.strategy.replace(/_/g, " ")}
            </p>
            {disclosure.message ? <p className="scene-meta">{disclosure.message}</p> : null}
          </div>

          <label className="field">
            <span>Generator</span>
            <select value={generatorId} onChange={(e) => setGeneratorId(e.target.value)}>
              <option value="">Use batch generator</option>
              {generators.map((generator) => (
                <option key={generator.id} value={generator.id}>
                  {generator.label}
                  {generator.capabilityLabel ? ` · ${generator.capabilityLabel}` : ""}
                </option>
              ))}
            </select>
          </label>
        </div>

        {loading ? <p className="scene-meta">Loading inpaint context…</p> : null}
        {message ? <p className="scene-meta">{message}</p> : null}

        <div className="timeline-inpaint-workspace__actions">
          <button type="button" className="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button type="button" onClick={() => void handlePreview()} disabled={busy || !canPersist}>
            Preview
          </button>
          <button type="button" className="primary" onClick={() => void handleGenerate()} disabled={busy || !canPersist}>
            Generate Candidates
          </button>
        </div>
      </div>
    </Drawer>
  );
}
