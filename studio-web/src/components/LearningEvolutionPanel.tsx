import { useCallback, useEffect, useState } from "react";
import type { Project } from "../types";
import { api } from "../api";
import { PanelHeading } from "./HelpTip";

type Lesson = {
  id: string;
  layer: string;
  status: string;
  version: number;
  title?: string;
  text: string;
  confidence?: number;
  evidenceScore?: number;
  mistakeClass?: string;
  regressionPassed?: boolean;
  regressionSuiteId?: string | null;
};

type Dash = {
  pendingApprovals?: Lesson[];
  activeLessons?: Lesson[];
  recentRollbacks?: Lesson[];
  calibrationHealth?: Record<string, unknown>;
  retrospectives?: Array<{ id: string; summary?: string }>;
  activeStrategyPack?: { id?: string; name?: string; version?: number } | null;
  safety?: Record<string, unknown>;
};

export function LearningEvolutionPanel({
  project,
  enabled,
}: {
  project: Project;
  enabled: boolean;
}) {
  const [dash, setDash] = useState<Dash | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!enabled || !project.id) return;
    setError(null);
    setBusy(true);
    try {
      const res = (await api.m212Dashboard(project.id)) as Dash;
      setDash(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Learning Evolution");
    } finally {
      setBusy(false);
    }
  }, [enabled, project.id]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  if (!enabled) {
    return (
      <div className="panel" data-testid="learning-evolution-disabled">
        <PanelHeading
          title="Learning Evolution"
          tip="M2.12 adaptive learning is off (STUDIO_FEATURE_CODIRECTOR_ADAPTIVE_LEARNING_V1)."
        />
        <p className="muted">
          Feature flag default OFF. Enable to review candidate lessons, promote, and rollback.
        </p>
      </div>
    );
  }

  const pending = dash?.pendingApprovals || [];
  const active = dash?.activeLessons || [];
  const rolled = dash?.recentRollbacks || [];
  const retros = dash?.retrospectives || [];

  const promote = async (id: string) => {
    setBusy(true);
    setMsg(null);
    try {
      await api.m212PromoteLesson(id, {
        actor: "user",
        role: "user",
        note: "UI promote",
        intoLearningPy: true,
      });
      setMsg("Promoted lesson " + id.slice(0, 8));
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Promote failed");
    } finally {
      setBusy(false);
    }
  };

  const regress = async (id: string) => {
    setBusy(true);
    try {
      await api.m212RunRegression(id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Regression failed");
    } finally {
      setBusy(false);
    }
  };

  const rollback = async (id: string) => {
    setBusy(true);
    try {
      await api.m212RollbackLesson(id, { actor: "user", note: "UI rollback" });
      setMsg("Rolled back " + id.slice(0, 8));
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rollback failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel" data-testid="learning-evolution-panel">
      <PanelHeading
        title="Learning Evolution"
        tip="Structured lessons and strategy packs — no fine-tuning, no Manifest/lock mutation, system layer never auto-activates."
      />
      <div className="row-actions">
        <button type="button" className="ghost" disabled={busy} onClick={() => void refresh()}>
          Refresh
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {msg && <p className="scene-meta">{msg}</p>}

      <div className="section-label" style={{ marginTop: 12 }}>
        Pending approvals
      </div>
      {pending.length === 0 && <p className="scene-meta">No candidate lessons.</p>}
      {pending.map((l) => (
        <div key={l.id} className="recommend-card" data-testid="m212-candidate">
          <p className="scene-meta">
            <span className="pill">{l.layer}</span>{" "}
            <span className="pill">{l.mistakeClass || "general"}</span>{" "}
            conf {(l.confidence ?? 0).toFixed(2)} / evidence {(l.evidenceScore ?? 0).toFixed(2)}
          </p>
          <p>{l.text}</p>
          <div className="row-actions">
            <button type="button" className="ghost" disabled={busy} onClick={() => void regress(l.id)}>
              Run regression
            </button>
            <button type="button" disabled={busy} onClick={() => void promote(l.id)}>
              Approve / promote
            </button>
            <button type="button" className="ghost" disabled={busy} onClick={() => void rollback(l.id)}>
              Reject
            </button>
          </div>
        </div>
      ))}

      <div className="section-label" style={{ marginTop: 14 }}>
        Active lessons
      </div>
      {active.length === 0 && <p className="scene-meta">No active lessons.</p>}
      {active.map((l) => (
        <div key={l.id} className="recommend-card" data-testid="m212-active-lesson">
          <p className="scene-meta">
            <span className="pill">{l.layer}</span> v{l.version}
          </p>
          <p>{l.text}</p>
          <button type="button" className="ghost" disabled={busy} onClick={() => void rollback(l.id)}>
            Rollback
          </button>
        </div>
      ))}

      <div className="section-label" style={{ marginTop: 14 }}>
        Retrospectives
      </div>
      {retros.length === 0 && <p className="scene-meta">None yet.</p>}
      {retros.map((r) => (
        <p key={r.id} className="scene-meta">
          {r.summary || r.id}
        </p>
      ))}

      <div className="section-label" style={{ marginTop: 14 }}>
        Calibration / rollbacks / strategy
      </div>
      <p className="scene-meta" data-testid="m212-calibration">
        Calibration: {JSON.stringify(dash?.calibrationHealth || {})}
      </p>
      <p className="scene-meta" data-testid="m212-strategy">
        Strategy: {dash?.activeStrategyPack?.name || "(none)"} v
        {dash?.activeStrategyPack?.version || "-"}
      </p>
      <p className="scene-meta">Recent rollbacks: {rolled.length}</p>
    </div>
  );
}
