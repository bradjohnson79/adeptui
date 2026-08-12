import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { buildAiGuidedSetupPath } from "../setup/navigation";
import { InstallStatusChip } from "./install/InstallStatusChip";
import type { ComfyHealth } from "../capabilities";
import { modelMark } from "./modelMark";

type ProviderRow = {
  providerId?: string;
  label?: string;
  status?: string;
  engine?: string | null;
  installed?: boolean;
  healthy?: boolean;
  storagePath?: string;
  version?: string | null;
  supportsTextToVideo?: boolean;
  supportsImageToVideo?: boolean;
  trueLocalT2vCertified?: boolean;
  recommendedProfile?: string;
  notes?: string[];
  hfRepo?: string;
  minVramGb?: number;
  diskGb?: number;
  lastError?: string | null;
  downloadPhase?: string | null;
  downloadPercent?: number | null;
  downloadOperationId?: string | null;
};

export function VideoModelLibrary() {
  const [providers, setProviders] = useState<ProviderRow[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [benchmarks, setBenchmarks] = useState<Record<string, Record<string, unknown>>>({});
  const [comfy, setComfy] = useState<ComfyHealth | null>(null);
  const refresh = useCallback(async () => {
    const lib = await api.hunyuanLibrary();
    setProviders((lib.providers || []) as ProviderRow[]);
    const next: Record<string, Record<string, unknown>> = {};
    for (const row of lib.providers || []) {
      const id = String((row as ProviderRow).providerId || "");
      if (!id.startsWith("hunyuan-video-")) continue;
      try {
        next[id] = await api.hunyuanBenchmarkLatest(id);
      } catch {
        /* ignore */
      }
    }
    setBenchmarks(next);
  }, []);

  useEffect(() => {
    void refresh().catch((err: Error) => setMessage(err.message));
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

  // Poll while any Hunyuan install is active so status doesn't look stuck on "Not Installed"
  useEffect(() => {
    const active = providers.some((p) => {
      const s = String(p.status || "");
      return (
        p.providerId?.startsWith("hunyuan-video-") &&
        (s.startsWith("Queued") || s.startsWith("Downloading") || s === "Installing" || Boolean(p.downloadPhase && !["failed", "completed", "cancelled"].includes(String(p.downloadPhase))))
      );
    });
    if (!active) return;
    const t = window.setInterval(() => {
      void refresh().catch(() => undefined);
    }, 2500);
    return () => window.clearInterval(t);
  }, [providers, refresh]);

  const projectIdFromPath = window.location.pathname.match(/^\/project\/([^/]+)/)?.[1];
  const setupPathForProvider = (providerId: string) =>
    buildAiGuidedSetupPath({
      projectId: projectIdFromPath,
      componentId:
        providerId === "hunyuan-video-15"
          ? "hunyuan_video_15"
          : providerId === "hunyuan-video-13b"
            ? "hunyuan_video_13b"
            : providerId.replace(/-/g, "_"),
      source: "video_studio",
    });

  const run = async (providerId: string, action: "install" | "remove" | "repair" | "benchmark" | "health") => {
    setBusyId(providerId);
    setMessage(null);
    try {
      if (action === "install") {
        const res = await api.hunyuanInstall(providerId);
        setMessage(
          String(
            res.message ||
              (res.ok === false
                ? "Install failed to queue."
                : "Install queued — track progress in Source Manager Active Downloads."),
          ),
        );
      } else if (action === "remove") {
        const res = await api.hunyuanRemove(providerId);
        setMessage(String(res.message || "Removed."));
      } else if (action === "repair") {
        const res = await api.hunyuanRepair(providerId);
        setMessage(String(res.message || "Repair finished."));
      } else if (action === "benchmark") {
        const res = await api.hunyuanBenchmark(providerId);
        setMessage(`Benchmark ${res.ok ? "recorded" : "failed"} for ${providerId}.`);
      } else {
        const res = await api.hunyuanHealth(providerId);
        setMessage(
          res.ok
            ? `${providerId} healthy`
            : String((res.verify as { message?: string })?.message || res.message || "Unhealthy / not installed"),
        );
      }
      await refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <section className="panel" data-testid="video-model-library" aria-label="Video Model Library">
      <h3>Video Models</h3>
      <p className="scene-meta">
        LTX 2.5 is the recommended production engine. HunyuanVideo 1.5 and 13B install independently
        from official Tencent Hugging Face sources. Installing one never overwrites the other. WAN stays
        optional. MiniMax H3 is selectable in Adept UI surfaces with honest preflight; local weights require
        license clearance and runtime certification before generation.
      </p>
      {message ? (
        <p className="scene-meta" role="status" data-testid="video-model-library-message">
          {message}{" "}
          <Link
            to={buildAiGuidedSetupPath({ projectId: projectIdFromPath, source: "video_studio" })}
            data-testid="video-model-open-source-manager"
          >
            Open Setup
          </Link>
        </p>
      ) : null}
      <ul className="video-model-library-list" style={{ listStyle: "none", padding: 0, margin: "0.75rem 0" }}>
        {providers.map((row) => {
          const id = String(row.providerId || "");
          const isHunyuan = id.startsWith("hunyuan-video-");
          // Honest label: ✓ ONLY when actually installed + healthy. The previous logic
          // showed ✓ for the default provider even when it was not installed (e.g. the
          // default minimax-h3 with no local weights), which falsely implied readiness.
          const mark = modelMark(row.installed, row.healthy);
          const bench = benchmarks[id];
          const statusText = String(row.status || "Unknown");
          return (
            <li
              key={id}
              className="video-model-library-item"
              data-testid={`video-model-${id}`}
              data-status={statusText}
              data-installed={row.installed ? "true" : "false"}
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
                  <div className="scene-meta" data-testid={`video-model-status-${id}`}>
                    Status: {statusText}
                    {row.engine ? ` · engine ${row.engine}` : ""}
                    {row.version ? ` · v${row.version}` : ""}
                    {" · "}
                    <InstallStatusChip
                      componentId={id === "hunyuan-video-15" ? "hunyuan_video_15" : id === "hunyuan-video-13b" ? "hunyuan_video_13b" : id.replace(/-/g, "_")}
                      href={setupPathForProvider(id)}
                    />
                  </div>
                  {row.storagePath ? <div className="scene-meta">Path: {row.storagePath}</div> : null}
                  {row.hfRepo ? <div className="scene-meta">Source: huggingface.co/{row.hfRepo}</div> : null}
                  <div className="scene-meta">
                    I2V: {row.supportsImageToVideo ? "yes" : "no"}
                    {" · "}
                    T2V: {row.supportsTextToVideo ? "yes (certified)" : row.trueLocalT2vCertified === false ? "gated" : "n/a"}
                  </div>
                  {(row.notes || []).map((note) => (
                    <div key={note} className="scene-meta">
                      {note}
                    </div>
                  ))}
                  {bench?.ok != null ? (
                    <div className="scene-meta">
                      Benchmark: {String(bench.outputResolution || "—")} · builder {String(bench.builderElapsedMs || "—")}ms
                      {bench.recommendedProfile ? ` · profile ${String(bench.recommendedProfile)}` : ""}
                    </div>
                  ) : null}
                </div>
                {isHunyuan ? (
                  <div
                    style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap", alignItems: "flex-start" }}
                    data-testid={`video-model-actions-${id}`}
                  >
                    <button
                      type="button"
                      data-testid={`video-model-install-${id}`}
                      title="Open AI-Guided Setup for this model"
                      onClick={() => {
                        window.location.assign(setupPathForProvider(id));
                      }}
                    >
                      Open Setup
                    </button>
                    <button
                      type="button"
                      data-testid={`video-model-repair-${id}`}
                      onClick={() => {
                        window.location.assign(setupPathForProvider(id));
                      }}
                    >
                      Repair in Setup
                    </button>
                    <button
                      type="button"
                      data-testid={`video-model-verify-${id}`}
                      disabled={busyId === id}
                      onClick={() => void run(id, "health")}
                    >
                      Verify
                    </button>
                    <button
                      type="button"
                      data-testid={`video-model-benchmark-${id}`}
                      disabled={busyId === id}
                      onClick={() => void run(id, "benchmark")}
                    >
                      Benchmark
                    </button>
                    <button
                      type="button"
                      className="ghost"
                      data-testid={`video-model-remove-${id}`}
                      disabled={busyId === id}
                      onClick={() => void run(id, "remove")}
                    >
                      Remove
                    </button>
                  </div>
                ) : null}
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

/** Group ComfyHealth model components by generator for the readiness section. */
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
  add("wan", "WAN", "wan_models");
  add("zimage", "Z-Image", "zimage_models");
  add("ltx_23", "LTX 2.3", "ltx_checkpoint");
  return byGen;
}
