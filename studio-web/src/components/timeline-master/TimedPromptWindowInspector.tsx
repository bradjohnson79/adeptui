import { useState } from "react";
import { api } from "../../api";
import type { BatchBlock, SceneTimelineMaster } from "../../timelineMaster/contracts";
import { formatBatchStatus } from "../../timelineMaster/contracts";
import {
  promoteCopy,
  usesFastQuality,
  type TimelineGeneratorOption,
} from "../../timelineMaster/draftCapabilities";
import { timelineActionError } from "../../timelineMaster/timelineErrors";
import { HelpTip } from "../HelpTip";
import { hasGeneratedTakeForRetake } from "../../timelineMaster/retakeEligibility";

function continuityChipLabel(status: string | undefined, stale?: boolean) {
  if (stale) return "Needs update";
  if (status === "Failed") return "Match failed";
  if (status === "Waiting" || status === "Analyzing") return "Matching.";
  if (status === "Ready" || status === "Applied") return "Matched";
  return null;
}

/**
 * Migrated Batch Inspector controls bound to an execution window resolved from a Timed Prompt clip.
 * Does not restore Batch track authoring (name/duration/window prompt edits stay CD/rematerialize-owned).
 */
export function TimedPromptWindowInspector({
  projectId,
  sceneId,
  master,
  windowBatch,
  windowSpan,
  selectedGenerator,
  videoRefBlocked,
  onRefresh,
  onActionError,
}: {
  projectId: string;
  sceneId: string;
  master: SceneTimelineMaster | null;
  windowBatch: BatchBlock;
  windowSpan: { start: number; end: number };
  selectedGenerator: TimelineGeneratorOption | null | undefined;
  videoRefBlocked: boolean;
  onRefresh: () => void | Promise<void>;
  onActionError?: (message: string) => void;
}) {
  const [retakeDelta, setRetakeDelta] = useState("");
  const [rerenderBusy, setRerenderBusy] = useState(false);
  const fastQuality = usesFastQuality(selectedGenerator);
  const latest = [...(windowBatch.candidateVersions || [])].reverse()[0];
  const isDraftTake = String(latest?.takeState?.quality || "").toLowerCase() === "draft";
  const generating = windowBatch.status === "Generating";
  const canRerenderThisTake = hasGeneratedTakeForRetake(windowBatch) && !generating && !rerenderBusy;
  const canStop =
    generating &&
    (selectedGenerator?.supportsQueuedCancel || selectedGenerator?.supportsRunningCancel);
  const showTakePicker =
    (windowBatch.candidateVersions || []).length >= 1 ||
    windowBatch.status === "CandidateReady" ||
    windowBatch.status === "Failed";

  return (
    <div
      className="timeline-inspector__section"
      data-testid="timeline-timed-prompt-window-inspector"
    >
      <h4>Takes for this Timed Prompt</h4>
      <p className="scene-meta" data-testid="timeline-timed-prompt-region">
        Region {windowSpan.start.toFixed(2)}s–{windowSpan.end.toFixed(2)}s (generation association is internal).
      </p>
      <div className="scene-meta" data-testid="timeline-timed-prompt-window-status">
        Status: {formatBatchStatus(windowBatch.status)}
        {windowBatch.generatorId ? ` · ${windowBatch.generatorId}` : ""}
      </div>
      {windowBatch.downstreamStale ? (
        <p className="scene-meta" data-testid="timeline-batch-stale">
          Later parts of the scene still use an earlier take.
        </p>
      ) : null}

      {generating && canStop ? (
        <button
          type="button"
          data-testid="timeline-stop-jobs"
          onClick={() =>
            void api
              .directorTimelineCancel(projectId, sceneId, { action: "cancel_active_local_job" })
              .then(onRefresh)
          }
        >
          Stop
        </button>
      ) : null}
      {generating && !canStop ? (
        <p className="scene-meta" data-testid="timeline-cancel-unavailable">
          Provider is rendering — cancellation unavailable
        </p>
      ) : null}

      {isDraftTake && latest ? (
        <div className="timeline-inspector__row" data-testid="timeline-draft-actions">
          <button
            type="button"
            className="primary"
            data-testid="timeline-promote-final"
            disabled={videoRefBlocked}
            title={promoteCopy(selectedGenerator?.finalRequiresNewGeneration !== false, selectedGenerator)}
            onClick={() =>
              void api
                .directorTimelineGenerateBatch(projectId, sceneId, windowBatch.id, { draftMode: false })
                .then((result) => {
                  const err = timelineActionError(result);
                  if (err) onActionError?.(err);
                  void onRefresh();
                })
            }
          >
            {fastQuality ? "Generate Quality" : "Promote to Final"}
          </button>
          <button
            type="button"
            data-testid="timeline-reject-take"
            onClick={() =>
              void api
                .directorTimelineRejectTake(projectId, sceneId, windowBatch.id, latest.id)
                .then(onRefresh)
            }
          >
            Reject
          </button>
          <p className="scene-meta">
            {promoteCopy(selectedGenerator?.finalRequiresNewGeneration !== false, selectedGenerator)}
          </p>
        </div>
      ) : null}

      {(() => {
        const incoming = (master?.continuityBridges || []).find(
          (bridge) => bridge.targetBatchId === windowBatch.id && bridge.status !== "Superseded",
        );
        if (!incoming) return null;
        if (incoming.status !== "Failed") {
          return (
            <p className="scene-meta" data-testid="timeline-batch-continuity">
              Continuity: {continuityChipLabel(incoming.status) || incoming.status}
            </p>
          );
        }
        return (
          <div data-testid="timeline-batch-continuity-failed">
            <p className="scene-meta">Matching the previous shot failed.</p>
            <button
              type="button"
              onClick={() =>
                void api.directorTimelineRetryBridge(projectId, sceneId, incoming.bridgeId).then(onRefresh)
              }
            >
              Retry
            </button>
            <button
              type="button"
              className="ghost"
              onClick={() =>
                void api
                  .directorTimelineContinueWithoutBridge(projectId, sceneId, incoming.bridgeId)
                  .then(onRefresh)
              }
            >
              Continue without matching
            </button>
          </div>
        );
      })()}

      <label className="field">
        <span>What should change</span>
        <textarea
          data-testid="timeline-retake-delta-field"
          rows={2}
          value={retakeDelta}
          onChange={(e) => setRetakeDelta(e.target.value)}
          placeholder="Example: walk behind the cruiser, not in front"
        />
        <HelpTip text="Adept keeps the scene, the match from the previous shot, and the original idea. This note is only the change." />
      </label>
      {canRerenderThisTake ? (
        <button
          type="button"
          data-testid="timeline-rerender-this-take"
          disabled={rerenderBusy}
          onClick={() => {
            const length = Math.max(0.15, windowSpan.end - windowSpan.start);
            const prompt = retakeDelta.trim() || "Re-render this take";
            setRerenderBusy(true);
            void (async () => {
              try {
                const run = async (spendApiCredits: boolean) =>
                  api.directorTimelineRetakeRange(projectId, sceneId, windowBatch.id, {
                    start: 0,
                    length,
                    prompt,
                    spendApiCredits,
                    referenceFrameTime: length / 2,
                  });
                let result = await run(false);
                if (result?.error === "API_CREDIT_CONFIRMATION_REQUIRED") {
                  const ok = window.confirm(
                    String(result.message || "This Re-render uses paid credits. Continue?"),
                  );
                  if (!ok) return;
                  result = await run(true);
                }
                if (result && result.ok === false) {
                  onActionError?.(
                    timelineActionError(result) ||
                      String(result.message || result.error || "Re-render could not start."),
                  );
                  return;
                }
                await onRefresh();
              } catch (error) {
                onActionError?.(
                  error instanceof Error ? error.message : "Re-render could not start.",
                );
              } finally {
                setRerenderBusy(false);
              }
            })();
          }}
        >
          {rerenderBusy ? "Re-rendering…" : "Re-render this take"}
        </button>
      ) : null}
      <p className="scene-meta" data-testid="timeline-rerender-vs-new-take-hint">
        Re-render this take replaces the active take in place. New take creates an alternate.
      </p>
      <button
        type="button"
        data-testid="timeline-batch-retake"
        onClick={() =>
          void api
            .directorTimelineRetakeBatch(projectId, sceneId, windowBatch.id, {
              mode: "directed",
              userCorrection: { delta: retakeDelta },
            })
            .then(onRefresh)
        }
      >
        New take
      </button>

      {showTakePicker ? (
        <div className="timeline-inspector__takes" data-testid="timeline-batch-takes">
          <p className="scene-meta">Choose an alternate take for this Timed Prompt region.</p>
          {windowBatch.status === "CandidateReady" ? (
            <p className="scene-meta">Use this take to place it on the scene.</p>
          ) : null}
          {(windowBatch.candidateVersions || []).map((cand, index) => (
            <button
              key={cand.id}
              type="button"
              className={cand.approved ? "active" : "ghost"}
              data-testid={`timeline-take-${cand.id}`}
              onClick={() =>
                void api
                  .directorTimelineActivateTake(projectId, sceneId, windowBatch.id, cand.id)
                  .then(onRefresh)
              }
            >
              {cand.label || `Take ${String.fromCharCode(65 + index)}`}
              {cand.approved
                ? " (active)"
                : windowBatch.status === "CandidateReady"
                  ? " — use this take"
                  : ""}
            </button>
          ))}
        </div>
      ) : (
        <p className="scene-meta" data-testid="timeline-batch-takes-empty">
          No takes yet for this Timed Prompt. Generate the scene to create candidates.
        </p>
      )}
    </div>
  );
}
