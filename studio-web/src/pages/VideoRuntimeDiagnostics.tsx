import { useEffect, useState, type CSSProperties } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

type Diagnostics = {
  comfyui?: { connected?: boolean; version?: string | null; status?: string; message?: string };
  gpu?: { name?: string | null; availableGb?: number | null; currentGb?: number | null };
  nodeInventory?: { installed?: number; missingVsRegistry?: number };
  modelInventory?: { wan?: boolean; ltx?: boolean; zimage?: boolean; icLora?: boolean };
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

function mark(ok: boolean | undefined) {
  if (ok === true) return "✓";
  if (ok === false) return "✗";
  return "—";
}

type CertifiedEntry = {
  workflowId?: string;
  workflowKey?: string;
  workflowVersion?: string;
  status?: string;
  productionReady?: boolean;
};

export default function VideoRuntimeDiagnostics() {
  const [data, setData] = useState<Diagnostics | null>(null);
  const [registry, setRegistry] = useState<CertifiedEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [d, reg] = await Promise.all([
          api.videoRuntimeDiagnostics() as Promise<Diagnostics>,
          api.videoRuntimeCertifiedRegistry().catch(() => ({ entries: [] as CertifiedEntry[] })),
        ]);
        if (!cancelled) {
          setData(d);
          setRegistry((reg as { entries?: CertifiedEntry[] }).entries || []);
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
    }, 8000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

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
          <section style={card}>
            <h2 style={h2}>ComfyUI</h2>
            <p>
              {data.comfyui?.connected ? "✓ Connected" : "✗ Disconnected"}
              {data.comfyui?.version ? ` · ${data.comfyui.version}` : ""}
            </p>
            <p style={muted}>{data.comfyui?.message}</p>
          </section>

          <section style={card}>
            <h2 style={h2}>GPU</h2>
            <p>{data.gpu?.name || "Unknown"}</p>
            <p>
              {data.gpu?.availableGb != null
                ? `${data.gpu.availableGb} GB available`
                : "Available VRAM unknown"}
            </p>
          </section>

          <section style={card}>
            <h2 style={h2}>Node Inventory</h2>
            <p>{data.nodeInventory?.installed ?? 0} installed</p>
            <p>{data.nodeInventory?.missingVsRegistry ?? 0} missing vs registry</p>
          </section>

          <section style={card}>
            <h2 style={h2}>Model Inventory</h2>
            <ul style={{ listStyle: "none", padding: 0, margin: 0, lineHeight: 1.7 }}>
              <li>WAN {mark(data.modelInventory?.wan)}</li>
              <li>LTX {mark(data.modelInventory?.ltx)}</li>
              <li>Z-Image {mark(data.modelInventory?.zimage)}</li>
              <li>IC-LoRA {mark(data.modelInventory?.icLora)}</li>
            </ul>
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
            <h2 style={h2}>Health</h2>
            <p style={{ fontSize: "1.35rem" }}>{data.health || "Unknown"}</p>
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
