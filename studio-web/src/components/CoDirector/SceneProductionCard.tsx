import { useState } from "react";
import { api } from "../../api";
import { useCoDirectorSession } from "./CoDirectorSession";
import type { CoDirectorMessageExecution } from "./types";
import type { SurfaceType } from "./AgentWorkSurface/types";

type ProductionEvent = {
  type?: string;
  message?: string;
  payload?: Record<string, unknown>;
};

type ProductionPlan = {
  sceneProduction?: boolean;
  preparationReady?: boolean;
  sceneId?: string;
  shotId?: string;
  sceneIndex?: number;
  shotLabel?: string;
  generatorId?: string;
  durationSeconds?: number;
  aspectRatio?: string;
  quality?: string;
  megapixels?: number | null;
  batchCount?: number;
  compiledPrompt?: string;
  events?: ProductionEvent[];
  directorIntent?: {
    shot_type?: string;
    environment?: { name?: string; tag?: string; verified?: boolean };
    subjects?: Array<{ name?: string; tag?: string; role?: string; verified?: boolean; scale?: string; is_global?: boolean }>;
    scale_summary?: string;
    action_text?: string;
  };
  generationJobId?: string;
  submitted?: boolean;
  error?: string;
};

function generatorLabel(id?: string) {
  if (!id) return "Generator";
  if (id.startsWith("minimax-h3")) return "MiniMax H3";
  if (id.startsWith("ltx")) return "LTX 2.5";
  if (id.startsWith("seedance")) return "Seedance";
  return id;
}

function qualityLabel(plan: ProductionPlan) {
  if (typeof plan.megapixels === "number") return `Megapixels ${plan.megapixels}`;
  return plan.quality || "Default";
}

export default function SceneProductionCard({
  execution,
  projectId,
}: {
  execution: CoDirectorMessageExecution;
  projectId: string;
}) {
  const { uiContext, setActiveExecution } = useCoDirectorSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const plan = (execution.plan_data || {}) as ProductionPlan;
  const events = (Array.isArray(plan.events) ? plan.events : []).filter(
    (event) => event.payload?.surface !== "debug",
  );
  const status = (execution.status || "").toLowerCase();
  const generating = status === "queued" || status === "running";
  const ready = status === "preview" && Boolean(plan.sceneId && plan.shotId) && !plan.submitted;

  const openTimeline = () => {
    uiContext.onGoTab?.("timeline", {
      sceneId: plan.sceneId || "",
      batchId: plan.shotId || "",
    });
  };

  const generate = async () => {
    if (!execution.execution_id || !projectId || busy) return;
    setBusy(true);
    setError("");
    try {
      const res = await api.approveExecution(projectId, execution.execution_id);
      const surfaceType = (res.surface_type as SurfaceType) || "timeline_production";
      setActiveExecution({
        mode: "agent_work",
        execution_id: res.execution_id,
        capability: res.capability || "",
        surface_type: surfaceType,
        status: res.status || "",
        progress: res.progress || 0,
        focused_artifact_ids: res.result_asset_ids || [],
        child_jobs: (res.child_jobs || []).map((c: { job_id?: string; label?: string; status?: string; asset_id?: string | null; error?: string | null; progress?: number; stage?: string; child_index?: number; metadata?: Record<string, unknown> }) => ({
          job_id: c.job_id || "",
          label: c.label || "Timeline generation",
          status: c.status || "queued",
          asset_id: c.asset_id ?? null,
          error: c.error ?? null,
          progress: c.progress || 0,
          stage: c.stage || "",
          child_index: c.child_index ?? 0,
          metadata: c.metadata || {},
        })),
        result_asset_ids: res.result_asset_ids || [],
        collection_id: res.collection_id ?? null,
        project_id: projectId,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generate in Timeline failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="codirector-scene-prod" data-testid="scene-production-card">
      <div className="codirector-scene-prod-header">
        <span className="codirector-scene-prod-title">Scene Prepared</span>
        <span className="codirector-scene-prod-meta">
          Timeline Shot: Scene {(plan.sceneIndex ?? 0) + 1} / {plan.shotLabel || "Shot 1"}
        </span>
      </div>
      <ul className="codirector-scene-prod-facts">
        <li>Generator: {generatorLabel(plan.generatorId)}</li>
        <li>Duration: {plan.durationSeconds ?? "—"} sec</li>
        <li>Aspect: {plan.aspectRatio || "—"}</li>
        <li>Quality: {qualityLabel(plan)}</li>
        <li>References: {(plan.events || []).filter((e) => e.type === "reference_found").length} bound</li>
      </ul>
      {events.length ? (
        <ul className="codirector-scene-prod-events" data-testid="scene-production-events">
          {events.map((event, i) => (
            <li key={`${event.type || "event"}-${i}`} className={`is-${event.type || "info"}`}>
              {event.type === "failed" || event.type === "reference_missing" || event.type === "reference_broken"
                ? "✗"
                : "✓"}{" "}
              {event.message}
            </li>
          ))}
        </ul>
      ) : null}
      {plan.directorIntent ? (
        <ul className="codirector-scene-prod-facts" data-testid="scene-director-breakdown">
          {plan.directorIntent.environment?.name ? (
            <li>
              Environment: {plan.directorIntent.environment.name}
              {plan.directorIntent.environment.tag ? ` ${plan.directorIntent.environment.tag}` : ""}
            </li>
          ) : null}
          {(plan.directorIntent.subjects || []).map((subject) => (
            <li key={`${subject.tag || subject.name}`}>
              {subject.role || "Subject"}: {subject.name}
              {subject.tag ? ` ${subject.tag}` : ""}
              {subject.scale ? ` — ${subject.scale}` : ""}
            </li>
          ))}
          {plan.directorIntent.scale_summary ? <li>Scale: {plan.directorIntent.scale_summary}</li> : null}
        </ul>
      ) : null}
      {plan.compiledPrompt ? (
        <div className="codirector-scene-prod-prompt" data-testid="scene-compiled-prompt">
          <div className="codirector-scene-prod-prompt-label">Refined {generatorLabel(plan.generatorId)} Prompt</div>
          <pre>{plan.compiledPrompt}</pre>
        </div>
      ) : null}
      {error || plan.error ? <p className="codirector-scene-prod-error">{error || plan.error}</p> : null}
      <div className="codirector-scene-prod-actions">
        {plan.sceneId ? (
          <button type="button" className="ghost" data-testid="open-in-timeline" onClick={openTimeline}>
            Open in Timeline
          </button>
        ) : null}
        {ready ? (
          <button
            type="button"
            className="ghost codirector-scene-prod-generate"
            data-testid="generate-in-timeline"
            onClick={() => void generate()}
            disabled={busy}
          >
            {busy ? "Submitting…" : "Generate in Timeline"}
          </button>
        ) : null}
        {generating ? <span data-testid="scene-production-generating">Generating in Timeline…</span> : null}
      </div>
    </div>
  );
}
