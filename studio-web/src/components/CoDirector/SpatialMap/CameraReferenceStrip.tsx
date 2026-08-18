/**
 * CameraReferenceStrip — ERS-linked Camera Shot References (C1-C4).
 *
 * Viewpoint/framing canon per camera (Part 14-18): independently
 * replaceable, low-overhead (one camera at a time), stale when authoritative
 * camera data or the ERS revision changes (Part 40). These are NOT final
 * scene art — they are conditioning inputs for Mini and Scene Creator.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../../api";

export type CameraReferenceRow = {
  cameraId: string;
  label?: string;
  assetId?: string | null;
  status?: string;
  stale?: boolean;
  staleReasons?: string[];
  shotSize?: string;
  primarySubject?: string;
  error?: string | null;
  jobId?: string;
};

type Props = {
  projectId: string;
  documentId: string;
  cameraLabels: Record<string, string>;
  generator: "qwen2512" | "gpt-image-2";
  canGenerate: boolean;
};

const POLL_MS = 2500;

export function CameraReferenceStrip({ projectId, documentId, cameraLabels, generator, canGenerate }: Props) {
  const [rows, setRows] = useState<CameraReferenceRow[] | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const stopPoll = useCallback(() => {
    if (pollRef.current) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const refresh = useCallback(async () => {
    try {
      const res = await api.spatialMap.listCameraReferences(projectId, documentId);
      setRows((res.references || []) as CameraReferenceRow[]);
      const live = (res.references || []).some(
        (r) => r.status === "queued" || r.status === "generating",
      );
      if (!live) stopPoll();
    } catch {
      // keep last rows; transient failure is not fatal
    }
  }, [documentId, projectId, stopPoll]);

  useEffect(() => {
    void refresh();
    return () => stopPoll();
  }, [refresh, stopPoll]);

  const generate = useCallback(
    async (cameraId: string) => {
      setBusyId(cameraId);
      setError(null);
      try {
        await api.spatialMap.generateCameraReference(projectId, documentId, cameraId, {
          generator,
        });
        stopPoll();
        void refresh();
        pollRef.current = window.setInterval(() => void refresh(), POLL_MS);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not generate camera reference.");
      } finally {
        setBusyId(null);
      }
    },
    [documentId, generator, projectId, refresh, stopPoll],
  );

  if (!rows) {
    return <p className="spatial-map__hint">Loading camera references…</p>;
  }

  return (
    <div className="spatial-map__camera-refs" data-testid="camera-reference-strip">
      <p className="spatial-map__camera-refs-title">Camera Shot References</p>
      <p className="spatial-map__hint">
        Viewpoint + framing canon per camera. Not final scene art — conditioning inputs only.
      </p>
      {error ? (
        <p className="spatial-map__hint spatial-map__hint--error" role="alert">
          {error}
        </p>
      ) : null}
      <div className="spatial-map__camera-refs-grid">
        {rows.map((row) => {
          const label = row.label || cameraLabels[row.cameraId] || "Camera";
          const live = row.status === "queued" || row.status === "generating";
          return (
            <div
              key={row.cameraId}
              className={"spatial-map__camera-ref" + (row.stale ? " is-stale" : "")}
              data-testid={`camera-ref-${label}`}
            >
              <div className="spatial-map__camera-ref-head">
                <span className="spatial-map__camera-ref-label">{label}</span>
                {row.stale ? (
                  <span className="spatial-map__mini-chip is-stale" title={(row.staleReasons || []).join("; ")}>
                    Stale
                  </span>
                ) : null}
                {row.status === "complete" ? (
                  <span className="spatial-map__mini-chip is-pass">Ready</span>
                ) : row.status === "failed" ? (
                  <span className="spatial-map__mini-chip is-failed">Failed</span>
                ) : live ? (
                  <span className="spatial-map__mini-chip is-validating">Generating…</span>
                ) : (
                  <span className="spatial-map__mini-chip is-generating">Not generated</span>
                )}
              </div>
              <div className="spatial-map__camera-ref-body">
                {row.assetId ? (
                  <img src={api.assetUrl(row.assetId)} alt={`${label} camera shot reference`} />
                ) : (
                  <span className="spatial-map__camera-ref-empty">
                    {row.status === "failed" ? row.error || "Generation failed." : "No reference yet."}
                  </span>
                )}
              </div>
              <div className="spatial-map__camera-ref-meta">
                {row.shotSize ? `Shot size: ${String(row.shotSize).replace(/_/g, " ")}` : ""}
                {row.primarySubject && row.primarySubject !== "auto"
                  ? " · Subject: " + row.primarySubject
                  : ""}
              </div>
              <button
                type="button"
                className="ui-btn ui-btn--secondary"
                onClick={() => void generate(row.cameraId)}
                disabled={busyId !== null || live || !canGenerate}
                data-testid={`camera-ref-generate-${label}`}
              >
                {live ? "Generating…" : row.assetId ? "Regenerate" : "Generate"}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
