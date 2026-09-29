import type { SceneFinalCheckState, FinalCheckCategoryResult } from "../../timelineMaster/sceneFinalCheck";
import {
  VERDICT_ACCEPTED,
  VERDICT_FOUND_ISSUES,
  VERDICT_PASSED,
  applyApiRepairDecision,
} from "../../timelineMaster/sceneFinalCheck";

type Props = {
  state: SceneFinalCheckState | null | undefined;
  open: boolean;
  onClose?: () => void;
  onRepairDecision?: (
    decision: "repair_automatically" | "review_first" | "keep_current" | "decline" | "dismiss",
    nextGate: NonNullable<SceneFinalCheckState["repairGate"]>,
  ) => void;
};

function categoryLabel(cat: string): string {
  return cat.charAt(0).toUpperCase() + cat.slice(1);
}

function statusLabel(row: FinalCheckCategoryResult): string {
  if (row.status === "not_run") return "Not run";
  if (row.status === "pass") return "Pass";
  if (row.status === "uncertain") return "Uncertain";
  return "Fail";
}

/**
 * Final Check UI shell — opens after stitch.
 * Dialogue/language/speaker hooked from Dialogue Authority QC.
 * identity/environment/technical = honest stubs; continuity/camera/equipment/audio = pipelines (not_run until Omni packet).
 */
export function FinalCheckPanel({ state, open, onClose, onRepairDecision }: Props) {
  if (!open || !state) return null;

  const gate = state.repairGate;
  const showApiActions =
    gate?.runtimeKind === "api" &&
    gate.requiresApproval &&
    gate.permission === "required" &&
    ((state.autoRepairEligibleCount || 0) > 0 || (gate.actions || []).includes("repair_automatically"));

  const verdict = state.creatorVerdict || VERDICT_FOUND_ISSUES;

  return (
    <div className="timeline-inspector__stack" data-testid="final-check-panel" role="region" aria-label="Final Check">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
        <strong>Final Check</strong>
        {onClose ? (
          <button type="button" className="btn ghost" data-testid="final-check-dismiss" onClick={onClose}>
            Close
          </button>
        ) : null}
      </div>
      <div className="scene-meta" data-testid="final-check-lifecycle">
        Status: {String(state.lifecycleStatus || "")}
      </div>
      <div className="scene-meta" data-testid="final-check-verdict">
        {verdict}
      </div>
      {verdict === VERDICT_PASSED ? (
        <p className="scene-meta">No blocking Hard findings. Scene Finished.</p>
      ) : null}
      {verdict === VERDICT_ACCEPTED ? (
        <p className="scene-meta">Creator kept current — Scene Finished with accepted issues.</p>
      ) : null}

      <div className="timeline-inspector__meta-grid" data-testid="final-check-categories">
        {(state.categories || []).map((row) => (
          <div key={String(row.category)} data-testid={`final-check-cat-${row.category}`}>
            <strong>{categoryLabel(String(row.category))}</strong>
            <div className="scene-meta">
              {statusLabel(row)}
              {row.taxonomy ? ` · ${row.taxonomy}` : ""}
              {row.source === "stub" ? " · stub" : ""}
            </div>
            {(row.findings || []).slice(0, 3).map((f, i) => (
              <div key={`${f.code}-${i}`} className="scene-meta">
                {f.code || f.message || "finding"}
                {f.taxonomy ? ` (${f.taxonomy})` : ""}
              </div>
            ))}
            {row.note && row.source === "stub" ? <div className="scene-meta">{row.note}</div> : null}
          </div>
        ))}
      </div>

      {state.retakePack ? (
        <div className="scene-meta" data-testid="final-check-retake-pack">
          <strong>Re-Take pack</strong>
          <div>WRONG: {JSON.stringify((state.retakePack as any).WHAT_WRONG || (state.retakePack as any).whatWrong)}</div>
          <div>CHANGE: {String((state.retakePack as any).WHAT_CHANGE || (state.retakePack as any).whatChange || "")}</div>
          <div>PRESERVE: {String((state.retakePack as any).WHAT_PRESERVE || (state.retakePack as any).whatPreserve || "")}</div>
          <div>METHOD: {String((state.retakePack as any).METHOD || (state.retakePack as any).method || "")}</div>
        </div>
      ) : null}

      {gate?.runtimeKind === "local" && gate.permission === "not_required" && (state.autoRepairEligibleCount || 0) > 0 ? (
        <p className="scene-meta" data-testid="final-check-local-auto">
          Local Hard defects — auto Manifest Re-Take (no permission prompt). Reuses dialogueRetakeRepair.
        </p>
      ) : null}

      {showApiActions ? (
        <div className="timeline-inspector__stack" data-testid="final-check-api-gate">
          <p className="scene-meta">API repair requires one approval this cycle. Decline = zero extra API calls.</p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            <button
              type="button"
              className="btn"
              data-testid="final-check-repair-auto"
              onClick={() => {
                if (!gate || !onRepairDecision) return;
                onRepairDecision("repair_automatically", applyApiRepairDecision(gate, "repair_automatically"));
              }}
            >
              Repair Automatically
            </button>
            <button
              type="button"
              className="btn ghost"
              data-testid="final-check-review-first"
              onClick={() => {
                if (!gate || !onRepairDecision) return;
                onRepairDecision("review_first", applyApiRepairDecision(gate, "review_first"));
              }}
            >
              Review First
            </button>
            <button
              type="button"
              className="btn ghost"
              data-testid="final-check-keep-current"
              onClick={() => {
                if (!gate || !onRepairDecision) return;
                onRepairDecision("keep_current", applyApiRepairDecision(gate, "keep_current"));
              }}
            >
              Keep Current
            </button>
            <button
              type="button"
              className="btn ghost"
              data-testid="final-check-decline"
              onClick={() => {
                if (!gate || !onRepairDecision) return;
                onRepairDecision("decline", applyApiRepairDecision(gate, "decline"));
              }}
            >
              Decline
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
