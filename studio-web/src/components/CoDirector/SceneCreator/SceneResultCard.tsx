/**
 * SceneResultCard — one result tile in the Scene Creator result grid.
 *
 * Shows: thumbnail (lazy-loaded), prompt summary, status, and actions
 * (Regenerate, Edit Prompt, Open, Send to Timeline, View in Library).
 *
 * Amendment #48 (targeted regen): [Regenerate] only re-runs this shot; the
 * card clearly indicates siblings remain intact.
 *
 * The `resultId` is the value stored in `batch.result_asset_ids[i]`. It can
 * be a real asset ID (completed), a job ID (queued/running), an empty string
 * (pending), or a `failed_*` marker (failed). The card derives a friendly
 * status from the prefix and renders the image when a real asset ID exists.
 */
import { useState } from "react";
import { api } from "../../../api";
import type { ShotRequest } from "./types";

export type SceneResultCardProps = {
  shot: ShotRequest;
  /** The current value in batch.result_asset_ids[i] for this shot. */
  resultId: string;
  /** Child job status from the Agent Operation Overlay, if known. */
  jobStatus?: string;
  jobError?: string | null;
  busy?: boolean;
  onRegenerate: () => void;
  onEditPrompt: (newPrompt: string) => void;
  onOpen: () => void;
  onSendToTimeline: () => void;
  sendingToTimeline?: boolean;
};

function isRealAssetId(id: string): boolean {
  if (!id) return false;
  if (id.startsWith("failed_")) return false;
  // Heuristic: real asset IDs are UUIDs (36 chars, hyphenated). Job IDs from
  // the storyboard_jobs queue are also UUIDs, so we additionally trust the
  // job status: a "completed" job means the ID is a real asset.
  return true;
}

function friendlyStatus(resultId: string, jobStatus?: string): { label: string; tone: "pending" | "running" | "completed" | "failed" } {
  if (!resultId) return { label: "Waiting", tone: "pending" };
  if (resultId.startsWith("failed_")) return { label: "Failed", tone: "failed" };
  if (jobStatus === "completed") return { label: "Completed", tone: "completed" };
  if (jobStatus === "failed") return { label: "Failed", tone: "failed" };
  if (jobStatus === "running" || jobStatus === "preview") return { label: "Generating", tone: "running" };
  if (jobStatus === "queued") return { label: "Queued", tone: "pending" };
  // Unknown job status but we have a non-failed id — assume completed if it
  // looks like a real asset, otherwise treat as queued.
  return { label: "Generating", tone: "running" };
}

function toneColor(tone: "pending" | "running" | "completed" | "failed"): string {
  switch (tone) {
    case "completed":
      return "color-mix(in srgb, var(--good, #4a8) 70%, transparent)";
    case "failed":
      return "color-mix(in srgb, var(--danger, #c33) 70%, transparent)";
    case "running":
      return "color-mix(in srgb, var(--accent, #4a8) 70%, transparent)";
    default:
      return "color-mix(in srgb, currentColor 30%, transparent)";
  }
}

export function SceneResultCard({
  shot,
  resultId,
  jobStatus,
  jobError,
  busy,
  onRegenerate,
  onEditPrompt,
  onOpen,
  onSendToTimeline,
  sendingToTimeline,
}: SceneResultCardProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(shot.raw_text);
  const status = friendlyStatus(resultId, jobStatus);
  const hasImage = isRealAssetId(resultId) && (jobStatus === "completed" || !jobStatus);
  const imageUrl = hasImage ? api.assetUrl(resultId) : "";

  const promptSummary = shot.framing || shot.raw_text.slice(0, 120) || `Shot ${shot.index + 1}`;

  const saveEdit = () => {
    const next = draft.trim();
    if (!next) return;
    onEditPrompt(next);
    setEditing(false);
  };

  return (
    <article
      className="codirector-content-card scene-creator-result-card"
      data-testid="scene-creator-result-card"
      aria-label={`Shot ${shot.index + 1}`}
      style={{ padding: "0.5rem", display: "flex", flexDirection: "column", gap: "0.4rem" }}
    >
      <div
        className="scene-creator-result-card__thumb"
        style={{
          position: "relative",
          aspectRatio: "16 / 9",
          background: "color-mix(in srgb, currentColor 6%, transparent)",
          borderRadius: "0.4rem",
          overflow: "hidden",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {hasImage && imageUrl ? (
          <img
            src={imageUrl}
            alt={promptSummary}
            loading="lazy"
            onClick={onOpen}
            style={{ width: "100%", height: "100%", objectFit: "cover", cursor: "zoom-in" }}
            data-testid="scene-creator-result-image"
          />
        ) : (
          <span className="muted" style={{ fontSize: "0.85rem" }}>
            {status.tone === "running" ? "Generating…" : status.tone === "failed" ? "Failed" : "Waiting"}
          </span>
        )}
        <span
          aria-label={`Status: ${status.label}`}
          style={{
            position: "absolute",
            top: "0.35rem",
            right: "0.35rem",
            background: toneColor(status.tone),
            color: status.tone === "pending" ? "inherit" : "#0b0d12",
            fontSize: "0.65rem",
            padding: "0.1rem 0.35rem",
            borderRadius: "0.3rem",
            fontWeight: 600,
          }}
        >
          {status.label}
        </span>
      </div>

      <p style={{ margin: 0, fontWeight: 600, fontSize: "0.85rem" }} title={shot.raw_text}>
        {promptSummary}
      </p>
      {shot.characters.length ? (
        <p className="muted" style={{ margin: 0, fontSize: "0.72rem" }}>
          Cast: {shot.characters.map((c) => `@${c}`).join(" · ")}
        </p>
      ) : null}

      {jobError ? (
        <p className="muted" style={{ margin: 0, fontSize: "0.72rem", color: "var(--danger, #c33)" }} title={jobError}>
          {jobError}
        </p>
      ) : null}

      {editing ? (
        <div className="row" style={{ gap: "0.4rem", flexDirection: "column", alignItems: "stretch" }}>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={3}
            aria-label={`Edit prompt for shot ${shot.index + 1}`}
            data-testid="scene-creator-edit-prompt-input"
            style={{ width: "100%", resize: "vertical", fontFamily: "inherit" }}
          />
          <div className="row" style={{ gap: "0.4rem" }}>
            <button
              type="button"
              className="primary"
              onClick={saveEdit}
              disabled={busy}
              data-testid="scene-creator-save-prompt"
            >
              Save & Regenerate
            </button>
            <button type="button" onClick={() => setEditing(false)} disabled={busy}>
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="row" style={{ gap: "0.35rem", flexWrap: "wrap" }}>
          <button
            type="button"
            onClick={onRegenerate}
            disabled={busy}
            title="Regenerate only this shot. Other shots stay intact."
            data-testid="scene-creator-regenerate-shot"
          >
            Regenerate
          </button>
          <button
            type="button"
            onClick={() => {
              setDraft(shot.raw_text);
              setEditing(true);
            }}
            disabled={busy}
            data-testid="scene-creator-edit-prompt"
          >
            Edit Prompt
          </button>
          {hasImage ? (
            <button
              type="button"
              onClick={onOpen}
              data-testid="scene-creator-open"
            >
              Open
            </button>
          ) : null}
          {hasImage ? (
            <button
              type="button"
              onClick={onSendToTimeline}
              disabled={sendingToTimeline}
              data-testid="scene-creator-send-to-timeline"
            >
              {sendingToTimeline ? "Sending…" : "Send to Timeline"}
            </button>
          ) : null}
        </div>
      )}
    </article>
  );
}
