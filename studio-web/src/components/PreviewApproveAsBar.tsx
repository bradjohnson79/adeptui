import { useMemo, useState } from "react";
import { api } from "../api";
import type { Asset } from "../types";
import { HelpTip } from "./HelpTip";
import {
  PREVIEW_APPROVE_AS_OPTIONS,
  labelForApproveAsKind,
  type PreviewApproveAsKind,
} from "./previewApproveAs";

/** Detect the approved role stamped on an asset's labels by the backend. */
function approvedKindFromAsset(asset: Asset): PreviewApproveAsKind | null {
  const labels = String(asset?.labels_json || asset?.labels || "[]").toLowerCase();
  if (!labels || labels === "[]") return null;
  if (labels.includes("character_reference_sheet") || labels.includes("character_sheet") || labels.includes('"crs"')) {
    return "character";
  }
  if (labels.includes("environment_reference_sheet") || labels.includes('"ers"')) {
    return "environment";
  }
  if (labels.includes("prop_reference_sheet") || labels.includes('"prs"')) {
    return "prop";
  }
  if (labels.includes("scene_frame") || labels.includes("opening_frame")) {
    return "scene_frame";
  }
  return null;
}

export function PreviewApproveAsBar({
  projectId,
  sceneId,
  asset,
  onApproved,
}: {
  projectId: string;
  sceneId?: string;
  asset: Asset;
  onApproved?: () => void | Promise<void>;
}) {
  const initialApproved = useMemo(() => approvedKindFromAsset(asset), [asset]);
  const [approvedKind, setApprovedKind] = useState<PreviewApproveAsKind | null>(initialApproved);
  const [editing, setEditing] = useState(false);
  const [kind, setKind] = useState<PreviewApproveAsKind>(initialApproved || "character");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.sceneReferences.approveAs(projectId, {
        asset_id: asset.id,
        kind,
        scene_id: sceneId,
      });
      setApprovedKind(kind);
      setEditing(false);
      await onApproved?.();
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Could not approve this picture.");
    } finally {
      setBusy(false);
    }
  };

  // Approved confirmation state — green check, no dropdown.
  if (approvedKind && !editing) {
    return (
      <div
        className="live-preview-approve-as live-preview-approve-as--approved"
        data-testid="live-preview-approve-as"
        data-approved-kind={approvedKind}
      >
        <span className="live-preview-approve-as__approved" data-testid="live-preview-approve-as-status">
          ✓ Approved as {labelForApproveAsKind(approvedKind)}
        </span>
        <button
          type="button"
          className="live-preview-approve-as__edit"
          data-testid="live-preview-approve-as-edit"
          onClick={() => {
            setKind(approvedKind);
            setEditing(true);
          }}
        >
          Change
        </button>
      </div>
    );
  }

  return (
    <form
      className="live-preview-approve-as"
      data-testid="live-preview-approve-as"
      onSubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      <label className="live-preview-approve-as__label" htmlFor="live-preview-approve-as-kind">
        Approve as
      </label>
      <select
        id="live-preview-approve-as-kind"
        className="live-preview-approve-as__select"
        data-testid="live-preview-approve-as-kind"
        value={kind}
        disabled={busy}
        onChange={(event) => setKind(event.target.value as PreviewApproveAsKind)}
      >
        {PREVIEW_APPROVE_AS_OPTIONS.map((option) => (
          <option key={option.kind} value={option.kind}>
            {option.label}
          </option>
        ))}
      </select>
      <button
        type="submit"
        className="live-preview-approve-as__ok"
        data-testid="live-preview-approve-as-ok"
        disabled={busy}
      >
        {busy ? "…" : "OK"}
      </button>
      <HelpTip
        label="What does Approve as do?"
        content="Name what this picture is. Character is that person's look. Environment is a place. Prop is an object. Scene Frame is the opening picture for this shot."
      />
      {error ? (
        <span className="live-preview-approve-as__error" data-testid="live-preview-approve-as-error" role="alert">
          {error}
        </span>
      ) : null}
    </form>
  );
}
