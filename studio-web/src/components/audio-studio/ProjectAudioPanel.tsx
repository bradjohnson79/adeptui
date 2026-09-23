import { useMemo, useState } from "react";
import { HelpTip } from "../HelpTip";
import { Button } from "../ui";
import { AudioRow } from "./AudioRow";
import { classifyLibraryAudio } from "./audioStudioCandidates";
import type { AudioLibraryAsset } from "./types";

type FilterId = "all" | "music" | "sfx" | "ambience" | "voice";

type ProjectAudioPanelProps = {
  assets: AudioLibraryAsset[];
  busy: boolean;
  approvedAssetIds: Record<string, boolean>;
  onAddToTimeline: (asset: AudioLibraryAsset) => Promise<void> | void;
  onGoLibrary: () => void;
  onGoTimeline: () => void;
};

const FILTERS: { id: FilterId; label: string }[] = [
  { id: "all", label: "All" },
  { id: "music", label: "Music" },
  { id: "sfx", label: "SFX" },
  { id: "ambience", label: "Ambience" },
  { id: "voice", label: "Voice" },
];

export function ProjectAudioPanel({
  assets,
  busy,
  approvedAssetIds,
  onAddToTimeline,
  onGoLibrary,
  onGoTimeline,
}: ProjectAudioPanelProps) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<FilterId>("all");

  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return assets.filter((asset) => {
      const kind = classifyLibraryAudio(asset);
      if (filter !== "all" && kind !== filter) return false;
      if (!needle) return true;
      const haystack = [asset.title, asset.tag, asset.filename, asset.id].filter(Boolean).join(" ").toLowerCase();
      return haystack.includes(needle);
    });
  }, [assets, filter, query]);

  return (
    <section className="audio-studio-panel" data-testid="audio-library-panel">
      <div className="audio-studio-panel__hero">
        <div>
          <h3>Project Audio</h3>
          <p className="muted">This project’s shelf. Nothing new is generated here.</p>
        </div>
        <div className="audio-studio-panel__hero-actions">
          <Button variant="ghost" onClick={onGoLibrary}>Open Library</Button>
          <Button variant="secondary" onClick={onGoTimeline}>Open Timeline</Button>
        </div>
      </div>

      <div className="audio-library-toolbar">
        <label className="audio-field audio-field--grow">
          <span className="audio-field__label">
            Search
            <HelpTip text="Find music, effects, beds, or voice already saved to this project." />
          </span>
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search this project"
            data-testid="audio-library-search"
          />
        </label>
        <div className="audio-chip-row" data-testid="audio-library-filters">
          {FILTERS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`audio-chip${filter === item.id ? " is-selected" : ""}`}
              onClick={() => setFilter(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {rows.length ? (
        <div className="audio-library-list">
          {rows.map((asset) => {
            const label = asset.title || asset.tag || asset.filename || "Audio";
            const kind = classifyLibraryAudio(asset);
            const duration = asset.durationSec ?? asset.duration_sec;
            return (
              <article key={asset.id} className="audio-library-card" data-testid={`audio-library-row-${asset.id}`}>
                <div className="audio-library-card__meta">
                  <div>
                    <h4>{label}</h4>
                    <p className="muted">{kind === "audio" ? "Audio" : kind}</p>
                  </div>
                  <div className="audio-candidate-card__chips">
                    {typeof duration === "number" ? <span className="audio-chip">{duration}s</span> : null}
                    {approvedAssetIds[asset.id] || asset.approved ? (
                      <span className="audio-chip audio-chip--success">Approved</span>
                    ) : null}
                  </div>
                </div>
                <AudioRow audioUrl={asset.url} label={label} testId={`audio-library-player-${asset.id}`} />
                <div className="audio-candidate-card__actions">
                  <Button variant="secondary" disabled={busy} onClick={() => void onAddToTimeline(asset)}>
                    Add to Timeline
                  </Button>
                </div>
              </article>
            );
          })}
        </div>
      ) : (
        <div className="audio-empty-state">
          <strong>{assets.length ? "Nothing matches that search." : "No project audio yet."}</strong>
          <p className="muted">Generate music, a sound, or a bed, then it will live here with the rest of this project.</p>
        </div>
      )}
    </section>
  );
}
