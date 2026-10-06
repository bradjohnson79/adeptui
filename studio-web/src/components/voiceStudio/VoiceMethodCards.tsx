import type { ReactNode } from "react";
import type { VoiceIdentityMethod } from "./voiceIdentityRoute";

type Card = {
  id: VoiceIdentityMethod;
  label: string;
  description: string;
  icon: ReactNode;
};

function MethodIcon({ children }: { children: ReactNode }) {
  return (
    <svg
      className="vip-method-svg"
      width="22"
      height="22"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

const CARDS: Card[] = [
  {
    id: "create",
    label: "Create New Voice",
    description: "Describe the voice, then play the samples you generate.",
    icon: (
      <MethodIcon>
        <rect x="9" y="3" width="6" height="11" rx="3" />
        <path d="M5 11a7 7 0 0014 0M12 18v3M8 21h8" />
      </MethodIcon>
    ),
  },
  {
    id: "existing",
    label: "Use Existing Voice",
    description: "Pick a saved voice, or assign audio you already have in your Project Library.",
    icon: (
      <MethodIcon>
        <path d="M4 20V8a2 2 0 012-2h3l2-2h5a2 2 0 012 2v14" />
        <path d="M4 20h16" />
      </MethodIcon>
    ),
  },
  {
    id: "elevenlabs",
    label: "Use ElevenLabs Voice",
    description: "Choose a voice from your ElevenLabs account and save it to this character.",
    icon: (
      <MethodIcon>
        <path d="M4 10v4M8 7v10M12 4v16M16 7v10M20 10v4" />
      </MethodIcon>
    ),
  },
  {
    id: "clone",
    label: "Clone from Recording",
    description: "Match a recording you have permission to use.",
    icon: (
      <MethodIcon>
        <circle cx="12" cy="12" r="3" />
        <path d="M12 5v2M12 17v2M5 12h2M17 12h2" />
        <path d="M7.5 7.5l1.4 1.4M15.1 15.1l1.4 1.4M7.5 16.5l1.4-1.4M15.1 8.9l1.4-1.4" />
      </MethodIcon>
    ),
  },
];

type Props = {
  method: VoiceIdentityMethod | null;
  onSelect: (method: VoiceIdentityMethod) => void;
  disabledReasons?: Partial<Record<VoiceIdentityMethod, string>>;
};

export function VoiceMethodCards({ method, onSelect, disabledReasons }: Props) {
  return (
    <div className="vip-method-grid">
      {CARDS.map((card) => {
        const reason = disabledReasons?.[card.id];
        return (
          <button
            key={card.id}
            type="button"
            className={"vip-method-card" + (method === card.id ? " selected" : "")}
            data-testid={"vs-method-" + card.id}
            aria-pressed={method === card.id}
            disabled={Boolean(reason)}
            onClick={() => onSelect(card.id)}
          >
            <span className="vip-method-icon">{card.icon}</span>
            <span className="vip-method-copy">
              <strong>{card.label}</strong>
              <span className="muted">{reason || card.description}</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}
