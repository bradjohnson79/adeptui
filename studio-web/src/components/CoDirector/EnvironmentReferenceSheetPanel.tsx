import { useEffect, useMemo, useState } from "react";
import { api } from "../../api";
import type {
  EnvironmentReferenceSheet,
  EnvironmentReferenceSheetSummary,
} from "../../contracts/environmentReferenceSheet";
import { CoDirectorEmptyState, CoDirectorErrorState } from "./cards";

type SheetTab = "overview" | "views" | "continuity" | "exports";

const TABS: Array<{ id: SheetTab; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "views", label: "Views" },
  { id: "continuity", label: "Continuity" },
  { id: "exports", label: "Exports" },
];

export function EnvironmentReferenceSheetPanel({ projectId }: { projectId: string }) {
  const [summaries, setSummaries] = useState<EnvironmentReferenceSheetSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [sheet, setSheet] = useState<EnvironmentReferenceSheet | null>(null);
  const [tab, setTab] = useState<SheetTab>("overview");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const loadSummaries = async (showLoading: boolean) => {
      if (showLoading && !cancelled) {
        setLoading(true);
      }
      if (!cancelled) {
        setError(null);
      }
      try {
        const res = await api.environmentReferenceSheet.listSheets(projectId);
        if (cancelled) return;
        const next = res.sheets || [];
        setSummaries(next);
        setSelectedId((current) => {
          if (current && next.some((item) => item.sheetId === current)) {
            return current;
          }
          return next[0]?.sheetId || "";
        });
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
        }
      } finally {
        if (showLoading && !cancelled) {
          setLoading(false);
        }
      }
    };

    void loadSummaries(true);
    const intervalId = window.setInterval(() => {
      void loadSummaries(false);
    }, 2_000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [projectId]);

  useEffect(() => {
    if (!selectedId) {
      setSheet(null);
      return;
    }
    let cancelled = false;
    const loadSheet = async () => {
      try {
        const res = await api.environmentReferenceSheet.getSheet(projectId, selectedId);
        if (!cancelled) {
          setSheet(res.sheet || null);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
        }
      }
    };

    void loadSheet();
    const intervalId = window.setInterval(() => {
      void loadSheet();
    }, 2_000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [projectId, selectedId]);

  const selectedSummary = useMemo(
    () => summaries.find((item) => item.sheetId === selectedId) || null,
    [selectedId, summaries],
  );

  if (loading) {
    return <p className="muted">Loading Environment Reference Sheets…</p>;
  }
  if (error) {
    return <CoDirectorErrorState title="ERS review unavailable" description={error} />;
  }
  if (!summaries.length) {
    return (
      <CoDirectorEmptyState
        testId="codirector-ers-empty"
        title="No Environment Reference Sheet yet"
        description="Ask Co-Director to create an Environment Reference Sheet. The review panel stays read-only until a canonical ERS exists."
      />
    );
  }

  return (
    <section className="codirector-content-card" data-testid="codirector-ers-panel">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center", gap: "0.75rem" }}>
        <div>
          <p className="eyebrow">Environment Reference Sheet</p>
          <h3 style={{ marginTop: 0 }}>{selectedSummary?.name || "ERS review"}</h3>
          <p className="muted">
            Status: {selectedSummary?.status.replace(/_/g, " ")} · Continuity:{" "}
            {selectedSummary?.continuityStatus}
          </p>
        </div>
        <label className="scene-meta">
          Open Sheet
          <select
            value={selectedId}
            onChange={(event) => setSelectedId(event.target.value)}
            data-testid="codirector-ers-select"
          >
            {summaries.map((item) => (
              <option key={item.sheetId} value={item.sheetId}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="workspace-tabs" role="tablist" aria-label="ERS review tabs">
        {TABS.map((entry) => (
          <button
            key={entry.id}
            type="button"
            className={tab === entry.id ? "primary" : ""}
            aria-selected={tab === entry.id}
            onClick={() => setTab(entry.id)}
          >
            {entry.label}
          </button>
        ))}
      </div>

      {!sheet ? (
        <p className="muted">Select a sheet to review.</p>
      ) : (
        <>
          {tab === "overview" ? (
            <div className="assistant-setup-list">
              <p>{sheet.description}</p>
              <li>North lock: {sheet.spatialMap?.northLockDirection || "missing"}</li>
              <li>Spatial Map: {sheet.spatialMap?.mapId || "Not attached yet"}</li>
              <li>Location link: {sheet.registration.locationDisplayName || "Not registered yet"}</li>
              <li>
                Creator highlights:{" "}
                {sheet.composition.profileHighlights.length
                  ? sheet.composition.profileHighlights.join(", ")
                  : "No highlights prepared yet."}
              </li>
            </div>
          ) : null}

          {tab === "views" ? (
            <div className="assistant-setup-list">
              {sheet.directionalViews.map((view) => (
                <div key={view.direction} className="codirector-content-card" style={{ marginBottom: "0.75rem" }}>
                  <strong>{view.direction.toUpperCase()}</strong>
                  <p className="muted">
                    {view.status} {view.approvedAssetId ? `· asset ${view.approvedAssetId}` : ""}
                  </p>
                  <p>{view.prompt || "No prompt prepared yet."}</p>
                </div>
              ))}
            </div>
          ) : null}

          {tab === "continuity" ? (
            <div>
              <p>{sheet.continuity.summary}</p>
              <p className="muted">{sheet.continuity.note}</p>
              {sheet.continuity.findings.length ? (
                <ul className="assistant-setup-list">
                  {sheet.continuity.findings.map((finding) => (
                    <li key={finding.findingId}>
                      <strong>{finding.title}:</strong> {finding.message}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted">No open continuity findings.</p>
              )}
            </div>
          ) : null}

          {tab === "exports" ? (
            <div>
              {sheet.exports.length ? (
                <ul className="assistant-setup-list">
                  {sheet.exports.map((item) => (
                    <li key={item.exportKind}>
                      <strong>{item.exportKind}</strong>: {item.status}
                      {item.assetId ? ` · asset ${item.assetId}` : ""}
                      {item.message ? ` · ${item.message}` : ""}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted">
                  No exports yet. Ask Co-Director to render a PNG, PDF, or offline package after the sheet is ready.
                </p>
              )}
              <p className="muted">
                This panel is review-only. Canonical ERS creation and export orchestration still goes through
                Co-Director approvals.
              </p>
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}
