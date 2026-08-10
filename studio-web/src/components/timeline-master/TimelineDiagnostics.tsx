import { useEffect, useState } from "react";
import type { DirectorSelection } from "../../directorSelection";
import type { PreviewComposition } from "./TimelinePreviewComposer";

/**
 * TimelineDiagnostics — developer-only overlay (TIMELINE_STATE_DIAGNOSTICS).
 * Gated behind `?timeline_diag=1` or localStorage flag so it never appears for
 * creators. Shows the authoritative selection, generation/composition state,
 * and a render counter to surface rerender storms.
 */
export function TimelineDiagnostics({
  selection,
  composition,
  reloadKey,
  saveError,
}: {
  selection: DirectorSelection;
  composition: PreviewComposition | null;
  reloadKey: number;
  saveError: string | null;
}) {
  const [enabled, setEnabled] = useState(false);
  const [renderCount, setRenderCount] = useState(0);

  useEffect(() => {
    const url = new URLSearchParams(window.location.search);
    const flag = url.get("timeline_diag") === "1" || localStorage.getItem("timeline_diag") === "1";
    setEnabled(flag);
  }, []);

  useEffect(() => {
    if (enabled) setRenderCount((c) => c + 1);
  });

  if (!enabled) return null;

  return (
    <div
      className="timeline-diagnostics"
      data-testid="timeline-diagnostics"
      style={{
        position: "fixed",
        bottom: 8,
        right: 8,
        zIndex: 9999,
        background: "rgba(0,0,0,0.82)",
        color: "#7eb6ff",
        padding: "8px 10px",
        fontSize: "11px",
        fontFamily: "monospace",
        borderRadius: 6,
        maxWidth: 320,
        pointerEvents: "none",
      }}
    >
      <div>renders: {renderCount} · reloadKey: {reloadKey}</div>
      <div>
        selection: {selection?.kind ?? "null"}
        {selection?.id ? ` #${selection.id}` : ""}
      </div>
      <div>composition: {composition ? composition.kind : "—"}</div>
      {saveError ? <div style={{ color: "#ffb37a" }}>saveError: {saveError}</div> : null}
    </div>
  );
}
