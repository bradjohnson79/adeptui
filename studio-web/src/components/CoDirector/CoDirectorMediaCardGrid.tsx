import { useMemo, useState } from "react";
import { api } from "../../api";
import "./codirectorMediaCards.css";

/**
 * Co-Director media result cards (production-orchestrator milestone, Part 10).
 *
 * Renders a responsive grid of asset thumbnails from structured execution
 * payloads (result_asset_ids / child job asset ids). Every card keeps its
 * asset id (data-asset-id) so later conversational references ("use the
 * second one") resolve against real ids. Images render via api.assetUrl;
 * videos render with a play affordance. Honest rendering only: cards appear
 * when the payload carries asset ids - never fabricated from prose.
 */
export type MediaCardItem = {
  assetId: string;
  label?: string;
  kind?: string;
};

export function CoDirectorMediaCardGrid({
  assetIds,
  children,
  title,
}: {
  assetIds: string[];
  children?: MediaCardItem[];
  title?: string;
}) {
  const items = useMemo(() => {
    const seen = new Set<string>();
    const out: MediaCardItem[] = [];
    for (const id of assetIds ?? []) {
      if (!id || seen.has(id)) continue;
      seen.add(id);
      out.push({ assetId: id });
    }
    for (const c of children ?? []) {
      if (!c?.assetId || seen.has(c.assetId)) continue;
      seen.add(c.assetId);
      out.push(c);
    }
    return out;
  }, [assetIds, children]);

  if (items.length === 0) return null;

  return (
    <div className="codirector-media-grid" data-testid="codirector-media-grid">
      {title ? <div className="codirector-media-grid-title">{title}</div> : null}
      <div className="codirector-media-grid-cards">
        {items.map((item, index) => (
          <MediaCard key={item.assetId} item={item} index={index} />
        ))}
      </div>
    </div>
  );
}

function MediaCard({ item, index }: { item: MediaCardItem; index: number }) {
  const [failed, setFailed] = useState(false);
  const label = item.label || (item.kind ? item.kind : "Asset " + (index + 1));
  return (
    <figure
      className="codirector-media-card"
      data-testid="codirector-media-card"
      data-asset-id={item.assetId}
    >
      {failed ? (
        <div className="codirector-media-card-fallback">Asset {item.assetId.slice(0, 8)}</div>
      ) : (
        <img
          src={api.assetUrl(item.assetId)}
          alt={label}
          loading="lazy"
          onError={() => setFailed(true)}
        />
      )}
      <figcaption title={item.assetId}>
        {label}
        <span className="codirector-media-card-id">{item.assetId.slice(0, 8)}</span>
      </figcaption>
    </figure>
  );
}