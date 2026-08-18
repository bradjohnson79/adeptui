import { useState } from "react";
import { useCoDirectorSession } from "./CoDirectorSession";
import type { CoDirectorMessage as Msg, CoDirectorMessageExecution } from "./types";
import { renderAssistantMarkdown } from "./assistantMarkdown";
import GenerationQueueCard from "./GenerationQueueCard";
import { CoDirectorMediaCardGrid, type MediaCardItem } from "./CoDirectorMediaCardGrid";

const MESSAGE_TYPE_LABELS: Record<string, string> = {
  recommendation: "Recommendation",
  clarification: "Clarification",
  warning: "Warning",
  proposal: "Proposal",
  plan: "Production plan",
  answer: "Answer",
  // Workstream H — execution-aware message kinds.
  execution_status: "Working",
  completion: "Done",
  error: "Error",
};

const CHILD_STATUS_LABELS: Record<string, string> = {
  queued: "Queued",
  running: "Working",
  preview: "Preview",
  completed: "Done",
  failed: "Failed",
  cancelled: "Stopped",
};

function capabilityLabel(capability: string | undefined): string {
  if (!capability) return "Execution";
  const short = capability.split(".").pop() || capability;
  return short.charAt(0).toUpperCase() + short.slice(1);
}

function progressPercent(progress: number | undefined, completed: number | undefined, total: number | undefined): number {
  if (typeof progress === "number" && progress > 0) return Math.round(progress * 100);
  if (typeof completed === "number" && typeof total === "number" && total > 0) {
    return Math.round((completed / total) * 100);
  }
  return 0;
}

function ExecutionSummaryCard({ execution }: { execution: CoDirectorMessageExecution }) {
  const pct = progressPercent(execution.progress, execution.completed, execution.total);
  const completed = execution.completed ?? 0;
  const total = execution.total ?? 0;
  const status = (execution.status || "").toLowerCase();
  const isDone = status === "completed" || status === "done";
  const isFailed = status === "failed";
  const isCancelled = status === "cancelled";
  const children = Array.isArray(execution.child_jobs) ? execution.child_jobs : [];

  return (
    <div className={`codirector-exec-card ${isFailed ? "is-failed" : isCancelled ? "is-cancelled" : isDone ? "is-done" : "is-running"}`}>
      <div className="codirector-exec-head">
        <span className="codirector-exec-cap">{capabilityLabel(execution.capability)}</span>
        <span className="codirector-exec-counts">
          {completed}/{total || "?"} complete
        </span>
      </div>
      <div className="codirector-exec-progress" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
        <div className="codirector-exec-progress-bar" style={{ width: `${pct}%` }} />
      </div>
      {children.length > 0 ? (
        <ul className="codirector-exec-children">
          {children.map((c, i) => {
            const label = c.label || (typeof c.child_index === "number" ? `Frame ${c.child_index + 1}` : `Item ${i + 1}`);
            const childStatus = CHILD_STATUS_LABELS[(c.status || "").toLowerCase()] || c.status || "Queued";
            return (
              <li key={c.job_id || i} className={`codirector-exec-child child-${(c.status || "queued").toLowerCase()}`}>
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

export function CoDirectorMessage({
  message,
  onRetry,
}: {
  message: Msg;
  onRetry?: () => void;
}) {
  const { uiContext } = useCoDirectorSession();
  const [dismissedQueue, setDismissedQueue] = useState(false);
  const typeLabel = message.messageType ? MESSAGE_TYPE_LABELS[message.messageType] : null;
  const isAssistant = message.role === "assistant";
  const html = isAssistant ? renderAssistantMarkdown(message.content) : "";
  const isExecutionStatus = message.messageType === "execution_status";
  const isCompletion = message.messageType === "completion";
  const hasExecutionPayload = Boolean(message.execution && message.execution.execution_id);
  const isPreviewQueue = hasExecutionPayload && message.execution?.status === "preview" && !!message.execution?.plan_data;

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
      {isExecutionStatus && hasExecutionPayload && !isPreviewQueue ? (
        <ExecutionSummaryCard execution={message.execution as CoDirectorMessageExecution} />
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
      {isCompletion && hasExecutionPayload ? (
        <ExecutionSummaryCard execution={message.execution as CoDirectorMessageExecution} />
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
