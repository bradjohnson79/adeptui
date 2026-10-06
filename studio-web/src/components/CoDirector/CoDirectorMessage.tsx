import { useState } from "react";
import { api } from "../../api";
import { useCoDirectorSession } from "./CoDirectorSession";
import type { CoDirectorMessage as Msg, CoDirectorMessageExecution } from "./types";
import { renderAssistantMarkdown } from "./assistantMarkdown";
import { projectCreatorReply } from "./creatorFacingReply";
import GenerationQueueCard from "./GenerationQueueCard";
import SceneProductionCard from "./SceneProductionCard";
import { CoDirectorMediaCardGrid, type MediaCardItem } from "./CoDirectorMediaCardGrid";
import { capabilityActionLabel, normalizeJobStatus } from "./liveExecutionSync";
import { LibraryQuickPreviewModal, type LibraryQuickPreviewAsset } from "../library/LibraryQuickPreviewModal";
import { OPEN_CONTENT_TAB_EVENT } from "./navEntries";

const MESSAGE_TYPE_LABELS: Record<string, string> = {
  recommendation: "Recommendation",
  clarification: "Clarification",
  warning: "Warning",
  proposal: "Proposal",
  plan: "Production plan",
  answer: "Answer",
  // Workstream H — execution-aware message kinds.
  // NOTE: execution_status label is derived dynamically from the execution
  // payload status (see typeLabel logic below) — the static entry here is a
  // fallback only when no execution payload is attached.
  execution_status: "Queued",
  completion: "Complete",
  error: "Failed",
};

const CHILD_STATUS_LABELS: Record<string, string> = {
  queued: "Queued",
  preparing: "Preparing",
  running: "Working",
  preview: "Preview",
  completed: "Complete",
  failed: "Failed",
  cancelled: "Cancelled",
};

function capabilityLabel(capability: string | undefined): string {
  return capabilityActionLabel(capability, "Execution");
}

function progressPercent(progress: number | undefined, completed: number | undefined, total: number | undefined): number {
  if (typeof progress === "number" && progress > 0) return Math.round(progress * 100);
  if (typeof completed === "number" && typeof total === "number" && total > 0) {
    return Math.round((completed / total) * 100);
  }
  return 0;
}

