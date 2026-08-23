import { useEffect, useState } from "react";
import { apiUrl } from "../runtime/apiBase";
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

function stateClass(state: string): string {
  if (state === "HEALTHY" || state === "ONLINE") return "state-ok";
  if (state === "DEGRADED" || state === "DEGRADED" || state === "PROXY_TIMEOUT") return "state-warn";
  return "state-error";
}

export function DiagnosticsPage() {
  const [result, setResult] = useState<DiagnosticsResult | null>(null);
  const [running, setRunning] = useState(false);

  const runTrace = async () => {
    setRunning(true);
    try {
      const res = await fetch(apiUrl("/api/diagnostics/run"));
      const data = await res.json();
      setResult(data);
    } catch (err) {
      console.error("Diagnostics trace failed", err);
    } finally {
      setRunning(false);
    }
  };

  useEffect(() => { void runTrace(); }, []);

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

      {result && (
        <>
          <section className="diagnostics-classification">
            <h2>Status: <span className={stateClass(result.classification.faultDomain)}>{result.classification.faultDomain}</span></h2>
            <p className="muted">{result.classification.evidence}</p>
            <p className="muted">Confidence: {result.classification.confidence} · {result.totalMs}ms total</p>
          </section>

          <section className="diagnostics-layers">
            <h3>Studio API</h3>
            <div className="diagnostics-grid">
              <div className={`diagnostics-card ${result.layers.apiDirect.tcp.listening ? "state-ok" : "state-error"}`}>
                <strong>TCP :8758</strong>
                <span>{result.layers.apiDirect.tcp.listening ? "Listening" : "Not listening"}</span>
                <span className="muted">{result.layers.apiDirect.healthz.elapsedMs}ms</span>
              </div>
              <div className={`diagnostics-card ${result.layers.apiDirect.healthz.status === 200 ? "state-ok" : "state-error"}`}>
                <strong>/healthz</strong>
                <span>{result.layers.apiDirect.healthz.status ?? "—"}</span>
                <span className="muted">{result.layers.apiDirect.healthz.elapsedMs}ms</span>
              </div>
              <div className={`diagnostics-card ${result.layers.apiDirect.health.status === 200 ? "state-ok" : "state-warn"}`}>
                <strong>/api/health</strong>
                <span>{result.layers.apiDirect.health.status ?? "—"}</span>
                <span className="muted">{result.layers.apiDirect.health.elapsedMs}ms</span>
              </div>
            </div>
          </section>

          <section className="diagnostics-layers">
            <h3>Providers</h3>
            <div className="diagnostics-grid">
              <div className={`diagnostics-card ${result.layers.providers.comfyui.state === "ONLINE" ? "state-ok" : "state-error"}`}>
                <strong>ComfyUI</strong>
                <span>{result.layers.providers.comfyui.state}</span>
                <span className="muted">:{result.layers.providers.comfyui.port}</span>
                {result.layers.providers.comfyui.error && <span className="muted">{result.layers.providers.comfyui.error}</span>}
              </div>
            </div>
          </section>

          <section className="diagnostics-layers">
            <h3>Ports</h3>
            <div className="diagnostics-grid">
              {result.layers.ports.map((p) => (
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
