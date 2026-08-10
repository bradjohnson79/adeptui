import { Button } from "../ui/Button";

export type StudioLaunchTarget = "timeline" | "magi" | "director";

type StudioLaunchCardsProps = {
  busy?: boolean;
  onOpen: (target: StudioLaunchTarget) => void;
};

const CARDS: {
  id: "timeline" | "magi";
  title: string;
  tagline: string;
  description: string;
  cta: string;
  imageSrc: string;
  imageAlt: string;
  testId: string;
  accent: "timeline" | "magi";
}[] = [
  {
    id: "timeline",
    title: "Timeline Generator",
    tagline: "Monitor. Tracks. Shot direction.",
    description:
      "Compose cinematic stills and sequences from your creative brief — camera, continuity, and generation in one Timeline workspace.",
    cta: "Open Timeline →",
    imageSrc: "/images/hero/Timeline_Anadriya_4-3.png",
    imageAlt: "Adept UI Timeline Generator — Anadriya",
    testId: "timeline-launch-card",
    accent: "timeline",
  },
  {
    id: "magi",
    title: "MAGI Editor",
    tagline: "Cut. Change. Create. All Types. All Takes.",
    description:
      "AI-native editing with MAGI Command, Actions, and Recipes — certified image edits today, honest multimodal tools as they certify.",
    cta: "Open MAGI Editor →",
    imageSrc: "/images/hero/MAGI_Korri_4-3.png",
    imageAlt: "Adept UI MAGI Editor — Korri",
    testId: "magi-launch-card",
    accent: "magi",
  },
];

export function StudioLaunchCards({ busy = false, onOpen }: StudioLaunchCardsProps) {
  return (
    <section
      className="gs-studio-launch-row"
      aria-label="Timeline Generator and MAGI Editor"
      data-testid="studio-launch-cards"
    >
      {CARDS.map((card) => (
        <article
          key={card.id}
          className={`glass-section gs-studio-launch-card gs-studio-launch-card--${card.accent}`}
          data-testid={card.testId}
        >
          <div className="gs-studio-launch-card__media">
            <img src={card.imageSrc} alt={card.imageAlt} loading="lazy" />
            <div className="gs-studio-launch-card__scrim" aria-hidden="true" />
          </div>
          <div className="gs-studio-launch-card__content">
            <p className="gs-studio-launch-card__tagline">{card.tagline}</p>
            <h2>{card.title}</h2>
            <p className="gs-studio-launch-card__desc">{card.description}</p>
            <Button
              type="button"
              variant="primary"
              disabled={busy}
              data-testid={`${card.id}-launch-open`}
              onClick={() => onOpen(card.id)}
            >
              {card.cta}
            </Button>
          </div>
        </article>
      ))}
    </section>
  );
}
