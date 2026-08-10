import { useMemo, useState } from "react";
import { api } from "../../api";
import type { Asset } from "../../types";

export type ReferenceFilter =
  | "all"
  | "characters"
  | "locations"
  | "props"
  | "images"
  | "previous"
  | "storyboard";

const FILTERS: { id: ReferenceFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "characters", label: "Characters" },
  { id: "locations", label: "Locations" },
  { id: "props", label: "Props" },
  { id: "images", label: "Images" },
  { id: "previous", label: "Previous Frames" },
  { id: "storyboard", label: "Storyboard" },
];

function assetTypeLabel(asset: Asset): string {
  const tag = (asset.tag || "").toLowerCase();
  const kind = (asset.kind || "").toLowerCase();
  if (kind.includes("character") || tag.includes("char") || tag.includes("portrait")) return "Character Image";
  if (kind.includes("location") || kind.includes("environment") || tag.includes("corridor") || tag.includes("loc"))
    return "Background";
  if (kind.includes("prop") || tag.includes("prop")) return "Prop";
  if (kind.includes("storyboard") || tag.includes("board")) return "Storyboard";
  if (kind === "image") return "Image";
  return kind ? kind[0].toUpperCase() + kind.slice(1) : "Image";
}

function assetBadge(asset: Asset): string | null {
  const type = assetTypeLabel(asset);
  if (type === "Character Image") return "Character";
  if (type === "Background") return "Location";
  if (type === "Prop") return "Prop";
  if (type === "Storyboard") return "Storyboard";
  return null;
}

function matchesFilter(asset: Asset, filter: ReferenceFilter): boolean {
  if (filter === "all" || filter === "images") return true;
  const type = assetTypeLabel(asset).toLowerCase();
  if (filter === "characters") return type.includes("character");
  if (filter === "locations") return type.includes("background") || type.includes("location");
  if (filter === "props") return type.includes("prop");
  if (filter === "storyboard") return type.includes("storyboard");
  if (filter === "previous") {
    const tag = (asset.tag || "").toLowerCase();
    return tag.includes("frame") || tag.includes("gen") || tag.includes("take");
  }
  return true;
}

export function ReferenceBrowser({
  assets,
  selectedIds,
  onChange,
}: {
  assets: Asset[];
  selectedIds: string[];
  onChange: (ids: string[]) => void;
}) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<ReferenceFilter>("all");
  const [hoverId, setHoverId] = useState<string | null>(null);

  const selected = useMemo(() => new Set(selectedIds), [selectedIds]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return assets.filter((asset) => {
      if (!matchesFilter(asset, filter)) return false;
      if (!q) return true;
      const hay = `${asset.tag || ""} ${asset.filename || ""} ${assetTypeLabel(asset)}`.toLowerCase();
      return hay.includes(q);
    });
  }, [assets, filter, query]);

  const toggle = (id: string) => {
    if (selected.has(id)) onChange(selectedIds.filter((item) => item !== id));
    else onChange([...selectedIds, id]);
  };

  const hoverAsset = hoverId ? assets.find((a) => a.id === hoverId) : null;

  return (
    <div className="cis-ref-browser" data-testid="cis-reference-browser">
      <div className="cis-ref-browser__toolbar">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search references…"
          aria-label="Search references"
          data-testid="cis-reference-search"
        />
        <div className="cis-ref-browser__filters" role="tablist" aria-label="Reference filters">
          {FILTERS.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={filter === item.id}
              className={filter === item.id ? "is-active" : ""}
              onClick={() => setFilter(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {selectedIds.length > 0 && (
        <p className="cis-ref-browser__count">{selectedIds.length} selected</p>
      )}

      {!visible.length ? (
        <p className="muted cis-empty-inline">No matching references in this project yet.</p>
      ) : (
        <div className="cis-ref-grid">
          {visible.map((asset) => {
            const isSelected = selected.has(asset.id);
            const tag = asset.tag ? `@${asset.tag}` : asset.filename || "Untitled";
            const badge = assetBadge(asset);
            return (
              <button
                key={asset.id}
                type="button"
                className={`cis-ref-card${isSelected ? " is-selected" : ""}`}
                onClick={() => toggle(asset.id)}
                onMouseEnter={() => setHoverId(asset.id)}
                onMouseLeave={() => setHoverId((current) => (current === asset.id ? null : current))}
                aria-pressed={isSelected}
                data-testid={`cis-ref-card-${asset.id}`}
              >
                <span className="cis-ref-card__thumb">
                  <img src={api.assetUrl(asset.id)} alt="" loading="lazy" />
                </span>
                <span className="cis-ref-card__meta">
                  <span className="cis-ref-card__tag">{tag}</span>
                  <span className="cis-ref-card__type">{assetTypeLabel(asset)}</span>
                  {badge ? <span className="cis-ref-card__badge">{badge}</span> : null}
                  {isSelected ? <span className="cis-ref-card__selected">Selected ✓</span> : null}
                </span>
              </button>
            );
          })}
        </div>
      )}

      {hoverAsset ? (
        <div className="cis-ref-hover-preview" aria-hidden>
          <img src={api.assetUrl(hoverAsset.id)} alt="" />
          <div>
            <strong>{hoverAsset.tag ? `@${hoverAsset.tag}` : hoverAsset.filename}</strong>
            <span>{assetTypeLabel(hoverAsset)}</span>
          </div>
        </div>
      ) : null}
    </div>
  );
}
