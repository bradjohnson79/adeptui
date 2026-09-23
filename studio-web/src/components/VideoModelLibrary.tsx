import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { ComfyHealth } from "../capabilities";
import type { ModelDescriptor } from "../modelRegistry/contracts";
import { modelMark } from "./modelMark";

/** Canonical local video generators in Adept UI v1.1. */
const CANONICAL_LOCAL_VIDEO_IDS = new Set([
  "minimax-h3",
  "ltx-2.5",
  "ltx-2.5-distilled",
  "ltx-2.5-full",
  "ltx-2.5-comfy",
]);

function isCanonicalLocalVideoModel(model: ModelDescriptor): boolean {
  if (model.locality !== "local") return false;
  if (CANONICAL_LOCAL_VIDEO_IDS.has(model.id)) return true;
  return model.id.startsWith("minimax-h3") || model.id.startsWith("ltx-2.5");
}

export function VideoModelLibrary() {
  const [models, setModels] = useState<ModelDescriptor[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [comfy, setComfy] = useState<ComfyHealth | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await api.productionControlModels("video");
      const all = (res.models || []) as ModelDescriptor[];
      setModels(all.filter(isCanonicalLocalVideoModel));
      setMessage(null);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Fetch structured ComfyUI health for the per-generator Model Readiness section.
  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const c = await api.comfyHealth();
        if (alive) setComfy(c as ComfyHealth | null);
      } catch {
        if (alive) setComfy(null);
      }
    };
    void tick();
    const id = window.setInterval(() => void tick(), 10000);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, []);

  return (
    <section className="panel" data-testid="video-model-library" aria-label="Video Model Library">
      <h3>Video Models</h3>
      <p className="scene-meta">
        Local video generation in Adept UI v1.1 uses MiniMax H3 and LTX 2.5.
        Other local engines are retired and are not production choices.
      </p>
      {message ? (
        <p className="scene-meta" role="status" data-testid="video-model-library-message">
          {message}{" "}
          <Link to="/source-manager">Open Model Manager</Link>
        </p>
      ) : null}
      <ul className="video-model-library-list" style={{ listStyle: "none", padding: 0, margin: "0.75rem 0" }}>
        {models.map((row) => {
          const mark = modelMark(row.executable, row.readiness === "Ready");
          const statusText = row.readiness || row.capabilityLabel || "Unknown";
          return (
            <li
              key={row.id}
              className="video-model-library-item"
              data-testid={`video-model-${row.id}`}
              data-status={statusText}
              data-installed={row.executable ? "true" : "false"}
              style={{
                borderTop: "1px solid var(--border, #333)",
                padding: "0.75rem 0",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap" }}>
                <div>
                  <strong>
                    {mark} {row.label}
                  </strong>
                  <div className="scene-meta" data-testid={`video-model-status-${row.id}`}>
                    Status: {statusText}
                    {row.executionClass ? ` · ${row.executionClass.replace(/_/g, " ")}` : ""}
                    {row.estimatedVramGb != null ? ` · ~${row.estimatedVramGb} GB VRAM` : ""}
                  </div>
                  {row.doesNotSupport?.length ? (
                    <div className="scene-meta">Limitations: {row.doesNotSupport.join(", ")}</div>
                  ) : null}
                </div>
              </div>
            </li>
          );
        })}
      </ul>

      {/* Per-generator Model Readiness from structured ComfyHealth. Shows exact
          missing dependencies (filename + expected path + type) instead of a
          vague count, with an [Open Model Manager] action. */}
      {comfy?.models && (
        <div
          style={{ marginTop: "1.25rem", borderTop: "1px solid var(--border, #333)", paddingTop: "0.85rem" }}
          data-testid="video-model-readiness"
        >
          <h4 style={{ margin: "0 0 0.5rem", fontSize: "0.85rem", textTransform: "uppercase", letterSpacing: "0.08em", opacity: 0.7 }}>
            Model Readiness
          </h4>
          <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: "0.5rem" }}>
            {generatorReadinessRows(comfy).map((g) => (
              <li key={g.id} data-testid={`generator-readiness-${g.id}`}>
                <details>
                  <summary style={{ cursor: "pointer" }}>
                    <strong>{g.label}</strong>{" "}
                    {g.ready ? (
                      <span style={{ color: "var(--aurora-success, #6c9)" }}>READY</span>
                    ) : (
                      <span style={{ color: "var(--aurora-warn, #ec8)" }}>
                        INCOMPLETE · {g.missing.length} missing
                      </span>
                    )}
                  </summary>
                  {g.missing.length > 0 && (
                    <ul style={{ listStyle: "none", padding: "0.5rem 0 0 1.25rem", margin: 0, lineHeight: 1.7 }}>
                      {g.missing.map((m) => (
                        <li key={m.componentId} data-testid={`missing-dep-${m.componentId}`}>
                          <span
                            style={{
                              display: "inline-block",
                              padding: "0.05rem 0.35rem",
                              fontSize: "0.7rem",
                              border: "1px solid var(--border, #444)",
                              borderRadius: "0.25rem",
                              marginRight: "0.4rem",
                            }}
                          >
                            {m.dependencyType || "MODEL"}
                          </span>
                          <code>{m.filename || m.name}</code>
                          {m.expectedPath && (
                            <span style={{ opacity: 0.65 }}> · {m.expectedPath}</span>
                          )}
                        </li>
                      ))}
                      <li style={{ marginTop: "0.4rem" }}>
                        <Link to="/source-manager" style={{ color: "inherit" }}>
                          [Open Model Manager]
                        </Link>
                      </li>
                    </ul>
                  )}
                </details>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

/** Group ComfyHealth model components by canonical v1.1 local video generator. */
function generatorReadinessRows(comfy: ComfyHealth) {
  const byGen: { id: string; label: string; missing: ComfyHealth["models"][number][]; ready: boolean }[] = [];
  const add = (id: string, label: string, componentId: string) => {
    const m = comfy.models.find((x) => x.componentId === componentId);
    if (!m) return;
    let gen = byGen.find((g) => g.id === id);
    if (!gen) {
      gen = { id, label, missing: [], ready: true };
      byGen.push(gen);
    }
    if (!m.present) {
      gen.missing.push(m);
      gen.ready = false;
    }
  };
  add("ltx_2_5", "LTX 2.5", "ltx_2_5_checkpoint");
  add("ltx_2_5", "LTX 2.5", "ltx_2_5_text_encoder");
  add("ltx_2_5", "LTX 2.5", "ltx_2_5_video_vae");
  return byGen;
}
