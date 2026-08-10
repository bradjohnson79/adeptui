import { useCallback, useEffect, useState } from "react";
import { api } from "../../../api";
import { CoDirectorEmptyState, CoDirectorErrorState } from "../cards";
import { PlanApprovals } from "./PlanApprovals";
import { PlanBlockers } from "./PlanBlockers";
import { PlanCommandProposal } from "./PlanCommandProposal";
import { PlanDependencyView } from "./PlanDependencyView";
import { PlanHistory } from "./PlanHistory";
import { PlanReadiness } from "./PlanReadiness";
import { PlanRevisionDiff } from "./PlanRevisionDiff";
import { PlanStepList } from "./PlanStepList";
import { PlanSummaryCard } from "./PlanSummaryCard";
import {
  envelopeData,
  type PlanEventRow,
  type PlanReadinessReport,
  type PlanVersionRow,
  type ProductionPlan,
  type ProductionPlanStep,
} from "./types";

export function PlanWorkspacePanel({ projectId }: { projectId: string }) {
  const [plan, setPlan] = useState<ProductionPlan | null>(null);
  const [readiness, setReadiness] = useState<PlanReadinessReport | null>(null);
  const [events, setEvents] = useState<PlanEventRow[]>([]);
  const [versions, setVersions] = useState<PlanVersionRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [diffAfter, setDiffAfter] = useState<ProductionPlanStep[] | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const active = await api.getCoDirectorActivePlan(projectId);
      const activePlanId = String(active.plan?.planId || "").trim();
      if (!activePlanId) {
        setPlan(null);
        setReadiness(null);
        setEvents([]);
        setVersions([]);
        return;
      }
      const resolved = await api.getCoDirectorProjectPlanById(projectId, activePlanId);
      const loaded = (resolved.plan || null) as ProductionPlan | null;
      setPlan(loaded);
      if (!loaded) return;
      const [readyInv, eventsInv, versionsInv] = await Promise.all([
        api.getProductionPlanReadiness(projectId, activePlanId),
        api.listProductionPlanEvents(projectId, activePlanId),
        api.listProductionPlanVersions(projectId, activePlanId),
      ]);
      const readyData = envelopeData<{ readiness?: PlanReadinessReport } & PlanReadinessReport>(readyInv);
      setReadiness(readyData?.readiness || readyData || null);
      const eventsData = envelopeData<{ events?: PlanEventRow[] }>(eventsInv);
      setEvents(eventsData?.events || []);
      const versionsData = envelopeData<{ versions?: PlanVersionRow[] }>(versionsInv);
      setVersions(versionsData?.versions || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const onRefresh = (event: Event) => {
      const detail =
        event instanceof CustomEvent && event.detail && typeof event.detail === "object"
          ? (event.detail as { projectId?: string })
          : {};
      if (detail.projectId && detail.projectId !== projectId) return;
      void load();
    };
    window.addEventListener("adept:codirector-plan-workspace-refresh", onRefresh);
    return () => window.removeEventListener("adept:codirector-plan-workspace-refresh", onRefresh);
  }, [load, projectId]);

  const onPropose = async (toolId: string) => {
    if (!plan) return;
    setBusy(true);
    setMessage(null);
    try {
      if (toolId === "production_plan.revise") {
        const after = [...(plan.steps || [])].map((s, i) => ({ ...s, order: i + 1 }));
        // Demo revision: move last step first for structured diff preview
        if (after.length > 1) {
          const last = after.pop()!;
          after.unshift({ ...last, order: 1 });
          after.forEach((s, i) => {
            s.order = i + 1;
          });
        }
        setDiffAfter(after);
        const proposal = await api.proposeProductionPlanCommand(projectId, toolId, {
          planId: plan.planId,
          expectedVersion: plan.version,
          stepsJson: JSON.stringify(after),
          revisionReason: "Reorder steps (Wave 4 revision)",
        });
        setMessage(`Revision proposal ${proposal.id} created — approve in Approvals. Diff shown below.`);
      } else {
        const proposal = await api.proposeProductionPlanCommand(projectId, toolId, {
          planId: plan.planId,
          expectedVersion: plan.version,
        });
        setMessage(`Proposal ${proposal.id} created for ${toolId}. Approve in Approvals.`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return <p className="muted">Loading plans…</p>;
  }
  if (error) {
    return <CoDirectorErrorState title="Plan workspace error" description={error} />;
  }
  if (!plan) {
    return (
      <CoDirectorEmptyState
        testId="codirector-plans-empty"
        title="No active plan"
        description="Create a draft plan from conversation. Drafts are unapproved until proposed and accepted."
      />
    );
  }

  return (
    <div className="codirector-plan-workspace" data-testid="codirector-plan-workspace">
      <PlanSummaryCard plan={plan} />
      <section>
        <h4>Steps</h4>
        <PlanStepList steps={plan.steps || []} />
        <PlanDependencyView steps={plan.steps || []} />
      </section>
      <section>
        <h4>Blockers</h4>
        <PlanBlockers blockers={plan.blockers || []} />
      </section>
      <section>
        <h4>Approvals</h4>
        <PlanApprovals approvals={plan.approvalRequirements || []} />
      </section>
      <section>
        <h4>Readiness</h4>
        <PlanReadiness report={readiness} />
      </section>
      <section>
        <h4>History</h4>
        <PlanHistory events={events} versions={versions} />
      </section>
      {diffAfter ? (
        <PlanRevisionDiff
          beforeSteps={plan.steps || []}
          afterSteps={diffAfter}
          reason="Proposed revision (awaiting approval)"
        />
      ) : null}
      <PlanCommandProposal
        planId={plan.planId}
        version={plan.version}
        state={plan.state}
        unapproved={plan.unapproved}
        onPropose={onPropose}
        busy={busy}
      />
      <p className="muted">
        Next action:{" "}
        {plan.unapproved || plan.state === "draft"
          ? "Propose for plan acceptance"
          : plan.state === "proposed" || plan.state === "awaiting_approval"
            ? "Approve or reject plan acceptance"
            : plan.state === "paused"
              ? "Resume plan"
              : "Review readiness / revise if capabilities changed"}
      </p>
      {message ? <p data-testid="codirector-plan-command-message">{message}</p> : null}
    </div>
  );
}
