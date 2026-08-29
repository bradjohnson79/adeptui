import { useTranslation } from "react-i18next";
import {
  trackControlLabel,
  type TrackControl,
} from "../../timelineMaster/trackFlags";

function TrackGlyph({ name }: { name: TrackControl | "plus" }) {
  const common = { width: 12, height: 12, viewBox: "0 0 16 16", fill: "none", stroke: "currentColor", strokeWidth: 1.4 };
  if (name === "eye") {
    return (
      <svg {...common} aria-hidden>
        <path d="M1.5 8s2.5-4.5 6.5-4.5S14.5 8 14.5 8 12 12.5 8 12.5 1.5 8 1.5 8z" />
        <circle cx="8" cy="8" r="1.8" />
      </svg>
    );
  }
  if (name === "lock") {
    return (
      <svg {...common} aria-hidden>
        <rect x="3.5" y="7" width="9" height="6.5" rx="1" />
        <path d="M5.5 7V5.2a2.5 2.5 0 0 1 5 0V7" />
      </svg>
    );
  }
  if (name === "mute") {
    return (
      <svg {...common} aria-hidden>
        <path d="M3 6.5h2.2L9 3.5v9L5.2 9.5H3z" />
        <path d="M11 6.5l3 3M14 6.5l-3 3" />
      </svg>
    );
  }
  if (name === "solo") {
    return (
      <svg {...common} aria-hidden>
        <path d="M12.5 4.5A5.5 5.5 0 1 0 8 13.5c2.4 0 4-1.5 4-3.2 0-1.1-.8-2-1.8-2H8.6" />
      </svg>
    );
  }
  return (
    <svg {...common} aria-hidden>
      <path d="M8 3v10M3 8h10" />
    </svg>
  );
}

export function TimelineTrackLabel({
  label,
  labelKey,
  testId,
  controls = ["eye", "lock"],
  controlState,
  onControlToggle,
  onAction,
}: {
  label: string;
  labelKey?: string;
  testId?: string;
  controls?: TrackControl[];
  controlState?: Partial<Record<TrackControl, boolean>>;
  onControlToggle?: (control: TrackControl) => void;
  onAction?: () => void;
}) {
  const { t } = useTranslation("timeline");
  const text = labelKey ? t(labelKey, { defaultValue: label }) : label;
  const slug = label.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return (
    <div className="timeline-v2__track-label" data-testid={testId || `timeline-v2-label-${slug}`}>
      <span className="timeline-v2__track-label-text">{text}</span>
      <div className="timeline-v2__track-label-tools">
        {controls.map((control) => {
          const active = Boolean(controlState?.[control]);
          const title = trackControlLabel(control, active, text);
          return (
            <button
              key={control}
              type="button"
              className={`timeline-v2__track-label-icon${active ? " is-active" : ""}`}
              aria-pressed={active}
              aria-label={title}
              title={title}
              data-testid={`track-control-${slug}-${control}`}
              onClick={() => onControlToggle?.(control)}
            >
              <TrackGlyph name={control} />
            </button>
          );
        })}
        {onAction ? (
          <button
            type="button"
            className="timeline-v2__track-label-add"
            aria-label={`Add ${text}`}
            data-testid={`track-add-${slug}`}
            onClick={onAction}
          >
            <TrackGlyph name="plus" />
          </button>
        ) : null}
      </div>
    </div>
  );
}
