import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { buildAiGuidedSetupPath } from "../setup/navigation";
import { InstallStatusChip } from "./install/InstallStatusChip";

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
  const [defaultId, setDefaultId] = useState("minimax-h3");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [benchmarks, setBenchmarks] = useState<Record<string, Record<string, unknown>>>({});

  const refresh = useCallback(async () => {
    const lib = await api.hunyuanLibrary();
    setDefaultId(lib.defaultProviderId || "minimax-h3");
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
          const isDefault = id === defaultId || row.status === "Default";
          const mark = row.installed && row.healthy ? "✓" : isDefault ? "✓" : "○";
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
    </section>
  );
}
