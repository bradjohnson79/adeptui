/**
 * ERS result display — composite image + 4 buttons.
 *
 * Per amendment #2, the ERS composite is assembled programmatically in code
 * (not image-generated). This component just displays the resulting asset by ID.
 * Buttons: Open Full Size, Regenerate, Open in Library, Use in Scene Creator.
 */
import { api } from "../../../api";

type Props = {
  ersCompositeAssetId: string;
  onRegenerate: () => void;
  onOpenInLibrary: () => void;
  onUseInSceneCreator: () => void;
  regenerateDisabled?: boolean;
};

export function ErsResultDisplay({
  ersCompositeAssetId,
  onRegenerate,
  onOpenInLibrary,
  onUseInSceneCreator,
  regenerateDisabled = false,
}: Props) {
  const url = api.assetUrl(ersCompositeAssetId);

  const openFullSize = () => {
    window.open(url, "_blank", "noopener,noreferrer");
  };

  return (
    <div className="spatial-map__ers" data-testid="spatial-map-ers">
      <p className="eyebrow" style={{ margin: 0 }}>Environment Reference Sheet</p>
      <img
        className="spatial-map__ers-img"
        src={url}
        alt="Environment Reference Sheet composite"
        loading="lazy"
      />
      <div className="spatial-map__ers-actions">
        <button
          type="button"
          className="ui-btn ui-btn--secondary"
          onClick={openFullSize}
          aria-label="Open Environment Reference Sheet full size"
        >
          Open Full Size
        </button>
        <button
          type="button"
          className="ui-btn ui-btn--secondary"
          onClick={onRegenerate}
          disabled={regenerateDisabled}
          aria-label="Regenerate Environment Reference Sheet"
        >
          Regenerate
        </button>
        <button
          type="button"
          className="ui-btn ui-btn--secondary"
          onClick={onOpenInLibrary}
          aria-label="Open ERS in Library"
        >
          Open in Library
        </button>
        <button
          type="button"
          className="ui-btn ui-btn--primary"
          onClick={onUseInSceneCreator}
          aria-label="Use ERS in Scene Creator"
        >
          Use in Scene Creator
        </button>
      </div>
    </div>
  );
}
