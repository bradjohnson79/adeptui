import { useEffect, useState, type CSSProperties } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { ComfyHealth } from "../capabilities";

type Diagnostics = {
  comfyui?: { connected?: boolean; version?: string | null; status?: string; message?: string };
  gpu?: { name?: string | null; availableGb?: number | null; currentGb?: number | null };
  nodeInventory?: { installed?: number; missingVsRegistry?: number };
  modelInventory?: { wan?: boolean; ltx?: boolean; ltx_2_5?: boolean; zimage?: boolean; icLora?: boolean };
  queue?: {
    comfyRunning?: number;
    comfyWaiting?: number;
    studioRunning?: number;
    studioWaiting?: number;
  };
  averageRenderSeconds?: Record<string, number | null>;
  vram?: { currentGb?: number | null; availableGb?: number | null; peakGb?: number | null };
  health?: string;
  wave6WiringUnlocked?: boolean;
  wave6ProductionActivationUnlocked?: boolean;
  wave6MediaExecutionUnlocked?: boolean;
  checkedAt?: string;
};

type CertifiedEntry = {
  workflowId?: string;
  workflowKey?: string;
  workflowVersion?: string;
  status?: string;
  productionReady?: boolean;
};

/** Group LTX 2.5 model components by generator for the Model Readiness section. */
function generatorReadiness(comfy: ComfyHealth | null) {
  if (!comfy || !comfy.models) return [];
  const byGen: Record<string, { id: string; label: string; missing: ComfyHealth["models"][number][]; ready: boolean }> = {};
  const add = (id: string, label: string, componentId: string) => {
    const m = comfy.models.find((x) => x.componentId === componentId);
    if (!m) return;
    if (!byGen[id]) byGen[id] = { id, label, missing: [], ready: true };
    if (!m.present) {
      byGen[id].missing.push(m);
      byGen[id].ready = false;
    }
  };
  add("ltx_2_5", "LTX 2.5", "ltx_2_5_checkpoint");
  add("ltx_2_5", "LTX 2.5", "ltx_2_5_text_encoder");
  add("ltx_2_5", "LTX 2.5", "ltx_2_5_video_vae");
  add("wan", "WAN", "wan_models");
  add("zimage", "Z-Image", "zimage_models");
  add("ltx_23", "LTX 2.3", "ltx_checkpoint");
  return Object.values(byGen);
}

