import { useEffect, useState } from "react";
import { api } from "../../api";

type PlanItem = {
  componentId?: string;
  name?: string;
  classification?: string;
  action?: string;
  installedBytes?: number;
};

type ReviewPlan = {
  requiresApproval?: boolean;
  approved?: boolean;
  diskBlocked?: boolean;
  diskMessage?: string | null;
  installedBytes?: number;
  freeBytes?: number | null;
  items?: PlanItem[];
  jobs?: Array<Record<string, unknown>>;
};

type UpdateItem = {
  componentId?: string;
  name?: string;
  classification?: string;
  reason?: string;
};

type UpdatePlan = {
  available?: boolean;
  message?: string | null;
  unhealthy?: boolean;
  rollbackAvailable?: boolean;
  items?: UpdateItem[];
};

function formatBytes(value: number | null | undefined): string {
  if (value == null) return "Unknown";
  if (value < 1024 * 1024) return `${value} B`;
  if (value < 1024 * 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  return `${(value / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

export function AdeptSetupUpdates({ boot = false }: { boot?: boolean }) {
  const [plan, setPlan] = useState<UpdatePlan | null>(null);
  const [review, setReview] = useState<ReviewPlan | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.setupLifecycleUpdates()
      .then((payload) => {
        if (!cancelled) setPlan(payload as UpdatePlan);
      })
      .catch(() => {
        if (!cancelled) setPlan({ available: false, message: "Update check unavailable", unhealthy: false, items: [] });
      });
    return () => {
      cancelled = true;
    };
  }, [boot]);

  const openUpdatePlan = async () => {
    const ids = (plan?.items || []).map((item) => item.componentId).filter((id): id is string => Boolean(id));
    if (!ids.length) return;
    setBusy(true);
    setMessage(null);
    try {
      const next = await api.setupLifecycleRecommendPlan({ componentIds: ids, action: "update" });
      setReview(next as ReviewPlan);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel" aria-label="Updates" data-testid="adept-setup-updates">
      <div className="setup-section-heading">
        <div>
          <h2>Updates</h2>
          <p>Certified channel only. Nothing installs until you approve it. Rollback stays unavailable until a previous version can actually be restored.</p>
        </div>
      </div>
      {plan?.message && <p className="setup-message" role="status">{plan.message}</p>}
      {message && <p className="setup-message" role="status">{message}</p>}
      <ul>
        {(plan?.items || []).map((item) => (
          <li key={item.componentId}>
            {item.name} — {item.classification}
          </li>
        ))}
        {plan && !plan.items?.length && plan.available !== false && <li>No certified updates.</li>}
      </ul>
      <div className="row-actions">
        <button type="button" className="primary" disabled={busy || !plan?.items?.length} onClick={() => void openUpdatePlan()}>
          Update Recommended
        </button>
      </div>
      {review && (
        <AdeptSetupReview
          plan={review}
          action="update"
          onClose={() => setReview(null)}
          onMessage={setMessage}
        />
      )}
    </section>
  );
}

export function AdeptSetupReview({
  plan,
  action = "install",
  onClose,
  onMessage,
}: {
  plan: ReviewPlan;
  action?: "install" | "update";
  onClose: () => void;
  onMessage: (message: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const ids = (plan.items || []).map((item) => item.componentId).filter((id): id is string => Boolean(id));

  const approve = async () => {
    if (plan.diskBlocked || !ids.length) return;
    setBusy(true);
    try {
      const result = await api.setupLifecycleApprovePlan({
        componentIds: ids,
        confirm: true,
        confirmDownloadModels: action === "update",
        action,
      });
      const jobs = Array.isArray(result.jobs) ? result.jobs.length : 0;
      onMessage(jobs ? "Install started. Ready follows verification, not the download." : "Nothing new needed to download.");
      onClose();
    } catch (error) {
      onMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel" data-testid="adept-setup-review-plan" role="region" aria-label="Review setup plan">
      <h3>{action === "update" ? "Review updates" : "Review recommended setup"}</h3>
      <p>
        {formatBytes(plan.installedBytes)} needed. {formatBytes(plan.freeBytes)} free.
      </p>
      {plan.diskMessage && <p className="setup-message" role="alert">{plan.diskMessage}</p>}
      <ul>
        {(plan.items || []).map((item) => (
          <li key={item.componentId}>
            {item.name} — {item.classification} — {item.action}
          </li>
        ))}
      </ul>
      <div className="row-actions">
        <button type="button" className="primary" data-testid="adept-setup-install" disabled={busy || Boolean(plan.diskBlocked) || !ids.length} onClick={() => void approve()}>
          {action === "update" ? "Update Recommended" : "Install Recommended Setup"}
        </button>
        <button type="button" disabled={busy} onClick={onClose}>Cancel</button>
      </div>
    </div>
  );
}

export function AdeptSetupRecommend({ onMessage }: { onMessage: (message: string) => void }) {
  const [plan, setPlan] = useState<ReviewPlan | null>(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setBusy(true);
    try {
      const next = await api.setupLifecycleRecommendPlan({ action: "install" });
      setPlan(next as ReviewPlan);
    } catch (error) {
      onMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel" aria-label="AI Setup plan" data-testid="adept-setup-recommend">
      <div className="row-actions">
        <button type="button" className="primary" disabled={busy} onClick={() => void load()}>
          Review Recommended Setup
        </button>
      </div>
      {plan && <AdeptSetupReview plan={plan} onClose={() => setPlan(null)} onMessage={onMessage} />}
    </section>
  );
}

export function AdeptSetupDiagnostics({ onMessage }: { onMessage: (message: string) => void }) {
  const [summary, setSummary] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const run = async () => {
    setBusy(true);
    try {
      const scan = await api.setupLifecycleScan();
      const readiness = (scan.readiness || {}) as { overall_label?: string; counts?: Record<string, number> };
      const hardware = (scan.hardware || {}) as { freeBytes?: number | null };
      setSummary(`${readiness.overall_label || "Scan complete"}. Free space ${formatBytes(hardware.freeBytes)}.`);
    } catch (error) {
      onMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel" aria-label="Diagnostics" data-testid="adept-setup-diagnostics">
      <div className="setup-section-heading">
        <div>
          <h2>Diagnostics</h2>
          <p>Uses the same machine scan as AI Setup.</p>
        </div>
      </div>
      <button type="button" disabled={busy} onClick={() => void run()}>Run scan</button>
      {summary && <p className="setup-message" role="status">{summary}</p>}
    </section>
  );
}
