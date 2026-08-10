import { useState } from "react";
import { Button } from "../ui";
import { api } from "../../api";
import type { CoDirectorNextStepOption } from "./types";
import { useCoDirectorSession } from "./CoDirectorSession";

function promptForOption(option: CoDirectorNextStepOption, ownership?: string): string {
  if (option.type === "CONTINUE_STORY" || option.type === "KEEP_LISTENING") {
    return "I'd like to keep telling the story — please keep listening and stay with me in discovery.";
  }
  if (option.type === "BUILD_TREATMENT") {
    if (ownership === "together") {
      return "Let's write a working treatment together from what we have so far.";
    }
    if (ownership === "assistant") {
      return "Draft a working treatment for me from what we have so far — I'll review before anything is final.";
    }
    return "I'll write the treatment — help me structure it from what we have so far.";
  }
  if (option.type === "EXPLORE_CHARACTER") {
    return "Let's explore the central character more deeply — who they are and what they want.";
  }
  if (option.type === "VISUAL_DEVELOPMENT") {
    return "Let's explore the visual concept and tone for the series.";
  }
  if (option.type === "EXPLORE_WORLD") {
    return "Let's define the world rules more clearly.";
  }
  if (option.type === "BUILD_PITCH") {
    if (ownership === "together") return "Let's prepare a short pitch together.";
    if (ownership === "assistant") return "Draft a short pitch for me to review.";
    return "I'll draft the pitch — help me sharpen it.";
  }
  if (option.type === "REVIEW_WIKI") {
    return "Please review what has been documented so far and tell me what still feels thin.";
  }
  return `Let's continue with: ${option.label}`;
}

function optionDescription(option: CoDirectorNextStepOption): string {
  return (
    option.shortDescription ||
    option.whyNow ||
    (option.type === "CONTINUE_STORY"
      ? "Stay in discovery and keep building the story together."
      : "Take this step when you're ready.")
  );
}

/** Soft invitations under the latest assistant message — card grid, not a workflow menu. */
export function CoDirectorNextStepChips() {
  const { activity, busy, send, uiContext } = useCoDirectorSession();
  const options = activity?.nextStepOptions || [];
  const intro = activity?.nextStepIntro || "Where should we go next?";
  const [ownershipFor, setOwnershipFor] = useState<CoDirectorNextStepOption | null>(null);
  const [dismissed, setDismissed] = useState<string[]>([]);

  if (!options.length) return null;
  const ordered = [...options].sort((a, b) => {
    if (a.type === "CONTINUE_STORY") return -1;
    if (b.type === "CONTINUE_STORY") return 1;
    return 0;
  });
  const visible = ordered.filter((o) => !dismissed.includes(o.id)).slice(0, 4);
  if (!visible.length) return null;

  const dismiss = async (option: CoDirectorNextStepOption) => {
    setDismissed((prev) => [...prev, option.id]);
    const projectId = uiContext.projectId;
    if (!projectId) return;
    try {
      await api.codirectorDeferNextStep(projectId, {
        optionType: option.type,
        userReason: "dismissed_in_ui",
      });
    } catch {
      /* local dismiss still applies */
    }
  };

  return (
    <div
      className="codirector-next-steps"
      data-testid="codirector-next-step-options"
      style={{ marginTop: "0.65rem" }}
    >
      <p className="muted" style={{ marginBottom: "0.5rem" }}>
        {intro.includes("Where") ? intro : "Where should we go next?"}
      </p>
      {ownershipFor ? (
        <div className="codirector-content-card" data-testid="codirector-next-step-ownership">
          <p>How should we handle “{ownershipFor.label}”?</p>
          {ownershipFor.whyNow ? (
            <p className="muted" data-testid="codirector-ownership-why-now">
              {ownershipFor.whyNow}
            </p>
          ) : null}
          {ownershipFor.previewSpine ? (
            <p className="muted" data-testid="codirector-ownership-preview">
              Preview: {ownershipFor.previewSpine}
            </p>
          ) : null}
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem", marginTop: "0.35rem" }}>
            <Button
              compact
              disabled={busy}
              data-testid="codirector-ownership-me"
              onClick={() => {
                const opt = ownershipFor;
                setOwnershipFor(null);
                void send(promptForOption(opt, "me"), "chat");
              }}
            >
              I’ll write it
            </Button>
            <Button
              compact
              variant="ghost"
              disabled={busy}
              data-testid="codirector-ownership-together"
              onClick={() => {
                const opt = ownershipFor;
                setOwnershipFor(null);
                void send(promptForOption(opt, "together"), "chat");
              }}
            >
              Let’s write it together
            </Button>
            <Button
              compact
              variant="ghost"
              disabled={busy}
              data-testid="codirector-ownership-assistant"
              onClick={() => {
                const opt = ownershipFor;
                setOwnershipFor(null);
                void send(promptForOption(opt, "assistant"), "chat");
              }}
            >
              Draft it for me
            </Button>
            <Button
              compact
              variant="ghost"
              disabled={busy}
              data-testid="codirector-ownership-keep-story"
              onClick={() => {
                setOwnershipFor(null);
                void send(
                  promptForOption({ ...ownershipFor, type: "CONTINUE_STORY", label: "Keep telling the story" }),
                  "chat",
                );
              }}
            >
              Keep developing the story
            </Button>
            <Button compact variant="ghost" disabled={busy} onClick={() => setOwnershipFor(null)}>
              Not now
            </Button>
          </div>
        </div>
      ) : (
        <>
          <div
            className="codirector-next-step-grid"
            data-testid="codirector-next-step-grid"
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(11rem, 1fr))",
              gap: "0.5rem",
              maxWidth: "36rem",
            }}
          >
            {visible.map((option) => (
              <button
                key={option.id}
                type="button"
                className="codirector-content-card codirector-next-step-card"
                disabled={busy || option.readiness === "NOT_READY"}
                data-testid={`codirector-next-step-${option.type}`}
                data-primary={option.type === "CONTINUE_STORY" ? "true" : "false"}
                title={optionDescription(option)}
                onClick={() => {
                  if (busy) return;
                  if (option.readiness === "NOT_READY") return;
                  if (option.ownershipRequired) {
                    setOwnershipFor(option);
                    return;
                  }
                  void send(promptForOption(option), "chat");
                }}
                style={{
                  textAlign: "left",
                  cursor: busy || option.readiness === "NOT_READY" ? "not-allowed" : "pointer",
                  opacity: option.readiness === "NOT_READY" ? 0.55 : 1,
                  border:
                    option.type === "CONTINUE_STORY"
                      ? "1px solid var(--accent, #6b8cae)"
                      : "1px solid transparent",
                  padding: "0.65rem 0.75rem",
                }}
              >
                <strong style={{ display: "block", marginBottom: "0.25rem" }}>{option.label}</strong>
                <span className="muted" style={{ fontSize: "0.8rem", lineHeight: 1.35 }}>
                  {optionDescription(option)}
                </span>
              </button>
            ))}
          </div>
          <div style={{ marginTop: "0.45rem" }}>
            <Button
              compact
              variant="ghost"
              disabled={busy}
              data-testid="codirector-next-steps-dismiss"
              onClick={() => {
                visible.forEach((o) => {
                  void dismiss(o);
                });
              }}
            >
              Not now
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
