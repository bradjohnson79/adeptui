import { Button } from "../../ui";

const COMMANDS: { toolId: string; label: string; needsConfirm?: boolean }[] = [
  { toolId: "production_plan.propose", label: "Propose for acceptance" },
  { toolId: "production_plan.approve", label: "Approve plan acceptance" },
  { toolId: "production_plan.reject", label: "Reject" },
  { toolId: "production_plan.pause", label: "Pause", needsConfirm: true },
  { toolId: "production_plan.resume", label: "Resume", needsConfirm: true },
  { toolId: "production_plan.cancel", label: "Cancel" },
  { toolId: "production_plan.archive", label: "Archive" },
];

export function PlanCommandProposal({
  planId,
  version,
  state,
  unapproved,
  onPropose,
  busy,
}: {
  planId: string;
  version: number;
  state: string;
  unapproved?: boolean;
  onPropose: (toolId: string) => void;
  busy?: boolean;
}) {
  const visible = COMMANDS.filter((c) => {
    if (c.toolId === "production_plan.propose") return state === "draft" || unapproved;
    if (c.toolId === "production_plan.approve") return state === "proposed" || state === "awaiting_approval";
    if (c.toolId === "production_plan.reject") return state === "proposed" || state === "awaiting_approval";
    if (c.toolId === "production_plan.pause") return ["approved", "ready", "blocked"].includes(state);
    if (c.toolId === "production_plan.resume") return state === "paused";
    if (c.toolId === "production_plan.cancel") return !["cancelled", "archived"].includes(state);
    if (c.toolId === "production_plan.archive") return state === "cancelled";
    return false;
  });

  return (
    <div className="codirector-plan-commands" data-testid="codirector-plan-commands">
      <p className="muted">
        Plan commands create Approvals proposals (except pause/resume confirm). No production execution
        buttons.
      </p>
      <div className="codirector-plan-command-row">
        {visible.map((c) => (
          <Button
            key={c.toolId}
            disabled={busy}
            onClick={() => {
              if (c.needsConfirm && !window.confirm(`${c.label} plan ${planId} (v${version})?`)) return;
              onPropose(c.toolId);
            }}
          >
            {c.label}
          </Button>
        ))}
      </div>
    </div>
  );
}
