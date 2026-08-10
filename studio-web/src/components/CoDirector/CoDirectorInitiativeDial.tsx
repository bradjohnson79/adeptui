import { useEffect, useState } from "react";
import { api } from "../../api";
import { useCoDirectorSession } from "./CoDirectorSession";

const LEVELS: { id: string; label: string }[] = [
  { id: "QUIET_PARTNER", label: "Quiet Partner" },
  { id: "COLLABORATIVE_PARTNER", label: "Collaborative Partner" },
  { id: "PROACTIVE_PRODUCER", label: "Proactive Producer" },
  { id: "HANDS_ON_CO_CREATOR", label: "Hands-On Co-Creator" },
];

/**
 * Creator-facing initiative dial — how hands-on Co-Director should be.
 * Progressive disclosure: lives under Options; plain language only.
 */
export function CoDirectorInitiativeDial({ compact = false }: { compact?: boolean }) {
  const { uiContext } = useCoDirectorSession();
  const projectId = uiContext.projectId;
  const [level, setLevel] = useState("COLLABORATIVE_PARTNER");
  const [tips, setTips] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    api
      .getCreativeOperating(projectId)
      .then((body) => {
        if (cancelled) return;
        setLevel(String(body.initiativeLevel || "COLLABORATIVE_PARTNER"));
        setTips(body.initiativeTips || {});
      })
      .catch(() => {
        /* keep defaults */
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  if (!projectId) return null;

  async function select(next: string) {
    setSaving(true);
    setError(null);
    setLevel(next);
    try {
      await api.setCreativeInitiative(projectId!, next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save partnership style");
    } finally {
      setSaving(false);
    }
  }

  const tip = tips[level] || LEVELS.find((l) => l.id === level)?.label || "";

  return (
    <section
      className={compact ? undefined : "codirector-content-card"}
      data-testid="codirector-initiative-dial"
      aria-label="How hands-on should Co-Director be"
      style={compact ? { marginTop: "0.85rem" } : { marginBottom: "0.75rem" }}
    >
      <p className="eyebrow">Partnership style</p>
      <p className="muted" style={{ margin: "0 0 0.4rem", fontSize: "0.85rem" }}>
        How hands-on should I be while we work?
        <button
          type="button"
          className="ghost"
          title="Quiet Partner listens and organizes quietly. Collaborative offers ideas at natural pauses. Proactive Producer surfaces next steps. Hands-On Co-Creator drafts with you more often."
          aria-label="About partnership style"
          data-testid="codirector-initiative-tip"
          style={{ marginLeft: "0.25rem" }}
        >
          (?)
        </button>
      </p>
      <div className="codirector-filter-chips" role="group" aria-label="Partnership style">
        {LEVELS.map((item) => (
          <button
            key={item.id}
            type="button"
            disabled={saving}
            className={level === item.id ? "primary is-active" : ""}
            aria-pressed={level === item.id}
            data-testid={`codirector-initiative-${item.id}`}
            onClick={() => void select(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
      {tip ? (
        <p className="muted" data-testid="codirector-initiative-description" style={{ fontSize: "0.8rem" }}>
          {tip}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="muted">
          {error}
        </p>
      ) : null}
    </section>
  );
}
