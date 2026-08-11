/**
 * Storyboard compact embedded view — the Co-Director Storyboard tab.
 *
 * Calls api.storyboardStudio.workspace(projectId) and renders scene-grouped
 * board thumbnails. Falls back to page grouping when no scriptwriterSceneId.
 * "Open Full Storyboard" calls onOpenFull (which calls onGoTab("script")).
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../../../api";
import type {
  StoryboardDocument,
  StoryboardPanelLink,
  StoryboardWorkspacePayload,
} from "../../../contracts/storyboardStudio";
import "./storyboardCompact.css";

type Props = {
  projectId: string;
  onOpenFull?: () => void;
};

function statusClass(status: string): string {
  const s = status?.toLowerCase();
  if (s === "approved" || s === "final") return "storyboard-compact__badge--approved";
  if (s === "draft" || s === "review") return "storyboard-compact__badge--draft";
  return "";
}

function statusLabel(status: string): string {
  return status || "Draft";
}

function formatDuration(seconds: number): string {
  if (!seconds || !isFinite(seconds) || seconds <= 0) return "";
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function groupPanels(panels: StoryboardPanelLink[]): { key: string; title: string; panels: StoryboardPanelLink[] }[] {
  const groups = new Map<string, StoryboardPanelLink[]>();
  for (const p of panels) {
    const key = p.scriptwriterSceneId || `page-${p.pageIndex + 1}`;
    const arr = groups.get(key) || [];
    arr.push(p);
    groups.set(key, arr);
  }
  return Array.from(groups.entries()).map(([key, ps]) => {
    const title = ps[0]?.scriptwriterSceneId
      ? `Scene ${key.slice(-4)}`
      : `Page ${ps[0].pageIndex + 1}`;
    return { key, title, panels: ps };
  });
}

function BoardCard({ panel }: { panel: StoryboardPanelLink }) {
  return (
    <button type="button" className="storyboard-compact__card" data-testid="storyboard-card">
      <div className="storyboard-compact__thumb">
        {panel.assetId ? (
          <img src={api.assetUrl(panel.assetId)} alt={panel.label} loading="lazy" />
        ) : (
          <span className="storyboard-compact__thumb-placeholder">Board</span>
        )}
      </div>
      <div className="storyboard-compact__meta">
        <strong>{panel.label || "Untitled board"}</strong>
        <span>
          {panel.shotSize ? `${panel.shotSize}` : ""}
          {panel.durationEst ? ` · ${formatDuration(panel.durationEst)}` : ""}
        </span>
        <span className={`storyboard-compact__badge ${statusClass(panel.status)}`}>
          {statusLabel(panel.status)}
        </span>
      </div>
    </button>
  );
}

function SkeletonGrid() {
  return (
    <div className="storyboard-compact__skeleton" aria-hidden="true">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="storyboard-compact__skeleton-card">
          <div className="storyboard-compact__skeleton-thumb" />
          <div className="storyboard-compact__skeleton-line" />
          <div className="storyboard-compact__skeleton-line" />
        </div>
      ))}
    </div>
  );
}

export function StoryboardCompactView({ projectId, onOpenFull }: Props) {
  const [workspace, setWorkspace] = useState<StoryboardWorkspacePayload | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await api.storyboardStudio.workspace(projectId);
      setWorkspace(result as StoryboardWorkspacePayload);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [projectId]);

  useEffect(() => {
    let cancelled = false;
    setBusy(true);
    setError(null);
    api
      .storyboardStudio.workspace(projectId)
      .then((result) => {
        if (cancelled) return;
        setWorkspace(result as StoryboardWorkspacePayload);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const doc: StoryboardDocument | undefined = workspace?.document;
  const panels: StoryboardPanelLink[] = workspace?.panels || [];
  const groups = useMemo(() => groupPanels(panels), [panels]);

  return (
    <div className="storyboard-compact" data-testid="storyboard-compact">
      {busy ? (
        <SkeletonGrid />
      ) : error ? (
        <div className="storyboard-compact__state storyboard-compact__state--error" data-testid="storyboard-compact-error">
          <strong>Storyboard could not load</strong>
          <p>{error}</p>
          <button type="button" className="storyboard-compact__actions-button primary" onClick={() => void refresh()}>
            Retry
          </button>
        </div>
      ) : panels.length === 0 ? (
        <div className="storyboard-compact__state" data-testid="storyboard-compact-empty">
          <strong>No storyboard frames yet.</strong>
          <p>Generate boards in the Storyboard Studio or ask Co-Director to help.</p>
          <div className="storyboard-compact__actions">
            <button
              type="button"
              className="storyboard-compact__actions-button primary"
              data-testid="storyboard-compact-open-studio"
              onClick={() => onOpenFull?.()}
            >
              Open Storyboard Studio
            </button>
            <button type="button" className="storyboard-compact__actions-button" onClick={() => onOpenFull?.()}>
              Ask Co-Director to help storyboard
            </button>
          </div>
        </div>
      ) : (
        <>
          <div className="storyboard-compact__header">
            <div>
              <h3 className="storyboard-compact__title">{doc?.title || "Untitled Storyboard"}</h3>
              <p className="storyboard-compact__subtitle">
                {panels.length} {panels.length === 1 ? "board" : "boards"}
                {doc?.updatedAt ? ` · Updated ${new Date(doc.updatedAt).toLocaleDateString()}` : ""}
              </p>
            </div>
            <div className="storyboard-compact__actions">
              <button
                type="button"
                className="storyboard-compact__actions-button primary"
                data-testid="storyboard-compact-open-full"
                onClick={() => onOpenFull?.()}
              >
                Open Full Storyboard
              </button>
            </div>
          </div>
          {groups.map((g) => (
            <div key={g.key} className="storyboard-compact__scene">
              <h4 className="storyboard-compact__scene-title">{g.title}</h4>
              <div className="storyboard-compact__grid">
                {g.panels.map((p) => (
                  <BoardCard key={p.panelId} panel={p} />
                ))}
              </div>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
