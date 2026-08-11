/**
 * Character Creator compact embedded view — the Co-Director Character tab.
 *
 * Simplified creator-facing surface: character selector, bio, personality
 * keywords, approved casting image, and character assets. Shares the same
 * authoritative data as the standalone CharacterProfileWorkspace (no duplicate
 * store). "Open Full Character Creator" calls onOpenFull.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../../../api";
import "./characterCompact.css";

type CharacterProfile = {
  id: string;
  name: string;
  role?: string;
  description?: string;
  apparent_age?: string;
  species_or_type?: string;
  body_type?: string;
  height_description?: string;
  hair?: {
    primary_color?: string;
    canonical_style?: string;
    length?: string;
  };
  personality?: {
    core_personality?: string;
    temperament?: string;
    humor?: string;
    strengths?: string | string[];
    flaws?: string | string[];
  };
  continuity?: {
    notes?: string;
  };
  approval_status?: string;
  updated_at?: string;
};

type CharacterReference = {
  id: string;
  asset_id?: string | null;
  reference_role?: string;
  approval_status?: string;
  canonical?: boolean;
  source_type?: string;
};

type Props = {
  projectId: string;
  onOpenFull?: (characterId?: string) => void;
};

const PREDEFINED_TAGS = [
  "Brave",
  "Sarcastic",
  "Kind",
  "Cunning",
  "Stoic",
  "Cheerful",
  "Mysterious",
  "Loyal",
  "Ambitious",
  "Anxious",
  "Confident",
  "Gentle",
];

function toArray(value: string | string[] | undefined): string[] {
  if (!value) return [];
  if (Array.isArray(value)) return value.filter(Boolean);
  return String(value)
    .split(/[,;]|\band\b/i)
    .map((s) => s.trim())
    .filter(Boolean);
}

function getApprovedImage(refs: CharacterReference[]): CharacterReference | undefined {
  return (
    refs.find((r) => r.canonical && r.approval_status === "approved") ||
    refs.find((r) => r.canonical) ||
    refs.find((r) => r.approval_status === "approved") ||
    refs.find((r) => r.reference_role === "hero_portrait")
  );
}

function ReferenceAsset({ ref }: { ref: CharacterReference }) {
  const role = ref.reference_role || "Reference";
  if (!ref.asset_id) {
    return (
      <div className="character-compact__asset">
        <div className="character-compact__asset-icon">{role.slice(0, 4)}</div>
        <strong>{role}</strong>
        <span>No asset</span>
      </div>
    );
  }
  return (
    <div className="character-compact__asset">
      <img src={api.assetUrl(ref.asset_id)} alt={role} loading="lazy" />
      <strong>{role}</strong>
      <span>{ref.approval_status || "Draft"}</span>
    </div>
  );
}

function CharacterDetail({
  projectId,
  characterId,
  onOpenFull,
}: {
  projectId: string;
  characterId: string;
  onOpenFull?: (id?: string) => void;
}) {
  const [profile, setProfile] = useState<CharacterProfile | null>(null);
  const [refs, setRefs] = useState<CharacterReference[]>([]);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tagInput, setTagInput] = useState("");

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const [p, r] = await Promise.all([
        api.getCharacterProfile(projectId, characterId),
        api.listCharacterReferences(projectId, characterId),
      ]);
      setProfile(p as CharacterProfile);
      setRefs(Array.isArray((r as { items?: CharacterReference[] }).items) ? (r as { items: CharacterReference[] }).items : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [projectId, characterId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const personality = profile?.personality || {};
  const tags = useMemo(
    () => [
      ...(personality.core_personality ? [personality.core_personality] : []),
      ...(personality.temperament ? [personality.temperament] : []),
      ...(personality.humor ? [personality.humor] : []),
      ...toArray(personality.strengths),
      ...toArray(personality.flaws),
    ].filter((v, i, arr) => arr.indexOf(v) === i),
    [personality],
  );

  const approvedImage = getApprovedImage(refs);

  if (busy) {
    return (
      <div className="character-compact__state" aria-hidden="true">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="character-compact__skeleton-line" />
        ))}
      </div>
    );
  }
  if (error) {
    return (
      <div className="character-compact__state character-compact__state--error">
        <strong>Character could not load</strong>
        <p>{error}</p>
        <button type="button" className="character-compact__actions-button primary" onClick={() => void refresh()}>
          Retry
        </button>
      </div>
    );
  }
  if (!profile) return null;

  const hairSummary = [profile.hair?.primary_color, profile.hair?.canonical_style]
    .filter(Boolean)
    .join(" ");

  return (
    <>
      <div className="character-compact__body">
        <div className="character-compact__section">
          <h4>Bio</h4>
          <dl className="character-compact__bio-row">
            <dt>Name</dt>
            <dd>{profile.name}</dd>
            {profile.role ? (<><dt>Role</dt><dd>{profile.role}</dd></>) : null}
            {profile.apparent_age ? (<><dt>Age</dt><dd>{profile.apparent_age}</dd></>) : null}
            {profile.species_or_type ? (<><dt>Species</dt><dd>{profile.species_or_type}</dd></>) : null}
            {profile.body_type ? (<><dt>Build</dt><dd>{profile.body_type}</dd></>) : null}
            {hairSummary ? (<><dt>Hair</dt><dd>{hairSummary}</dd></>) : null}
          </dl>
          {profile.description ? (
            <p className="character-compact__bio-text">{profile.description}</p>
          ) : null}
          {profile.continuity?.notes ? (
            <p className="character-compact__bio-text">
              <strong>Notes:</strong> {profile.continuity.notes}
            </p>
          ) : null}
        </div>

        <div className="character-compact__section">
          <h4>Approved Casting Image</h4>
          {approvedImage?.asset_id ? (
            <div className="character-compact__hero">
              <img
                className="character-compact__hero-img"
                src={api.assetUrl(approvedImage.asset_id)}
                alt={`${profile.name} casting`}
              />
              <span className="character-compact__tag">
                {approvedImage.reference_role || "Hero"}
                {approvedImage.approval_status === "approved" ? " · Approved" : ""}
              </span>
            </div>
          ) : (
            <div className="character-compact__hero-placeholder">
              No approved casting image yet.
            </div>
          )}
        </div>

        <div className="character-compact__section">
          <h4>Personality</h4>
          <div className="character-compact__tags">
            {tags.map((tag) => (
              <span key={tag} className="character-compact__tag">{tag}</span>
            ))}
            {tags.length === 0 ? <span className="character-compact__bio-text">No personality keywords yet.</span> : null}
          </div>
          <div className="character-compact__tag-add">
            <input
              type="text"
              placeholder="Add a keyword…"
              value={tagInput}
              onChange={(e) => setTagInput(e.target.value)}
              list="character-predefined-tags"
              aria-label="Add personality keyword"
            />
            <datalist id="character-predefined-tags">
              {PREDEFINED_TAGS.map((t) => (
                <option key={t} value={t} />
              ))}
            </datalist>
            <button
              type="button"
              onClick={() => {
                const v = tagInput.trim();
                if (!v) return;
                setTagInput("");
                void api.patchCharacterProfile(projectId, characterId, {
                  personality: { ...personality, core_personality: [personality.core_personality, v].filter(Boolean).join(", ") },
                }).then(() => void refresh());
              }}
            >
              Add
            </button>
          </div>
        </div>

        <div className="character-compact__section">
          <h4>Character Assets</h4>
          {refs.length === 0 ? (
            <p className="character-compact__bio-text">No character assets yet.</p>
          ) : (
            <div className="character-compact__assets-grid">
              {refs.map((r) => (
                <ReferenceAsset key={r.id} ref={r} />
              ))}
            </div>
          )}
        </div>
      </div>
      <div className="character-compact__actions">
        <button
          type="button"
          className="character-compact__actions-button primary"
          data-testid="character-compact-open-full"
          onClick={() => onOpenFull?.(characterId)}
        >
          Open Full Character Creator
        </button>
      </div>
    </>
  );
}

export function CharacterCompactView({ projectId, onOpenFull }: Props) {
  const [characters, setCharacters] = useState<CharacterProfile[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const result = (await api.listCharacterProfiles(projectId)) as { items?: CharacterProfile[] };
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
    let cancelled = false;
    setBusy(true);
    setError(null);
    api
      .listCharacterProfiles(projectId)
      .then((result) => {
        if (cancelled) return;
        const list = Array.isArray((result as { items?: CharacterProfile[] }).items)
          ? (result as { items: CharacterProfile[] }).items
          : [];
        setCharacters(list);
        setSelectedId((prev) => prev || list[0]?.id || "");
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

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
          <button type="button" className="character-compact__actions-button primary" onClick={() => void refresh()}>
            Retry
          </button>
        </div>
      ) : characters.length === 0 ? (
        <div className="character-compact__state" data-testid="character-compact-empty">
          <strong>No characters have been created yet.</strong>
          <p>Define your cast and assign casting images, voice and references.</p>
          <button
            type="button"
            className="character-compact__actions-button primary"
            data-testid="character-compact-create"
            onClick={() =>
              void api
                .createCharacterProfile(projectId, { name: "New Character" })
                .then(() => void refresh())
            }
          >
            Create Character
          </button>
        </div>
      ) : (
        <>
          <div className="character-compact__selector">
            <label htmlFor="character-select">Character</label>
            <select
              id="character-select"
              value={selectedId}
              onChange={(e) => setSelectedId(e.target.value)}
              aria-label="Select character"
            >
              {characters.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
          {selectedId ? (
            <CharacterDetail projectId={projectId} characterId={selectedId} onOpenFull={onOpenFull} />
          ) : null}
        </>
      )}
    </div>
  );
}
