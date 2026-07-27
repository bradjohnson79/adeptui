import { useState } from "react";
import { api } from "../../api";

type Summary = {
  recommendedModel: string;
  why: string;
  confidence: number;
  audioPlan: string;
  knownLimitations: string[];
  preflight: string;
  warnings: string[];
  advanced: Record<string, unknown>;
};

/** Filmmaker-friendly Model Intelligence summary (M3.0e). */
export function ModelIntelligencePanel({ projectId }: { projectId: string }) {
  const [prompt, setPrompt] = useState(
    "Image-to-video shot. No background music. No score. Preserve intended dialogue.",
  );
  const [summary, setSummary] = useState<Summary | null>(null);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await api.milFilmmakerSummary(prompt);
      setSummary(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Model Intelligence unavailable");
      setSummary(null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="mil-panel" aria-label="Model Intelligence" style={{ marginTop: "0.75rem" }}>
      <h3 style={{ margin: "0 0 0.35rem", fontSize: "0.95rem" }}>Model Intelligence</h3>
      <p style={{ margin: "0 0 0.5rem", opacity: 0.8, fontSize: "0.85rem" }}>
        Co-Director translates filmmaking language into model-specific generation settings.
        Project: {projectId.slice(0, 8)}…
      </p>
      <label style={{ display: "block", fontSize: "0.8rem" }}>
        Creative intent
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={3}
          style={{ width: "100%", marginTop: 4 }}
        />
      </label>
      <button type="button" className="primary" disabled={busy || !prompt.trim()} onClick={() => void run()}>
        {busy ? "Planning…" : "Recommend model"}
      </button>
      {error ? (
        <p role="alert" style={{ color: "crimson", fontSize: "0.85rem" }}>
          {error}
        </p>
      ) : null}
      {summary ? (
        <div style={{ marginTop: "0.75rem", fontSize: "0.9rem", lineHeight: 1.45 }}>
          <p>
            <strong>Recommended model:</strong> {summary.recommendedModel || "—"}
          </p>
          <p>
            <strong>Why:</strong> {summary.why}
          </p>
          <p>
            <strong>Confidence:</strong> {Math.round((summary.confidence || 0) * 100)}%
          </p>
          <p>
            <strong>Audio plan:</strong> {summary.audioPlan || "—"}
          </p>
          {summary.knownLimitations?.length ? (
            <p>
              <strong>Known limitation:</strong> {summary.knownLimitations[0]}
            </p>
          ) : null}
          <p>
            <strong>Preflight:</strong> {summary.preflight}
          </p>
          <button type="button" onClick={() => setAdvancedOpen((v) => !v)}>
            {advancedOpen ? "Hide advanced" : "Show compiled prompt & rules"}
          </button>
          {advancedOpen ? (
            <pre
              style={{
                marginTop: 8,
                padding: 8,
                overflow: "auto",
                maxHeight: 240,
                fontSize: "0.75rem",
                background: "rgba(0,0,0,0.04)",
              }}
            >
              {JSON.stringify(summary.advanced, null, 2)}
            </pre>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
