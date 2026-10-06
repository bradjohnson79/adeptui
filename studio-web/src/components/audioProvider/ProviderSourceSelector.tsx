import type { AdeptAudioProviderSource, ElevenLabsHealth } from "../../audioProvider/types";

type Props = {
  id: string;
  label?: string;
  source: AdeptAudioProviderSource;
  onChange: (next: AdeptAudioProviderSource) => void;
  health: ElevenLabsHealth | null;
  healthBusy?: boolean;
  disabled?: boolean;
  compact?: boolean;
};

/**
 * Local | ElevenLabs API.
 * Local stays available. ElevenLabs is disabled until a valid key is saved.
 */
export function ProviderSourceSelector({
  id,
  label = "Provider",
  source,
  onChange,
  health,
  healthBusy = false,
  disabled = false,
  compact = false,
}: Props) {
  const elevenSelected = source === "elevenlabs";
  const notConfigured = Boolean(health && !health.configured);
  const connectionFail =
    elevenSelected &&
    health &&
    health.configured &&
    ["error", "fail", "failed", "unreachable", "offline"].some((s) =>
      health.connectionStatus.toLowerCase().includes(s),
    );

  return (
    <div
      className={`adept-provider-source${compact ? " adept-provider-source--compact" : ""}`}
      data-testid={`${id}-provider-source`}
      data-provider={source}
    >
      <label className="adept-provider-source__label" htmlFor={`${id}-provider-select`}>
        {label}
      </label>
      <select
        id={`${id}-provider-select`}
        className="adept-provider-source__select"
        value={source}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value === "elevenlabs" ? "elevenlabs" : "local")}
        aria-describedby={
          notConfigured || connectionFail ? `${id}-provider-status` : undefined
        }
      >
        <option value="local">Local</option>
        <option value="elevenlabs" disabled={Boolean(health) && !health?.configured}>
          ElevenLabs API
        </option>
      </select>
      {healthBusy && elevenSelected ? (
        <p className="adept-provider-source__hint" role="status">
          Checking API — ElevenLabs availability…
        </p>
      ) : null}
      {notConfigured && elevenSelected ? (
        <p
          id={`${id}-provider-status`}
          className="adept-provider-source__alert"
          role="alert"
          data-testid={`${id}-provider-unavailable`}
        >
          ElevenLabs is currently unavailable. Check your API configuration in Setup.
        </p>
      ) : notConfigured ? (
        <p
          id={`${id}-provider-status`}
          className="adept-provider-source__alert"
          role="alert"
          data-testid={`${id}-provider-not-configured`}
        >
          {health?.message || "ElevenLabs API key not configured."}
        </p>
      ) : null}
      {connectionFail ? (
        <p
          id={`${id}-provider-status`}
          className="adept-provider-source__alert"
          role="alert"
          data-testid={`${id}-provider-connection-fail`}
        >
          ElevenLabs is currently unavailable. Check your API configuration in Setup.
        </p>
      ) : null}
      {elevenSelected && health?.configured && !connectionFail && !healthBusy ? (
        <p className="adept-provider-source__ok" role="status" data-testid={`${id}-provider-ok`}>
          {health.message || "API — ElevenLabs ready"}
        </p>
      ) : null}
    </div>
  );
}
