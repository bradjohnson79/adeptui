import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api";
import { CapabilityStatusBadge } from "../CapabilityPanel";
import type { Health } from "../../types";

export function SystemStatusStrip({
  compact = false,
  queuedJobs,
  projectId,
}: {
  compact?: boolean;
  /** Explicit queued count from dashboard context */
  queuedJobs?: number | null;
  /** When set, polls project jobs for queued count */
  projectId?: string;
}) {
  const [health, setHealth] = useState<Health | null>(null);
  const [gpuOk, setGpuOk] = useState<boolean | null>(null);
  const [queued, setQueued] = useState<number | null>(queuedJobs ?? null);

  useEffect(() => {
    if (queuedJobs != null) setQueued(queuedJobs);
  }, [queuedJobs]);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const h = await api.health();
        if (alive) setHealth(h);
      } catch {
        if (alive) setHealth(null);
      }
      try {
        const g = await api.gpuStats();
        if (alive) setGpuOk(Boolean(g.ok && g.gpus?.length));
      } catch {
        if (alive) setGpuOk(null);
      }
      if (projectId && queuedJobs == null) {
        try {
          const jobs = await api.listJobs(projectId);
          if (alive) {
            setQueued(jobs.filter((j) => ["queued", "running", "pending"].includes(j.status)).length);
          }
        } catch {
          /* leave queued as-is */
        }
      }
    };
    tick();
    const id = setInterval(tick, 15000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [projectId, queuedJobs]);

  const missingCount = health?.missing_model_component_ids?.length ?? health?.missing_models?.length ?? 0;
  const comfy =
    !health
      ? { label: "ComfyUI Checking…", cls: "warn" }
      : !health.comfy_reachable
        ? { label: "ComfyUI Offline", cls: "bad" }
        : missingCount
          ? { label: `ComfyUI · ${missingCount} models missing`, cls: "warn" }
          : { label: "ComfyUI Connected", cls: "ok" };

  const gpu =
    gpuOk === null
      ? { label: "GPU…", cls: "warn" }
      : gpuOk
        ? { label: "GPU Ready", cls: "ok" }
        : { label: "GPU Unavailable", cls: "warn" };

  const op = health?.operator;
  const provider = op?.provider;
  const registry = op?.registry;
  const intelligenceOn = Boolean(op?.intelligenceEnabled);
  const visionOn = Boolean(op?.visionValidationEnabled);
  const executiveOn = Boolean(op?.productionExecutiveEnabled);
  const packBlockers = op?.packBlockers?.length ?? 0;

  return (
    <div
      className={`system-status-strip ${compact ? "compact" : ""}`}
      role="status"
      aria-live="polite"
      data-testid="system-status-strip"
    >
      <span className="status-badge ok" data-testid="status-api">
        API {op?.api === "ok" ? "Ready" : "…"}
      </span>
      <span className={`status-badge ${comfy.cls}`} data-testid="status-comfy">
        {comfy.label}
      </span>
      <span
        className={`status-badge ${provider?.reachable ? "ok" : "warn"}`}
        data-testid="status-provider"
        title={provider?.selectedModel || provider?.status || "Provider"}
      >
        {provider?.reachable
          ? `Provider ${provider.status || "Ready"}`
          : "Provider Offline"}
      </span>
      <span className="status-badge ok" data-testid="status-bible">
        Bible {op?.bibleStorage || "…"}
      </span>
      <span
        className={`status-badge ${intelligenceOn ? "ok" : "warn"}`}
        data-testid="status-intelligence"
      >
        Intelligence {intelligenceOn ? "On" : "Off"}
      </span>
      <span
        className={`status-badge ${visionOn ? "ok" : "warn"}`}
        data-testid="status-vision-validation"
        title={op?.visualValidationPendingNote || ""}
      >
        Vision {visionOn ? "On" : "Off"}
      </span>
      <span
        className={`status-badge ${executiveOn ? "ok" : "warn"}`}
        data-testid="status-production-executive"
        title="STUDIO_FEATURE_PRODUCTION_EXECUTIVE_V1"
      >
        Exec {executiveOn ? "On" : "Off"}
      </span>
      <span className="status-badge ok" data-testid="status-specialists">
        {op?.specialistCount ?? "…"} Specialists
      </span>
      <span
        className={`status-badge ${(registry?.blocked || 0) > 0 ? "warn" : "ok"}`}
        data-testid="status-registry"
        title={op?.visualValidationPendingNote || ""}
      >
        Registry {registry?.callable ?? "…"}/{registry?.total ?? "…"}
        {(registry?.blocked || 0) > 0 ? ` · ${registry?.blocked} blocked` : ""}
      </span>
      {packBlockers > 0 && (
        <span className="status-badge warn" data-testid="status-pack-blockers">
          {packBlockers} Pack Blocker{packBlockers === 1 ? "" : "s"}
        </span>
      )}
      <span className="status-badge warn" data-testid="status-visual-validation">
        Visual validation pending (M2.5)
      </span>
      <span className={`status-badge ${gpu.cls}`}>{gpu.label}</span>
      <CapabilityStatusBadge projectId={projectId} />
      {queued != null && (
        <span className={`status-badge ${queued ? "warn" : "ok"}`}>
          {queued} Job{queued === 1 ? "" : "s"} Queued
        </span>
      )}
    </div>
  );
}

export function StudioChrome({
  variant = "home",
  projectName,
  workspaceLabel,
  leftExtra,
  rightExtra,
  onOpenCoDirector,
  onSetup,
  searchValue,
  onSearchChange,
  onSearchSubmit,
  projectId,
  queuedJobs,
}: {
  variant?: "home" | "project";
  projectName?: string;
  workspaceLabel?: string;
  leftExtra?: ReactNode;
  rightExtra?: ReactNode;
  onOpenCoDirector?: () => void;
  onSetup?: () => void;
  searchValue?: string;
  onSearchChange?: (v: string) => void;
  onSearchSubmit?: () => void;
  projectId?: string;
  queuedJobs?: number | null;
}) {
  return (
    <header className="studio-chrome topbar">
      <div className="studio-chrome-left">
        <Link to="/" className="brand-link">
          <div className="brand">
            Adept <span>UI Generation Studio</span>
          </div>
        </Link>
        {variant === "project" && leftExtra}
        {variant === "project" && projectName && (
          <span className="chrome-project-meta">
            <span className="chrome-sep" aria-hidden="true">
              /
            </span>
            {workspaceLabel && <span className="chrome-workspace">{workspaceLabel}</span>}
          </span>
        )}
      </div>
      <div className="studio-chrome-right topbar-meta">
        {onSetup && (
          <button type="button" onClick={onSetup}>
            Setup Wizard
          </button>
        )}
        <Link to="/source-manager" className="chrome-nav-link">
          Source Manager
        </Link>
        {onSearchChange && (
          <label className="chrome-search">
            <span className="chrome-search-icon" aria-hidden="true">
              ⌕
            </span>
            <input
              aria-label="Search"
              placeholder="Search…"
              value={searchValue || ""}
              onChange={(e) => onSearchChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") onSearchSubmit?.();
              }}
            />
            <kbd className="chrome-kbd">⌘K</kbd>
          </label>
        )}
        <SystemStatusStrip compact projectId={projectId} queuedJobs={queuedJobs} />
        {onOpenCoDirector && (
          <button type="button" className="primary" onClick={onOpenCoDirector}>
            Co-Director
          </button>
        )}
        {rightExtra}
      </div>
    </header>
  );
}
