import { useRef, type ReactNode } from "react";
import { HelpTip } from "../../HelpTip";
import { AtlasGenerationMonitor } from "./AtlasGenerationMonitor";
import {
  ENV_DESCRIPTION_HELP,
  GPT_REQUIRED_MESSAGE,
  USE_AS_ATLAS_HELP,
  expressGenerateReadiness,
  expressProgressMessage,
} from "./expressReadiness";
import type { NormalizedJobProgress } from "./normalizeJobProgress";

export type ExpressReference = {
  assetId: string;
  name: string;
};

type Props = {
  description: string;
  onDescriptionChange: (value: string) => void;
  gptConfigured: boolean | null;
  reference: ExpressReference | null;
  generating: boolean;
  failed: boolean;
  failureMessage?: string | null;
  onSelectFromLibrary: () => void;
  onUploadReference: () => void;
  onUploadAtlas: () => void;
  onReferenceFileSelected: (file: File) => void;
  onAtlasFileSelected: (file: File) => void;
  onReplaceReference: () => void;
  onRemoveReference: () => void;
  onGenerate: () => void;
  useAsAtlas: boolean;
  onUseAsAtlasChange: (value: boolean) => void;
  onOpenSettings?: () => void;
  referenceThumbUrl?: string;
  progress: NormalizedJobProgress;
  progressLive: boolean;
  elapsedSec: number;
  progressExtra?: ReactNode;
};

