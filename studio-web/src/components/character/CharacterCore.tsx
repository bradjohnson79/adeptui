/**
 * CharacterCore — the single shared Character Profile workflow composed from the
 * shared building blocks. Used by BOTH the Co-Director Express surface and the
 * standalone Character Creator so they share schema, hydration, and behavior.
 */
import { useCallback, useMemo, useState } from "react";
import { api } from "../../api";
import { CharacterActions } from "./CharacterActions";
import { CharacterCandidateGrid } from "./CharacterCandidateGrid";
import { CharacterProfileForm } from "./CharacterProfileForm";
import { CharacterReferenceControl } from "./CharacterReferenceControl";
import { CharacterSheetGenerator } from "./CharacterSheetGenerator";
import { GeneratorSourceSelector } from "./GeneratorSourceSelector";
import type { CharacterCandidate, GeneratorSourceState } from "./types";
import { getHeroIdentity, getReferenceImage, useCharacterProfile } from "./useCharacterProfile";
import "./characterCore.css";

type Props = {
  projectId: string;
  characterId: string;
  /** Optional advanced-workspace buttons rendered when the character is saved. */
  renderAdvanced?: (ctx: { characterId: string; saved: boolean }) => React.ReactNode;
  onDeleted?: () => void;
  /** When true, auto-focus the name field (new character). */
  autoFocusName?: boolean;
};

export function CharacterCore({ projectId, characterId, renderAdvanced, onDeleted, autoFocusName }: Props) {
  const cp = useCharacterProfile(projectId, characterId);
  const { profile, references } = cp;

  const [sources, setSources] = useState<{ local: GeneratorSourceState; api: GeneratorSourceState }>({
    local: { enabled: true, selectedId: "" },
    api: { enabled: false, selectedId: "" },
  });
  const [candidates, setCandidates] = useState<CharacterCandidate[]>([]);
  const [notice, setNotice] = useState("");

  const hero = useMemo(() => getHeroIdentity(references), [references]);
  const referenceImage = useMemo(() => getReferenceImage(references), [references]);
  const hasReference = !!referenceImage?.asset_id;
  const selectedAssetId = hero?.asset_id ?? null;

  const saved = !!profile?.id;
  const canSave = !!profile?.name?.trim();

  const handleApprove = useCallback(
    async (candidate: CharacterCandidate) => {
      const assetId = candidate.sheetAssetId || candidate.assetId;
      if (!assetId) {
        setNotice("That look is still generating. Wait for it to finish.");
        return;
      }
      if (hero?.asset_id) {
        const confirmed = window.confirm(
          `Replace ${profile?.name || "this character"}'s look with this one?`,
        );
        if (!confirmed) return;
      }
      setNotice("");
      try {
        await api.approveCharacterCandidate(projectId, characterId, {
          assetId,
          referenceRole: "hero_identity",
          sourceType: candidate.generator || candidate.provider ? "generation" : "generation",
          notes: `Approved character sheet ${candidate.label || ""}`.trim(),
        });
        try {
          await api.ownerApproveCharacterVisualSheet(projectId, characterId);
        } catch {
          // gate approval optional in embedded flow
        }
        await cp.refresh();
        setNotice("Character look saved.");
      } catch (e) {
        setNotice(e instanceof Error ? e.message : "Approve failed");
      }
    },
    [projectId, characterId, hero, profile, cp],
  );

  const handleUseAsIdentity = useCallback(
    async (assetId: string, sourceType: "upload" | "library") => {
      setNotice("");
      try {
        await api.approveCharacterCandidate(projectId, characterId, {
          assetId,
          referenceRole: "hero_identity",
          sourceType,
          notes: "Used reference image as character identity (no AI generation).",
        });
        await cp.refresh();
        setNotice("Reference set as this character's look.");
      } catch (e) {
        setNotice(e instanceof Error ? e.message : "Could not use as identity.");
      }
    },
    [projectId, characterId, cp],
  );

  const handleDelete = useCallback(async () => {
    const confirmed = window.confirm(
      `Delete ${profile?.name || "this character"}? This cannot be undone.`,
    );
    if (!confirmed) return;
    const ok = await cp.remove();
    if (ok) onDeleted?.();
  }, [cp, profile, onDeleted]);

  if (cp.loading && !profile) {
    return <p className="character-core__hint">Loading character…</p>;
  }

  return (
    <div className="character-core" data-testid="character-core">
      <div className="character-core__section">
        <h3 className="character-core__section-title">Character Profile</h3>
        <CharacterProfileForm
          profile={profile}
          autoFocusName={autoFocusName}
          onChange={(fields) => cp.patchDebounced(fields)}
        />
      </div>

      <div className="character-core__section">
        <h3 className="character-core__section-title">Character Reference</h3>
        <CharacterReferenceControl
          projectId={projectId}
          characterId={characterId}
          references={references}
          onChanged={cp.refresh}
          onUseAsIdentity={handleUseAsIdentity}
        />
      </div>

      <div className="character-core__section">
        <h3 className="character-core__section-title">Character Sheet</h3>
        <GeneratorSourceSelector
          projectId={projectId}
          visualStyle={profile?.visual_style}
          hasReference={hasReference}
          value={sources}
          onChange={setSources}
        />
        <CharacterSheetGenerator
          projectId={projectId}
          characterId={characterId}
          profile={profile}
          sources={sources}
          onCandidates={setCandidates}
        />
        <CharacterCandidateGrid
          candidates={candidates}
          selectedAssetId={selectedAssetId}
          onApprove={(c) => void handleApprove(c)}
        />
      </div>

      {notice ? (
        <p className="character-core__hint" data-testid="character-core-notice">
          {notice}
        </p>
      ) : null}
      {cp.error ? (
        <p className="character-core__hint" style={{ color: "#f08787" }} data-testid="character-core-error">
          {cp.error}
        </p>
      ) : null}

      <CharacterActions
        isSaved={saved}
        canSave={canSave}
        saving={cp.saving}
        onSave={() => void cp.save()}
        onReset={() => cp.reset()}
        onDelete={() => void handleDelete()}
      />

      {renderAdvanced ? (
        <div className="character-core__advanced-toggle">
          <h3 className="character-core__section-title">Advanced</h3>
          <div className="character-core__advanced-grid">{renderAdvanced({ characterId, saved })}</div>
        </div>
      ) : null}
    </div>
  );
}
