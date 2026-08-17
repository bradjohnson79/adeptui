import { useMemo, useState } from "react";
import { api } from "../../api";
import type { LibraryAsset } from "../CoDirector/library/assetModel";
import { getAssetName, isAudioAsset, isImageAsset, isVideoAsset } from "../CoDirector/library/assetModel";

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

export function isReferenceImage(asset: LibraryAsset): boolean {
  if (isVideoAsset(asset) || isAudioAsset(asset)) return false;
  if (isImageAsset(asset)) return true;
  const kind = (asset.kind || "").toLowerCase();
  return (
    kind.includes("environment") ||
    kind.includes("character") ||
    kind.includes("prop") ||
    kind.includes("location") ||
    kind.includes("storyboard")
  );
}

export function referenceRole(asset: LibraryAsset): string {
  if (asset.characterId) return "Character";
  if (asset.propId) return "Prop";
  if (asset.sceneId) return "Location";
  const kind = (asset.kind || "").toLowerCase();
  const tag = (asset.tag || "").toLowerCase();
  if (kind.includes("character") || tag.includes("char") || tag.includes("portrait")) return "Character";
  if (kind.includes("prop") || tag.includes("prop")) return "Prop";
  if (kind.includes("location") || kind.includes("environment") || tag.includes("loc")) return "Location";
  if (kind.includes("storyboard") || tag.includes("board")) return "Storyboard";
  return "Image";
}

function matchesFilter(asset: LibraryAsset, filter: ReferenceFilter): boolean {
  if (filter === "all" || filter === "images") return true;
  const role = referenceRole(asset).toLowerCase();
  if (filter === "characters") return role === "character";
  if (filter === "locations") return role === "location";
  if (filter === "props") return role === "prop";
  if (filter === "storyboard") return role === "storyboard";
  if (filter === "previous") {
    const tag = `${asset.tag || ""} ${asset.filename || ""}`.toLowerCase();
    return tag.includes("frame") || tag.includes("gen") || tag.includes("take");
  }
  return true;
}

export function ReferenceBrowser({
  assets,
  pendingIds,
  activeIds,
  highlightId,
  onPendingChange,
}: {
  assets: LibraryAsset[];
  pendingIds: string[];
  activeIds: string[];
  highlightId?: string | null;
  onPendingChange: (ids: string[]) => void;
}) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<ReferenceFilter>("all");
  const [hoverId, setHoverId] = useState<string | null>(null);

  const pending = useMemo(() => new Set(pendingIds), [pendingIds]);
  const active = useMemo(() => new Set(activeIds), [activeIds]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return assets.filter((asset) => {
      if (!matchesFilter(asset, filter)) return false;
      if (!q) return true;
      const hay = `${getAssetName(asset)} ${asset.filename || ""} ${referenceRole(asset)}`.toLowerCase();
      return hay.includes(q);
    });
  }, [assets, filter, query]);

  const toggle = (id: string) => {
    if (active.has(id)) return;
    if (pending.has(id)) onPendingChange(pendingIds.filter((item) => item !== id));
    else onPendingChange([...pendingIds, id]);
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

      {pendingIds.length > 0 && (
        <p className="cis-ref-browser__count" data-testid="cis-ref-selected-count">
          {pendingIds.length} selected
        </p>
      )}

      {!visible.length ? (
        <p className="muted cis-empty-inline">No matching references in this project yet.</p>
      ) : (
        <div className="cis-ref-scroller" data-testid="cis-ref-scroller">
          <div className="cis-ref-grid">
            {visible.map((asset) => {
              const isPending = pending.has(asset.id);
              const isActive = active.has(asset.id);
              const isHighlight = highlightId === asset.id;
              const name = getAssetName(asset);
              const role = referenceRole(asset);
              return (
                <button
                  key={asset.id}
                  type="button"
                  className={`cis-ref-card${isPending ? " is-selected" : ""}${isActive ? " is-active-ref" : ""}${isHighlight ? " is-highlight" : ""}`}
                  onClick={() => toggle(asset.id)}
                  onMouseEnter={() => setHoverId(asset.id)}
                  onMouseLeave={() => setHoverId((current) => (current === asset.id ? null : current))}
                  aria-pressed={isPending || isActive}
                  disabled={isActive}
                  title={isActive ? "Already added as a reference" : undefined}
                  data-testid={`cis-ref-card-${asset.id}`}
                >
                  <span className="cis-ref-card__thumb">
                    <img src={api.assetUrl(asset.id)} alt="" loading="lazy" />
                  </span>
                  <span className="cis-ref-card__meta">
                    <span className="cis-ref-card__tag">{name}</span>
                    <span className="cis-ref-card__type">{role}</span>
                    {isActive ? <span className="cis-ref-card__selected">Already added</span> : null}
                    {isPending && !isActive ? <span className="cis-ref-card__selected">Selected ✓</span> : null}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {hoverAsset ? (
        <div className="cis-ref-hover-preview" aria-hidden>
          <img src={api.assetUrl(hoverAsset.id)} alt="" />
          <div>
            <strong>{getAssetName(hoverAsset)}</strong>
            <span>{referenceRole(hoverAsset)}</span>
          </div>
        </div>
      ) : null}
    </div>
  );
}