export function SpatialMapExpressForm({
  description,
  onDescriptionChange,
  gptConfigured,
  reference,
  generating,
  failed,
  failureMessage,
  onSelectFromLibrary,
  onUploadReference: _onUploadReference,
  onUploadAtlas: _onUploadAtlas,
  onReferenceFileSelected,
  onAtlasFileSelected,
  onReplaceReference,
  onRemoveReference,
  onGenerate,
  useAsAtlas,
  onUseAsAtlasChange,
  onOpenSettings,
  referenceThumbUrl,
  progress,
  progressLive,
  elapsedSec,
  progressExtra,
}: Props) {
  const referenceFileRef = useRef<HTMLInputElement>(null);
  const atlasFileRef = useRef<HTMLInputElement>(null);
  const readiness = expressGenerateReadiness({
    gptConfigured,
    description,
    referenceAssetId: reference?.assetId || "",
    useAsAtlas,
  });
  const primaryLabel = useAsAtlas ? "Use Spatial Map" : "Generate Spatial Map";
  const primaryBusy = useAsAtlas ? "Opening Spatial Map…" : "Generating Spatial Map…";
  const mappedProgress = {
    ...progress,
    message: expressProgressMessage(progress.stage, progress.message),
    stage: expressProgressMessage(progress.stage, progress.stage),
  };

  return (
    <div className="spatial-map__express" data-testid="spatial-map-express-form">
      <p className="spatial-map__subtitle">Create Spatial Map with Co-Director</p>

      {gptConfigured ? (
        <p className="spatial-map__tip" data-testid="spatial-map-atlas-engine">
          <strong>Atlas Engine: GPT Image 2</strong>
        </p>
      ) : (
        <div className="spatial-map__tip" data-testid="spatial-map-gpt-required">
          <p>{GPT_REQUIRED_MESSAGE}</p>
          {onOpenSettings ? (
            <button
              type="button"
              className="ui-btn ui-btn--secondary"
              onClick={onOpenSettings}
              data-testid="spatial-map-open-settings"
            >
              Open API Settings
            </button>
          ) : null}
        </div>
      )}

      <label className="spatial-map__scene-desc spatial-map__express-desc" data-testid="scene-description-block">
        <span className="spatial-map__scene-desc-label">
          Environment Description
          <span data-testid="scene-description-help">
            <HelpTip
              label="Environment Description"
              content={ENV_DESCRIPTION_HELP}
            />
          </span>
        </span>
        <textarea
          id="spatial-map-environment-description"
          rows={4}
          data-testid="scene-description-input"
          placeholder="Describe the environment…"
          value={description}
          onChange={(e) => onDescriptionChange(e.target.value)}
          disabled={generating}
          aria-label="Environment Description"
        />
      </label>

      <div className="spatial-map__empty-actions">
        <button
          type="button"
          className="ui-btn ui-btn--secondary"
          onClick={onSelectFromLibrary}
          disabled={generating}
          data-testid="spatial-map-select-library"
        >
          Select from Library
        </button>
        <button
          type="button"
          className="ui-btn ui-btn--secondary"
          onClick={() => referenceFileRef.current?.click()}
          disabled={generating}
          data-testid="spatial-map-upload-reference"
        >
          Upload Reference Image
        </button>
        <button
          type="button"
          className="ui-btn ui-btn--secondary"
          onClick={() => atlasFileRef.current?.click()}
          disabled={generating}
          data-testid="spatial-map-upload-atlas"
        >
          Upload Spatial Map
        </button>
        <input
          ref={referenceFileRef}
          type="file"
          accept="image/*"
          hidden
          data-testid="spatial-map-reference-file"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) onReferenceFileSelected(file);
            e.target.value = "";
          }}
        />
        <input
          ref={atlasFileRef}
          type="file"
          accept="image/*"
          hidden
          data-testid="spatial-map-atlas-file"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) onAtlasFileSelected(file);
            e.target.value = "";
          }}
        />
      </div>

      {reference ? (
        <div className="spatial-map__express-ref" data-testid="spatial-map-selected-reference">
          {referenceThumbUrl ? (
            <img
              src={referenceThumbUrl}
              alt={`Selected reference: ${reference.name}`}
              className="spatial-map__express-ref-thumb"
            />
          ) : (
            <span className="spatial-map__express-ref-thumb spatial-map__express-ref-thumb--empty" aria-hidden="true" />
          )}
          <p className="spatial-map__express-ref-name">{reference.name}</p>
          <div className="spatial-map__empty-actions">
            <button
              type="button"
              className="ui-btn ui-btn--secondary"
              onClick={onReplaceReference}
              disabled={generating}
              data-testid="spatial-map-replace-reference"
            >
              Replace
            </button>
            <button
              type="button"
              className="ui-btn ui-btn--secondary"
              onClick={onRemoveReference}
              disabled={generating}
              data-testid="spatial-map-remove-reference"
            >
              Remove
            </button>
          </div>
          <label className="spatial-map__express-direct" data-testid="spatial-map-use-as-atlas-row">
            <input
              type="checkbox"
              checked={useAsAtlas}
              onChange={(e) => onUseAsAtlasChange(e.target.checked)}
              disabled={generating}
              data-testid="spatial-map-use-as-atlas"
              aria-describedby="spatial-map-use-as-atlas-help"
            />
            <span>
              Use this image as the Spatial Map
              <span data-testid="spatial-map-use-as-atlas-help">
                <HelpTip label="Use this image as the Spatial Map" content={USE_AS_ATLAS_HELP} />
              </span>
            </span>
          </label>
          <p id="spatial-map-use-as-atlas-help" className="spatial-map__hint">
            {USE_AS_ATLAS_HELP}
          </p>
        </div>
      ) : null}

      <div className="spatial-map__empty-actions">
        <button
          type="button"
          className="ui-btn ui-btn--primary"
          onClick={onGenerate}
          disabled={!readiness.ok || generating}
          aria-label={primaryLabel}
          data-testid="spatial-map-generate"
        >
          {generating ? primaryBusy : primaryLabel}
        </button>
        {failed && !generating ? (
          <button
            type="button"
            className="ui-btn ui-btn--secondary"
            onClick={onGenerate}
            disabled={!readiness.ok}
            data-testid="spatial-map-retry"
          >
            Retry
          </button>
        ) : null}
      </div>
      {!readiness.ok ? (
        <p className="spatial-map__hint" data-testid="spatial-map-generate-reason">
          {readiness.reason}
        </p>
      ) : null}
      {failed && failureMessage ? (
        <p className="spatial-map__hint" data-testid="spatial-map-generate-error">
          {failureMessage}
        </p>
      ) : null}

      {useAsAtlas ? null : (
        <AtlasGenerationMonitor
          progress={mappedProgress}
          live={progressLive}
          modelLine="GPT Image 2"
          elapsedSec={elapsedSec}
        />
      )}
      {progressExtra}
    </div>
  );
}
