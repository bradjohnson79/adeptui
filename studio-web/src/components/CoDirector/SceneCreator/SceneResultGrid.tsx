/**
 * SceneResultGrid — responsive grid of SceneResultCards for one batch.
 *
 * Renders one card per shot_request, mapped against the batch's
 * result_asset_ids array. Child job status (from the Agent Operation
 * Overlay) is overlaid per-card so a generating/failed shot shows live state.
 *
 * Amendment #42 (output count): displays exactly len(shot_requests) cards —
 * never invents extra shots even if output_count > len(shots).
 */
import { createPortal } from "react-dom";
import { useEffect, useState } from "react";
import { api } from "../../../api";
import type { ChildJobSummary, SceneGenerationBatch, ShotRequest } from "./types";
import { SceneResultCard } from "./SceneResultCard";

export type SceneResultGridProps = {
  batch: SceneGenerationBatch;
  /** Child jobs from the current execution, keyed by shot index. */
  childJobs?: ChildJobSummary[];
  busy?: boolean;
  onRegenerateShot: (shotIndex: number) => void;
  onEditPrompt: (shotIndex: number, newPrompt: string) => void;
  onSendShotToTimeline: (shotIndex: number) => void;
  sendingShotIndex?: number | null;
  onSendBatchToTimeline: () => void;
  sendingBatchToTimeline?: boolean;
  onViewInLibrary?: () => void;
};

export function SceneResultGrid({
  batch,
  childJobs,
  busy,
  onRegenerateShot,
  onEditPrompt,
  onSendShotToTimeline,
  sendingShotIndex,
  onSendBatchToTimeline,
  sendingBatchToTimeline,
  onViewInLibrary,
}: SceneResultGridProps) {
  const [previewShot, setPreviewShot] = useState<{ shot: ShotRequest; assetId: string } | null>(null);

  if (!batch.shot_requests.length) {
    return (
      <p className="muted" data-testid="scene-creator-grid-empty">
        No shots in this batch yet.
      </p>
    );
  }

  const jobsByIndex = new Map<number, ChildJobSummary>();
  for (const job of childJobs || []) {
    const idx = typeof job.child_index === "number" ? job.child_index : -1;
    if (idx >= 0) jobsByIndex.set(idx, job);
  }

  const completedAssets = batch.result_asset_ids.filter(
    (id) => id && !id.startsWith("failed_") && (jobsByIndex.get(batch.result_asset_ids.indexOf(id))?.status === "completed" || !jobsByIndex.size),
  );
  const canSendBatch = completedAssets.length > 0;

  return (
    <section data-testid="scene-creator-result-grid" style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.5rem" }}>
        <p className="eyebrow" style={{ margin: 0 }}>
          {batch.shot_requests.length} shot{batch.shot_requests.length === 1 ? "" : "s"} in this batch
        </p>
        <div className="row" style={{ gap: "0.4rem" }}>
          {onViewInLibrary ? (
            <button
              type="button"
              onClick={onViewInLibrary}
              data-testid="scene-creator-view-library"
              title="Open the Library tab to see this batch's collection"
            >
              View in Library
            </button>
          ) : null}
          <button
            type="button"
            className="primary"
            onClick={onSendBatchToTimeline}
            disabled={!canSendBatch || sendingBatchToTimeline}
            data-testid="scene-creator-send-batch-to-timeline"
            title={canSendBatch ? "Send all completed shots to the Timeline" : "No completed shots yet"}
          >
            {sendingBatchToTimeline ? "Sending…" : "Send Batch to Timeline"}
          </button>
        </div>
      </div>
      <div
        className="scene-creator-grid"
        role="list"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
          gap: "0.6rem",
        }}
      >
        {batch.shot_requests.map((shot, index) => {
          const resultId = batch.result_asset_ids[index] || "";
          const job = jobsByIndex.get(index);
          return (
            <div role="listitem" key={`${shot.index}-${index}`}>
              <SceneResultCard
                shot={shot}
                resultId={resultId}
                jobStatus={job?.status}
                jobError={job?.error}
                busy={busy}
                onRegenerate={() => onRegenerateShot(index)}
                onEditPrompt={(next) => onEditPrompt(index, next)}
                onOpen={() => resultId && setPreviewShot({ shot, assetId: resultId })}
                onSendToTimeline={() => onSendShotToTimeline(index)}
                sendingToTimeline={sendingShotIndex === index}
              />
            </div>
          );
        })}
      </div>
      {previewShot ? (
        <PreviewModal
          shot={previewShot.shot}
          assetId={previewShot.assetId}
          onClose={() => setPreviewShot(null)}
        />
      ) : null}
    </section>
  );
}

function PreviewModal({
  shot,
  assetId,
  onClose,
}: {
  shot: ShotRequest;
  assetId: string;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return createPortal(
    <div
      className="library-media-preview"
      role="dialog"
      aria-modal="true"
      aria-label={`Shot ${shot.index + 1} preview`}
      data-testid="scene-creator-preview"
    >
      <button
        type="button"
        className="library-media-preview__backdrop"
        aria-label="Close preview"
        onClick={onClose}
      />
      <div className="library-media-preview__panel">
        <button
          type="button"
          className="library-media-preview__close"
          aria-label="Close"
          onClick={onClose}
        >
          ×
        </button>
        <div className="library-media-preview__media">
          <img src={api.assetUrl(assetId)} alt={`Shot ${shot.index + 1}`} />
        </div>
        <div className="library-media-preview__meta">
          <h3>Shot {shot.index + 1}</h3>
          <p className="muted">{shot.raw_text}</p>
        </div>
      </div>
    </div>,
    document.body,
  );
}
