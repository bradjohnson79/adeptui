/**
 * Script Writer compact embedded view — the Co-Director Script Writer tab.
 *
 * Shows a read-only preview of the current screenplay (title, page/scene
 * counts, last saved, and a short formatted preview of the first elements)
 * with an "Open Full Script Writer" action. Shares the same authoritative
 * document as the standalone ScriptwriterStudio (no duplicate document).
 */
import { useCallback, useEffect, useState } from "react";
import { api } from "../../../api";
import "./scriptwriterCompact.css";

type ScriptElement = {
  id: string;
  type: string;
  text: string;
  order: number;
  sceneId?: string | null;
  characterId?: string | null;
};

type ScriptDocument = {
  id: string;
  title: string;
  elements?: ScriptElement[];
  updatedAt?: string;
  draftStatus?: string;
};

type ScriptStats = {
  pagesEstimated?: number;
  scenes?: number;
  words?: number;
  runtimeMinutesEstimated?: number;
};

type StudioBundle = {
  ok?: boolean;
  document?: ScriptDocument;
  stats?: ScriptStats;
};

type Props = {
  projectId: string;
  onOpenFull?: () => void;
};

function formatLastSaved(updatedAt?: string): string {
  if (!updatedAt) return "";
  try {
    const d = new Date(updatedAt);
    if (isNaN(d.getTime())) return "";
    return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  } catch {
    return "";
  }
}

function ScreenplayPreview({ elements }: { elements: ScriptElement[] }) {
  const preview = elements.slice(0, 40);
  if (preview.length === 0) {
    return <p className="scriptwriter-compact__preview-empty">No script content yet.</p>;
  }
  return (
    <div className="scriptwriter-compact__preview" data-testid="scriptwriter-compact-preview">
      {preview.map((el) => {
        switch (el.type) {
          case "scene_heading":
            return <p key={el.id} className="scriptwriter-compact__preview-scene-heading">{el.text}</p>;
          case "action":
            return <p key={el.id} className="scriptwriter-compact__preview-action">{el.text}</p>;
          case "character":
            return <p key={el.id} className="scriptwriter-compact__preview-character">{el.text}</p>;
          case "parenthetical":
            return <p key={el.id} className="scriptwriter-compact__preview-parenthetical">{el.text}</p>;
          case "dialogue":
            return <p key={el.id} className="scriptwriter-compact__preview-dialogue">{el.text}</p>;
          case "transition":
            return <p key={el.id} className="scriptwriter-compact__preview-transition">{el.text}</p>;
          default:
            return el.text ? <p key={el.id} className="scriptwriter-compact__preview-action">{el.text}</p> : null;
        }
      })}
      {elements.length > preview.length ? (
        <p className="scriptwriter-compact__preview-empty">… {elements.length - preview.length} more elements</p>
      ) : null}
    </div>
  );
}

export function ScriptwriterCompactView({ projectId, onOpenFull }: Props) {
  const [bundle, setBundle] = useState<StudioBundle | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const result = (await api.scriptwriter.studio(projectId)) as unknown as StudioBundle;
      setBundle(result);
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
      .scriptwriter.studio(projectId)
      .then((result) => {
        if (cancelled) return;
        setBundle(result as unknown as StudioBundle);
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

  const doc = bundle?.document;
  const stats = bundle?.stats;
  const elements = (doc?.elements || []) as ScriptElement[];
  const isEmpty = !doc || elements.length === 0;

  return (
    <div className="scriptwriter-compact" data-testid="scriptwriter-compact">
      {busy ? (
        <div className="scriptwriter-compact__state" aria-hidden="true">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="scriptwriter-compact__skeleton-line" />
          ))}
        </div>
      ) : error ? (
        <div className="scriptwriter-compact__state scriptwriter-compact__state--error" data-testid="scriptwriter-compact-error">
          <strong>Script could not load</strong>
          <p>{error}</p>
          <button type="button" className="scriptwriter-compact__actions-button primary" onClick={() => void refresh()}>
            Retry
          </button>
        </div>
      ) : isEmpty ? (
        <div className="scriptwriter-compact__state" data-testid="scriptwriter-compact-empty">
          <strong>No script yet.</strong>
          <p>Start writing your screenplay in the full Script Writer.</p>
          <button
            type="button"
            className="scriptwriter-compact__actions-button primary"
            data-testid="scriptwriter-compact-start"
            onClick={() => onOpenFull?.()}
          >
            Start Writing
          </button>
        </div>
      ) : (
        <>
          <div className="scriptwriter-compact__header">
            <div>
              <h3 className="scriptwriter-compact__title">{doc?.title || "Untitled Script"}</h3>
              <div className="scriptwriter-compact__stats">
                <span className="scriptwriter-compact__stat">{(stats?.pagesEstimated ?? 0).toFixed(1)} pages</span>
                <span className="scriptwriter-compact__stat">{stats?.scenes ?? 0} scenes</span>
                <span className="scriptwriter-compact__stat">{stats?.words ?? 0} words</span>
                {stats?.runtimeMinutesEstimated ? (
                  <span className="scriptwriter-compact__stat">~{Math.round(stats.runtimeMinutesEstimated)} min</span>
                ) : null}
                {doc?.updatedAt ? (
                  <span className="scriptwriter-compact__stat">Saved {formatLastSaved(doc.updatedAt)}</span>
                ) : null}
              </div>
            </div>
          </div>
          <ScreenplayPreview elements={elements} />
          <div className="scriptwriter-compact__actions">
            <button
              type="button"
              className="primary"
              data-testid="scriptwriter-compact-open-full"
              onClick={() => onOpenFull?.()}
            >
              Open Full Script Writer
            </button>
            <button type="button" onClick={() => onOpenFull?.()}>
              Continue Writing
            </button>
          </div>
        </>
      )}
    </div>
  );
}
