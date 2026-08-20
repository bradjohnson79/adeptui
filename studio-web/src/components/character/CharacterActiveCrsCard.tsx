import { api } from "../../api";
import type { CharacterCandidate } from "./types";

export type ActiveCrsStatus = "approved" | "draft" | "none";

export function CharacterActiveCrsCard({
  hero,
  characterName,
  status,
  revision,
  generatorLabel,
  conditioningLabel,
  disabled,
  onPreview,
  onRegenerate,
  onApprove,
  onUpdateIdentity,
}: {
  hero: CharacterCandidate | null;
  characterName: string;
  status: ActiveCrsStatus;
  revision: number | null;
  generatorLabel: string | null;
  conditioningLabel: string | null;
  disabled?: boolean;
  onPreview: (assetId: string) => void;
  onRegenerate: () => void;
  onApprove: (candidate: CharacterCandidate) => void;
  onUpdateIdentity?: () => void;
}) {
  const atName = characterName.trim() ? `@${characterName.trim()}` : null;
  const assetId = hero?.sheetAssetId || hero?.assetId || "";
  const assetUrl = assetId ? api.assetUrl(assetId) : null;
  const measured =
    hero && typeof hero.width === "number" && typeof hero.height === "number" && hero.width > 0
      ? `${hero.width}×${hero.height}`
      : null;

  return (
    <section className="character-active-crs" data-testid="character-active-crs">
      <h3 className="character-active-crs__title">Active Character Reference Sheet</h3>
      {!hero ? (
        <p className="character-core__hint" data-testid="character-active-crs-empty">
          No Character Reference Sheet is active yet. Generate one to begin.
        </p>
      ) : (
        <div className="character-active-crs__body">
          <button
            type="button"
            className="character-active-crs__thumb"
            data-testid="character-active-crs-preview"
            onClick={() => onPreview(assetId)}
            aria-label="Preview Active Character Reference Sheet"
          >
            {assetUrl ? <img src={assetUrl} alt="" /> : null}
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
              {status === "approved" ? "Approved / Production Ready" : "Draft"}
            </div>
            {revision != null ? (
              <div data-testid="character-active-crs-revision">Revision {revision}</div>
            ) : null}
            {status === "approved" && atName ? (
              <div data-testid="character-active-crs-at">{atName} is ready everywhere</div>
            ) : null}
          </div>
        </div>
      )}
      <div className="character-active-crs__actions">
        {hero ? (
          <button type="button" className="character-core__button" disabled={disabled} onClick={() => onPreview(assetId)}>
            Preview
          </button>
        ) : null}
        <button
          type="button"
          className="character-core__button"
          data-testid="character-active-crs-regenerate"
          disabled={disabled}
          onClick={onRegenerate}
        >
          Regenerate
        </button>
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
        {hero && status === "approved" && onUpdateIdentity ? (
          <button
            type="button"
            className="character-core__button"
            data-testid="character-active-crs-update-identity"
            disabled={disabled}
            onClick={onUpdateIdentity}
          >
            Update Character Identity
          </button>
        ) : null}
      </div>
    </section>
  );
}
