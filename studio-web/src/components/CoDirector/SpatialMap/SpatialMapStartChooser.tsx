import type { ReactNode } from "react";

export type SpatialMapVariant = "express" | "standard";
export type SpatialStartRoute = "design" | "reconstruct" | "assign";

type Props = {
  busy: boolean;
  variant?: SpatialMapVariant;
  gptConfigured?: boolean;
  description: string;
  onDescriptionChange: (value: string) => void;
  descriptionError?: string | null;
  onCreateAtlas: () => void;
  onChooseStyleReference?: () => void;
  onUploadStyleReference?: () => void;
  styleReferenceLabel?: string;
  designExtras?: ReactNode;
  designLook?: ReactNode;
  designProgress?: ReactNode;
  onChooseLocationLibrary: () => void;
  onUploadLocation: () => void;
  reconstructExtras?: ReactNode;
  reconstructProgress?: ReactNode;
  onChooseAtlasLibrary: () => void;
  onUploadAtlas: () => void;
};

export function SpatialMapStartChooser({
  busy,
  variant = "express",
  gptConfigured = false,
  description,
  onDescriptionChange,
  descriptionError,
  onCreateAtlas,
  onChooseStyleReference,
  onUploadStyleReference,
  styleReferenceLabel,
  designExtras,
  designLook,
  designProgress,
  onChooseLocationLibrary,
  onUploadLocation,
  reconstructExtras,
  reconstructProgress,
  onChooseAtlasLibrary,
  onUploadAtlas,
}: Props) {
  const designBlocked = busy || !gptConfigured;
  return (
    <div className="spatial-map__start" data-testid="spatial-map-start-chooser" data-variant={variant}>
      <p className="spatial-map__subtitle">How would you like to create your Spatial Map?</p>

      <section
        className="spatial-map__start-option spatial-map__start-option--recommended"
        data-testid="spatial-map-start-design"
      >
        <div className="spatial-map__start-heading-row">
          {gptConfigured ? (
            <span className="spatial-map__badge" data-testid="spatial-map-recommended-badge">
              Recommended
            </span>
          ) : null}
          <span className="spatial-map__badge spatial-map__badge--paid" data-testid="spatial-map-paid-badge">
            Paid API
          </span>
        </div>
        <h4 className="spatial-map__start-title">Create Environment with Co-Director</h4>
        <p className="spatial-map__tip">
          {gptConfigured ? (
            <>
              <strong>Recommended — simplest method.</strong> Describe the location you want to create
              and Co-Director will design a roofless, top-down Atlas Shot specifically for Spatial Map
              using GPT Image 2. Paid API usage applies.
            </>
          ) : (
            <>
              GPT Image 2 is not configured. You can use the free local reconstruction method, or
              configure the provider.
            </>
          )}
        </p>
        <label className="spatial-map__scene-desc" data-testid="scene-description-block">
          <span className="spatial-map__scene-desc-label">
            Environment description
            <span
              className="spatial-map__scene-desc-tip"
              title="Describe the place you want to create. Co-Director uses this to design the Atlas."
            >
              (?)
            </span>
          </span>
          <textarea
            rows={variant === "standard" ? 3 : 2}
            data-testid="scene-description-input"
            placeholder="e.g. a silver underground research corridor with an elevator at the south end"
            value={description}
            onChange={(e) => onDescriptionChange(e.target.value)}
            disabled={busy}
          />
        </label>
        {descriptionError ? <p className="spatial-map__hint">{descriptionError}</p> : null}
        <div className="spatial-map__empty-actions">
          <button
            type="button"
            className="ui-btn ui-btn--secondary"
            onClick={onChooseStyleReference}
            disabled={designBlocked}
            data-testid="spatial-map-style-library"
          >
            Optional Reference
          </button>
          <button
            type="button"
            className="ui-btn ui-btn--secondary"
            onClick={onUploadStyleReference}
            disabled={designBlocked}
            data-testid="spatial-map-style-upload"
          >
            Upload Reference
          </button>
        </div>
        {styleReferenceLabel ? (
          <p className="spatial-map__hint" data-testid="spatial-map-style-ref-label">
            {styleReferenceLabel}
          </p>
        ) : null}
        {variant === "standard" ? designExtras : null}
        {variant === "standard" ? designLook : null}
        <div className="spatial-map__empty-actions">
          <button
            type="button"
            className="ui-btn ui-btn--primary"
            onClick={onCreateAtlas}
            disabled={designBlocked || !!descriptionError || !description.trim()}
            aria-label="Create Atlas"
            data-testid="spatial-map-create-from-description"
          >
            {busy ? "Creating Atlas…" : "Create Atlas"}
          </button>
        </div>
        {designProgress}
      </section>

      <section className="spatial-map__start-option" data-testid="spatial-map-start-location">
        <div className="spatial-map__start-heading-row">
          <span className="spatial-map__badge spatial-map__badge--free" data-testid="spatial-map-free-badge">
            Free / Local
          </span>
        </div>
        <h4 className="spatial-map__start-title">Reconstruct from Location Image</h4>
        <p className="spatial-map__tip">
          <strong>Free local method.</strong> Use a master shot or wide-angle image of an existing
          location. Co-Director will reconstruct the visible environment locally with MoGe-2 and
          create the Spatial Map Atlas. Reconstruction from one image is approximate.
        </p>
        <div className="spatial-map__empty-actions">
          <button
            type="button"
            className="ui-btn ui-btn--primary"
            onClick={onChooseLocationLibrary}
            disabled={busy}
            data-testid="spatial-map-location-library"
          >
            Choose from Library
          </button>
          <button
            type="button"
            className="ui-btn ui-btn--secondary"
            onClick={onUploadLocation}
            disabled={busy}
            data-testid="spatial-map-location-upload"
          >
            Upload Image
          </button>
        </div>
        {variant === "standard" ? reconstructExtras : null}
        {reconstructProgress}
      </section>

      <section className="spatial-map__start-option" data-testid="spatial-map-start-atlas">
        <h4 className="spatial-map__start-title">Use Existing Spatial Map</h4>
        <p className="spatial-map__tip">
          <strong>Already have a finished map?</strong> Select or upload a roofless top-down Spatial
          Map / Atlas. Adept uses your image exactly as it is — no generation, no restyle.
        </p>
        <div className="spatial-map__empty-actions">
          <button
            type="button"
            className="ui-btn ui-btn--primary"
            onClick={onChooseAtlasLibrary}
            disabled={busy}
            data-testid="spatial-map-atlas-library"
          >
            Choose Spatial Map
          </button>
          <button
            type="button"
            className="ui-btn ui-btn--secondary"
            onClick={onUploadAtlas}
            disabled={busy}
            data-testid="spatial-map-atlas-upload"
          >
            Upload Spatial Map
          </button>
        </div>
      </section>
    </div>
  );
}