function ExecutionSummaryCard({
  execution,
  projectId,
}: {
  execution: CoDirectorMessageExecution;
  projectId: string;
}) {
  const pct = progressPercent(execution.progress, execution.completed, execution.total);
  const completed = execution.completed ?? 0;
  const total = execution.total ?? 0;
  const status = (execution.status || "").toLowerCase();
  const isDone = status === "completed" || status === "done";
  const isFailed = status === "failed";
  const isCancelled = status === "cancelled";
  const isActive = !isDone && !isFailed && !isCancelled;
  const children = Array.isArray(execution.child_jobs) ? execution.child_jobs : [];
  const [cancelling, setCancelling] = useState(false);

  const stopThis = async () => {
    if (!projectId || !execution.execution_id || cancelling) return;
    setCancelling(true);
    try {
      await api.cancelExecution(projectId, execution.execution_id);
    } catch {
      setCancelling(false);
    }
  };

  return (
    <div className={`codirector-exec-card ${isFailed ? "is-failed" : isCancelled ? "is-cancelled" : isDone ? "is-done" : "is-running"}`}>
      <div className="codirector-exec-head">
        <span className="codirector-exec-cap">{capabilityLabel(execution.capability)}</span>
        <span className="codirector-exec-counts">
          {completed}/{total || "?"} complete
        </span>
        {isActive && projectId ? (
          <button
            type="button"
            className="ghost codirector-exec-stop"
            data-testid="codirector-exec-stop"
            onClick={() => void stopThis()}
            disabled={cancelling}
          >
            {cancelling ? "Stopping…" : "Stop this"}
          </button>
        ) : null}
      </div>
      <div className="codirector-exec-progress" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
        <div className="codirector-exec-progress-bar" style={{ width: `${pct}%` }} />
      </div>
      {children.length > 0 ? (
        <ul className="codirector-exec-children">
          {children.map((c, i) => {
            const label = c.label || (typeof c.child_index === "number" ? `Frame ${c.child_index + 1}` : `Item ${i + 1}`);
            const childKind = normalizeJobStatus(c.status) || "queued";
            const childStatus = CHILD_STATUS_LABELS[childKind] || childKind || "Queued";
            return (
              <li key={c.job_id || i} className={`codirector-exec-child child-${childKind}`}>
                <span className="codirector-exec-child-label">{label}</span>
                <span className="codirector-exec-child-status">{childStatus}</span>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}

function GenerationReadyActions({ message }: { message: Msg }) {
  const ready = message.generationReady;
  const [preview, setPreview] = useState<LibraryQuickPreviewAsset | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  if (!ready) return null;

  const openAsset = () => {
    const assetId = String(ready.assetId || "").trim();
    if (!assetId) {
      window.dispatchEvent(
        new CustomEvent(OPEN_CONTENT_TAB_EVENT, { detail: { tab: "library" } }),
      );
      return;
    }
    const kind =
      String(ready.previewKind || "").trim() ||
      (ready.modality === "video" ? "video" : ready.modality === "image" ? "image" : "audio");
    setPreview({
      id: assetId,
      kind,
      name: ready.actionLabel || "Generated media",
    });
  };

  if (ready.outcome === "cancelled") {
    return null;
  }

  if (ready.outcome === "failed") {
    return (
      <div className="codirector-gen-ready" data-testid="codirector-gen-ready-failed">
        {ready.actionLabel ? (
          <button
            type="button"
            className="codirector-gen-ready__action ghost"
            data-testid="codirector-gen-ready-details"
            onClick={() => setDetailsOpen((v) => !v)}
          >
            {ready.actionLabel}
          </button>
        ) : null}
        {detailsOpen && ready.technical ? (
          <details className="codirector-message-technical" open data-testid="codirector-gen-ready-tech">
            <summary>Technical details</summary>
            <pre className="codirector-retrieval-json">{ready.technical}</pre>
          </details>
        ) : null}
      </div>
    );
  }

  return (
    <div className="codirector-gen-ready" data-testid="codirector-gen-ready">
      {ready.actionLabel ? (
        <button
          type="button"
          className="codirector-gen-ready__action"
          data-testid="codirector-gen-ready-action"
          onClick={openAsset}
        >
          {ready.actionLabel}
        </button>
      ) : null}
      <LibraryQuickPreviewModal asset={preview} onClose={() => setPreview(null)} />
    </div>
  );
}

export function CoDirectorMessage({
  message,
  onRetry,
}: {
  message: Msg;
  onRetry?: () => void;
}) {
  const { uiContext } = useCoDirectorSession();
  const [dismissedQueue, setDismissedQueue] = useState(false);
  // Derive label from the execution's actual status when a payload is present,
  // falling back to the static messageType label. This prevents "Working" from
  // being shown for a terminal failure.
  const typeLabel = (() => {
    if (!message.messageType) return null;
    const execStatus = message.execution?.status ?? "";
    if (message.execution?.execution_id && execStatus) {
      const s = execStatus.toLowerCase();
      if (s === "completed") return "Complete";
      if (s === "failed") return "Failed";
      if (s === "cancelled") return "Cancelled";
      if (s === "queued" || s === "preparing") return "Preparing";
      if (s === "preview") return "Preview";
    }
    return MESSAGE_TYPE_LABELS[message.messageType] ?? null;
  })();
  const isAssistant = message.role === "assistant";
  const projected = isAssistant ? projectCreatorReply(message.content || "") : null;
  const html = projected ? renderAssistantMarkdown(projected.text) : "";
  const isExecutionStatus = message.messageType === "execution_status";
  const isCompletion = message.messageType === "completion";
  const hasExecutionPayload = Boolean(message.execution && message.execution.execution_id);
  const planData = (message.execution?.plan_data || {}) as { sceneProduction?: boolean; timelineHandoff?: boolean; outputs?: unknown[] };
  const isSceneProduction = hasExecutionPayload && Boolean(planData.sceneProduction);
  const isPreviewQueue =
    hasExecutionPayload &&
    message.execution?.status === "preview" &&
    !!message.execution?.plan_data &&
    !planData.sceneProduction &&
    Array.isArray(planData.outputs);

  return (
    <article
      className={`codirector-msg ${message.role}${message.messageType ? ` type-${message.messageType}` : ""}`}
    >
      {typeLabel && isAssistant ? <span className="codirector-msg-type">{typeLabel}</span> : null}
      {isPreviewQueue && !dismissedQueue ? (
        <GenerationQueueCard
          execution={message.execution as CoDirectorMessageExecution}
          projectId={uiContext.projectId || ""}
          onClose={() => setDismissedQueue(true)}
        />
      ) : null}
      {isSceneProduction ? (
        <SceneProductionCard
          execution={message.execution as CoDirectorMessageExecution}
          projectId={uiContext.projectId || ""}
        />
      ) : null}
      {isExecutionStatus && hasExecutionPayload && !isPreviewQueue && !isSceneProduction ? (
        <ExecutionSummaryCard
          execution={message.execution as CoDirectorMessageExecution}
          projectId={uiContext.projectId || ""}
        />
      ) : null}
      {isAssistant ? (
        <div
          className="codirector-msg-bubble codirector-msg-html"
          dangerouslySetInnerHTML={{
            __html:
              html ||
              (message.status === "streaming" && !message.content ? "<p>…</p>" : ""),
          }}
        />
      ) : (
        <div className="codirector-msg-bubble">
          {message.content}
          {message.status === "streaming" && !message.content ? "…" : null}
        </div>
      )}
      {projected?.technical ? (
        <details className="codirector-message-technical" data-testid="codirector-message-technical">
          <summary>Technical details</summary>
          <pre className="codirector-retrieval-json">{projected.technical}</pre>
        </details>
      ) : null}
      {message.generationReady ? <GenerationReadyActions message={message} /> : null}
      {isCompletion && hasExecutionPayload ? (
        <ExecutionSummaryCard
          execution={message.execution as CoDirectorMessageExecution}
          projectId={uiContext.projectId || ""}
        />
      ) : null}
      {(isCompletion || isExecutionStatus) && hasExecutionPayload ? (
        <CoDirectorMediaCardGrid
          assetIds={(message.execution?.result_asset_ids || []).filter(Boolean) as string[]}
          children={((message.execution?.child_jobs || []) as Array<{ asset_id?: string | null; label?: string }>)
            .map((c): MediaCardItem | null => (c.asset_id ? { assetId: c.asset_id, label: c.label || undefined } : null))
            .filter((x): x is MediaCardItem => x !== null)}
          title="Generated media"
        />
      ) : null}
      {message.status === "cancelled" && <span className="codirector-msg-status">Stopped</span>}
      {message.status === "interrupted" && (
        <span className="codirector-msg-status">Interrupted — you can retry</span>
      )}
      {message.role === "assistant" && message.messageType === "error" && onRetry ? (
        <div className="codirector-msg-actions" data-testid="codirector-exec-fail-actions">
          <button
            type="button"
            className="ui-btn ui-btn--primary"
            data-testid="codirector-exec-fail-retry"
            onClick={onRetry}
          >
            Retry
          </button>
        </div>
      ) : null}
      {message.role === "user" && onRetry ? (
        <div className="codirector-msg-actions">
          <button type="button" className="ghost" onClick={onRetry}>
            Retry
          </button>
        </div>
      ) : null}
    </article>
  );
}
