import { HelpTip } from "../HelpTip";
import { CREATOR_SCOPE_HELP } from "../../creatorScope";
import "./globalScopeField.css";

export function GlobalScopeField({
  checked,
  disabled,
  onChange,
  testId = "creator-global",
  helpText = CREATOR_SCOPE_HELP,
}: {
  checked: boolean;
  disabled?: boolean;
  onChange: (next: boolean) => void;
  testId?: string;
  /** Override help tip (Prop ORDER 18 uses edit-from-any-project copy). */
  helpText?: string;
}) {
  return (
    <label className="creator-global-field" data-testid={testId}>
      <span className="creator-global-field__row">
        <input
          type="checkbox"
          checked={checked}
          disabled={disabled}
          onChange={(e) => onChange(e.target.checked)}
          data-testid={`${testId}-checkbox`}
          aria-describedby={`${testId}-help`}
        />
        <span className="creator-global-field__label">Global</span>
        <HelpTip text={helpText} label="What Global means" />
      </span>
    </label>
  );
}
