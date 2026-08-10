import { HelpTip } from "../HelpTip";
import { Button } from "../ui";
import type { AudioLibraryAsset } from "./types";

type ProjectAudioPanelProps = {
  assets: AudioLibraryAsset[];
  busy: boolean;
  previewAssetId?: string | null;
  approvedAssetIds: Record<string, boolean>;
  onPreview: (asset: AudioLibraryAsset) => void;
  onApprove: (asset: AudioLibraryAsset) => Promise<void> | void;
  onAddToTimeline: (asset: AudioLibraryAsset) => Promise<void> | void;
  onGoLibrary: () => void;
  onGoTimeline: () => void;
  onGoMixer: () => void;
};

export function ProjectAudioPanel({
  assets,
  busy,
  previewAssetId,
  approvedAssetIds,
  onPreview,
  onApprove,
  onAddToTimeline,
  onGoLibrary,
  onGoTimeline,
  onGoMixer,
}: ProjectAudioPanelProps) {
  return (
    <section className="audio-studio-panel">
      <div className="audio-studio-panel__hero">
        <div>
          <p className="audio-studio-panel__eyebrow">Project audio</p>
          <h3>Everything you have already saved for this project.</h3>
          <p className="muted">Use this shelf for music, scene beds, and sound details you want to reuse.</p>
        </div>
        <div className="audio-studio-panel__hero-actions">
          <Button variant="ghost" onClick={onGoLibrary}>
            Open Library
          </Button>
          <Button variant="secondary" onClick={onGoTimeline}>
            Open Timeline
          </Button>
        </div>
      </div>

      <div className="audio-inline-note">
        <HelpTip text="Approving marks the take you want to keep moving forward with. Add to Timeline places it on an audio track." />
        <span>Keep only the strongest takes in motion.</span>
      </div>

      {assets.length ? (
        <div className="audio-library-list">
          {assets.map((asset) => {
            const label = asset.tag || asset.title || asset.filename || "Audio asset";
            const duration = asset.durationSec ?? asset.duration_sec;
            return (
              <article key={asset.id} className="audio-library-card">
                <div className="audio-library-card__meta">
                  <div>
                    <h4>{label}</h4>
                    <p className="muted">{asset.filename || asset.id}</p>
                  </div>
                  <div className="audio-candidate-card__chips">
                    {typeof duration === "number" ? <span className="audio-chip audio-chip--subtle">{duration}s</span> : null}
                    {approvedAssetIds[asset.id] || asset.approved ? (
                      <span className="audio-chip audio-chip--success">Approved</span>
                    ) : null}
                  </div>
                </div>

                {previewAssetId === asset.id && asset.url ? (
                  <audio controls autoPlay src={asset.url} className="audio-candidate-card__player" />
                ) : null}

                <div className="audio-candidate-card__actions">
                  <Button variant="ghost" onClick={() => onPreview(asset)}>
                    {previewAssetId === asset.id ? "Playing" : "Play"}
                  </Button>
                  <Button
                    variant="primary"
                    disabled={busy || approvedAssetIds[asset.id] || asset.approved}
                    onClick={() => void onApprove(asset)}
                  >
                    {approvedAssetIds[asset.id] || asset.approved ? "Approved" : "Approve"}
                  </Button>
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
          <strong>No project audio yet.</strong>
          <p className="muted">Generated tracks and uploaded clips will show up here once they are saved to the project library.</p>
        </div>
      )}

      <div className="audio-studio-panel__footer">
        <div>
          <strong>Ready to balance the mix?</strong>
          <p className="muted">Place clips on the timeline, then open Audio Mixer in Editor for levels, pans, fades, and real stem controls.</p>
        </div>
        <Button variant="secondary" onClick={onGoMixer}>
          Open Audio Mixer
        </Button>
      </div>
    </section>
  );
}
