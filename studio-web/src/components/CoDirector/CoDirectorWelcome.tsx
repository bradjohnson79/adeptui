import { useCoDirectorSession } from "./CoDirectorSession";

export function CoDirectorWelcome({ compact = false }: { compact?: boolean }) {
  const { welcomeSuggestions, send, busy } = useCoDirectorSession();

  return (
    <div className={`codirector-welcome ${compact ? "compact" : ""}`}>
      <h3>What would you like to create?</h3>
      <p className="muted">Ask anything about scenes, prompts, storyboards, or production next steps.</p>
      <div className="codirector-suggestions" role="list">
        {welcomeSuggestions.map((item) => (
          <button
            key={item.id}
            type="button"
            role="listitem"
            className="codirector-suggestion"
            disabled={busy}
            onClick={() => void send(item.text, item.mode)}
          >
            <strong>{item.label}</strong>
            {!compact && item.description ? <span>{item.description}</span> : null}
          </button>
        ))}
      </div>
    </div>
  );
}
