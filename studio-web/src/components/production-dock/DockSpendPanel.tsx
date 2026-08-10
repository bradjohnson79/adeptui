import { useCallback, useEffect, useState } from "react";
import { api } from "../../api";

type SpendSummary = {
  confirmedSpend?: number;
  estimatedPending?: number;
  totalProjected?: number;
  disclaimer?: string;
};

export function DockSpendPanel({ projectId }: { projectId?: string | null }) {
  const [summary, setSummary] = useState<SpendSummary | null>(null);
  const [budgetPref, setBudgetPref] = useState("balanced");
  const [projectBudget, setProjectBudget] = useState("");
  const [warnUsd, setWarnUsd] = useState("0.50");
  const [message, setMessage] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const dock = await api.providerUsageDock(projectId || undefined);
    setSummary(dock.projectSpend || null);
    const budgets = dock.budgets || {};
    setBudgetPref(String(budgets.budgetPreference || "balanced"));
    setProjectBudget(
      budgets.projectBudgetUsd == null || budgets.projectBudgetUsd === undefined
        ? ""
        : String(budgets.projectBudgetUsd),
    );
    setWarnUsd(String(budgets.perRequestWarnUsd ?? 0.5));
  }, [projectId]);

  useEffect(() => {
    void refresh().catch(() => setSummary(null));
  }, [refresh]);

  return (
    <div className="production-dock-spend" data-testid="production-dock-spend">
      <h4>API spending</h4>
      <p data-testid="dock-spend-local-label">Local — No API charge</p>
      <p data-testid="dock-spend-project">
        Project: confirmed ${Number(summary?.confirmedSpend || 0).toFixed(4)} · estimated pending $
        {Number(summary?.estimatedPending || 0).toFixed(4)} · projected $
        {Number(summary?.totalProjected || 0).toFixed(4)}
      </p>
      <p style={{ fontSize: "0.85rem", opacity: 0.85 }}>{summary?.disclaimer}</p>
      <label>
        Spending preference
        <select
          data-testid="dock-budget-preference"
          value={budgetPref}
          aria-label="Dock spending preference"
          onChange={(e) => {
            const value = e.target.value;
            setBudgetPref(value);
            void api
              .providerUsagePutBudgets({ budgetPreference: value })
              .then(() => setMessage(`Spending preference: ${value}`));
          }}
        >
          <option value="low_cost">Lower cost</option>
          <option value="balanced">Balanced</option>
          <option value="quality">Higher quality</option>
        </select>
      </label>
      <label>
        Warn above ($)
        <input
          data-testid="dock-budget-warn"
          value={warnUsd}
          onChange={(e) => setWarnUsd(e.target.value)}
          aria-label="Warn above USD"
        />
      </label>
      <label>
        Project budget ($)
        <input
          data-testid="dock-project-budget"
          value={projectBudget}
          placeholder="No limit"
          onChange={(e) => setProjectBudget(e.target.value)}
          aria-label="Project budget USD"
        />
      </label>
      <button
        type="button"
        data-testid="dock-budget-save"
        onClick={() => {
          void api
            .providerUsagePutBudgets({
              budgetPreference: budgetPref,
              perRequestWarnUsd: Number(warnUsd) || 0.5,
              projectBudgetUsd: projectBudget.trim() ? Number(projectBudget) : null,
              askBeforeSpending: true,
              onExceed: "require_confirmation",
            })
            .then(() => {
              setMessage("Budget saved. Adept will ask before spending.");
              return refresh();
            });
        }}
      >
        Save budget
      </button>
      {message && (
        <p role="status" data-testid="dock-spend-message">
          {message}
        </p>
      )}
      <p style={{ fontSize: "0.85rem" }}>
        Adept never silently switches to a paid API when a local model is unavailable.
      </p>
    </div>
  );
}
