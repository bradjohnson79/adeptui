import { useCallback, useEffect, useState } from "react";
import { api } from "../../api";
import "./prompt-intelligence-v2.css";

type Suite = {
  suiteId?: string;
  domain?: string;
  matrixMode?: string;
  cases?: Array<{ benchmarkId?: string; category?: string }>;
};

type Review = {
  comparisonId?: string;
  benchmarkId?: string;
  category?: string;
  domain?: string;
  providerId?: string;
  modelRevision?: string;
  submitted?: boolean;
  revealed?: boolean;
  items?: Array<{ slotId: string; runId: string; outputPaths?: string[] }>;
  strategyMap?: Record<string, string>;
};

export function PromptIntelligenceBenchmarkDashboard() {
  const [suites, setSuites] = useState<Suite[]>([]);
  const [suiteId, setSuiteId] = useState("image-core");
  const [providerId, setProviderId] = useState("comfyui");
  const [suiteRunId, setSuiteRunId] = useState<string | null>(null);
  const [status, setStatus] = useState<Record<string, unknown> | null>(null);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [selectedReview, setSelectedReview] = useState<Review | null>(null);
  const [slotScores, setSlotScores] = useState<Record<string, number>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [evidence, setEvidence] = useState<Record<string, unknown>[]>([]);
  const [promoteCategory, setPromoteCategory] = useState("portrait");
  const [promoteStrategy, setPromoteStrategy] = useState("refined-english");

  const refresh = useCallback(async () => {
    const [s, r, e] = await Promise.all([
      api.promptIntelligence.v2.suites(),
      api.promptIntelligence.v2.reviews(),
      api.promptIntelligence.v2.evidence(),
    ]);
    setSuites((s.suites || []) as Suite[]);
    setReviews((r.reviews || []) as Review[]);
    setEvidence((e.evidence || []) as Record<string, unknown>[]);
    if (suiteRunId) {
      setStatus(await api.promptIntelligence.v2.runs(suiteRunId));
    }
  }, [suiteRunId]);

  useEffect(() => {
    void refresh().catch((err: Error) => setMessage(err.message));
  }, [refresh]);

  const startDryRun = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const res = await api.promptIntelligence.v2.startRun({
        suiteId,
        providerId,
        modelRevision: "default",
        samplesPerStrategy: 1,
        dryRun: true,
      });
      const id = String((res.suiteRun as { suiteRunId?: string })?.suiteRunId || "");
      setSuiteRunId(id);
      setMessage(`Suite run started: ${id}`);
      // poll briefly
      for (let i = 0; i < 40; i++) {
        await new Promise((r) => setTimeout(r, 250));
        const st = await api.promptIntelligence.v2.runs(id);
        setStatus(st);
        const suiteRun = st.suiteRun as { status?: string } | undefined;
        if (suiteRun?.status === "completed" || suiteRun?.status === "cancelled" || suiteRun?.status === "failed") {
          break;
        }
      }
      await refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const submitBlindReview = async () => {
    if (!selectedReview?.comparisonId) return;
    setBusy(true);
    try {
      const reviewsPayload: Record<string, Record<string, unknown>> = {};
      for (const item of selectedReview.items || []) {
        const overall = slotScores[item.slotId] ?? 70;
        reviewsPayload[item.slotId] = {
          overall,
          scores: { overall },
          preferred: overall >= 80 ? "preferred" : "none",
          notes: "blind review",
          reviewerId: "local",
        };
      }
      const res = await api.promptIntelligence.v2.submitReview({
        comparisonId: selectedReview.comparisonId,
        reviews: reviewsPayload,
        reveal: true,
      });
      setSelectedReview(res.review as Review);
      setMessage("Blind review submitted — strategies revealed.");
      await refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const evaluate = async () => {
    setBusy(true);
    try {
      const domain = suites.find((s) => s.suiteId === suiteId)?.domain || "image";
      const res = await api.promptIntelligence.v2.evaluate({
        providerId,
        modelRevision: "default",
        domain,
        category: promoteCategory,
        suiteRunId: suiteRunId || undefined,
      });
      setMessage(`Evaluated: ${String((res.evidence as { status?: string })?.status)}`);
      await refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const promote = async () => {
    setBusy(true);
    try {
      const domain = suites.find((s) => s.suiteId === suiteId)?.domain || "image";
      const res = await api.promptIntelligence.v2.promote({
        providerId,
        modelRevision: "default",
        domain,
        category: promoteCategory,
        strategy: promoteStrategy,
        force: false,
      });
      if ((res as { detail?: { code?: string } }).detail?.code === "INSUFFICIENT_EVIDENCE" || !res.ok) {
        // surface typed refusal
        const detail = (res as { detail?: { code?: string; message?: string } }).detail;
        setMessage(detail?.message || "Promotion refused (insufficient evidence).");
      } else {
        setMessage(`Promoted ${promoteStrategy} for ${promoteCategory}`);
      }
      await refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const rollback = async () => {
    setBusy(true);
    try {
      const domain = suites.find((s) => s.suiteId === suiteId)?.domain || "image";
      await api.promptIntelligence.v2.rollback({
        providerId,
        modelRevision: "default",
        domain,
        category: promoteCategory,
      });
      setMessage(`Rolled back ${promoteCategory}`);
      await refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section
      className="pi-bench-dashboard panel"
      data-testid="prompt-intelligence-benchmark-dashboard"
      aria-label="Prompt Intelligence Benchmark Dashboard"
    >
      <header className="pi-bench-dashboard__header">
        <h2>Prompt Intelligence V2 Benchmarks</h2>
        <p className="muted">
          Category-scoped live certification. Automatic bilingual stays Off globally. Human blind review is required for
          creative quality.
        </p>
      </header>

      <div className="pi-bench-dashboard__controls">
        <label>
          Suite
          <select
            data-testid="pi-bench-suite"
            value={suiteId}
            onChange={(e) => setSuiteId(e.target.value)}
          >
            {suites.map((s) => (
              <option key={s.suiteId} value={s.suiteId}>
                {s.suiteId} ({s.domain}, {s.matrixMode})
              </option>
            ))}
          </select>
        </label>
        <label>
          Provider
          <input
            data-testid="pi-bench-provider"
            value={providerId}
            onChange={(e) => setProviderId(e.target.value)}
          />
        </label>
        <button type="button" className="primary" disabled={busy} data-testid="pi-bench-start" onClick={() => void startDryRun()}>
          {busy ? "Working…" : "Start dry-run suite"}
        </button>
        {suiteRunId ? (
          <>
            <button type="button" disabled={busy} onClick={() => void api.promptIntelligence.v2.pause(suiteRunId).then(refresh)}>
              Pause
            </button>
            <button type="button" disabled={busy} onClick={() => void api.promptIntelligence.v2.resume(suiteRunId).then(refresh)}>
              Resume
            </button>
            <button
              type="button"
              disabled={busy}
              data-testid="pi-bench-cancel"
              onClick={() => void api.promptIntelligence.v2.cancel(suiteRunId).then(refresh)}
            >
              Cancel
            </button>
          </>
        ) : null}
      </div>

      {message ? (
        <p className="pi-bench-dashboard__message" data-testid="pi-bench-message">
          {message}
        </p>
      ) : null}

      {status ? (
        <div className="pi-bench-dashboard__status" data-testid="pi-bench-status">
          <strong>Run status</strong>
          <pre>{JSON.stringify(status.counts || status, null, 2)}</pre>
        </div>
      ) : null}

      <div className="pi-bench-dashboard__columns">
        <div>
          <h3>Blind comparisons</h3>
          <ul data-testid="pi-bench-review-list">
            {reviews.map((r) => (
              <li key={r.comparisonId}>
                <button
                  type="button"
                  className={selectedReview?.comparisonId === r.comparisonId ? "primary" : "ghost"}
                  data-testid={`pi-bench-review-${r.comparisonId}`}
                  onClick={() => {
                    setSelectedReview(r);
                    setSlotScores({});
                  }}
                >
                  {r.benchmarkId} {r.submitted ? "(reviewed)" : "(blind)"}
                </button>
              </li>
            ))}
          </ul>
          {selectedReview ? (
            <div className="pi-bench-compare" data-testid="pi-bench-comparison-viewer">
              <p className="eyebrow">
                {selectedReview.revealed ? "Strategies revealed" : "Strategy labels hidden until submit"}
              </p>
              {(selectedReview.items || []).map((item) => (
                <div key={item.slotId} className="pi-bench-compare__slot">
                  <strong>
                    {item.slotId}
                    {selectedReview.revealed && selectedReview.strategyMap?.[item.slotId]
                      ? ` · ${selectedReview.strategyMap[item.slotId]}`
                      : ""}
                  </strong>
                  <label>
                    Score 0–100
                    <input
                      type="number"
                      min={0}
                      max={100}
                      data-testid={`pi-bench-score-${item.slotId}`}
                      value={slotScores[item.slotId] ?? 70}
                      onChange={(e) =>
                        setSlotScores((prev) => ({ ...prev, [item.slotId]: Number(e.target.value) }))
                      }
                    />
                  </label>
                </div>
              ))}
              {!selectedReview.submitted ? (
                <button
                  type="button"
                  className="primary"
                  disabled={busy}
                  data-testid="pi-bench-submit-review"
                  onClick={() => void submitBlindReview()}
                >
                  Submit blind review
                </button>
              ) : null}
            </div>
          ) : null}
        </div>

        <div>
          <h3>Certification</h3>
          <label>
            Category
            <input
              data-testid="pi-bench-category"
              value={promoteCategory}
              onChange={(e) => setPromoteCategory(e.target.value)}
            />
          </label>
          <label>
            Strategy
            <select
              data-testid="pi-bench-strategy"
              value={promoteStrategy}
              onChange={(e) => setPromoteStrategy(e.target.value)}
            >
              <option value="refined-english">refined-english</option>
              <option value="bilingual-subtle">bilingual-subtle</option>
              <option value="bilingual-balanced">bilingual-balanced</option>
              <option value="bilingual-strong">bilingual-strong</option>
            </select>
          </label>
          <div className="row-actions">
            <button type="button" disabled={busy} data-testid="pi-bench-evaluate" onClick={() => void evaluate()}>
              Evaluate
            </button>
            <button type="button" className="primary" disabled={busy} data-testid="pi-bench-promote" onClick={() => void promote()}>
              Promote
            </button>
            <button type="button" disabled={busy} data-testid="pi-bench-rollback" onClick={() => void rollback()}>
              Rollback
            </button>
          </div>
          <ul data-testid="pi-bench-evidence-list">
            {evidence.map((ev, idx) => (
              <li key={idx}>
                {String(ev.providerId)}/{String(ev.domain)}/{String(ev.category)} → {String(ev.status)}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
