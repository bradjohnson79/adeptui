export type MediaCard = {
  id: string;
  kind: string;
  title: string;
  honesty?: string;
  groupKey?: string;
  status?: string;
  payload?: Record<string, unknown>;
};

export function UnifiedMediaCard({
  card,
  onExpand,
}: {
  card: MediaCard;
  onExpand: () => void;
}) {
  const honesty = card.honesty || "mocked";
  return (
    <article
      className="m214-media-card"
      data-testid={`m214-media-${card.kind}`}
      data-honesty={honesty}
    >
      <header>
        <span className="m214-media-kind">{card.kind}</span>
        <span className={`m214-honesty m214-honesty-${honesty}`} aria-label={`Honesty ${honesty}`}>
          {honesty.toUpperCase()}
        </span>
      </header>
      <p>{card.title}</p>
      <button type="button" onClick={onExpand}>
        Expand
      </button>
    </article>
  );
}
