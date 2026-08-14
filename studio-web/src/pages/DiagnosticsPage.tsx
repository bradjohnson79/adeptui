import { useEffect, useState } from "react";
import { apiUrl } from "../runtime/apiBase";
import { isDiagnosticsResult } from "./diagnosticsResult";
import "./DiagnosticsPage.css";

type PortInfo = {
  port: number;
  listening: boolean;
  pid: number | null;
  processName: string | null;
};

type HttpCheck = {
  status: number | null;
  elapsedMs: number | null;
  error?: string;
};

type ApiLayer = {
  tcp: PortInfo;
  healthz: HttpCheck;
  health: HttpCheck;
};

type ProviderInfo = {
  state: string;
  port: number;
  listening: boolean;
  httpOk?: boolean;
  error?: string;
};

type Classification = {
  faultDomain: string;
  confidence: string;
  evidence: string;
};

type DiagnosticsResult = {
  timestamp: string;
  layers: {
    ports: PortInfo[];
    apiDirect: ApiLayer;
    proxy: { healthz: HttpCheck; health: HttpCheck };
    providers: { comfyui: ProviderInfo };
    productionControl: { available: boolean; responseMs: number | null };
  };
  totalMs: number;
  classification: Classification;
};

function stateClass(state: string | undefined): string {
  if (state === "HEALTHY" || state === "ONLINE") return "state-ok";
  if (state === "DEGRADED" || state === "PROXY_TIMEOUT") return "state-warn";
  return "state-error";
}

export function DiagnosticsPage() {
  const [result, setResult] = useState<DiagnosticsResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  const runTrace = async () => {
    setRunning(true);
    setError(null);
    try {
      const res = await fetch(apiUrl("/api/diagnostics/run"));
      let data: unknown = null;
      try {
        data = await res.json();
      } catch {
        data = null;
      }
      if (!res.ok || !isDiagnosticsResult(data)) {
        setResult(null);
        const statusHint = res.ok ? "unexpected response" : `HTTP ${res.status}`;
        const message =
          data && typeof data === "object" && "error" in data && typeof (data as { error: unknown }).error === "string"
            ? (data as { error: string }).error
            : data && typeof data === "object" && "message" in data && typeof (data as { message: unknown }).message === "string"
              ? (data as { message: string }).message
              : statusHint;
        setError(`Diagnostics could not complete (${message}). The API did not return a full result.`);
        return;
      }
      setResult(data as DiagnosticsResult);
    } catch (err) {
      console.error("Diagnostics trace failed", err);
      setResult(null);
      setError(err instanceof Error ? err.message : "Diagnostics trace failed.");
    } finally {
      setRunning(false);
    }
  };

  useEffect(() => { void runTrace(); }, []);

  const faultDomain = result?.classification?.faultDomain;
  const evidence = result?.classification?.evidence;
  const confidence = result?.classification?.confidence;
  const layers = result?.layers;
  const apiDirect = layers?.apiDirect;
  const proxy = layers?.proxy;
  const comfy = layers?.providers?.comfyui;
  const ports = layers?.ports;

  return (
    <div className="diagnostics-page">
      <header className="diagnostics-header">
        <h1>System Diagnostics</h1>
        <div className="diagnostics-actions">
          <button onClick={runTrace} disabled={running}>
            {running ? "Running…" : "Run Diagnostic Trace"}
          </button>
          {result && (
            <button onClick={() => {
              const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url; a.download = `adept-diagnostics-${Date.now()}.json`;
              a.click(); URL.revokeObjectURL(url);
            }}>
              Export Report
            </button>
          )}
        </div>
      </header>

      {error && (
        <section className="diagnostics-error" role="alert">
          <h2>Diagnostics unavailable</h2>
          <p>{error}</p>
        </section>
      )}

      {result && (
        <>
          <section className="diagnostics-classification">
            <h2>Status: <span className={stateClass(faultDomain)}>{faultDomain ?? "Unknown"}</span></h2>
            <p className="muted">{evidence}</p>
            <p className="muted">Confidence: {confidence} · {result.totalMs}ms total</p>
          </section>

          <section className="diagnostics-layers">
            <h3>Studio API</h3>
            <div className="diagnostics-grid">
              <div className={`diagnostics-card ${apiDirect?.tcp?.listening ? "state-ok" : "state-error"}`}>
                <strong>TCP :8758</strong>
                <span>{apiDirect?.tcp?.listening ? "Listening" : "Not listening"}</span>
                <span className="muted">{apiDirect?.healthz?.elapsedMs}ms</span>
              </div>
              <div className={`diagnostics-card ${apiDirect?.healthz?.status === 200 ? "state-ok" : "state-error"}`}>
                <strong>/healthz</strong>
                <span>{apiDirect?.healthz?.status ?? "—"}</span>
                <span className="muted">{apiDirect?.healthz?.elapsedMs}ms</span>
              </div>
              <div className={`diagnostics-card ${apiDirect?.health?.status === 200 ? "state-ok" : "state-warn"}`}>
                <strong>/api/health</strong>
                <span>{apiDirect?.health?.status ?? "—"}</span>
                <span className="muted">{apiDirect?.health?.elapsedMs}ms</span>
              </div>
            </div>
          </section>

          {proxy?.healthz?.status !== null && proxy?.healthz?.status !== undefined && (
            <section className="diagnostics-layers">
              <h3>Proxy (8760)</h3>
              <div className="diagnostics-grid">
                <div className={`diagnostics-card ${proxy?.healthz?.status === 200 ? "state-ok" : "state-error"}`}>
                  <strong>/healthz (proxied)</strong>
                  <span>{proxy?.healthz?.status ?? "—"}</span>
                  <span className="muted">{proxy?.healthz?.elapsedMs}ms</span>
                </div>
                <div className={`diagnostics-card ${proxy?.health?.status === 200 ? "state-ok" : "state-warn"}`}>
                  <strong>/api/health (proxied)</strong>
                  <span>{proxy?.health?.status ?? "—"}</span>
                  <span className="muted">{proxy?.health?.elapsedMs}ms</span>
                </div>
              </div>
            </section>
          )}

          <section className="diagnostics-layers">
            <h3>Providers</h3>
            <div className="diagnostics-grid">
              <div className={`diagnostics-card ${comfy?.state === "ONLINE" ? "state-ok" : "state-error"}`}>
                <strong>ComfyUI</strong>
                <span>{comfy?.state}</span>
                <span className="muted">:{comfy?.port}</span>
                {comfy?.error && <span className="muted">{comfy.error}</span>}
              </div>
            </div>
          </section>

          <section className="diagnostics-layers">
            <h3>Ports</h3>
            <div className="diagnostics-grid">
              {(ports ?? []).map((p) => (
                <div key={p.port} className={`diagnostics-card ${p.listening ? "state-ok" : "state-error"}`}>
                  <strong>:{p.port}</strong>
                  <span>{p.processName || "—"}</span>
                  <span className="muted">{p.listening ? `PID ${p.pid}` : "Not listening"}</span>
                </div>
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
}