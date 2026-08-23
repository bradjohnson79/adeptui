/**
 * Character Creator embedded view — Co-Director Project Building pane.
 *
 * Phase 3: the inner CharacterDetail now renders the shared CharacterCore so
 * Express and the standalone Character Creator share one schema, hydration,
 * and behavior. The Co-Director mounting wrapper, the saved-character
 * selector, and the "Open Full Character Creator" deep-link are preserved.
 */
import { useCallback, useEffect, useState } from "react";
import { api } from "../../../api";
import { CharacterCore } from "../../character";
import "./characterCompact.css";

type CharacterProfile = {
  id: string;
  name: string;
  status?: string;
};

type Props = {
  projectId: string;
  onOpenFull?: (characterId?: string) => void;
};

type CharacterDetailProps = {
  projectId: string;
  characterId: string;
  onOpenFull?: (id?: string) => void;
};

function CharacterDetail({ projectId, characterId, onOpenFull }: CharacterDetailProps) {
  return (
    <div className="character-compact__detail">
      <CharacterCore
        key={characterId}
        projectId={projectId}
        characterId={characterId}
        onDeleted={() => onOpenFull?.("__delete__")}
        mode="express"
      />
      <div className="character-compact__actions">
        <div className="character-compact__actions-left">
          <button
            type="button"
            className="character-compact__actions-button"
            data-testid="character-compact-open-full"
            onClick={() => onOpenFull?.(characterId)}
          >
            Open Full Character Creator
          </button>
        </div>
      </div>
    </div>
  );
}

const LOAD_TIMEOUT_MS = 10_000;

export function CharacterCompactView({ projectId, onOpenFull }: Props) {
  const [characters, setCharacters] = useState<CharacterProfile[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
      setSelectedId((prev) => prev || list[0]?.id || "");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [projectId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleCreate = useCallback(async () => {
    try {
      const created = (await api.createCharacterProfile(projectId, { name: "New Character" })) as CharacterProfile;
      await refresh();
      setSelectedId(created.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [projectId, refresh]);

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
            <label htmlFor="character-select">Saved Characters</label>
            <select
              id="character-select"
              className="character-compact__select"
              data-testid="character-compact-saved-select"
              value={selectedId}
              onChange={(e) => setSelectedId(e.target.value)}
              aria-label="Select saved character"
            >
              <option value="">— Select a saved character —</option>
              {characters.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
          {selectedId ? (
            <CharacterDetail
              projectId={projectId}
              characterId={selectedId}
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
              <strong>No characters have been created yet.</strong>
              <p>Define your cast and assign casting images, voice and references.</p>
              <button
                type="button"
                className="character-compact__actions-button primary"
                data-testid="character-compact-create"
                onClick={() => void handleCreate()}
              >
                Create Character
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
