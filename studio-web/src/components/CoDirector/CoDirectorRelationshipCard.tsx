import { useEffect, useState } from "react";
import { api } from "../../api";
import { Button } from "../ui";
import { useCoDirectorSession } from "./CoDirectorSession";

const ROLES = [
  { id: "BALANCED", label: "Balanced Co-Director" },
  { id: "CREATIVE_SUPPORTER", label: "Creative Supporter" },
  { id: "STORY_PARTNER", label: "Story Partner" },
  { id: "PRODUCER", label: "Producer" },
  { id: "CREATIVE_DIRECTOR", label: "Creative Director" },
  { id: "RESEARCH_PARTNER", label: "Research Partner" },
  { id: "MARKETING_PITCH_PARTNER", label: "Marketing & Pitch Partner" },
  { id: "PRODUCTION_OPERATOR", label: "Production Operator" },
];

const OWNERSHIP = [
  { id: "USER_LEADS", label: "Advise while I create" },
  { id: "CO_CREATE", label: "Create it with me" },
  { id: "CODIRECTOR_LEADS", label: "Prepare first drafts for me" },
  { id: "CODIRECTOR_EXECUTES", label: "Take the lead unless I stop you" },
  { id: "ASK_EACH_TIME", label: "Ask me at each major stage" },
];

/**
 * Compact first-run relationship card — names + role + assistance depth + skip.
 * After save, starts a warm conversational acknowledgment (not a silent dismiss).
 */
export function CoDirectorRelationshipCard() {
  const { uiContext, send, busy } = useCoDirectorSession();
  const projectId = uiContext.projectId;
  const [needed, setNeeded] = useState(false);
  const [assistantName, setAssistantName] = useState("Co-Director");
  const [userName, setUserName] = useState("");
  const [role, setRole] = useState("BALANCED");
  const [ownership, setOwnership] = useState("CO_CREATE");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    api
      .getCoDirectorRelationship(projectId)
      .then((body) => {
        if (cancelled) return;
        const rel = body.relationship || {};
        setNeeded(!rel.onboarding_completed && !rel.onboarding_skipped);
        setAssistantName(String(rel.assistant_preferred_name || "Co-Director"));
        setUserName(String(rel.user_preferred_name || ""));
        setRole(String(rel.primary_role || "BALANCED"));
        setOwnership(String(rel.default_ownership || "CO_CREATE"));
      })
      .catch(() => {
        if (!cancelled) setNeeded(false);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  if (!projectId || !needed) return null;

  async function save(skip = false) {
    setSaving(true);
    setError(null);
    try {
      await api.updateCoDirectorRelationship(projectId!, {
        skip,
        assistantPreferredName: assistantName,
        userPreferredName: userName,
        primaryRole: role,
        defaultOwnership: ownership,
      });
      setNeeded(false);

      const roleLabel = ROLES.find((item) => item.id === role)?.label || role;
      const ownershipLabel = OWNERSHIP.find((item) => item.id === ownership)?.label || ownership;
      const you = (userName || "").trim() || "friend";
      const me = (assistantName || "").trim() || "Co-Director";

      // Kick off a live conversational turn so Co-Director acknowledges the form — never silent.
      if (!busy) {
        if (skip) {
          void send(
            "Let's skip the setup form for now and use balanced defaults. " +
              "Please greet me warmly, introduce yourself briefly, and invite me to start sharing the project.",
            "chat",
          );
        } else {
          void send(
            `I've filled in how I'd like us to work together. Please call me ${you}. ` +
              `I'd like to call you ${me}. I'd like you as my ${roleLabel}. ` +
              `For hands-on help, please ${ownershipLabel.toLowerCase()}. ` +
              "Please acknowledge our names and your role out loud, thank me for sharing, " +
              "and warmly invite me to start telling you about the project. Be conversational — don't go silent.",
            "chat",
          );
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save preferences");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section
      className="codirector-content-card"
      data-testid="codirector-relationship-card"
      aria-label="Working relationship"
      style={{ marginBottom: "0.75rem" }}
    >
      <p className="eyebrow">Working together</p>
      <p className="muted">
        Hello there. I’m looking forward to collaborating. What would you like to call me—and what should I call you?
      </p>
      <label className="muted" style={{ display: "block", marginTop: "0.5rem" }}>
        What should I call you?
        <input
          data-testid="codirector-relationship-user-name"
          value={userName}
          onChange={(e) => setUserName(e.target.value)}
          style={{ display: "block", width: "100%", marginTop: "0.25rem" }}
        />
      </label>
      <label className="muted" style={{ display: "block", marginTop: "0.5rem" }}>
        What would you like to call me?
        <input
          data-testid="codirector-relationship-assistant-name"
          value={assistantName}
          onChange={(e) => setAssistantName(e.target.value)}
          style={{ display: "block", width: "100%", marginTop: "0.25rem" }}
        />
      </label>
      <p className="muted" style={{ marginTop: "0.75rem" }}>
        How would you like me to work with you most of the time?
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem", marginTop: "0.35rem" }}>
        {ROLES.map((item) => (
          <button
            key={item.id}
            type="button"
            data-testid={`codirector-role-${item.id}`}
            className={role === item.id ? "button" : "button ghost"}
            onClick={() => setRole(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
      <p className="muted" style={{ marginTop: "0.75rem" }}>
        How hands-on would you like me to be?
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem", marginTop: "0.35rem" }}>
        {OWNERSHIP.map((item) => (
          <button
            key={item.id}
            type="button"
            data-testid={`codirector-ownership-${item.id}`}
            className={ownership === item.id ? "button" : "button ghost"}
            onClick={() => setOwnership(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
      {error ? (
        <p role="alert" className="muted">
          {error}
        </p>
      ) : null}
      <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.75rem" }}>
        <Button data-testid="codirector-relationship-save" disabled={saving || busy} onClick={() => void save(false)}>
          Save and continue
        </Button>
        <Button
          data-testid="codirector-relationship-skip"
          variant="ghost"
          disabled={saving || busy}
          onClick={() => void save(true)}
        >
          Skip for now
        </Button>
      </div>
    </section>
  );
}
