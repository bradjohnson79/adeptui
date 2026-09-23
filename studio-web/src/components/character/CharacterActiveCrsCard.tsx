import { useEffect, useState } from "react";
import { api } from "../../api";
import { candidateAssetId, isLiveGenerating, type ActiveCrsStatus } from "./activeCrsCard";
import {
  openCharacterSheetInImageGenerator,
  openCharacterSheetInLibrary,
  type GoTab,
} from "./characterSheetDestinations";
import { candidateErrorMessage, candidateStage, type CharacterCandidate } from "./types";
import { promptCanonicalCharacterTag } from "../../creatorScope/identityTags";

export type { ActiveCrsStatus };

export function CharacterActiveCrsCard({
  hero,
  characterName,
  status,
  revision,
  generatorLabel,
  conditioningLabel,
  disabled,
  title,
  testId,
  onPreview,
  onRegenerate,
  onApprove,
  onReject,
  onGoTab,
  characterId,
}: {
  hero: CharacterCandidate | null;
  characterName: string;
  status: ActiveCrsStatus;
  revision: number | null;
  generatorLabel: string | null;
  conditioningLabel: string | null;
  disabled?: boolean;
  title?: string;
  testId?: string;
  onPreview: (assetId: string) => void;
  onRegenerate?: () => void;
  onApprove: (candidate: CharacterCandidate) => void;
  onReject?: (candidate: CharacterCandidate) => void;
  onGoTab?: GoTab;
  characterId?: string;
}) {
  const atTag = promptCanonicalCharacterTag(characterName);
  const assetId = candidateAssetId(hero);
  const assetUrl = assetId ? api.assetUrl(assetId, revision) : null;
  const [imgFailed, setImgFailed] = useState(false);
  useEffect(() => {
    setImgFailed(false);
  }, [assetId, revision]);
  const measured =
    hero && typeof hero.width === "number" && typeof hero.height === "number" && hero.width > 0
      ? `${hero.width}×${hero.height}`
      : null;

  return (
    <section className="character-active-crs" data-testid={testId || "character-active-crs"}>
      <h3 className="character-active-crs__title">
        {title
          || (status === "approved" ? "Approved Character Reference Sheet" : status === "draft" ? "Draft Character Reference Sheet" : "Active Character Reference Sheet")}
      </h3>
      {!hero ? (
        <p className="character-core__hint" data-testid="character-active-crs-empty">
          No Character Reference Sheet is active yet. Generate one to begin.
        </p>
      ) : (
        <div className="character-active-crs__body">
          {atTag && assetId ? (
            <div className="character-core__tag-row" data-testid="character-creator-tag-row" style={{ display: "flex", gap: "0.5rem", alignItems: "center", marginBottom: "0.5rem", flexWrap: "wrap" }}>
              <code data-testid="character-creator-tag">{atTag}</code>
              <button
                type="button"
                className="character-core__button"
                data-testid="character-creator-copy-tag"
                onClick={() => {
                  void navigator.clipboard.writeText(atTag);
                }}
              >
                Copy @tag
              </button>
            </div>
          ) : null}
          <button
            type="button"
            className="character-active-crs__thumb"
            data-testid="character-active-crs-preview"
            onClick={() => onPreview(assetId)}
            aria-label="Preview Active Character Reference Sheet"
          >
            {assetUrl && !imgFailed ? (
              <img
                key={`${assetId}:${revision ?? ""}`}
                src={assetUrl}
                alt=""
                data-testid="character-active-crs-thumb-img"
                onError={() => setImgFailed(true)}
              />
            ) : isLiveGenerating(hero) ? (
              <span className="character-active-crs__thumb-missing" data-testid="character-active-crs-thumb-generating">
                Generating Character Reference Sheet…
              </span>
            ) : candidateStage(hero) === "failed" ? (
              <span className="character-active-crs__thumb-missing" data-testid="character-active-crs-thumb-failed">
                {candidateErrorMessage(hero) || "Generation failed"}
              </span>
            ) : (
              <span className="character-active-crs__thumb-missing" data-testid="character-active-crs-thumb-missing">
                The Character Reference Sheet image is missing.
              </span>
            )}
          </button>
          <div className="character-active-crs__meta">
            <div data-testid="character-active-crs-name">{characterName || "Character"}</div>
            {generatorLabel ? <div data-testid="character-active-crs-generator">{generatorLabel}</div> : null}
            {measured ? (
              <div data-testid="character-active-crs-size">
                {measured}
                {hero.qualityTier ? ` / ${hero.qualityTier}` : " / 2K"}
              </div>
            ) : (
              <div data-testid="character-active-crs-size">{hero.qualityTier || "2K"}</div>
            )}
            {conditioningLabel ? (
              <div data-testid="character-active-crs-conditioning">{conditioningLabel}</div>
            ) : null}
            <div data-testid="character-active-crs-status">
              {status === "approved" ? "Approved — this is the look" : "Draft"}
            </div>
            {revision != null ? (
              <div data-testid="character-active-crs-revision">Revision {revision}</div>
            ) : null}
            {status === "approved" && atTag ? (
              <div data-testid="character-active-crs-at">{atTag} is ready everywhere</div>
            ) : null}
          </div>
        </div>
      )}
      <div className="character-active-crs__actions">
        {hero && assetId ? (
          <button type="button" className="character-core__button" disabled={disabled} onClick={() => onPreview(assetId)}>
            Preview
          </button>
        ) : null}
        {onRegenerate ? (
          <button
            type="button"
            className="character-core__button"
            data-testid="character-active-crs-regenerate"
            disabled={disabled}
            onClick={onRegenerate}
          >
            Regenerate
          </button>
        ) : null}
        {hero && status !== "approved" ? (
          <button
            type="button"
            className="character-core__button character-core__button--primary"
            data-testid="character-active-crs-approve"
            disabled={disabled}
            onClick={() => onApprove(hero)}
          >
            Approve
          </button>
        ) : null}
        {hero && status !== "approved" && onReject ? (
          <button
            type="button"
            className="character-core__button"
            data-testid="character-active-crs-reject"
            disabled={disabled}
            onClick={() => onReject(hero)}
          >
            Reject
          </button>
        ) : null}
        {hero && assetId && onGoTab ? (
          <>
            <button
              type="button"
              className="character-core__button"
              data-testid="character-active-crs-open-library"
              disabled={disabled}
              onClick={() => openCharacterSheetInLibrary(onGoTab, assetId)}
            >
              Open in Library
            </button>
            <button
              type="button"
              className="character-core__button character-core__button--primary"
              data-testid="character-active-crs-use-imagegen"
              disabled={disabled}
              onClick={() =>
                openCharacterSheetInImageGenerator(onGoTab, {
                  characterId: characterId || "",
                  assetId,
                })
              }
            >
              Use in Image Generator
            </button>
          </>
        ) : null}
      </div>
    </section>
  );
}
