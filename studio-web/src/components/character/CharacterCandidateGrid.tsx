/**
 * CharacterCandidateGrid — renders composed character-sheet candidates with
 * provenance labels (LOCAL — Illustrious XL / LOCAL — Z-Image / API — provider/model).
 * The creator-facing candidate image is the composed canonical sheet asset.
 */
import { api } from "../../api";
import type { CharacterCandidate } from "./types";

type Props = {
  candidates: CharacterCandidate[];
  selectedAssetId?: string | null;
  disabled?: boolean;
  onApprove: (candidate: CharacterCandidate) => void;
};

function provenanceLabel(c: CharacterCandidate): string {
  const src = (c.generator || c.provider || "").toLowerCase();
  const modelName = c.model || c.modelVariant || "";
  if (src.includes("api") || src.includes("cloud") || c.provider) {
    return `API — ${[c.provider, modelName].filter(Boolean).join(" / ") || "cloud"}`;
  }
  const model = modelName || c.workflowKey || "";
  return model ? `LOCAL — ${model}` : "LOCAL";
}

export function CharacterCandidateGrid({ candidates, selectedAssetId, disabled, onApprove }: Props) {
  if (!candidates.length) return null;
  return (
    <div className="character-core__candidates" data-testid="character-candidate-grid">
      {candidates.map((c, i) => {
        // Creator-facing image is the composed canonical sheet.
        const assetId = c.sheetAssetId || c.assetId || null;
        const src = assetId ? api.assetUrl(assetId) : "";
        const isSelected = selectedAssetId && assetId === selectedAssetId;
        const ready = c.status === "done" || !!assetId;
        return (
          <div
            key={c.jobId || assetId || `cand-${i}`}
            className={`character-core__candidate${isSelected ? " is-selected" : ""}`}
            data-testid={`character-candidate-${i}`}
          >
            <div className="character-core__candidate-media">
              {src ? (
                <img src={src} alt={c.label || `Candidate ${i + 1}`} loading="lazy" />
              ) : (
                <div className="character-core__candidate-placeholder">
                  {ready ? "No preview" : "Generating…"}
                </div>
              )}
            </div>
            <div className="character-core__candidate-meta">
              <span className="character-core__candidate-prov" data-testid={`candidate-provenance-${i}`}>
                {provenanceLabel(c)}
              </span>
              <button
                type="button"
                className="character-core__button primary"
                data-testid={`candidate-approve-${i}`}
                disabled={disabled || !ready || !assetId}
                onClick={() => onApprove(c)}
              >
                {isSelected ? "Selected" : "Use This Look"}
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