export default function VideoRuntimeDiagnostics() {
  const [data, setData] = useState<Diagnostics | null>(null);
  const [registry, setRegistry] = useState<CertifiedEntry[]>([]);
  const [comfy, setComfy] = useState<ComfyHealth | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [d, reg, ch] = await Promise.all([
          api.videoRuntimeDiagnostics() as Promise<Diagnostics>,
          api.videoRuntimeCertifiedRegistry().catch(() => ({ entries: [] as CertifiedEntry[] })),
          api.comfyHealth().catch(() => null),
        ]);
        if (!cancelled) {
          setData(d);
          setRegistry((reg as { entries?: CertifiedEntry[] }).entries || []);
          setComfy(ch as ComfyHealth | null);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    const id = window.setInterval(() => {
      void api.videoRuntimeDiagnostics().then((d) => setData(d as Diagnostics)).catch(() => undefined);
      void api
        .videoRuntimeCertifiedRegistry()
        .then((r) => setRegistry((r as { entries?: CertifiedEntry[] }).entries || []))
        .catch(() => undefined);
      void api.comfyHealth().then((c) => setComfy(c as ComfyHealth | null)).catch(() => undefined);
    }, 8000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  // Layered overall verdict: Runtime healthy + no required-missing → HEALTHY;
  // required-missing or runtime offline → DEGRADED/OFFLINE; optional-missing only → PARTIAL.
  const runtimeOk = Boolean(data?.comfyui?.connected);
  const requiredMissing = comfy?.missingRequiredModelComponentIds?.length ?? 0;
  const optionalMissing = (comfy?.missingModelComponentIds?.length ?? 0) - requiredMissing;
  const overallVerdict = !runtimeOk
    ? "OFFLINE"
    : requiredMissing > 0
      ? "DEGRADED"
      : optionalMissing > 0
        ? "PARTIAL"
        : "HEALTHY";
  const verdictTone =
    overallVerdict === "HEALTHY" ? "ok" : overallVerdict === "PARTIAL" ? "warn" : "bad";

  return (
    <main
      className="video-runtime-diagnostics"
      data-testid="video-runtime-diagnostics"
      style={{
        maxWidth: 880,
        margin: "0 auto",
        padding: "2rem 1.25rem 4rem",
        color: "var(--aurora-text, #e8e6e3)",
        fontFamily: "var(--font-body, Georgia, serif)",
      }}
    >
      <p style={{ marginBottom: "0.5rem" }}>
        <Link to="/" style={{ color: "inherit", opacity: 0.75 }}>
          ← Home
        </Link>
      </p>
      <h1 style={{ fontWeight: 500, letterSpacing: "-0.02em", marginBottom: "0.25rem" }}>
        Video Runtime
      </h1>
      <p style={{ opacity: 0.7, marginBottom: "1.75rem", maxWidth: 52 + "ch" }}>
        Operator diagnostics for ComfyUI, VRAM, Certified Workflow Library, and queue health
        (M41 4.1B). Not a generation UI.
      </p>

      {loading && <p>Loading diagnostics…</p>}
      {error && (
        <p role="alert" style={{ color: "var(--aurora-danger, #c45)" }}>
          {error}
        </p>
      )}

      {data && (
        <div
          style={{
            display: "grid",
            gap: "1.25rem",
            gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
          }}
        >
          {/* Overall verdict — creator-facing summary */}
          <section
            style={{ ...card, gridColumn: "1 / -1" }}
            data-testid="runtime-overall-verdict"
          >
            <h2 style={h2}>Overall Studio Readiness</h2>
            <p style={{ fontSize: "1.35rem", margin: 0 }}>
              <span
                data-testid="runtime-overall-verdict-status"
                style={{
                  color:
                    verdictTone === "ok"
                      ? "var(--aurora-success, #6c9)"
                      : verdictTone === "warn"
                        ? "var(--aurora-warn, #ec8)"
                        : "var(--aurora-danger, #c45)",
                }}
              >
                {overallVerdict}
              </span>
            </p>
            <p style={muted}>
              {overallVerdict === "HEALTHY" && "Runtime, hardware, and all configured generators are ready."}
              {overallVerdict === "PARTIAL" && `Runtime is healthy, but ${optionalMissing} optional/generator component(s) incomplete. Affected generators are blocked; others remain usable.`}
              {overallVerdict === "DEGRADED" && `${requiredMissing} required model component(s) missing. Runtime cannot generate until installed.`}
              {overallVerdict === "OFFLINE" && "ComfyUI runtime is offline. Start ComfyUI, then refresh."}
            </p>
          </section>

          {/* RUNTIME — ComfyUI reachability + node catalog (NOT model readiness) */}
          <section style={card} data-testid="runtime-comfyui">
            <h2 style={h2}>Runtime · ComfyUI</h2>
            <p>
              {runtimeOk ? "● Healthy" : "● Offline"}
              {data.comfyui?.version ? ` · v${data.comfyui.version}` : ""}
            </p>
            <p style={muted}>{data.comfyui?.message}</p>
            <p style={muted}>
              Node catalogue: {comfy?.nodeCatalogAvailable ? "available" : "loading/unavailable"}
              {comfy?.nodeTypeCount != null ? ` · ${comfy.nodeTypeCount} types` : ""}
            </p>
          </section>

          {/* HARDWARE — GPU + VRAM */}
          <section style={card} data-testid="runtime-hardware">
            <h2 style={h2}>Hardware · GPU</h2>
            <p>{data.gpu?.name || "Unknown"}</p>
            <p>
              {data.gpu?.availableGb != null
                ? `${data.gpu.availableGb} GB available`
                : "Available VRAM unknown"}
            </p>
          </section>

          {/* MODEL READINESS — per-generator, expandable missing deps */}
          <section style={{ ...card, gridColumn: "1 / -1" }} data-testid="runtime-model-readiness">
            <h2 style={h2}>Model Readiness</h2>
            <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: "0.5rem" }}>
              {generatorReadiness(comfy).map((g) => (
                <li key={g.id} data-testid={`generator-readiness-${g.id}`}>
                  <details>
                    <summary style={{ cursor: "pointer" }}>
                      <strong>{g.label}</strong>{" "}
                      {g.ready
                        ? "✓ Ready"
                        : `⚠ Incomplete · ${g.missing.length} missing`}
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
                                border: "1px solid rgba(255,255,255,0.2)",
                                borderRadius: "0.25rem",
                                marginRight: "0.4rem",
                              }}
                            >
                              {m.dependencyType || "MODEL"}
                            </span>
                            <code>{m.filename || m.name}</code>
                            {m.expectedPath && (
                              <span style={muted}> · {m.expectedPath}</span>
                            )}
                          </li>
                        ))}
                      </ul>
                    )}
                    {g.missing.length > 0 && (
                      <p style={{ marginTop: "0.4rem" }}>
                        <Link to="/source-manager" style={{ color: "inherit" }}>
                          [Open Model Manager]
                        </Link>
                      </p>
                    )}
                  </details>
                </li>
              ))}
            </ul>
          </section>

          <section style={card}>
            <h2 style={h2}>Node Inventory</h2>
            <p>{data.nodeInventory?.installed ?? 0} installed</p>
            <p>{data.nodeInventory?.missingVsRegistry ?? 0} missing vs registry</p>
          </section>

          <section style={card}>
            <h2 style={h2}>Queue</h2>
            <p>
              Comfy {data.queue?.comfyRunning ?? 0} running · {data.queue?.comfyWaiting ?? 0}{" "}
              waiting
            </p>
            <p>
              Studio {data.queue?.studioRunning ?? 0} running · {data.queue?.studioWaiting ?? 0}{" "}
              waiting
            </p>
          </section>

          <section style={card}>
            <h2 style={h2}>Average Render Time</h2>
            <ul style={{ listStyle: "none", padding: 0, margin: 0, lineHeight: 1.7 }}>
              <li>LTX: {fmtSec(data.averageRenderSeconds?.ltx)}</li>
              <li>LTX 2.5: {fmtSec(data.averageRenderSeconds?.ltx_2_5)}</li>
              <li>WAN: {fmtSec(data.averageRenderSeconds?.wan)}</li>
              <li>fal: {fmtSec(data.averageRenderSeconds?.fal)}</li>
            </ul>
          </section>

          <section style={card}>
            <h2 style={h2}>VRAM</h2>
            <p>
              Current:{" "}
              {data.vram?.currentGb != null ? `${data.vram.currentGb} GB` : "—"}
            </p>
            <p>
              Available:{" "}
              {data.vram?.availableGb != null ? `${data.vram.availableGb} GB` : "—"}
            </p>
          </section>

          <section style={card}>
            <h2 style={h2}>Legacy Health</h2>
            <p style={{ fontSize: "1.15rem" }}>{data.health || "Unknown"}</p>
            <p style={muted}>
              Wave 6 wiring:{" "}
              {data.wave6WiringUnlocked ? "unlocked" : "blocked"}
            </p>
            <p style={muted}>
              Wave 6 production activation:{" "}
              {data.wave6ProductionActivationUnlocked
                ? "unlocked (4.1B GO)"
                : "blocked until CERTIFIED workflows + 4.1B Full GO"}
            </p>
            <p style={muted}>{data.checkedAt}</p>
          </section>

          <section style={{ ...card, gridColumn: "1 / -1" }} data-testid="certified-workflow-registry">
            <h2 style={h2}>Certified Workflow Library</h2>
            <p style={muted}>
              Production Ready = status CERTIFIED with Certification Record only.
            </p>
            <ul style={{ listStyle: "none", padding: 0, margin: "0.75rem 0 0", lineHeight: 1.7 }}>
              {registry.length === 0 && <li style={muted}>Registry unavailable</li>}
              {registry.map((w) => (
                <li key={w.workflowKey || w.workflowId}>
                  <code>{w.workflowId}</code> {w.workflowKey}@{w.workflowVersion} —{" "}
                  <strong>{w.status}</strong>
                  {w.productionReady ? " · Production Ready" : ""}
                </li>
              ))}
            </ul>
          </section>

          {/* Technical Information — raw JSON behind expandable details */}
          <section style={{ ...card, gridColumn: "1 / -1" }} data-testid="runtime-technical-details">
            <details>
              <summary style={{ cursor: "pointer", ...h2 }}>Technical Information</summary>
              <pre style={{ fontSize: "0.75rem", overflowX: "auto", opacity: 0.85 }}>
                {JSON.stringify({ diagnostics: data, comfyHealth: comfy }, null, 2)}
              </pre>
            </details>
          </section>
        </div>
      )}
    </main>
  );
}

function fmtSec(v: number | null | undefined) {
  if (v == null) return "—";
  const m = Math.floor(v / 60);
  const s = Math.round(v % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

const card: CSSProperties = {
  borderTop: "1px solid rgba(255,255,255,0.12)",
  paddingTop: "0.85rem",
};

const h2: CSSProperties = {
  fontSize: "0.85rem",
  textTransform: "uppercase",
  letterSpacing: "0.08em",
  opacity: 0.65,
  margin: "0 0 0.5rem",
  fontWeight: 500,
};

const muted: CSSProperties = { opacity: 0.65, fontSize: "0.9rem" };
