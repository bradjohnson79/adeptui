import { useState } from "react";
import { api } from "../../../api";
import { useCoDirectorSession } from "./CoDirectorSession";
import type { CoDirectorMessageExecution as ExecPayload, GenerationPlan, GenerationOutputPlan } from "./types";
import type { SurfaceType } from "./AgentWorkSurface/types";

function outputTypeLabel(output: GenerationOutputPlan): string {
  if (output.output_type === "four_panel_storyboard") return "4-Panel Storyboard";
  return "Storyboard Frame";
}

function GenerationQueueCard({
  execution,
  projectId,
  onClose,
}: {
  execution: ExecPayload;
  projectId: string;
  onClose: () => void;
}) {
  const { setActiveExecution } = useCoDirectorSession();
  const [approving, setApproving] = useState(false);
  const [refining, setRefining] = useState(false);
  const planData = execution.plan_data as GenerationPlan | null;
  const outputs = planData?.outputs ?? [];

  const handleApprove = async () => {
    if (!execution.execution_id || !projectId || approving) return;
    setApproving(true);
    try {
      const res = await api.approveExecution(projectId, execution.execution_id);
      const surfaceType = (res.surface_type as SurfaceType) || "storyboard_generation";
      setActiveExecution({
        mode: "agent_work",
        execution_id: res.execution_id,
        capability: res.capability || "",
        surface_type: surfaceType,
        status: res.status || "",
        progress: res.progress || 0,
        focused_artifact_ids: res.result_asset_ids || [],
        child_jobs: (res.child_jobs || []).map((c: any) => ({
          job_id: c.job_id || "",
          label: c.label || `Output ${(c.child_index ?? 0) + 1}`,
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
      console.error("Approval failed:", err);
    } finally {
      setApproving(false);
      onClose();
    }
  };

  return (
    <div className="codirector-gen-queue" data-testid="generation-queue">
      <div className="codirector-gen-queue-header">
        <span className="codirector-gen-queue-title">STORYBOARD GENERATION QUEUE</span>
        <span className="codirector-gen-queue-count">{outputs.length} Output{outputs.length !== 1 ? "s" : ""}</span>
      </div>

      <div className="codirector-gen-queue-body">
        {outputs.map((output, i) => (
          <div key={i} className="codirector-gen-queue-output">
            <div className="codirector-gen-queue-output-head">
              <span className="codirector-gen-queue-output-index">Output {i + 1}</span>
              <span className="codirector-gen-queue-output-type">{outputTypeLabel(output)}</span>
            </div>
            <div className="codirector-gen-queue-output-framing">{output.framing?.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}</div>
            {output.description && (
              <div className="codirector-gen-queue-output-desc">{output.description}</div>
            )}
          </div>
        ))}
      </div>

      {planData?.style_context && (
        <div className="codirector-gen-queue-style">
          <span className="codirector-gen-queue-style-label">Style:</span> {planData.style_context}
        </div>
      )}

      <div className="codirector-gen-queue-status">
        STATUS: <span className="codirector-gen-queue-status-value">Awaiting Approval</span>
      </div>

      <div className="codirector-gen-queue-actions">
        <button
          type="button"
          className="ghost codirector-gen-queue-approve"
          onClick={handleApprove}
          disabled={approving}
          data-testid="generation-queue-approve"
        >
          {approving ? "Approving…" : "Approve Generation"}
        </button>
        <button
          type="button"
          className="ghost codirector-gen-queue-refine"
          onClick={() => setRefining(true)}
          disabled={refining}
          data-testid="generation-queue-refine"
        >
          Refine
        </button>
      </div>

      {refining && (
        <div className="codirector-gen-queue-refine-hint">
          Describe what you'd like to change in chat above, then send.
        </div>
      )}
    </div>
  );
}

export default GenerationQueueCard;
