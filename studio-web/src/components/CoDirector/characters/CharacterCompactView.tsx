/**
 * Character Creator embedded view — Co-Director Project Building pane.
 *
 * Phase 3: the inner CharacterDetail now renders the shared CharacterCore so
 * Express and the standalone Character Creator share one schema, hydration,
 * and behavior. The Co-Director mounting wrapper, the saved-character
 * selector, and the "Open Full Character Creator" deep-link are preserved.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../../../api";
import {
  characterOwnedByProject,
  groupScopeItems,
  pickOwnedCharacterId,
  scopeLabel,
} from "../../../creatorScope";
import { CharacterCore } from "../../character";
import type { GoTab } from "../../character/characterSheetDestinations";
import {
  CHARACTER_PROFILE_SAVED_EVENT,
  DRAFT_CHARACTER_ID,
  isUnsavedCharacterId,
  upsertCharacterSummary,
  type CharacterProfileSavedDetail,
} from "../../character/useCharacterProfile";
import { CreatorProfileDeleteModal } from "../../creators/CreatorProfileDeleteModal";
import type { CreatorDeletePreview } from "../../creators/creatorProfileDelete";
import "./characterCompact.css";

type CharacterProfile = {
  id: string;
  name: string;
  status?: string;
  project_id?: string;
  isGlobal?: boolean;
  is_global?: boolean;
};

type Props = {
  projectId: string;
  onOpenFull?: (characterId?: string) => void;
  onGoTab?: GoTab;
};

type CharacterDetailProps = {
  projectId: string;
  characterId: string;
  onOpenFull?: (id?: string) => void;
  onCreated?: (characterId: string) => void;
  onGoTab?: GoTab;
};

function CharacterDetail({ projectId, characterId, onOpenFull, onCreated, onGoTab }: CharacterDetailProps) {
  return (
    <div className="character-compact__detail">
      <CharacterCore
        key={characterId}
        projectId={projectId}
        characterId={characterId}
        onDeleted={() => onOpenFull?.("__delete__")}
        onCreated={onCreated}
        autoFocusName={characterId === DRAFT_CHARACTER_ID}
        mode="express"
        onGoTab={onGoTab}
      />
      <div className="character-compact__actions">
        <div className="character-compact__actions-left">
          <button
            type="button"
            className="character-compact__actions-button"
            data-testid="character-compact-open-full"
            disabled={isUnsavedCharacterId(characterId)}
            onClick={() => {
              if (isUnsavedCharacterId(characterId)) return;
              onOpenFull?.(characterId);
            }}
          >
            Open Full Character Creator
          </button>
        </div>
      </div>
    </div>
  );
}

const LOAD_TIMEOUT_MS = 10_000;

export function CharacterCompactView({ projectId, onOpenFull, onGoTab }: Props) {
  const [characters, setCharacters] = useState<CharacterProfile[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletePreview, setDeletePreview] = useState<CreatorDeletePreview | null>(null);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const result = (await Promise.race([
        api.listCharacterProfiles(projectId) as Promise<{ items?: CharacterProfile[] }>,
        new Promise<never>((_, reject) =>
          window.setTimeout(() => reject(new Error("Character Creator took too long to load.")), LOAD_TIMEOUT_MS),
        ),
      ]));
      const list = Array.isArray(result?.items) ? result.items : [];
      setCharacters(list);
      setSelectedId((prev) => {
        if (prev === DRAFT_CHARACTER_ID) return prev;
        return pickOwnedCharacterId(list, projectId, prev);
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [projectId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Instant dropdown refresh: when the embedded CharacterCore saves (create
  // or rename), upsert the saved profile into the Saved Characters list in
  // place — no remount, no stale "New Character" label. Also covers saves
  // made from the Standard workspace while this pane is mounted.
  useEffect(() => {
    const onSaved = (ev: Event) => {
      const detail = (ev as CustomEvent<CharacterProfileSavedDetail>).detail;
      if (!detail || detail.projectId !== projectId || !detail.profile?.id) return;
      const saved = detail.profile;
      setCharacters((prev) => upsertCharacterSummary(prev, saved));
      setSelectedId((prev) => {
        if (prev) return prev;
        return characterOwnedByProject(saved, projectId) ? saved.id : prev;
      });
    };
    window.addEventListener(CHARACTER_PROFILE_SAVED_EVENT, onSaved);
    return () => window.removeEventListener(CHARACTER_PROFILE_SAVED_EVENT, onSaved);
  }, [projectId]);

  const grouped = useMemo(() => groupScopeItems(characters, projectId), [characters, projectId]);

  const handleDeleteClick = useCallback(async () => {
    if (!selectedId || selectedId === DRAFT_CHARACTER_ID || busy || deleting) return;
    const selected = characters.find((c) => c.id === selectedId);
    if (selected && !characterOwnedByProject(selected, projectId)) {
      setActionNotice("Global characters can only be deleted from the project that created them.");
      return;
    }
    setActionNotice(null);
    try {
      const preview = await api.getCharacterDeletePreview(projectId, selectedId);
      setDeletePreview(preview);
      setDeleteModalOpen(true);
    } catch (e) {
      setActionNotice(e instanceof Error ? e.message : "Failed to load delete preview.");
    }
  }, [busy, characters, deleting, projectId, selectedId]);

  const handleConfirmDelete = useCallback(async () => {
    if (!selectedId || !deletePreview) return;
    setDeleting(true);
    try {
      await api.deleteCharacterProfile(
        projectId,
        selectedId,
        deletePreview.isGlobal && deletePreview.usageCount > 0,
      );
      setDeleteModalOpen(false);
      setDeletePreview(null);
      await refresh();
      setSelectedId("");
    } catch (e) {
      setActionNotice(e instanceof Error ? e.message : "Failed to delete character.");
    } finally {
      setDeleting(false);
    }
  }, [deletePreview, projectId, refresh, selectedId]);

  const handleCreate = useCallback(() => {
    setActionNotice(null);
    setSelectedId(DRAFT_CHARACTER_ID);
  }, []);

  return (
    <div className="character-compact" data-testid="character-compact">
      {busy ? (
        <div className="character-compact__state" aria-hidden="true">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="character-compact__skeleton-line" />
          ))}
        </div>
      ) : error ? (
        <div className="character-compact__state character-compact__state--error" data-testid="character-compact-error">
          <strong>Characters could not load</strong>
          <p>{error}</p>
          <button type="button" className="character-compact__actions-button primary" data-testid="character-compact-retry" onClick={() => void refresh()}>
            Retry
          </button>
          <button type="button" className="character-compact__actions-button" data-testid="character-compact-open-standard" onClick={() => onOpenFull?.()}>
            Open Standard
          </button>
        </div>
      ) : (
        <>
          <div className="character-compact__selector">
            <div className="character-compact__selector-row">
              <label htmlFor="character-select">
                Saved Characters
                <select
                  id="character-select"
                  className="character-compact__select"
                  data-testid="character-compact-saved-select"
                  value={selectedId}
                  onChange={(e) => setSelectedId(e.target.value)}
                  aria-label="Select saved character"
                >
                  <option value="">— Select a saved character —</option>
                  {selectedId === DRAFT_CHARACTER_ID ? (
                    <option value={DRAFT_CHARACTER_ID}>Unsaved character</option>
                  ) : null}
                  {grouped.project.length ? (
                    <optgroup label="Project">
                      {grouped.project.map((c) => (
                        <option key={c.id} value={c.id}>
                          {scopeLabel(c.name, c, projectId)}
                        </option>
                      ))}
                    </optgroup>
                  ) : null}
                  {grouped.global.length ? (
                    <optgroup label="Global">
                      {grouped.global.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                        </option>
                      ))}
                    </optgroup>
                  ) : null}
                </select>
              </label>
              <button
                type="button"
                className="character-compact__actions-button primary"
                data-testid="character-compact-create"
                onClick={() => void handleCreate()}
              >
                Create Character
              </button>
              <button
                type="button"
                className="character-compact__actions-button danger"
                data-testid="character-compact-delete"
                disabled={!selectedId || selectedId === DRAFT_CHARACTER_ID || busy || deleting}
                onClick={() => void handleDeleteClick()}
              >
                Delete Character
              </button>
            </div>
            {actionNotice ? (
              <p className="character-compact__state--error" data-testid="character-compact-action-notice" role="status">
                {actionNotice}
              </p>
            ) : null}
          </div>
          {selectedId ? (
            <CharacterDetail
              projectId={projectId}
              characterId={selectedId}
              onGoTab={onGoTab}
              onCreated={setSelectedId}
              onOpenFull={(id) => {
                if (id === "__delete__") {
                  void refresh();
                  setSelectedId("");
                } else {
                  onOpenFull?.(id);
                }
              }}
            />
          ) : (
            <div className="character-compact__state" data-testid="character-compact-empty">
              <strong>No characters have been created in this project yet.</strong>
              <p>Create a character to write the Character Profile and make views. Global characters from other projects stay view-only here.</p>
            </div>
          )}
          <CreatorProfileDeleteModal
            open={deleteModalOpen}
            entityType="character"
            preview={deletePreview}
            deleting={deleting}
            onClose={() => {
              if (!deleting) {
                setDeleteModalOpen(false);
                setDeletePreview(null);
              }
            }}
            onConfirm={() => void handleConfirmDelete()}
          />
        </>
      )}
    </div>
  );
}
