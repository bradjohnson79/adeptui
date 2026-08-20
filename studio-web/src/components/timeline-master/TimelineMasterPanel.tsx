import { useCallback, useEffect, useState } from "react";
import { api } from "../../api";
import { formatDurationSeconds } from "../../lib/formatDuration";
import type { BatchBlock, BatchStatus, ModalityMode, SceneTimelineMaster } from "../../timelineMaster/contracts";
import { formatBatchStatus } from "../../timelineMaster/contracts";
import { timelineActionError } from "../../timelineMaster/timelineErrors";
import { getTimelineHelp } from "../../timelineMaster/helpCatalog";
import { HelpTip } from "../HelpTip";
import { MiniMaxH3PlanPanel } from "../minimax-h3/MiniMaxH3PlanPanel";
import { TimelineRetakeDrawer } from "./TimelineRetakeDrawer";
import { useDirectorSelection } from "../DirectorSelectionContext";
import "../../styles/timeline-master/timeline-master.css";

function statusHint(status: BatchStatus): string {
  return formatBatchStatus(status);
}

function HelpBtn({ id }: { id: string }) {
  const h = getTimelineHelp(id);
  return <HelpTip label={h.title} content={h.body} text={h.title} />;
}

export function TimelineMasterPanel({
  projectId,
  sceneId,
}: {
  projectId: string;
  sceneId: string;
}) {
  const [master, setMaster] = useState<SceneTimelineMaster | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [findings, setFindings] = useState<Array<{ severity: string; message: string }>>([]);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [retakeOpen, setRetakeOpen] = useState(false);
  const { selection } = useDirectorSelection();
  const shotId = `scene-${sceneId}-shot-1`;

  const refresh = useCallback(async () => {
    if (!projectId || !sceneId) return;
    setError(null);
    try {
      const data = await api.directorTimelineMaster(projectId, sceneId);
      setMaster(data.master as SceneTimelineMaster);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [projectId, sceneId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  if (!projectId || !sceneId) {
    return <p className="production-dock-muted">Select a scene to manage Batch Blocks.</p>;
  }

  const batches = master?.batchBlocks ?? [];

  return (
    <section className="timeline-master-panel" data-testid="timeline-master-panel" aria-label="Timeline Master">
      <header className="timeline-master-panel__header">
        <div>
          <h3>Timeline Master</h3>
          <p>Scene mode, generation status, and Batch inspector. Add Batch and Preflight live in the top toolbar.</p>
        </div>
        <div className="timeline-master-panel__modes" role="group" aria-label="Timeline mode">
          {(["image_planning", "video_finishing"] as ModalityMode[]).map((mode) => (
            <button
              key={mode}
              type="button"
              className={master?.mode === mode ? "primary" : ""}
              disabled={busy}
              data-testid={`timeline-master-mode-${mode}`}
              onClick={() =>
                void run(async () => {
                  await api.directorTimelineSetMode(projectId, sceneId, mode);
                  setMessage(`Mode: ${mode.replace("_", " ")} (Batch state preserved).`);
                })
              }
            >
              {mode === "image_planning" ? "Image Planning" : "Video Finishing"}
            </button>
          ))}
        </div>
      </header>

      <MiniMaxH3PlanPanel
        projectId={projectId}
        prompt="Timeline segment generation with MiniMax H3."
        mode="text-to-video"
        sourceSurface="timeline"
        sceneId={sceneId}
        durationSec={5}
      />

      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", margin: "0.75rem 0" }}>
        <button
          type="button"
          className="primary"
          data-testid="timeline-open-retake"
          aria-label="Open Re-take"
          onClick={() => setRetakeOpen(true)}
        >
          Re-take
        </button>
        <span className="production-dock-muted">
          Continuity variation on the selected shot — MiniMax H3 Route A (never silent LTX).
        </span>
      </div>

      <TimelineRetakeDrawer
        projectId={projectId}
        sceneId={sceneId}
        shotId={shotId}
        open={retakeOpen}
        onClose={() => setRetakeOpen(false)}
        baselinePrompt="A glowing glass bottle on a dark studio table, slow cinematic push-in, subtle condensation, controlled rim lighting."
      />

      <div className="timeline-master-panel__toolbar" data-testid="timeline-master-scene-actions">
        <span className="scene-meta">Scene Actions</span>
        <button
          type="button"
          disabled={busy || !(selection?.kind === "batch" && selection.id)}
          title={
            selection?.kind === "batch" && selection.id
              ? "Generate only the selected batch"
              : "Select a batch on the timeline first — Generate Current runs just that one batch"
          }
          data-testid="timeline-master-generate-current"
          onClick={() =>
            void run(async () => {
              // GENERATE_CURRENT_USES_SELECTED_BATCH: only the explicitly
              // selected batch — never a silent batches[0] fallback for a
              // chargeable generation (NO_SILENT_BEHAVIOR).
              const selectedBatchId =
                selection?.kind === "batch" && selection.id ? selection.id : null;
              if (!selectedBatchId) return;
              const result = await api.directorTimelineGenerateBatch(projectId, sceneId, selectedBatchId);
              const err = timelineActionError(result);
              if (err) {
                setMessage(err);
                return;
              }
              setMessage(`Generate Current → snapshot ${String(result.executionSnapshotId || "")}`);
            })
          }
        >
          Generate Current <HelpBtn id="generate_current" />
        </button>
        <button
          type="button"
          disabled={busy || !(selection?.kind === "batch" && selection.id)}
          title={
            selection?.kind === "batch" && selection.id
              ? "Generate the selected batch through the scene queue"
              : "Select a batch on the timeline first — Generate Selected runs just that batch"
          }
          data-testid="timeline-generate-selected"
          onClick={() =>
            void run(async () => {
              // GENERATE_SELECTED_IS_SELECTION_SCOPED: pass only the selected
              // batch id — previously this passed every batch id, making it a
              // silent Generate Full Scene.
              const selectedBatchId =
                selection?.kind === "batch" && selection.id ? selection.id : null;
              if (!selectedBatchId) return;
              const result = await api.directorTimelineGenerateScene(projectId, sceneId, {
                scope: "selected",
                batchBlockIds: [selectedBatchId],
              });
              const err = timelineActionError(result);
              if (err) {
                setMessage(err);
                return;
              }
              setMessage(String(result.message || "Generate Selected submitted."));
            })
          }
        >
          Generate Selected <HelpBtn id="generate_selected" />
        </button>
        <button
          type="button"
          className="primary"
          data-testid="timeline-master-generate-scene"
          disabled={busy}
          title={busy ? "Working — please wait" : "Generate every ready batch in this scene, in order"}
          onClick={() =>
            void run(async () => {
              const result = await api.directorTimelineGenerateScene(projectId, sceneId, { scope: "full" });
              const err = timelineActionError(result);
              if (err) {
                setMessage(err);
                return;
              }
              setMessage(String(result.message || "Generate submitted."));
              setFindings((result.findings as Array<{ severity: string; message: string }>) || []);
            })
          }
        >
          Generate Full Scene <HelpBtn id="generate_full_scene" />
        </button>
        <button
          type="button"
          data-testid="timeline-master-stop-remaining"
          disabled={busy}
          title={busy ? "Working — please wait" : "Stop queued and running jobs — finished batches stay untouched"}
          onClick={() =>
            void run(async () => {
              const result = await api.directorTimelineCancel(projectId, sceneId, {
                action: "stop_remaining_scene_jobs",
              });
              setMessage(String(result.message || "Stopped remaining jobs."));
            })
          }
        >
          Stop Remaining Jobs <HelpBtn id="stop_remaining" />
        </button>
        <button
          type="button"
          data-testid="timeline-master-resume-incomplete"
          disabled={busy}
          title={busy ? "Working — please wait" : "Re-queue only cancelled or failed batches — approved batches are never regenerated"}
          onClick={() =>
            void run(async () => {
              const result = await api.directorTimelineCancel(projectId, sceneId, {
                action: "resume_incomplete_only",
              });
              setMessage(String(result.message || "Resume incomplete only."));
            })
          }
        >
          Resume Incomplete Jobs <HelpBtn id="resume_incomplete" />
        </button>
      </div>

      {message ? (
        <p className="setup-message" role="status">
          {message}
        </p>
      ) : null}
      {error ? (
        <p className="setup-message error" role="alert">
          {error}
        </p>
      ) : null}

      {findings.length > 0 ? (
        <ul className="timeline-master-findings" data-testid="timeline-master-findings">
          {findings.map((f, i) => (
            <li key={i}>
              <strong>{f.severity === "error" ? "Blocking" : f.severity === "warning" ? "Warning" : "Suggestion"}</strong>
              : {f.message}
            </li>
          ))}
        </ul>
      ) : null}

      <ul className="timeline-master-batches" data-testid="timeline-master-batches">
        {batches.map((batch: BatchBlock) => {
          const open = expanded[batch.id] ?? false;
          const promptMissing = !batch.promptSegments.some((p) => p.text.trim());
          const marker = [...(master?.temporalPackets || [])]
            .reverse()
            .find((packet) => packet.source?.batchId === batch.id)?.creatorMarker;
          return (
            <li key={batch.id} className="timeline-master-batch" data-testid={`timeline-master-batch-${batch.id}`}>
              <button
                type="button"
                className="timeline-master-batch__toggle"
                onClick={() => setExpanded((s) => ({ ...s, [batch.id]: !open }))}
              >
                <div className="timeline-master-batch__row">
                  <strong>{batch.label}</strong>
                  <span>{statusHint(batch.status)}</span>
                </div>
                <div className="timeline-master-batch__meta">
                  {formatDurationSeconds(batch.duration.plannedDuration)} · {batch.generatorId || "No generator"} ·{" "}
                  {batch.references?.length || 0} refs
                  {promptMissing ? " · Prompt missing ⚠" : ""}
                  {marker ? (
                    <span data-testid={`timeline-cd-batch-marker-${batch.id}`}> · {marker}</span>
                  ) : null}
                </div>
              </button>
              {open ? (
                <>
                  <div className="timeline-master-batch__meta">
                    Planned {formatDurationSeconds(batch.duration.plannedDuration)}
                    {batch.duration.generatedDuration != null
                      ? ` · Generated ${formatDurationSeconds(batch.duration.generatedDuration)}`
                      : ""}
                    {batch.duration.timelineVisibleDuration != null
                      ? ` · Visible ${formatDurationSeconds(batch.duration.timelineVisibleDuration)}`
                      : ""}
                  </div>
                  {batch.status === "ApprovedConfigurationChanged" ||
                  batch.status === "RegenerationRecommended" ? (
                    <p className="timeline-master-batch__warn">
                      Prior approved clip remains playable from an older execution snapshot. Regeneration
                      recommended.
                    </p>
                  ) : null}
                  <div className="timeline-master-batch__actions">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() =>
                        void run(async () => {
                          const result = await api.directorTimelineGenerateBatch(projectId, sceneId, batch.id);
                          const err = timelineActionError(result);
                          if (err) {
                            setMessage(err);
                            return;
                          }
                          setMessage(
                            `Submitted ${batch.label} → snapshot ${String(result.executionSnapshotId || "")}`,
                          );
                        })
                      }
                    >
                      Generate
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() =>
                        void run(async () => {
                          await api.directorTimelinePatchBatch(projectId, sceneId, batch.id, {
                            plannedDuration: (batch.duration.plannedDuration || 5) + 0.5,
                          });
                          setMessage(`Updated ${batch.label} duration.`);
                        })
                      }
                    >
                      Edit Duration <HelpBtn id="edit_duration" />
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() =>
                        void run(async () => {
                          await api.directorTimelineDuplicateBatch(projectId, sceneId, batch.id);
                          setMessage(`Duplicated ${batch.label}.`);
                        })
                      }
                    >
                      Duplicate
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() =>
                        void run(async () => {
                          const result = await api.directorTimelineAddRepair(projectId, sceneId, batch.id, {
                            start: 0.5,
                            length: 1,
                            label: "Repair range",
                          });
                          setMessage(String(result.message || "Repair range result."));
                        })
                      }
                    >
                      Mark Repair Range <HelpBtn id="mark_repair_range" />
                    </button>
                  </div>
                </>
              ) : null}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
