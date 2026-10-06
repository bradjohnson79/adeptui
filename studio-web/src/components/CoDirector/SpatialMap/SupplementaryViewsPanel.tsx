import { useCallback, useEffect, useState } from "react";
import { api } from "../../../api";

type Slot = "A" | "B";

type ViewRecord = {
  slot?: Slot;
  assetId?: string;
  cameraRole?: string;
  evidenceClass?: string;
  status?: string;
  approvedForSpatialReasoning?: boolean;
  gateVerdict?: string;
  gateReasons?: string[];
};

type Props = {
  projectId: string;
  documentId: string;
  masterAssetId: string;
};

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

export function SupplementaryViewsPanel({ projectId, documentId, masterAssetId }: Props) {
  const [payload, setPayload] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [analysis, setAnalysis] = useState<Record<string, unknown> | null>(null);

  const load = useCallback(async () => {
    const next = await api.spatialMap.getSupplementaryViews(projectId, documentId);
    setPayload(next);
  }, [documentId, projectId]);

  useEffect(() => {
    void load().catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, [load]);

  useEffect(() => {
    const state = asRecord(payload?.state);
    if (state.inFlightSlot) {
      const timer = window.setInterval(() => {
        void load();
      }, 2500);
      return () => window.clearInterval(timer);
    }
    return undefined;
  }, [load, payload]);

  const state = asRecord(payload?.state);
  const viewA = asRecord(state.viewA) as ViewRecord;
  const viewB = asRecord(state.viewB) as ViewRecord;
  const confidence = asRecord(state.confidence);

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="spatial-map__supplementary" data-testid="supplementary-views-panel">
      <h4 className="spatial-map__start-title">Improve Spatial Understanding</h4>
      <p className="spatial-map__tip">
        Co-Director can create up to two additional views of this location to help Spatial Map understand
        the environment more clearly. These are inferred references, not observed photographs.
      </p>
      <div className="spatial-map__empty-actions">
        <button
          type="button"
          className="ui-btn ui-btn--primary"
          data-testid="generate-additional-views"
          disabled={busy || !!state.inFlightSlot}
          onClick={() =>
            void run(async () => {
              const picked = await api.spatialMap.analyzeSupplementaryViews(projectId, documentId);
              setAnalysis(picked);
              const slot = (picked.slot as Slot) || "A";
              await api.spatialMap.generateSupplementaryView(projectId, documentId, { slot });
            })
          }
        >
          {state.inFlightSlot ? "Generating additional view…" : "Generate Additional Views"}
        </button>
      </div>
      {analysis ? (
        <p className="muted" data-testid="supplementary-analysis">
          Next camera: {String(analysis.cameraRole || "")} — {String(analysis.reason || "")}
        </p>
      ) : null}
      {error ? <p className="spatial-map__error" data-testid="supplementary-error">{error}</p> : null}

      <div className="spatial-map__supplementary-grid">
        <article className="spatial-map__supplementary-card" data-testid="master-reference-card">
          <p className="eyebrow">Master Reference</p>
          {masterAssetId ? <img src={api.assetUrl(masterAssetId)} alt="Master location reference" /> : null}
          <p className="muted">Observed reference</p>
        </article>
        <ViewCard
          label="Supplementary View 1"
          view={viewA}
          testId="supplementary-view-a"
          disabled={busy}
          onAccept={() => void run(() => api.spatialMap.acceptSupplementaryView(projectId, documentId, "A"))}
          onReject={() => void run(() => api.spatialMap.rejectSupplementaryView(projectId, documentId, "A"))}
          onRegenerate={() => void run(() => api.spatialMap.regenerateSupplementaryView(projectId, documentId, "A"))}
        />
        <ViewCard
          label="Supplementary View 2"
          view={viewB}
          testId="supplementary-view-b"
          disabled={busy || !viewA.approvedForSpatialReasoning}
          onAccept={() => void run(() => api.spatialMap.acceptSupplementaryView(projectId, documentId, "B"))}
          onReject={() => void run(() => api.spatialMap.rejectSupplementaryView(projectId, documentId, "B"))}
          onRegenerate={() => void run(() => api.spatialMap.regenerateSupplementaryView(projectId, documentId, "B"))}
        />
      </div>
      <div className="spatial-map__confidence" data-testid="spatial-confidence-summary">
        <p><strong>Observed:</strong> {(confidence.observed as string[] | undefined)?.[0] || "Master facts only."}</p>
        <p><strong>Supported:</strong> {(confidence.inferredSupported as string[] | undefined)?.join(" ") || "None yet."}</p>
        <p><strong>Conflicted:</strong> {(confidence.conflicted as string[] | undefined)?.join(" ") || "None."}</p>
        <p><strong>Unknown:</strong> {(confidence.unknown as string[] | undefined)?.[0] || "Still unseen space stays unknown."}</p>
      </div>
    </section>
  );
}

function ViewCard({
  label,
  view,
  testId,
  disabled,
  onAccept,
  onReject,
  onRegenerate,
}: {
  label: string;
  view: ViewRecord;
  testId: string;
  disabled: boolean;
  onAccept: () => void;
  onReject: () => void;
  onRegenerate: () => void;
}) {
  const rejected = view.status === "REJECTED";
  const shown = rejected ? {} : view;
  const ready = shown.status === "READY";
  return (
    <article className="spatial-map__supplementary-card" data-testid={testId}>
      <p className="eyebrow">{label}</p>
      {shown.assetId ? <img src={api.assetUrl(shown.assetId)} alt={label} /> : <p className="muted">No additional view yet.</p>}
      {shown.cameraRole ? <p data-testid={`${testId}-role`}>{shown.cameraRole}</p> : null}
      {shown.evidenceClass === "INFERRED" ? (
        <p className="spatial-map__inferred-badge" data-testid={`${testId}-inferred`}>Inferred Reference</p>
      ) : null}
      {shown.status ? <p className="muted">{shown.status}{shown.approvedForSpatialReasoning ? " · Accepted for Spatial Reasoning" : ""}</p> : null}
      <div className="spatial-map__slot-actions">
        <button type="button" className="spatial-map__slot-action" disabled={disabled || !ready} onClick={onAccept} data-testid={`${testId}-accept`}>
          Accept for Spatial Reasoning
        </button>
        <button type="button" className="spatial-map__slot-action" disabled={disabled || !shown.assetId} onClick={onRegenerate} data-testid={`${testId}-regenerate`}>
          Regenerate
        </button>
        <button type="button" className="spatial-map__slot-remove" disabled={disabled || !shown.assetId} onClick={onReject} data-testid={`${testId}-reject`}>
          Reject
        </button>
      </div>
    </article>
  );
}
