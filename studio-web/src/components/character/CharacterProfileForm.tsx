/**
 * Shared Character Profile form — Name / Gender / Profile / Style.
 * Used by both Character Creator Express and the standalone Character Creator.
 */
import type { CharacterProfile } from "./types";
import { CHARACTER_GENDER_OPTIONS, CHARACTER_STYLE_OPTIONS } from "./types";

type Props = {
  profile: CharacterProfile | null;
  disabled?: boolean;
  onChange: (fields: Record<string, unknown>) => void;
  autoFocusName?: boolean;
};

export function CharacterProfileForm({ profile, disabled, onChange, autoFocusName }: Props) {
  return (
    <div className="character-core__form">
      <label className="character-core__field">
        <span className="character-core__label">
          Character Name <em aria-hidden>*</em>
        </span>
        <input
          type="text"
          data-testid="character-field-name"
          value={profile?.name ?? ""}
          placeholder="e.g. Korri"
          autoFocus={autoFocusName}
          disabled={disabled}
          onChange={(e) => onChange({ name: e.target.value })}
        />
      </label>

      <label className="character-core__field">
        <span className="character-core__label">Gender</span>
        <select
          data-testid="character-field-gender"
          value={profile?.gender_presentation ?? ""}
          disabled={disabled}
          onChange={(e) => onChange({ gender_presentation: e.target.value })}
        >
          {CHARACTER_GENDER_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>

      <label className="character-core__field">
        <span className="character-core__label">Style</span>
        <select
          data-testid="character-field-style"
          value={profile?.visual_style ?? ""}
          disabled={disabled}
          onChange={(e) => onChange({ visual_style: e.target.value })}
        >
          {CHARACTER_STYLE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>

      <label className="character-core__field character-core__field--full">
        <span className="character-core__label">Character Profile</span>
        <textarea
          data-testid="character-field-profile"
          rows={5}
          value={profile?.description ?? ""}
          placeholder="Who is this character? Personality, look, and feel…"
          disabled={disabled}
          onChange={(e) => onChange({ description: e.target.value })}
        />
      </label>
    </div>
  );
}
