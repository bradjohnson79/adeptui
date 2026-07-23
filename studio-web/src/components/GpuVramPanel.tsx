import { useEffect, useMemo, useState } from "react";
import type { Project } from "../types";
import { api } from "../api";
import { PanelHeading } from "./HelpTip";

type VramPreset = {
  vram_gb: number;
  label: string;
  width: number;
  height: number;
  fps: number;
  max_duration_sec: number;
  max_frames: number;
  steps_draft: number;
  steps_quality: number;
  assist_chunk_frames: number;
  summary: string;
  assists: string[];
};

type GpuDevice = {
  index: number;
  name: string;
  driver_version: string;
  memory_total_mib?: number | null;
  memory_used_mib?: number | null;
  memory_free_mib?: number | null;
  memory_used_pct?: number | null;
  temperature_c?: number | null;
  utilization_gpu_pct?: number | null;
  utilization_memory_pct?: number | null;
  power_draw_w?: number | null;
  fan_speed_pct?: number | null;
};

function fmtMib(v?: number | null) {
  if (v == null || Number.isNaN(v)) return "—";
  if (v >= 1024) return `${(v / 1024).toFixed(1)} GB`;
  return `${Math.round(v)} MiB`;
}

function fmtNum(v?: number | null, suffix = "") {
  if (v == null || Number.isNaN(v)) return "—";
  return `${Math.round(v)}${suffix}`;
}

export function GpuVramPanel({ project, onChange }: { project: Project; onChange: () => void }) {
  const [presets, setPresets] = useState<VramPreset[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [statsOk, setStatsOk] = useState(false);
  const [gpus, setGpus] = useState<GpuDevice[]>([]);
  const [primaryIndex, setPrimaryIndex] = useState(0);
  const [recommendedTier, setRecommendedTier] = useState<number | null>(null);

  const active = useMemo(
    () => presets.find((p) => p.vram_gb === (project.vram_gb || 32)) || null,
    [presets, project.vram_gb]
  );

  const primary = gpus[primaryIndex] || gpus[0] || null;

  const refreshStats = async () => {
    try {
      const s = await api.gpuStats();
      setStatsOk(s.ok);
      setGpus(s.gpus || []);
      setPrimaryIndex(s.primary_index || 0);
      setRecommendedTier(s.recommended_tier ?? null);
      if (!s.ok) setMsg(s.message || "GPU stats unavailable");
    } catch (err) {
      setStatsOk(false);
      setGpus([]);
      setMsg(err instanceof Error ? err.message : String(err));
    }
  };

  useEffect(() => {
    api.vramPresets()
      .then(setPresets)
      .catch(() => setPresets([]));
    refreshStats();
    const id = setInterval(refreshStats, 4000);
    return () => clearInterval(id);
  }, []);

  const applyVram = async (tier: number) => {
    setBusy(true);
    setMsg(null);
    try {
      await api.updateProject(project.id, { vram_gb: tier, apply_vram_profile: true });
      await onChange();
      setMsg(`Applied ${tier} GB VRAM profile`);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const detectAndApply = async () => {
    setBusy(true);
    setMsg(null);
    try {
      await refreshStats();
      const d = await api.vramDetect();
      if (d.tier) {
        await api.updateProject(project.id, { vram_gb: d.tier, apply_vram_profile: true });
        await onChange();
      }
      setMsg(d.message);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel gpu-vram-panel">
      <PanelHeading
        title="GPU & VRAM"
        tip="Live GPU stats from nvidia-smi plus a VRAM profile that tunes resolution, fps, frames, and steps for safe local renders."
      >
        <button type="button" className="ghost" disabled={busy} onClick={refreshStats}>
          Refresh
        </button>
      </PanelHeading>

      {primary && statsOk ? (
        <div className="gpu-live">
          <div className="gpu-live-name">{primary.name}</div>
          <div className="scene-meta">Driver {primary.driver_version || "—"}</div>
          <div className="gpu-stat-grid">
            <div>
              <div className="scene-meta">VRAM</div>
              <div className="gpu-stat-value">
                {fmtMib(primary.memory_used_mib)} / {fmtMib(primary.memory_total_mib)}
              </div>
              <div className="bar" title={`${primary.memory_used_pct ?? 0}%`}>
                <i style={{ width: `${Math.min(100, Math.max(0, primary.memory_used_pct || 0))}%` }} />
              </div>
            </div>
            <div>
              <div className="scene-meta">GPU util</div>
              <div className="gpu-stat-value">{fmtNum(primary.utilization_gpu_pct, "%")}</div>
              <div className="bar">
                <i style={{ width: `${Math.min(100, Math.max(0, primary.utilization_gpu_pct || 0))}%` }} />
              </div>
            </div>
            <div>
              <div className="scene-meta">Temp</div>
              <div className="gpu-stat-value">{fmtNum(primary.temperature_c, "°C")}</div>
            </div>
            <div>
              <div className="scene-meta">Power</div>
              <div className="gpu-stat-value">{fmtNum(primary.power_draw_w, " W")}</div>
            </div>
          </div>
          <div className="gpu-stat-row scene-meta">
            <span>Mem util {fmtNum(primary.utilization_memory_pct, "%")}</span>
            <span>Free {fmtMib(primary.memory_free_mib)}</span>
            {primary.fan_speed_pct != null && <span>Fan {fmtNum(primary.fan_speed_pct, "%")}</span>}
          </div>
          {gpus.length > 1 && (
            <div className="scene-meta" style={{ marginTop: 6 }}>
              {gpus.length} GPUs detected · showing GPU {primary.index}
            </div>
          )}
        </div>
      ) : (
        <div className="empty" style={{ marginBottom: 8 }}>
          GPU not detected yet. Use Detect to read nvidia-smi.
        </div>
      )}

      <div className="field" style={{ marginTop: 10 }}>
        <label>VRAM profile</label>
        <p className="scene-meta" style={{ marginTop: 0 }}>
          Tunes resolution, fps, frame budget, steps, and assists for local generation.
        </p>
        <select
          value={project.vram_gb || 32}
          disabled={busy}
          onChange={(e) => applyVram(Number(e.target.value))}
        >
          <option value={8}>8 GB</option>
          <option value={16}>16 GB</option>
          <option value={24}>24 GB</option>
          <option value={32}>32+ GB</option>
        </select>
        <div className="row-actions" style={{ marginTop: 8 }}>
          <button type="button" disabled={busy} onClick={detectAndApply}>
            {busy ? "Working…" : "Detect & apply"}
          </button>
        </div>
        {recommendedTier != null && recommendedTier !== (project.vram_gb || 32) && (
          <div className="scene-meta" style={{ marginTop: 6 }}>
            Detected class: {recommendedTier} GB — profile is {project.vram_gb || 32} GB
          </div>
        )}
      </div>

      {active && (
        <div className="vram-profile-card">
          <strong>{active.label}</strong>
          <div className="scene-meta">{active.summary}</div>
          <div className="scene-meta" style={{ marginTop: 6 }}>
            {project.width}×{project.height} · {project.fps} fps · max ~{active.max_duration_sec}s · steps{" "}
            {active.steps_draft}/{active.steps_quality}
            {active.assist_chunk_frames > 0 ? ` · chunk ${active.assist_chunk_frames}` : ""}
          </div>
        </div>
      )}
      {msg && <div className="scene-meta" style={{ marginTop: 8 }}>{msg}</div>}
    </div>
  );
}
